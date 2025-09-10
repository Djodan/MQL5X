import requests
import Globals

# Endpoints
ACCOUNT_URL  = "https://api.topstepx.com/api/Account/search"
POSITION_URL = "https://api.topstepx.com/api/Position/searchOpen"
ORDER_URL    = "https://api.topstepx.com/api/Order/place"

headers = {
    "Authorization": f"Bearer {Globals.KEY_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

account_id  = 11357588
contract_id = "CON.F.US.GCE.Z25"

# 1. Get account balance
acc_resp = requests.post(ACCOUNT_URL, json={"onlyActiveAccounts": True}, headers=headers)
accounts = acc_resp.json().get("accounts", [])
acct = next((a for a in accounts if a["id"] == account_id), None)
if not acct:
    raise Exception("Account not found.")
balance = acct["balance"]
risk_amount = balance * 0.01
print(f"Account Balance: {balance}, Risk/TP Amount (1%): {risk_amount}")

# 2. Get current position
pos_resp = requests.post(POSITION_URL, json={"accountId": account_id}, headers=headers)
positions = pos_resp.json().get("positions", [])
if not positions:
    raise Exception("No open position found.")
position = positions[0]
entry_price = position["averagePrice"]
size = position["size"]
print(f"Position: {size} @ {entry_price}")

# 3. Tick values for Gold
tick_value = 10.0   # Gold futures
tick_size  = 0.1

# 4. Calculate TP distance
ticks = risk_amount / (tick_value * size)
tp_price = entry_price + (ticks * tick_size)
print(f"Calculated TP: {tp_price}")

# 5. Place TP Limit order
tp_payload = {
    "accountId": account_id,
    "contractId": contract_id,
    "type": 1,           # Limit
    "side": 1,           # Sell
    "size": size,
    "limitPrice": round(tp_price, 1)  # round to nearest tick
}

tp_resp = requests.post(ORDER_URL, json=tp_payload, headers=headers)
print("TP Response:", tp_resp.status_code, tp_resp.json())
