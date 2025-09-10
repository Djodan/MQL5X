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
        # Include any discovered TopStepX account ids as well
        base |= set(_DISCOVERED_TOPSTEPX_ACCOUNTS)
        return sorted(base)


def get_client_mode(client_id: str) -> str:
    with _LOCK:
        return _CLIENT_MODE.get(str(client_id), "")


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
            with _LOCK:
                for aid in ids:
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
    with _LOCK:
        return sorted(_DISCOVERED_TOPSTEPX_ACCOUNTS)


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


def get_topstepx_closed(account_id: str) -> List[dict]:
    with _LOCK:
        return deepcopy(_TOPSTEPX_CLOSED.get(str(account_id), []))


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


# ---------------------- TopStepX background threads ----------------------

def _poll_topstepx_account_loop(aid: str, interval_seconds: int = 10, timeout: int = 10) -> None:
    stop = _TOPSTEPX_THREAD_STOPS.setdefault(aid, _threading.Event())
    while True:
        if stop.is_set():
            break
        try:
            # Force refresh by bypassing throttle for this account
            refresh_topstepx_open_positions([aid], refresh_seconds=0, timeout=timeout)
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

def topstepx_place_order(account_id: int | str,
                         contract_id: str,
                         side: int,
                         size: int,
                         order_type: int = 2,
                         bracket1: Optional[Dict[str, Any]] = None,
                         bracket2: Optional[Dict[str, Any]] = None,
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

        payload: Dict[str, Any] = {
            "accountId": int(account_id) if str(account_id).isdigit() else account_id,
            "contractId": contract_id,
            "type": int(order_type),
            "side": int(side),
            "size": int(size),
        }
        if bracket1:
            payload["bracket1"] = bracket1
        if bracket2:
            payload["bracket2"] = bracket2

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
                    res = topstepx_place_order(aid, cid, side=side, size=int(size))
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
