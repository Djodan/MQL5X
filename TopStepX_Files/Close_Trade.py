import requests
import Globals

# API Endpoint
POSITION_CLOSE_URL = "https://api.topstepx.com/api/Position/closeContract"

headers = {
    "Authorization": f"Bearer {Globals.KEY_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# Practice account and contract from your open trade
account_id  = 11357588
contract_id = "CON.F.US.GCE.Z25"

payload = {
    "accountId": account_id,
    "contractId": contract_id
}

resp = requests.post(POSITION_CLOSE_URL, json=payload, headers=headers)
print("Status:", resp.status_code)
try:
    print("Close Position Response:", resp.json())
except Exception:
    print("Raw Response:", resp.text)
