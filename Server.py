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
import os
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Tuple
import Globals
import Functions
from Functions import (
    now_iso,
    ingest_payload,
    get_next_command,
    record_command_delivery,
    get_client_open,
    get_client_closed_online,
    list_clients,
    enqueue_command,
    ack_command,
)
import subprocess

class MQL5XRequestHandler(BaseHTTPRequestHandler):
    server_version = "MQL5XHTTP/1.0"

    def log_message(self, format: str, *args) -> None:
        # Silence default HTTP logs to avoid noisy JSON prints.
        return

    def _send_json(self, code: int, payload: dict) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        # Simple health check
        if self.path in ("/", "/health", "/status"):
            self._send_json(200, {"status": "ok", "ts": now_iso()})
            return

        # Back-compat message
        if self.path == "/message":
            self._send_json(200, {"message": getattr(Globals, "test_message", "")})
            return

        # EA polls next command: /command/<id>
        if self.path.startswith("/command/"):
            parts = [p for p in self.path.split("/") if p]
            if len(parts) == 2:
                client_id = parts[1]
                msg = get_next_command(client_id)
                # Record delivery stats based on current planned state
                int_state = 0
                if "state" in msg:
                    try:
                        int_state = int(msg.get("state", 0))
                    except Exception:
                        int_state = 0
                stats = record_command_delivery(client_id, int_state)
                # Inject sequence:
                # - On reply 20 open a BUY
                # - On reply 40 open a SELL
                # - On reply 60 open another BUY
                # - On reply 80 close the SELL
                try:
                    r = int(stats.get("replies", 0))
                    injected = False
                    if r == 20:
                        # First BUY with large pip-based SL/TP
                        enqueue_command(
                            client_id,
                            1,
                            {"symbol": "XAUUSD", "volume": 1.00, "comment": "auto BUY on reply #20", "slPips": 10000, "tpPips": 10000}
                        )
                        injected = True
                    elif r == 40:
                        enqueue_command(client_id, 2, {"symbol": "XAUUSD", "volume": 1.00, "comment": "auto SELL on reply #40"})
                        injected = True
                    elif r == 60:
                        # Second BUY with absolute SL/TP prices
                        enqueue_command(
                            client_id,
                            1,
                            {"symbol": "XAUUSD", "volume": 1.00, "comment": "auto BUY on reply #60", "sl": 3341, "tp": 3722}
                        )
                        injected = True
                    elif r == 80:
                        # Close the SELL (type=1)
                        enqueue_command(client_id, 3, {"symbol": "XAUUSD", "type": 1, "comment": "auto CLOSE SELL on reply #80"})
                        injected = True
                    if injected and int(msg.get("state", 0)) == 0:
                        msg = get_next_command(client_id)
                except Exception:
                    pass
                # Print concise line: ID, open count, last action, replies
                try:
                    open_count = len(get_client_open(client_id))
                except Exception:
                    open_count = 0
                # Display the effective state being returned to EA
                eff_state = 0
                try:
                    eff_state = int(msg.get("state", 0))
                except Exception:
                    eff_state = 0
                sys.stdout.write(f"[{now_iso()}] ID={client_id} Open={open_count} LastAction={eff_state} Replies={stats['replies']}\n")
                # If this is an open order command, also print a single summary line
                if eff_state in (1,2):
                    side = "BUY" if eff_state==1 else "SELL"
                    sym = msg.get("symbol")
                    vol = msg.get("volume")
                    tp = msg.get("tp") if "tp" in msg else msg.get("tpPips")
                    sl = msg.get("sl") if "sl" in msg else msg.get("slPips")
                    sys.stdout.write(f"[{now_iso()}] ORDER -> {side} {sym} vol={vol} TP={tp} SL={sl}\n")
                self._send_json(200, msg)
            else:
                self._send_json(400, {"error": "bad_path"})
            return

        # Client views
        if self.path.startswith("/clients"):
            parts = [p for p in self.path.split("/") if p]
            if len(parts) == 1:  # /clients
                self._send_json(200, {"clients": list_clients()})
                return
            if len(parts) >= 2:
                client_id = parts[1]
                if len(parts) == 3 and parts[2] == "open":
                    self._send_json(200, {"id": client_id, "open": get_client_open(client_id)})
                    return
                if len(parts) == 3 and parts[2] == "closed_online":
                    self._send_json(200, {"id": client_id, "closed_online": get_client_closed_online(client_id)})
                    return
                # default: client summary
                self._send_json(200, {
                    "id": client_id,
                    "open_count": len(get_client_open(client_id)),
                    "closed_online_count": len(get_client_closed_online(client_id)),
                })
                return

        # Not found
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

        # Routes: payload ingest or command enqueue/ack
        path = self.path
        if path == "/":
            # Process and store per-client snapshots
            summary, identity = ingest_payload(data)
            self.log_message(
                "Received payload: id=%s mode=%s open=%d",
                identity.get("id"), identity.get("mode"), summary.get("open", 0)
            )
            self._send_json(200, {"status": "ok", "received": summary, **identity})
            return

        if path.startswith("/command/"):
            # Enqueue a command to a client: POST /command/<id>
            parts = [p for p in path.split("/") if p]
            if len(parts) == 2:
                client_id = parts[1]
                # Expect { state: 0|1|2|3, payload?: {...} }
                state = int(data.get("state", 0))
                payload = data.get("payload") or {}
                cmd = enqueue_command(client_id, state, payload)
                self._send_json(200, {"status": "queued", "command": cmd})
                return
            self._send_json(400, {"error": "bad_path"})
            return

        if path.startswith("/ack/"):
            # EA acknowledges a command: POST /ack/<id>
            parts = [p for p in path.split("/") if p]
            if len(parts) == 2:
                client_id = parts[1]
                cmd_id = data.get("cmdId")
                success = bool(data.get("success", False))
                details = data.get("details") or {}
                res = ack_command(client_id, cmd_id, success, details)
                # concise ack log with order details when available
                paid = None
                typestr = None
                vol = None
                tp = None
                sl = None
                sym = None
                if isinstance(details, dict):
                    paid = details.get("retcode")
                    typestr = details.get("type")
                    vol = details.get("volume")
                    tp = details.get("tp")
                    sl = details.get("sl")
                    sym = details.get("symbol")
                    # paid price if present
                    try:
                        price_paid = details.get("paid")
                        if price_paid is not None:
                            paid = price_paid
                    except Exception:
                        pass
                sys.stdout.write(f"[{now_iso()}] ACK id={client_id} cmd={cmd_id} success={success} Paid={paid} OrderType={typestr} Symbol={sym} Volume={vol} TP={tp} SL={sl}\n")
                self._send_json(200, res)
                return
            self._send_json(400, {"error": "bad_path"})
            return

        # Default: unknown POST route
        self._send_json(404, {"status": "not_found"})


def parse_args(argv=None) -> Tuple[str, int]:
    parser = argparse.ArgumentParser(description="MQL5X JSON receiver")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", default=5000, type=int, help="Port to listen on (default: 5000)")
    args = parser.parse_args(argv)
    return args.host, args.port


def main() -> None:
    # Clear terminal on start (Windows: cls, others: clear)
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
    except Exception:
        pass
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
