import requests
import Globals

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
position = pos_resp.json()["positions"][0]
entry_price = position["averagePrice"]
size = position["size"]

# 2. Account balance and risk
balance = 150111.9
risk_amount = balance * 0.01
tick_value = 10.0
tick_size  = 0.1

ticks = risk_amount / (tick_value * size)
sl_price = entry_price - (ticks * tick_size)
print(f"Placing new SL at {sl_price}")

# 3. Place Stop Loss order
sl_payload = {
    "accountId": account_id,
    "contractId": contract_id,
    "type": 4,           # Stop
    "side": 1,           # Sell
    "size": size,
    "stopPrice": round(sl_price, 1)
}

resp = requests.post(ORDER_URL, json=sl_payload, headers=headers)
print("Place SL Response:", resp.status_code, resp.json())
