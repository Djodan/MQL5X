#!/usr/bin/env python3
"""
Shared utilities and state for the MQL5X Python server.
Keeps per-client (id) open positions and closed-online snapshots.
"""
from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime, UTC
from typing import Any, Dict, List, Tuple, Optional, Set
import uuid
import time as _time
import threading as _threading
import importlib

LOG_FILE = "received_log.jsonl"

# In-memory stores keyed by client id (string)
_LOCK = threading.Lock()
_CLIENT_OPEN: Dict[str, List[dict]] = {}
_CLIENT_CLOSED_ONLINE: Dict[str, List[dict]] = {}
_CLIENT_COMMANDS: Dict[str, List[dict]] = {}
_CLIENT_STATS: Dict[str, Dict[str, int]] = {}  # { id: { replies: int, last_action: int } }
_CLIENT_MODE: Dict[str, str] = {}  # { id: mode }
_CLIENT_LAST_SEEN: Dict[str, float] = {}  # { id: epoch_seconds }

# Discovered TopStepX accounts (from API) and cache of last fetch
_DISCOVERED_TOPSTEPX_ACCOUNTS: Set[str] = set()
_DISCOVERED_LAST_FETCHED: float = 0.0
_DISCOVERED_LAST_RESPONSE: Optional[dict] = None

# TopStepX per-account open/closed tracking
_TOPSTEPX_OPEN: Dict[str, List[dict]] = {}
_TOPSTEPX_CLOSED: Dict[str, List[dict]] = {}
_TOPSTEPX_LAST_POS_IDS: Dict[str, Set[str]] = {}
_TOPSTEPX_LAST_POLL_TIME: Dict[str, float] = {}

# TopStepX per-account background threads
_TOPSTEPX_THREADS: Dict[str, _threading.Thread] = {}
_TOPSTEPX_THREAD_STOPS: Dict[str, _threading.Event] = {}

# Throttle map for TSX actions: key=(accountId, contractId, side) -> last_epoch
_TSX_LAST_ACTION: Dict[Tuple[str, str, int], float] = {}

# Pending TopStepX adds to avoid exceeding cap while snapshots catch up
_TSX_PENDING_ADD: Dict[Tuple[str, str, int], int] = {}
# Last seen live sizes per (account, contract, side)
_TSX_LAST_SIZES: Dict[Tuple[str, str, int], int] = {}

# Copier background thread control
_COPIER_THREAD: Optional[_threading.Thread] = None
_COPIER_THREAD_STOP: Optional[_threading.Event] = None


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _type_name(v: Any) -> str:
    try:
        return {0: "BUY", 1: "SELL"}.get(int(v), str(v))
    except Exception:
        return str(v)


def _fmt(v: Any, digits: int | None = None) -> str:
    try:
        if isinstance(v, (int, float)) and digits is not None:
            return f"{v:.{digits}f}"
        return str(v)
    except Exception:
        return str(v)


def pretty_print_open_block(id_: Any, mode: Any, open_list: List[dict]) -> None:
    # Intentionally quiet to avoid noisy terminal output.
    # Keep function as stub in case of future debug toggles.
    return


def append_log(entry: dict) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[WARN {now_iso()}] Failed to write log: {exc}")


def record_client_snapshot(client_id: str, open_list: List[dict], closed_online: List[dict]) -> None:
    # Replace snapshot per incoming payload to reflect current EA state
    with _LOCK:
        _CLIENT_OPEN[client_id] = deepcopy(open_list) if open_list is not None else []
        _CLIENT_CLOSED_ONLINE[client_id] = deepcopy(closed_online) if closed_online is not None else []
    _CLIENT_LAST_SEEN[client_id] = _time.time()


def ingest_payload(data: dict) -> Tuple[dict, dict]:
    """
    Process an incoming EA payload: update per-client stores and build a small echo summary.
    Returns: (summary_dict, identity_dict)
    """
    client_id = str(data.get("id")) if data.get("id") is not None else "unknown"
    mode = data.get("mode")
    open_list = data.get("open", [])
    closed_offline = data.get("closed_offline", [])
    closed_online = data.get("closed_online", [])

    # Silence noisy dumps (printing disabled)

    # Persist full payload to JSONL with server timestamp
    append_log({"ts": now_iso(), **data})

    # Update in-memory per-client snapshots
    record_client_snapshot(client_id, open_list, closed_online)
    # Store/refresh client mode label for logging
    with _LOCK:
        _CLIENT_MODE[client_id] = str(mode) if mode is not None else ""

    summary = {
        "open": len(open_list),
        "closed_offline": len(closed_offline),
        "closed_online": len(closed_online),
    }
    identity = {"id": client_id, "mode": mode}
    return summary, identity


def get_client_open(client_id: str) -> List[dict]:
    with _LOCK:
        return deepcopy(_CLIENT_OPEN.get(str(client_id), []))


def get_client_closed_online(client_id: str) -> List[dict]:
    with _LOCK:
        return deepcopy(_CLIENT_CLOSED_ONLINE.get(str(client_id), []))


def list_clients() -> List[str]:
    with _LOCK:
        # Union keys across both maps in case one side hasn't reported yet
        base = set(_CLIENT_OPEN.keys()) | set(_CLIENT_CLOSED_ONLINE.keys())
        # Include discovered TopStepX account ids, but filtered by allowlist
        try:
            filtered_discovered = set(get_discovered_topstepx_accounts())
        except Exception:
            filtered_discovered = set()
        base |= filtered_discovered
        return sorted(base)


def get_client_mode(client_id: str) -> str:
    with _LOCK:
        return _CLIENT_MODE.get(str(client_id), "")


def _side_to_int(side: str | int) -> int:
    try:
        if isinstance(side, str):
            s = side.strip().upper()
            return 0 if s == "BUY" else 1 if s == "SELL" else int(side)
        return int(side)
    except Exception:
        return 0


def _mt5_open_signature(pos: dict) -> Tuple[str, int]:
    """Signature for matching: (symbol, type0/1). Volume differences will be reconciled by additional opens/closes.
    Returns tuple key; falls back to ('', 0) on missing fields.
    """
    try:
        sym = str(pos.get("symbol", ""))
        side = _side_to_int(pos.get("type", 0))
        return sym, side
    except Exception:
        return "", 0


def _positions_by_sig(open_list: List[dict]) -> Dict[Tuple[str, int], float]:
    """Map signature -> total volume for that signature."""
    out: Dict[Tuple[str, int], float] = {}
    for p in open_list or []:
        sig = _mt5_open_signature(p)
        try:
            vol = float(p.get("volume", 0.0))
        except Exception:
            vol = 0.0
        out[sig] = out.get(sig, 0.0) + vol
    return out


def _enqueue_open(client_id: str, side: int, symbol: str, volume: float, sl: float | None = None, tp: float | None = None) -> None:
    payload = {"symbol": symbol, "volume": float(volume)}
    if tp is not None:
        payload["tp"] = float(tp)
    if sl is not None:
        payload["sl"] = float(sl)
    enqueue_command(client_id, 1 if side == 0 else 2, payload)


