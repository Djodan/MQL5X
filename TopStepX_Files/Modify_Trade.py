import requests
import Globals

ORDER_URL = "https://api.topstepx.com/api/Order/place"

headers = {
    "Authorization": f"Bearer {Globals.KEY_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

account_id   = 11357588
contract_id  = "CON.F.US.GCE.Z25"
avg_price    = 3610.1

tp_price = avg_price + 20
sl_price = avg_price - 20

# 1. Place Take Profit (Sell Limit)
tp_payload = {
    "accountId": account_id,
    "contractId": contract_id,
    "type": 1,           # 1 = Limit
    "side": 1,           # 1 = Sell
    "size": 1,
    "limitPrice": tp_price
}

tp_resp = requests.post(ORDER_URL, json=tp_payload, headers=headers)
print("TP Response:", tp_resp.status_code, tp_resp.json())

# 2. Place Stop Loss (Sell Stop)
sl_payload = {
    "accountId": account_id,
    "contractId": contract_id,
    "type": 4,           # 4 = Stop
    "side": 1,           # 1 = Sell
    "size": 1,
    "stopPrice": sl_price
}

sl_resp = requests.post(ORDER_URL, json=sl_payload, headers=headers)
print("SL Response:", sl_resp.status_code, sl_resp.json())
