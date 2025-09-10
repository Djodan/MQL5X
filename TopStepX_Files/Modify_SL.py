import requests
import Globals

# Endpoints
ORDER_SEARCHOPEN_URL = "https://api.topstepx.com/api/Order/searchOpen"
ORDER_MODIFY_URL     = "https://api.topstepx.com/api/Order/modify"
POSITION_URL         = "https://api.topstepx.com/api/Position/searchOpen"

headers = {
    "Authorization": f"Bearer {Globals.KEY_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

account_id  = 11357588
contract_id = "CON.F.US.GCE.Z25"

# 1. Get the open position (to grab entry price)
pos_resp = requests.post(POSITION_URL, json={"accountId": account_id}, headers=headers)
pos_data = pos_resp.json()
if not pos_data.get("positions"):
    raise Exception("No open positions found.")
entry_price = pos_data["positions"][0]["averagePrice"]
print(f"Entry Price: {entry_price}")

# 2. Find the current Stop Loss order
order_resp = requests.post(ORDER_SEARCHOPEN_URL, json={"accountId": account_id}, headers=headers)
orders = order_resp.json().get("orders", [])
sl_order = next((o for o in orders if o.get("contractId") == contract_id and o.get("type") == 4), None)

if not sl_order:
    raise Exception("No open Stop Loss order found.")
print(f"Found SL Order ID: {sl_order['id']}")

# 3. Modify SL to entry price
modify_payload = {
    "orderId": sl_order["id"],
    "accountId": account_id,
    "contractId": contract_id,
    "type": 4,              # Stop
    "side": 1,              # Sell
    "size": sl_order["size"],
    "stopPrice": entry_price
}

mod_resp = requests.post(ORDER_MODIFY_URL, json=modify_payload, headers=headers)
print("Modify SL Response:", mod_resp.status_code, mod_resp.json())