def _enqueue_close_by_symbol(client_id: str, symbol: str, side: int, volume: float) -> None:
    # Close by symbol with optional side and volume; EA supports this path in Server.mqh
    payload = {"symbol": symbol, "type": int(side), "volume": float(volume)}
    enqueue_command(client_id, 3, payload)


def _pending_by_sig(client_id: str) -> Dict[Tuple[str, int], float]:
    """Pending (unacked) delta volume per (symbol, side) for an MT5 client. Opens add, closes subtract."""
    out: Dict[Tuple[str, int], float] = {}
    with _LOCK:
        queue = _CLIENT_COMMANDS.get(str(client_id), [])
        for cmd in queue:
            if cmd.get("status") == "ack":
                continue
            st = int(cmd.get("state", 0))
            payload = cmd.get("payload") or {}
            sym = str(payload.get("symbol", ""))
            if not sym:
                continue
            if st in (1, 2):
                side = 0 if st == 1 else 1
                vol = float(payload.get("volume", 0.0))
                out[(sym, side)] = out.get((sym, side), 0.0) + vol
            elif st == 3:
                try:
                    side = int(payload.get("type", -1))
                except Exception:
                    side = -1
                if side in (0, 1):
                    vol = float(payload.get("volume", 0.0))
                    out[(sym, side)] = out.get((sym, side), 0.0) - vol
    return out


# ---------------------- TopStepX helpers for copier ----------------------

def _symbol_to_contract(symbol: str) -> Optional[str]:
    try:
        import Globals
        mapping = getattr(Globals, "TOPSTEPX_SYMBOL_CONTRACT_MAP", None)
        if isinstance(mapping, dict):
            v = mapping.get(symbol)
            if v:
                return str(v)
    except Exception:
        pass
    # Fallback defaults
    if str(symbol).upper() == "XAUUSD":
        return _DEFAULT_TSX_CONTRACT_ID
    return None


def _tsx_positions_by_sig(account_id: str) -> Dict[Tuple[str, int], int]:
    """Build a map (contractId, side) -> size for TopStepX account."""
    raw = get_topstepx_open(account_id)
    out: Dict[Tuple[str, int], int] = {}
    for p in raw:
        try:
            cid = str(p.get("contractId") or p.get("contract") or "")
            side = int(p.get("type", 0))
            size = int(round(float(p.get("size", 0))))
            if cid:
                out[(cid, side)] = out.get((cid, side), 0) + size
        except Exception:
            continue
    return out


def _tsx_live_size(account_id: str, contract_id: str, side: int) -> int:
    """Return current live size on TSX for a given (account, contract, side) from cached snapshot."""
    try:
        raw = get_topstepx_open(account_id)
        total = 0
        for p in raw:
            try:
                if str(p.get("contractId") or p.get("contract")) != str(contract_id):
                    continue
                if int(p.get("type", 0)) != int(side):
                    continue
                total += int(round(float(p.get("size", 0))))
            except Exception:
                continue
        return int(total)
    except Exception:
        return 0


def topstepx_partial_close_contract(account_id: str, contract_id: str, size: int, timeout: int = 10) -> dict:
    try:
        import requests, Globals
    except Exception:
        return {"success": False, "error": "deps"}
    headers = {
        "Authorization": f"Bearer {getattr(Globals, 'KEY_ACCESS_TOKEN', '')}",
        "Content-Type": "application/json",
    }
    payload = {"accountId": int(account_id) if str(account_id).isdigit() else account_id, "contractId": contract_id, "size": int(size)}
    url = "https://api.topstepx.com/api/Position/partialCloseContract"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        try:
            return resp.json()
        except Exception:
            return {"success": False, "status": resp.status_code}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _tsx_find_orders(account_id: str, contract_id: str, timeout: int = 10) -> List[dict]:
    try:
        import requests, Globals
    except Exception:
        return []
    # Enforce allowlist
    try:
        allowed = getattr(Globals, "TOPSTEPX_ALLOWED_ACCOUNTS", []) or getattr(Globals, "TOPSTEP_ALLOWED_ACCOUNTS", [])
        if allowed and str(account_id) not in set(str(a) for a in allowed):
            return []
    except Exception:
        return []
    headers = {
        "Authorization": f"Bearer {getattr(Globals, 'KEY_ACCESS_TOKEN', '')}",
        "Content-Type": "application/json",
    }
    payload = {"accountId": int(account_id) if str(account_id).isdigit() else account_id}
    try:
        resp = requests.post("https://api.topstepx.com/api/Order/searchOpen", json=payload, headers=headers, timeout=timeout)
        data = resp.json()
    except Exception:
        data = {"orders": []}
    return [o for o in (data.get("orders") or []) if str(o.get("contractId") or o.get("contract")) == str(contract_id)]


def _tsx_modify_order(order_id: str, account_id: str, contract_id: str, otype: int, side: int, size: int, price: Optional[float], timeout: int = 10) -> dict:
    try:
        import requests, Globals
    except Exception:
        return {"success": False}
    # Enforce allowlist
    try:
        allowed = getattr(Globals, "TOPSTEPX_ALLOWED_ACCOUNTS", []) or getattr(Globals, "TOPSTEP_ALLOWED_ACCOUNTS", [])
        if allowed and str(account_id) not in set(str(a) for a in allowed):
            return {"success": False, "error": "account_not_allowed"}
    except Exception:
        return {"success": False, "error": "account_not_allowed"}
    headers = {
        "Authorization": f"Bearer {getattr(Globals, 'KEY_ACCESS_TOKEN', '')}",
        "Content-Type": "application/json",
    }
    payload = {"orderId": order_id, "accountId": int(account_id) if str(account_id).isdigit() else account_id, "contractId": contract_id, "type": int(otype), "side": int(side), "size": int(size)}
    if otype == 1 and price is not None:
        payload["limitPrice"] = float(price)
    if otype == 4 and price is not None:
        payload["stopPrice"] = float(price)
    try:
        resp = requests.post("https://api.topstepx.com/api/Order/modify", json=payload, headers=headers, timeout=timeout)
        return resp.json()
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _tsx_place_tp_sl(account_id: str, contract_id: str, side: int, size: int, tp: Optional[float], sl: Optional[float], timeout: int = 10) -> None:
    # Upsert TP (type=1) and SL (type=4) orders; both should be opposite side to position
    try:
        # Enforce allowlist
        try:
            import Globals as _G
            allowed = getattr(_G, "TOPSTEPX_ALLOWED_ACCOUNTS", []) or getattr(_G, "TOPSTEP_ALLOWED_ACCOUNTS", [])
            if allowed and str(account_id) not in set(str(a) for a in allowed):
                return
        except Exception:
            return
        if tp is None and sl is None:
            return
        opp = 1 if int(side) == 0 else 0
        orders = _tsx_find_orders(account_id, contract_id, timeout=timeout)
        # TP
        if tp is not None:
            existing = next((o for o in orders if o.get("type") == 1), None)
            if existing and existing.get("id") is not None:
                _tsx_modify_order(str(existing.get("id")), account_id, contract_id, 1, opp, size, tp, timeout=timeout)
            else:
                topstepx_place_order(account_id, contract_id, side=opp, size=size, order_type=1, limit_price=tp, timeout=timeout)
        # SL
        if sl is not None:
            existing = next((o for o in orders if o.get("type") == 4), None)
            if existing and existing.get("id") is not None:
                _tsx_modify_order(str(existing.get("id")), account_id, contract_id, 4, opp, size, sl, timeout=timeout)
            else:
                topstepx_place_order(account_id, contract_id, side=opp, size=size, order_type=4, stop_price=sl, timeout=timeout)
    except Exception:
        pass


