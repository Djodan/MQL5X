import requests
import Globals

ORDER_URL = "https://api.topstepx.com/api/Order/place"

headers = {
    "Authorization": f"Bearer {Globals.KEY_ACCESS_TOKEN}",
    "Content-Type": "application/json"
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
    "size": 0,          # size=0 because we're attaching brackets
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

resp = requests.post(ORDER_URL, json=payload, headers=headers)
print("Status:", resp.status_code)
print("Response:", resp.json())
