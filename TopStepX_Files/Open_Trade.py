import requests
import os
import sys

# Ensure this script's folder is first on sys.path so sibling modules are imported
sys.path.insert(0, os.path.dirname(__file__))

import Globals  # noqa: E402
import Connector  # noqa: E402

ORDER_URL = "https://api.topstepx.com/api/Order/place"

def get_auth_headers():
    """Fetch a fresh token and build headers."""
    token = Connector.authenticate(Globals.username, Globals.KEY_API_KEY_2)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

# Example values
account_id   = 11357588
contract_id  = "CON.F.US.GCE.Z25"
position_avg = 3610.1   # from your open position

# Define TP and SL
tp_price = position_avg + 20   # Take profit $20 higher
sl_price = position_avg - 20   # Stop loss $20 lower

payload = {
    "accountId": account_id,
    "contractId": contract_id,
    "type": 2,          # Market entry (already open, so brackets attach)
    "side": 0,          # 0 = Buy (your current side)
    "size": 1,          # size=0 because we're attaching brackets
    "bracket1": {
        "action": "Sell",
        "orderType": "Limit",
        "price": tp_price
    },
    "bracket2": {
        "action": "Sell",
        "orderType": "Stop",
        "stopPrice": sl_price
    }
}

if __name__ == "__main__":
    headers = get_auth_headers()
    resp = requests.post(ORDER_URL, json=payload, headers=headers)
    if resp.status_code == 401:
        # Token may be expired; refresh once and retry
        headers = get_auth_headers()
        resp = requests.post(ORDER_URL, json=payload, headers=headers)

    print("Status:", resp.status_code)
    # Print JSON if available, else raw text for debugging
    try:
        print("Response JSON:", resp.json())
    except Exception:
        print("Response Text:", getattr(resp, "text", "<no text>"))