def _copy_mt5_mode_one_cycle() -> None:
    """One reconciliation pass for Mode 1: mirror MAIN_MT5_ACCOUNT to other MT5 clients."""
    try:
        import Globals
    except Exception:
        return

    main_id = str(getattr(Globals, "MAIN_MT5_ACCOUNT", ""))
    if not main_id:
        return

    # Snapshot open lists
    with _LOCK:
        main_open = deepcopy(_CLIENT_OPEN.get(main_id, []))
        targets = [cid for cid, mode in _CLIENT_MODE.items() if str(cid) != main_id and str(mode).lower() == "sender"]
        target_open = {cid: deepcopy(_CLIENT_OPEN.get(cid, [])) for cid in targets}

    main_map = _positions_by_sig(main_open)
    # Representative TP/SL per signature from main
    rep_tpsl: Dict[Tuple[str, int], Tuple[Optional[float], Optional[float]]] = {}
    for p in main_open:
        sig = _mt5_open_signature(p)
        if sig not in rep_tpsl:
            rep_tpsl[sig] = (p.get("tp"), p.get("sl"))
    for tid, t_open in target_open.items():
        t_map = _positions_by_sig(t_open)
        # Include pending commands to avoid duplicate rapid opens/closes
        pend = _pending_by_sig(tid)
        for k, dv in pend.items():
            t_map[k] = t_map.get(k, 0.0) + dv
        # Reconcile per signature
        all_sigs = set(main_map.keys()) | set(t_map.keys())
        for sig in all_sigs:
            sym, side = sig
            m_vol = main_map.get(sig, 0.0)
            t_vol = t_map.get(sig, 0.0)
            delta = round(m_vol - t_vol, 2)
            if abs(delta) < 1e-6:
                continue
            if delta > 0:
                # Need to open additional volume on target to match main
                tp, sl = rep_tpsl.get((sym, side), (None, None))
                _enqueue_open(tid, side, sym, delta, sl=sl, tp=tp)
            else:
                # Need to reduce volume on target; close delta (positive amount)
                _enqueue_close_by_symbol(tid, sym, side, abs(delta))

    # Also reconcile TopStepX targets using market orders; entry can differ; TP/SL and size should match (rounded to int)
    # rep_tpsl already built above
    # Determine TSX targets
    try:
        tsx_targets = get_discovered_topstepx_accounts()
        if not tsx_targets:
            import Globals
            _allowed = getattr(Globals, "TOPSTEPX_ALLOWED_ACCOUNTS", []) or getattr(Globals, "TOPSTEP_ALLOWED_ACCOUNTS", [])
            tsx_targets = [str(x) for x in _allowed]
    except Exception:
        tsx_targets = []
    # For each TSX target, compute deltas by mapped contract
    # Simple throttle to avoid rapid duplicate placements while positions cache lags
    global _TSX_LAST_ACTION, _TSX_PENDING_ADD
    now_ts = _time.time()
    for aid in tsx_targets:
        tmap = _tsx_positions_by_sig(aid)
        # For each main signature, map to contract
        for (sym, side), m_vol in main_map.items():
            cid = _symbol_to_contract(sym)
            if not cid:
                continue
            # Cap TSX total size to floor(master volume). No rounding up.
            try:
                size_cap = int(float(m_vol)) if float(m_vol) > 0 else 0
            except Exception:
                size_cap = 0
            # Cached size snapshot
            t_size = int(tmap.get((cid, side), 0))
            # Live size from current cache (potentially fresher than aggregated map)
            live_size = _tsx_live_size(aid, cid, side)
            # If we need to add contracts, ensure we never exceed size_cap; include pending
            pending = int(_TSX_PENDING_ADD.get((aid, cid, side), 0))
            if size_cap > (live_size + pending):
                missing_from_live = size_cap - (live_size + pending)
                # Also compute missing from cached map to avoid overshoot
                missing_from_cached = max(0, size_cap - (t_size + pending))
                to_add = min(missing_from_live, missing_from_cached)
                if to_add > 0:
                    k = (aid, cid, side)
                    last = _TSX_LAST_ACTION.get(k, 0.0)
                    if now_ts - last >= 5.0:
                        topstepx_place_order(aid, cid, side=side, size=to_add, order_type=2)
                        _TSX_LAST_ACTION[k] = now_ts
                        _TSX_PENDING_ADD[k] = _TSX_PENDING_ADD.get(k, 0) + int(to_add)
                        # Upsert TP/SL if available (use target size_cap for order sizing)
                        tp, sl = rep_tpsl.get((sym, side), (None, None))
                        _tsx_place_tp_sl(aid, cid, side, size_cap, tp, sl)
            # If we have more than cap, reduce using live size to compute excess
            elif size_cap < live_size:
                extra_live = live_size - size_cap
                if extra_live > 0:
                    # If extra equals or exceeds entire position, close; else partial close the extra
                    if extra_live >= live_size:
                        topstepx_close_contract(aid, cid)
                    else:
                        topstepx_partial_close_contract(aid, cid, extra_live)
            # Ensure TP/SL are set/updated for any existing exposure
            try:
                if live_size > 0:
                    tp, sl = rep_tpsl.get((sym, side), (None, None))
                    _tsx_place_tp_sl(aid, cid, side, live_size, tp, sl)
            except Exception:
                pass


def start_mode_one_copier(interval_seconds: int = 2) -> None:
    """Start a background thread that keeps other MT5 accounts in sync with MAIN_MT5_ACCOUNT when COPIER_MODE==1."""
    global _COPIER_THREAD, _COPIER_THREAD_STOP
    try:
        import Globals
    except Exception:
        return
    if getattr(Globals, "COPIER_MODE", 0) != 1:
        return
    if _COPIER_THREAD and _COPIER_THREAD.is_alive():
        return
    stop = _threading.Event()
    _COPIER_THREAD_STOP = stop

    def _loop():
        while not stop.is_set():
            try:
                _copy_mt5_mode_one_cycle()
            except Exception:
                pass
            # Sleep in small chunks for responsive stop
            slept = 0.0
            while slept < max(1.0, float(interval_seconds)):
                if stop.is_set():
                    break
                _time.sleep(0.5)
                slept += 0.5

    t = _threading.Thread(target=_loop, name="Mode1Copier", daemon=True)
    _COPIER_THREAD = t
    t.start()


def stop_mode_one_copier() -> None:
    global _COPIER_THREAD, _COPIER_THREAD_STOP
    if _COPIER_THREAD_STOP:
        _COPIER_THREAD_STOP.set()
    if _COPIER_THREAD and _COPIER_THREAD.is_alive():
        try:
            _COPIER_THREAD.join(timeout=2.0)
        except Exception:
            pass
    _COPIER_THREAD = None
    _COPIER_THREAD_STOP = None


