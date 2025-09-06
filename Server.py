#!/usr/bin/env python3
"""
Simple HTTP server to receive JSON payloads from the MQL5X EA.
- Expects POST requests with Content-Type: application/json
- Logs a summary to stdout and appends full payloads to received_log.jsonl
- No external dependencies (uses Python standard library)

Usage (PowerShell):
    python Server.py --host 0.0.0.0 --port 5000

In MetaTrader 5, add this URL to:
  Tools > Options > Expert Advisors > Allow WebRequest for listed URL:
  http://<host>:<port>
"""

import argparse
import json
import sys
from datetime import datetime, UTC
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Tuple
import Globals

LOG_FILE = "received_log.jsonl"


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _type_name(v) -> str:
    # Common MT5 conventions: 0=BUY, 1=SELL (others possible)
    try:
        return {0: "BUY", 1: "SELL"}.get(int(v), str(v))
    except Exception:
        return str(v)


def _ts(ts: int | float | None) -> str:
    if ts in (None, "", 0):
        return "-"
    try:
        return datetime.fromtimestamp(int(ts), UTC).isoformat(timespec="seconds")
    except Exception:
        return str(ts)


def _fmt(v, digits: int | None = None) -> str:
    try:
        if isinstance(v, (int, float)) and digits is not None:
            return f"{v:.{digits}f}"
        return str(v)
    except Exception:
        return str(v)


def pretty_print_payload(data: dict) -> None:
    id_ = data.get("id")
    mode = data.get("mode")
    open_list = data.get("open", [])

    print("\n=== MQL5X Open Positions ===")
    print(f"id: {id_}  mode: {mode}")
    print(f"open positions: {len(open_list)}")
    for i, p in enumerate(open_list, 1):
        sym = p.get("symbol")
        typ = _type_name(p.get("type"))
        vol = _fmt(p.get("volume"), 2)
        opn = _fmt(p.get("openPrice"))
        cur = _fmt(p.get("price"))
        sl = _fmt(p.get("sl"))
        tp = _fmt(p.get("tp"))
        tic = p.get("ticket")
        mgc = p.get("magic")
        cmt = p.get("comment", "")
        print(f"  - #{i} {sym} {typ} vol={vol} open={opn} price={cur} sl={sl} tp={tp} ticket={tic} magic={mgc} comment={cmt}")
    print("=== end open positions ===\n")


class MQL5XRequestHandler(BaseHTTPRequestHandler):
    server_version = "MQL5XHTTP/1.0"

    def log_message(self, format: str, *args) -> None:
        # Compact log lines
        sys.stdout.write("[%s] %s\n" % (now_iso(), format % args))

    def _send_json(self, code: int, payload: dict) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        # Simple health check
        if self.path in ("/", "/health", "/status"):
            self._send_json(200, {"status": "ok", "ts": now_iso()})
        elif self.path == "/message":
            # Two-way test: return the global test_message
            self._send_json(200, {"message": getattr(Globals, "test_message", "")})
        else:
            self._send_json(404, {"status": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body.decode("utf-8"))
        except Exception as exc:  # malformed JSON
            self.log_message("Malformed JSON from %s: %s", self.client_address[0], exc)
            self._send_json(400, {"status": "error", "error": "invalid_json"})
            return

        # Extract summary
        id_ = data.get("id")
        mode = data.get("mode")
        open_list = data.get("open", [])
        closed_offline = data.get("closed_offline", [])
        closed_online = data.get("closed_online", [])

        # Only summarize opens in server logs
        self.log_message(
            "Received payload: id=%s mode=%s open=%d",
            id_, mode, len(open_list),
        )

        # Pretty print the contents for quick inspection
        pretty_print_payload(data)

        # Append full payload with timestamp to a log file for later inspection
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": now_iso(), **data}) + "\n")
        except Exception as exc:
            self.log_message("Failed to write log: %s", exc)

        # Respond OK with a tiny echo summary
        self._send_json(200, {
            "status": "ok",
            "received": {
                "open": len(open_list),
                "closed_offline": len(closed_offline),
                "closed_online": len(closed_online),
            }
        })


def parse_args(argv=None) -> Tuple[str, int]:
    parser = argparse.ArgumentParser(description="MQL5X JSON receiver")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", default=5000, type=int, help="Port to listen on (default: 5000)")
    args = parser.parse_args(argv)
    return args.host, args.port


def main() -> None:
    host, port = parse_args()
    server = HTTPServer((host, port), MQL5XRequestHandler)
    print(f"[{now_iso()}] Listening on http://{host}:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{now_iso()}] Shutting down...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
