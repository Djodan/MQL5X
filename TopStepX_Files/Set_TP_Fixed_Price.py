import requests
import Globals

# Endpoint
ORDER_URL    = "https://api.topstepx.com/api/Order/place"
POSITION_URL = "https://api.topstepx.com/api/Position/searchOpen"

headers = {
    "Authorization": f"Bearer {Globals.KEY_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

account_id  = 11357588
contract_id = "CON.F.US.GCE.Z25"

# 1. Get current open position
pos_resp = requests.post(POSITION_URL, json={"accountId": account_id}, headers=headers)
positions = pos_resp.json().get("positions", [])
if not positions:
    raise Exception("No open positions found.")
position = positions[0]
size = position["size"]

# 2. Fixed TP price
tp_price = 3800.0

# 3. Place TP Limit order
tp_payload = {
    "accountId": account_id,
    "contractId": contract_id,
    "type": 1,            # 1 = Limit
    "side": 1,            # 1 = Sell
    "size": size,
    "limitPrice": tp_price
}

tp_resp = requests.post(ORDER_URL, json=tp_payload, headers=headers)
print("TP Response:", tp_resp.status_code, tp_resp.json())
