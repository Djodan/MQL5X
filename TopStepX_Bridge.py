#!/usr/bin/env python3
"""
Minimal TopStepX bridge that posts a TopStepX-style payload to the local server
so it appears alongside MetaTrader in the status lines.

This script simulates a TopStepX client (mode: "TopStepX").
Adjust to call real TopStepX APIs as needed.
"""
import os
import time
import json
import requests

SERVER = os.environ.get("MQL5X_SERVER", "http://127.0.0.1:5000/")
CLIENT_ID = os.environ.get("MQL5X_TOPSTEPX_ID", "TSX")

# Dummy open position sample (contract-like symbol)
dummy_open = [
    {
        "ticket": 360018684,
        "symbol": "CON.F.US.GCE.Z25",
        "type": 0,
        "volume": 1,
        "openPrice": 3668.0,
        "price": 3668.5,
        "sl": 0.0,
        "tp": 0.0,
        "magic": 0,
        "comment": "TopStepX bridge"
    }
]

payload = {
    "id": CLIENT_ID,
    "mode": "TopStepX",
    "open": dummy_open,
    "closed_offline": [],
    "closed_online": []
}

if __name__ == "__main__":
    url = SERVER.rstrip("/") + "/"
    try:
        r = requests.post(url, json=payload, timeout=5)
        print("Bridge POST:", r.status_code, r.text[:200])
    except Exception as exc:
        print("Bridge error:", exc)
