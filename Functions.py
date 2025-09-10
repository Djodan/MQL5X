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
from typing import Any, Dict, List, Tuple, Optional
import uuid

LOG_FILE = "received_log.jsonl"

# In-memory stores keyed by client id (string)
_LOCK = threading.Lock()
_CLIENT_OPEN: Dict[str, List[dict]] = {}
_CLIENT_CLOSED_ONLINE: Dict[str, List[dict]] = {}
_CLIENT_COMMANDS: Dict[str, List[dict]] = {}
_CLIENT_STATS: Dict[str, Dict[str, int]] = {}  # { id: { replies: int, last_action: int } }


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
        return sorted(set(_CLIENT_OPEN.keys()) | set(_CLIENT_CLOSED_ONLINE.keys()))


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
                    # expected: symbol, volume, comment?
                    msg.update({
                        "symbol": payload.get("symbol"),
                        "volume": payload.get("volume"),
                        "comment": payload.get("comment", ""),
                    })
                elif state == 2:  # Open SELL
                    msg.update({
                        "symbol": payload.get("symbol"),
                        "volume": payload.get("volume"),
                        "comment": payload.get("comment", ""),
                    })
                elif state == 3:  # Close trade
                    # expected: ticket or symbol/volume
                    msg.update({
                        "ticket": payload.get("ticket"),
                        "symbol": payload.get("symbol"),
                        "volume": payload.get("volume"),
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
