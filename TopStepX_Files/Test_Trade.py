import requests
import Globals

# API Endpoints (production TopstepX)
ACCOUNT_URL  = "https://api.topstepx.com/api/Account/search"
CONTRACT_URL = "https://api.topstepx.com/api/Contract/available"
ORDER_URL    = "https://api.topstepx.com/api/Order/place"

# Headers
headers = {
    "Authorization": f"Bearer {Globals.KEY_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# 1. Get all active accounts and pick practice account
resp = requests.post(ACCOUNT_URL, json={"onlyActiveAccounts": True}, headers=headers)
accounts = resp.json().get("accounts", [])
if not accounts:
    raise Exception("No active accounts found. Make sure your token is valid.")

practice_acct = next((a for a in accounts if "PRAC" in a["name"]), None)
if not practice_acct:
    print("Accounts found:", accounts)
    raise Exception("Practice account not found.")
account_id = practice_acct["id"]
print(f"Using Practice Account: {practice_acct['name']} (ID: {account_id})")

# 2. Get available contracts and find Gold (GCZ5)
resp = requests.post(CONTRACT_URL, json={"accountId": account_id, "live": False}, headers=headers)
contracts = resp.json().get("contracts", [])

gc_contract = next(
    (c for c in contracts if c.get("name", "").startswith("GC") or "Gold" in c.get("description", "")),
    None
)

if not gc_contract:
    print("Available contracts:")
    for c in contracts:
        print(c)
    raise Exception("Gold contract not found. See above list for details.")

contract_id = gc_contract["id"]
print(f"Using Contract: {gc_contract['name']} - {gc_contract['description']} (ID: {contract_id})")

# 3. Place market buy order
payload = {
    "accountId": account_id,
    "contractId": contract_id,
    "type": 2,   # 2 = Market
    "side": 0,   # 0 = Buy
    "size": 1
}
resp = requests.post(ORDER_URL, json=payload, headers=headers)
print("Order Response:", resp.status_code, resp.json())