# ---------------------- Command queue (server -> EA) ----------------------

def enqueue_command(client_id: str, state: int, payload: Optional[dict] = None) -> dict:
    """Add a command for a specific client id. Returns the stored command."""
    cmd = {
        "cmdId": str(uuid.uuid4()),
        "id": str(client_id),
        "state": int(state),  # 0..3 per contract
        "payload": payload or {},
        "status": "queued",  # queued|sent|ack
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    with _LOCK:
        _CLIENT_COMMANDS.setdefault(str(client_id), []).append(cmd)
    return cmd


def get_next_command(client_id: str) -> dict:
    """Return the next pending command for the client without losing it until acked.
    If none pending, return a no-op state=0.
    """
    with _LOCK:
        queue = _CLIENT_COMMANDS.get(str(client_id), [])
        for cmd in queue:
            if cmd.get("status") != "ack":
                # mark as sent (first delivery)
                if cmd.get("status") == "queued":
                    cmd["status"] = "sent"
                    cmd["updatedAt"] = now_iso()
                # Build the precise message for EA
                state = int(cmd.get("state", 0))
                msg = {"id": str(client_id), "state": state, "cmdId": cmd["cmdId"]}
                payload = cmd.get("payload") or {}
                # shape by state
                if state == 1:  # Open BUY
                    # expected: symbol, volume, optional comment and SL/TP (absolute or pip distances)
                    msg.update({
                        "symbol": payload.get("symbol"),
                        "volume": payload.get("volume"),
                        "comment": payload.get("comment", ""),
                    })
                    # propagate optional SL/TP fields
                    if "sl" in payload: msg["sl"] = payload.get("sl")
                    if "tp" in payload: msg["tp"] = payload.get("tp")
                    if "slPips" in payload: msg["slPips"] = payload.get("slPips")
                    if "tpPips" in payload: msg["tpPips"] = payload.get("tpPips")
                elif state == 2:  # Open SELL
                    msg.update({
                        "symbol": payload.get("symbol"),
                        "volume": payload.get("volume"),
                        "comment": payload.get("comment", ""),
                    })
                    # propagate optional SL/TP fields
                    if "sl" in payload: msg["sl"] = payload.get("sl")
                    if "tp" in payload: msg["tp"] = payload.get("tp")
                    if "slPips" in payload: msg["slPips"] = payload.get("slPips")
                    if "tpPips" in payload: msg["tpPips"] = payload.get("tpPips")
                elif state == 3:  # Close trade
                    # expected: ticket or symbol/volume
                    msg.update({
                        "ticket": payload.get("ticket"),
                        "symbol": payload.get("symbol"),
                        "volume": payload.get("volume"),
                        "type": payload.get("type"),  # optional: 0 buy, 1 sell
                    })
                # state 0: do nothing
                return msg
    # No pending command
    return {"id": str(client_id), "state": 0}


def ack_command(client_id: str, cmd_id: str, success: bool, details: Optional[dict] = None) -> dict:
    """Mark a command as acknowledged and store result details."""
    with _LOCK:
        queue = _CLIENT_COMMANDS.get(str(client_id), [])
        for cmd in queue:
            if cmd.get("cmdId") == cmd_id:
                cmd["status"] = "ack"
                cmd["updatedAt"] = now_iso()
                cmd["result"] = {"success": bool(success), **(details or {})}
                return {"ok": True, "cmdId": cmd_id}
    return {"ok": False, "error": "cmd_not_found", "cmdId": cmd_id}


def get_command_queue(client_id: str) -> List[dict]:
    with _LOCK:
        return deepcopy(_CLIENT_COMMANDS.get(str(client_id), []))


def record_command_delivery(client_id: str, state: int) -> Dict[str, int]:
    with _LOCK:
        stats = _CLIENT_STATS.setdefault(str(client_id), {"replies": 0, "last_action": 0})
        stats["replies"] += 1
        stats["last_action"] = int(state)
        return deepcopy(stats)


def get_client_stats(client_id: str) -> Dict[str, int]:
    with _LOCK:
        return deepcopy(_CLIENT_STATS.get(str(client_id), {"replies": 0, "last_action": 0}))


def get_client_last_seen(client_id: str) -> float:
    with _LOCK:
        return float(_CLIENT_LAST_SEEN.get(str(client_id), 0.0))


def is_client_online(client_id: str, timeout_seconds: int = 10) -> bool:
    try:
        last = get_client_last_seen(client_id)
        if last <= 0:
            return False
        return (_time.time() - last) <= timeout_seconds
    except Exception:
        return False


# ---------------------- TopStepX account discovery ----------------------

def find_all_topstepx_accounts(only_active_accounts: bool = False, refresh_seconds: int = 60) -> dict:
    """
    Call TopStepX Account/search API (like TopStepX_Files/Find_All_Accounts.py) and cache results.
    Extract account ids and add them to the global client list so they print in status output.
    Returns the parsed JSON response (or {} on error).
    """
    global _DISCOVERED_LAST_FETCHED, _DISCOVERED_LAST_RESPONSE
    try:
        now = _time.time()
        if (now - _DISCOVERED_LAST_FETCHED) < max(1, int(refresh_seconds)) and _DISCOVERED_LAST_RESPONSE is not None:
            return _DISCOVERED_LAST_RESPONSE
    except Exception:
        pass

    # Perform network call
    try:
        import requests  # rely on same dependency used in TopStepX_Files
        import Globals

        API_URL = "https://api.topstepx.com/api/Account/search"
        headers = {
            "Authorization": f"Bearer {getattr(Globals, 'KEY_ACCESS_TOKEN', '')}",
            "Content-Type": "application/json",
        }
        payload = {"onlyActiveAccounts": bool(only_active_accounts)}

        resp = requests.post(API_URL, json=payload, headers=headers, timeout=10)
        data: dict
        try:
            data = resp.json()
        except Exception:
            data = {"success": False, "status": resp.status_code, "raw": resp.text}

        # Update cache timestamps regardless
        _DISCOVERED_LAST_FETCHED = _time.time()
        _DISCOVERED_LAST_RESPONSE = data

        # Extract accounts -> ids
        accounts = []
        try:
            if isinstance(data, dict):
                accounts = data.get("accounts") or []
        except Exception:
            accounts = []

        ids: List[str] = []
        for acc in accounts:
            try:
                aid = str(acc.get("id"))
                if aid and aid != "None":
                    ids.append(aid)
            except Exception:
                continue

        if ids:
            # Apply allowlist filter: only manage accounts explicitly listed
            try:
                import Globals as _G
                allowed = getattr(_G, "TOPSTEPX_ALLOWED_ACCOUNTS", []) or getattr(_G, "TOPSTEP_ALLOWED_ACCOUNTS", [])
                allowed_set = set(str(a) for a in allowed)
            except Exception:
                allowed_set = set()
            filtered_ids = [i for i in ids if (str(i) in allowed_set)] if allowed_set else []
            with _LOCK:
                for aid in filtered_ids:
                    _DISCOVERED_TOPSTEPX_ACCOUNTS.add(aid)
                    # Mark mode to help status prefix classify as TopStepX
                    _CLIENT_MODE.setdefault(aid, "TopStepX")
                    # Ensure thread structures exist
                    _TOPSTEPX_THREAD_STOPS.setdefault(aid, _threading.Event())

        return data
    except Exception:
        # On any failure, do not crash server; return last or empty
        return _DISCOVERED_LAST_RESPONSE or {}


def get_discovered_topstepx_accounts() -> List[str]:
    """Return discovered TopStepX accounts filtered to TOPSTEPX_ALLOWED_ACCOUNTS.
    If the allowlist is empty/missing, return the raw discovered set.
    """
    with _LOCK:
        raw = set(_DISCOVERED_TOPSTEPX_ACCOUNTS)
    # Apply allowlist filter
    try:
        import Globals
        allowed = getattr(Globals, "TOPSTEPX_ALLOWED_ACCOUNTS", []) or getattr(Globals, "TOPSTEP_ALLOWED_ACCOUNTS", [])
        allowed_set = set(str(a) for a in allowed)
        if allowed_set:
            raw &= allowed_set
    except Exception:
        pass
    return sorted(raw)


def refresh_topstepx_open_positions(account_ids: Optional[List[str]] = None, refresh_seconds: int = 10, timeout: int = 10) -> None:
    """
    For each TopStepX account id, call Position/searchOpen and update per-account open list.
    Also detect closures by diffing with previous snapshot and append to closed list.
    """
    try:
        import requests
        import Globals
    except Exception:
        return

    ids = account_ids or get_discovered_topstepx_accounts()
    # Enforce allowlist on provided ids as well
    try:
        import Globals as _G
        allowed = getattr(_G, "TOPSTEPX_ALLOWED_ACCOUNTS", []) or getattr(_G, "TOPSTEP_ALLOWED_ACCOUNTS", [])
        allowed_set = set(str(a) for a in allowed)
        if allowed_set:
            ids = [str(i) for i in ids if str(i) in allowed_set]
    except Exception:
        pass
    if not ids:
        return

    for aid in ids:
        try:
            now = _time.time()
            last_poll = _TOPSTEPX_LAST_POLL_TIME.get(aid, 0.0)
            if (now - last_poll) < max(1, int(refresh_seconds)):
                continue

            headers = {
                "Authorization": f"Bearer {getattr(Globals, 'KEY_ACCESS_TOKEN', '')}",
                "Content-Type": "application/json",
            }
            payload = {"accountId": int(aid) if aid.isdigit() else aid}
            url = "https://api.topstepx.com/api/Position/searchOpen"

            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            try:
                data = resp.json()
            except Exception:
                data = {"success": False, "status": resp.status_code}

            positions = []
            if isinstance(data, dict):
                positions = data.get("positions") or []

            # Normalize to string ids
            cur_ids: Set[str] = set()
            for p in positions:
                try:
                    cur_ids.add(str(p.get("id")))
                except Exception:
                    continue

            with _LOCK:
                prev_ids = _TOPSTEPX_LAST_POS_IDS.get(aid, set())
                # Detect closed: in prev but not in current
                closed_ids = prev_ids - cur_ids
                if closed_ids:
                    # Append minimal records to closed list
                    lst = _TOPSTEPX_CLOSED.setdefault(aid, [])
                    ts = now_iso()
                    for cid in closed_ids:
                        lst.append({"id": cid, "closedAt": ts, "accountId": aid})
                # Store current snapshot
                _TOPSTEPX_OPEN[aid] = deepcopy(positions)
                _TOPSTEPX_LAST_POS_IDS[aid] = set(cur_ids)
                _TOPSTEPX_LAST_POLL_TIME[aid] = now
                # Ensure mode classification
                _CLIENT_MODE.setdefault(aid, "TopStepX")
        except Exception:
            # Skip errors per account; keep last snapshot
            continue


def get_topstepx_open(account_id: str) -> List[dict]:
    with _LOCK:
        return deepcopy(_TOPSTEPX_OPEN.get(str(account_id), []))


def has_topstepx_snapshot(account_id: str) -> bool:
    """Return True if we've polled TopStepX for this account at least once."""
    try:
        return float(_TOPSTEPX_LAST_POLL_TIME.get(str(account_id), 0.0)) > 0.0
    except Exception:
        return False


# ---------------------- TopStepX standalone fetch (no cache) ----------------------

def topstepx_fetch_open_positions(account_id: str, timeout: int = 10) -> List[dict]:
    """Directly call Position/searchOpen for the given TopStepX account and return raw positions."""
    try:
        import requests, Globals
    except Exception:
        return []
    # Enforce allowlist
    try:
        allowed = getattr(Globals, "TOPSTEPX_ALLOWED_ACCOUNTS", []) or getattr(Globals, "TOPSTEP_ALLOWED_ACCOUNTS", [])
        if allowed and str(account_id) not in set(str(a) for a in allowed):
            return []
    except Exception:
        return []
    headers = {
        "Authorization": f"Bearer {getattr(Globals, 'KEY_ACCESS_TOKEN', '')}",
        "Content-Type": "application/json",
    }
    payload = {"accountId": int(account_id) if str(account_id).isdigit() else account_id}
    try:
        resp = requests.post("https://api.topstepx.com/api/Position/searchOpen", json=payload, headers=headers, timeout=timeout)
        data = resp.json()
        return data.get("positions") or []
    except Exception:
        return []


def topstepx_enrich_tp_sl_simple(account_id: str, positions: List[dict], timeout: int = 10) -> List[dict]:
    """Fetch open orders once and merge TP/SL (limitPrice/stopPrice) into the given positions list."""
    try:
        import requests, Globals
    except Exception:
        return positions or []
    # Enforce allowlist
    try:
        allowed = getattr(Globals, "TOPSTEPX_ALLOWED_ACCOUNTS", []) or getattr(Globals, "TOPSTEP_ALLOWED_ACCOUNTS", [])
        if allowed and str(account_id) not in set(str(a) for a in allowed):
            return positions or []
    except Exception:
        return positions or []
    headers = {
        "Authorization": f"Bearer {getattr(Globals, 'KEY_ACCESS_TOKEN', '')}",
        "Content-Type": "application/json",
    }
    payload = {"accountId": int(account_id) if str(account_id).isdigit() else account_id}
    try:
        resp = requests.post("https://api.topstepx.com/api/Order/searchOpen", json=payload, headers=headers, timeout=timeout)
        data = resp.json()
        orders = data.get("orders") or data.get("openOrders") or []
    except Exception:
        orders = []
    by_contract: Dict[str, Dict[str, Any]] = {}
    for o in orders:
        try:
            c = o.get("contractId") or o.get("contract") or ""
            if not c:
                continue
            m = by_contract.setdefault(str(c), {})
            if o.get("type") == 1 and o.get("limitPrice") is not None:
                m["tp"] = o.get("limitPrice")
            if o.get("type") == 4 and o.get("stopPrice") is not None:
                m["sl"] = o.get("stopPrice")
        except Exception:
            continue
    out: List[dict] = []
    for p in positions or []:
        try:
            c = p.get("contractId") or p.get("contract")
            merge = by_contract.get(str(c), {})
            e = dict(p)
            if "tp" not in e and "tp" in merge:
                e["tp"] = merge.get("tp")
            if "sl" not in e and "sl" in merge:
                e["sl"] = merge.get("sl")
            out.append(e)
        except Exception:
            out.append(p)
    return out


def topstepx_get_open_normalized_simple(account_id: str, timeout: int = 10) -> List[dict]:
    """Standalone: fetch positions and orders, merge TP/SL, and normalize for printing."""
    raw = topstepx_fetch_open_positions(account_id, timeout=timeout)
    enriched = topstepx_enrich_tp_sl_simple(account_id, raw, timeout=timeout)
    out: List[dict] = []
    for p in enriched:
        try:
            out.append({
                "id": p.get("id"),
                "symbol": p.get("contractId") or p.get("contract"),
                "type": p.get("type"),
                "volume": p.get("size"),
                "entryPrice": p.get("averagePrice"),
                "tp": p.get("tp"),
                "sl": p.get("sl"),
            })
        except Exception:
            continue
    return out


def topstepx_get_open_count_simple(account_id: str, timeout: int = 10) -> int:
    """Standalone: return the count of open positions by calling the API directly."""
    try:
        return len(topstepx_fetch_open_positions(account_id, timeout=timeout))
    except Exception:
        return 0


def get_topstepx_closed(account_id: str) -> List[dict]:
    with _LOCK:
        return deepcopy(_TOPSTEPX_CLOSED.get(str(account_id), []))


def refresh_topstepx_open_details(account_ids: Optional[List[str]] = None, refresh_seconds: int = 10, timeout: int = 10) -> None:
    """
    Fetch open positions and open orders for each account, and merge TP/SL into positions.
    """
    try:
        import requests
        import Globals
    except Exception:
        return

    ids = account_ids or get_discovered_topstepx_accounts()
    # Enforce allowlist on provided ids as well
    try:
        import Globals as _G
        allowed = getattr(_G, "TOPSTEPX_ALLOWED_ACCOUNTS", []) or getattr(_G, "TOPSTEP_ALLOWED_ACCOUNTS", [])
        allowed_set = set(str(a) for a in allowed)
        if allowed_set:
            ids = [str(i) for i in ids if str(i) in allowed_set]
    except Exception:
        pass
    if not ids:
        return

    for aid in ids:
        try:
            now = _time.time()
            last_poll = _TOPSTEPX_LAST_POLL_TIME.get(aid, 0.0)
            if (now - last_poll) < max(1, int(refresh_seconds)):
                continue

            headers = {
                "Authorization": f"Bearer {getattr(Globals, 'KEY_ACCESS_TOKEN', '')}",
                "Content-Type": "application/json",
            }
            payload = {"accountId": int(aid) if str(aid).isdigit() else aid}
            pos_url = "https://api.topstepx.com/api/Position/searchOpen"
            ord_url = "https://api.topstepx.com/api/Order/searchOpen"

            pos_resp = requests.post(pos_url, json=payload, headers=headers, timeout=timeout)
            try:
                pos_data = pos_resp.json()
            except Exception:
                pos_data = {"positions": []}
            positions = pos_data.get("positions") or []

            ord_resp = requests.post(ord_url, json=payload, headers=headers, timeout=timeout)
            try:
                ord_data = ord_resp.json()
            except Exception:
                ord_data = {"orders": []}
            orders = ord_data.get("orders") or ord_data.get("openOrders") or []

            # Index orders by contract and classify TP/SL using TopStepX fields
            # type: 1=Limit (TP), 4=Stop (SL)
            by_contract: Dict[str, Dict[str, Any]] = {}
            for o in orders:
                try:
                    c = o.get("contractId") or o.get("contract") or ""
                    otype = o.get("type")
                    limit_price = o.get("limitPrice")
                    stop_price = o.get("stopPrice")
                    m = by_contract.setdefault(str(c), {})
                    if otype == 1 and limit_price is not None:
                        m["tp"] = limit_price
                    elif otype == 4 and stop_price is not None:
                        m["sl"] = stop_price
                except Exception:
                    continue

            # Normalize and merge into positions
            enriched: List[dict] = []
            cur_ids: Set[str] = set()
            for p in positions:
                try:
                    pid = str(p.get("id"))
                    cur_ids.add(pid)
                    contract = p.get("contractId") or p.get("contract")
                    avg = p.get("averagePrice")
                    side = p.get("type")  # assuming 0 buy, 1 sell
                    size = p.get("size")
                    m = by_contract.get(str(contract), {})
                    enr = dict(p)
                    if "tp" not in enr and "tp" in m:
                        enr["tp"] = m.get("tp")
                    if "sl" not in enr and "sl" in m:
                        enr["sl"] = m.get("sl")
                    enriched.append(enr)
                except Exception:
                    continue

            with _LOCK:
                prev_ids = _TOPSTEPX_LAST_POS_IDS.get(aid, set())
                closed_ids = prev_ids - cur_ids
                if closed_ids:
                    lst = _TOPSTEPX_CLOSED.setdefault(aid, [])
                    ts = now_iso()
                    for cid in closed_ids:
                        lst.append({"id": cid, "closedAt": ts, "accountId": aid})
                _TOPSTEPX_OPEN[aid] = deepcopy(enriched)
                _TOPSTEPX_LAST_POS_IDS[aid] = set(cur_ids)
                _TOPSTEPX_LAST_POLL_TIME[aid] = _time.time()
                _CLIENT_MODE.setdefault(aid, "TopStepX")
                # Reconcile TSX pending adds against live sizes for this account
                try:
                    cur_map: Dict[Tuple[str, str, int], int] = {}
                    for p in enriched:
                        try:
                            c = str(p.get("contractId") or p.get("contract") or "")
                            s = int(p.get("type", 0))
                            z = int(round(float(p.get("size", 0))))
                            if c:
                                cur_map[(aid, c, s)] = cur_map.get((aid, c, s), 0) + z
                        except Exception:
                            continue
                    # Update last sizes and adjust pending based on observed increases
                    for key, cur_val in list(cur_map.items()):
                        if key[0] != aid:
                            continue
                        prev_val = _TSX_LAST_SIZES.get(key, 0)
                        delta = cur_val - prev_val
                        if delta > 0:
                            pend = _TSX_PENDING_ADD.get(key, 0)
                            if pend > 0:
                                _TSX_PENDING_ADD[key] = max(0, pend - delta)
                        _TSX_LAST_SIZES[key] = cur_val
                    # Clear sizes/pending for keys not present anymore
                    for key in list(_TSX_LAST_SIZES.keys()):
                        if key[0] != aid:
                            continue
                        if key not in cur_map:
                            _TSX_LAST_SIZES[key] = 0
                            _TSX_PENDING_ADD[key] = 0
                except Exception:
                    pass
        except Exception:
            continue


def get_topstepx_open_normalized(account_id: str) -> List[dict]:
    """
    Return open positions normalized for side-by-side with MT5: id, symbol, type, volume, entryPrice, tp, sl.
    """
    raw = get_topstepx_open(account_id)
    out: List[dict] = []
    for p in raw:
        try:
            out.append({
                "id": p.get("id"),
                "symbol": p.get("contractId") or p.get("contract"),
                "type": p.get("type"),
                "volume": p.get("size"),
                "entryPrice": p.get("averagePrice"),
                "tp": p.get("tp"),
                "sl": p.get("sl"),
            })
        except Exception:
            continue
    return out


def get_topstepx_open_count(account_id: str, refresh: bool = False, refresh_seconds: int = 10, timeout: int = 10) -> int:
    """
    Return the number of open positions for the given TopStepX account. Optionally refresh via API.
    """
    try:
        if refresh:
            refresh_topstepx_open_positions([str(account_id)], refresh_seconds=refresh_seconds, timeout=timeout)
        return len(get_topstepx_open(str(account_id)))
    except Exception:
        return 0


def get_all_topstepx_open_counts(refresh: bool = False, refresh_seconds: int = 10, timeout: int = 10) -> Dict[str, int]:
    """
    Return a mapping of accountId -> open positions count for all discovered TopStepX accounts.
    """
    try:
        ids = get_discovered_topstepx_accounts()
        if refresh and ids:
            refresh_topstepx_open_positions(ids, refresh_seconds=refresh_seconds, timeout=timeout)
        return {aid: len(get_topstepx_open(aid)) for aid in ids}
    except Exception:
        return {}


def get_topstepx_tp_sl(account_id: str, contract_id: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Return the TP (limitPrice) and SL (stopPrice) for the given account/contract by
    querying open orders. Shape: {"tp": <float|None>, "sl": <float|None>}.
    """
    try:
        import requests
        import Globals
    except Exception:
        return {"tp": None, "sl": None}

    headers = {
        "Authorization": f"Bearer {getattr(Globals, 'KEY_ACCESS_TOKEN', '')}",
        "Content-Type": "application/json",
    }
    payload = {"accountId": int(account_id) if str(account_id).isdigit() else account_id}
    try:
        resp = requests.post("https://api.topstepx.com/api/Order/searchOpen", json=payload, headers=headers, timeout=timeout)
        data = resp.json()
    except Exception:
        data = {"orders": []}
    orders = data.get("orders") or data.get("openOrders") or []
    tp = None
    sl = None
    for o in orders:
        try:
            if str(o.get("contractId") or o.get("contract")) != str(contract_id):
                continue
            otype = o.get("type")
            if tp is None and otype == 1:
                tp = o.get("limitPrice")
            if sl is None and otype == 4:
                sl = o.get("stopPrice")
            if tp is not None and sl is not None:
                break
        except Exception:
            continue
    return {"tp": tp, "sl": sl}


# ---------------------- TopStepX background threads ----------------------

def _poll_topstepx_account_loop(aid: str, interval_seconds: int = 10, timeout: int = 10) -> None:
    stop = _TOPSTEPX_THREAD_STOPS.setdefault(aid, _threading.Event())
    while True:
        if stop.is_set():
            break
        try:
            # Force enriched refresh (positions + orders merged)
            refresh_topstepx_open_details([aid], refresh_seconds=0, timeout=timeout)
        except Exception:
            pass
        # Sleep in small chunks so we can react to stop
        slept = 0
        while slept < max(1, int(interval_seconds)):
            if stop.is_set():
                break
            _time.sleep(0.5)
            slept += 0.5


def start_topstepx_account_thread(aid: str, interval_seconds: int = 10, timeout: int = 10) -> None:
    aid = str(aid)
    with _LOCK:
        # Create or restart if thread is missing or not alive
        th = _TOPSTEPX_THREADS.get(aid)
        if th is not None and th.is_alive():
            return
        # Reset/ensure stop event exists and cleared
        stop = _TOPSTEPX_THREAD_STOPS.setdefault(aid, _threading.Event())
        try:
            stop.clear()
        except Exception:
            _TOPSTEPX_THREAD_STOPS[aid] = _threading.Event()
        # Spawn thread
        t = _threading.Thread(target=_poll_topstepx_account_loop, args=(aid, interval_seconds, timeout), daemon=True)
        _TOPSTEPX_THREADS[aid] = t
        t.start()


def start_topstepx_threads_for_discovered(interval_seconds: int = 10, timeout: int = 10) -> None:
    ids = get_discovered_topstepx_accounts()
    for aid in ids:
        start_topstepx_account_thread(aid, interval_seconds=interval_seconds, timeout=timeout)


# ---------------------- TopStepX order placement ----------------------

def _normalize_topstepx_size(value: Any) -> int:
    """Round to nearest whole number, clamp to minimum 1."""
    try:
        f = float(value)
    except Exception:
        return 1
    # Round to nearest whole number; Python's round uses banker's rounding.
    # For trading volume, a simple half-up approach is often preferred; implement manually.
    try:
        import math
        n = int(math.floor(f + 0.5))
    except Exception:
        n = int(round(f))
    if n < 1:
        n = 1
    return n

def topstepx_place_order(account_id: int | str,
                         contract_id: str,
                         side: int,
                         size: int,
                         order_type: int = 2,
                         bracket1: Optional[Dict[str, Any]] = None,
                         bracket2: Optional[Dict[str, Any]] = None,
                         limit_price: Optional[float] = None,
                         stop_price: Optional[float] = None,
                         timeout: int = 15) -> Dict[str, Any]:
    """
    Place an order via TopStepX Order/place.
    Mirrors TopStepX_Files/Open_Trade.py behavior with token refresh retry.

    Params:
      - account_id: numeric account id
      - contract_id: e.g. "CON.F.US.GCE.Z25"
      - side: 0 Buy, 1 Sell
      - size: integer contract size
      - order_type: 2 for market (per example)
      - bracket1: optional dict, e.g. {"action": "Sell", "orderType": "Limit", "price": 123.45}
      - bracket2: optional dict, e.g. {"action": "Sell", "orderType": "Stop", "stopPrice": 120.00}

    Returns parsed JSON or dict with status/text on errors.
    """
    ORDER_URL = "https://api.topstepx.com/api/Order/place"
    try:
        import requests
        # Enforce allowlist
        try:
            import Globals as _G
            allowed = getattr(_G, "TOPSTEPX_ALLOWED_ACCOUNTS", []) or getattr(_G, "TOPSTEP_ALLOWED_ACCOUNTS", [])
            if allowed and str(account_id) not in set(str(a) for a in allowed):
                return {"success": False, "error": "account_not_allowed"}
        except Exception:
            return {"success": False, "error": "account_not_allowed"}
        # Import TopStepX_Files.Connector dynamically to reuse authenticate
        # Ensure the TopStepX_Files dir is importable
        import os as _os, sys as _sys
        tsx_dir = _os.path.join(_os.path.dirname(__file__), "TopStepX_Files")
        if tsx_dir not in _sys.path:
            _sys.path.insert(0, tsx_dir)
        Connector = importlib.import_module("Connector")
        TGlobals = importlib.import_module("Globals")

        def _get_headers() -> Dict[str, str]:
            token = Connector.authenticate(getattr(TGlobals, "username", ""), getattr(TGlobals, "KEY_API_KEY_2", ""))
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

        norm_size = _normalize_topstepx_size(size)
        payload: Dict[str, Any] = {
            "accountId": int(account_id) if str(account_id).isdigit() else account_id,
            "contractId": contract_id,
            "type": int(order_type),
            "side": int(side),
            "size": norm_size,
        }
        if bracket1:
            payload["bracket1"] = bracket1
        if bracket2:
            payload["bracket2"] = bracket2
        if int(order_type) == 1 and limit_price is not None:
            payload["limitPrice"] = float(limit_price)
        if int(order_type) == 4 and stop_price is not None:
            payload["stopPrice"] = float(stop_price)

        headers = _get_headers()
        resp = requests.post(ORDER_URL, json=payload, headers=headers, timeout=timeout)
        if resp.status_code == 401:
            headers = _get_headers()
            resp = requests.post(ORDER_URL, json=payload, headers=headers, timeout=timeout)

        try:
            return resp.json()
        except Exception:
            return {"success": False, "status": resp.status_code, "text": getattr(resp, "text", "")}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def topstepx_close_contract(account_id: int | str,
                            contract_id: str,
                            timeout: int = 15) -> Dict[str, Any]:
    """
    Close a TopStepX contract position via Position/closeContract.
    Mirrors TopStepX_Files/Close_Trade.py but uses Connector.authenticate and retries on 401.
    """
    URL = "https://api.topstepx.com/api/Position/closeContract"
    try:
        import requests
        # Enforce allowlist
        try:
            import Globals as _G
            allowed = getattr(_G, "TOPSTEPX_ALLOWED_ACCOUNTS", []) or getattr(_G, "TOPSTEP_ALLOWED_ACCOUNTS", [])
            if allowed and str(account_id) not in set(str(a) for a in allowed):
                return {"success": False, "error": "account_not_allowed"}
        except Exception:
            return {"success": False, "error": "account_not_allowed"}
        import os as _os, sys as _sys
        tsx_dir = _os.path.join(_os.path.dirname(__file__), "TopStepX_Files")
        if tsx_dir not in _sys.path:
            _sys.path.insert(0, tsx_dir)
        Connector = importlib.import_module("Connector")
        TGlobals = importlib.import_module("Globals")

        def _get_headers() -> Dict[str, str]:
            token = Connector.authenticate(getattr(TGlobals, "username", ""), getattr(TGlobals, "KEY_API_KEY_2", ""))
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

        payload = {
            "accountId": int(account_id) if str(account_id).isdigit() else account_id,
            "contractId": contract_id,
        }

        headers = _get_headers()
        resp = requests.post(URL, json=payload, headers=headers, timeout=timeout)
        if resp.status_code == 401:
            headers = _get_headers()
            resp = requests.post(URL, json=payload, headers=headers, timeout=timeout)
        try:
            return resp.json()
        except Exception:
            return {"success": False, "status": resp.status_code, "text": getattr(resp, "text", "")}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------- MT5 sequence mirroring for TopStepX ----------------------

_DEFAULT_TSX_CONTRACT_ID = "CON.F.US.GCE.Z25"


def _get_allowed_topstepx_accounts() -> List[str]:
    try:
        import Globals
        allowed = getattr(Globals, "TOPSTEPX_ALLOWED_ACCOUNTS", []) or getattr(Globals, "TOPSTEP_ALLOWED_ACCOUNTS", [])
        return [str(a) for a in allowed]
    except Exception:
        return []


def topstepx_mirror_mt5_sequence_step(step_reply: int, contract_id: Optional[str] = None, size: int = 1) -> None:
    """
    Mirror MT5 sequence on TopStepX at specific reply counts.
    20: BUY, 40: SELL, 60: BUY, 80: CLOSE contract.
    """
    try:
        import Globals as _G
        if not getattr(_G, "TESTER_MODE", False):
            return
    except Exception:
        return
    cid = contract_id or _DEFAULT_TSX_CONTRACT_ID
    acts: List[Tuple[str, Dict[str, Any]]] = []
    if step_reply == 20:
        acts.append(("BUY", {"side": 0}))
    elif step_reply == 40:
        acts.append(("SELL", {"side": 1}))
    elif step_reply == 60:
        acts.append(("BUY", {"side": 0}))
    elif step_reply == 80:
        acts.append(("CLOSE", {}))
    else:
        return

    accts = _get_allowed_topstepx_accounts()
    for aid in accts:
        try:
            if not acts:
                continue
            for name, params in acts:
                if name == "CLOSE":
                    res = topstepx_close_contract(aid, cid)
                    # Minimal log line
                    try:
                        sys = __import__("sys").stdout
                        sys.write(f"[{now_iso()}] TSX CLOSE account={aid} contract={cid} ok={res.get('success', True)}\n")
                    except Exception:
                        pass
                else:
                    side = int(params.get("side", 0))
                    res = topstepx_place_order(aid, cid, side=side, size=size)
                    try:
                        sys = __import__("sys").stdout
                        sys.write(f"[{now_iso()}] TSX ORDER {name} account={aid} contract={cid} size={size} ok={res.get('success', True)}\n")
                    except Exception:
                        pass
        except Exception:
            continue


def print_find_all_accounts(only_active_accounts: bool = False, timeout: int = 10) -> dict:
    """
    Produce the same console output as TopStepX_Files/Find_All_Accounts.py and update discovered IDs.
    Prints:
      Status: <code>
      Response: <json>  (or Raw Response: <text>)
    Returns parsed JSON (or minimal dict on error).
    """
    try:
        import requests
        import Globals
    except Exception:
        print("Status:", -1)
        print("Raw Response:", "requests/Globals not available")
        return {"success": False}

    API_URL = "https://api.topstepx.com/api/Account/search"
    headers = {
        "Authorization": f"Bearer {getattr(Globals, 'KEY_ACCESS_TOKEN', '')}",
        "Content-Type": "application/json",
    }
    payload = {"onlyActiveAccounts": bool(only_active_accounts)}

    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=timeout)
        status_code = resp.status_code
        try:
            data = resp.json()
        except Exception:
            data = {"success": False, "status": status_code}

        # Extract IDs
        accounts = data.get("accounts") if isinstance(data, dict) else []
        ids = []
        if isinstance(accounts, list):
            for acc in accounts:
                try:
                    aid = str(acc.get("id")) if isinstance(acc, dict) else None
                    if aid:
                        ids.append(aid)
                except Exception:
                    continue

        # Print concise output
        print("Status:", status_code)
        print("IDs Found:", ", ".join(ids) if ids else "")

        # Update discovered cache and client modes
        if ids:
            with _LOCK:
                for aid in ids:
                    _DISCOVERED_TOPSTEPX_ACCOUNTS.add(aid)
                    _CLIENT_MODE.setdefault(aid, "TopStepX")
            try:
                global _DISCOVERED_LAST_FETCHED, _DISCOVERED_LAST_RESPONSE
                _DISCOVERED_LAST_FETCHED = _time.time()
                _DISCOVERED_LAST_RESPONSE = data
            except Exception:
                pass
        return data
    except Exception as exc:
        print("Status:", -1)
        print("IDs Found:")
        return {"success": False, "error": str(exc)}
