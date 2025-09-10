import requests
import Globals

# Endpoint
POSITION_PARTIAL_CLOSE_URL = "https://api.topstepx.com/api/Position/partialCloseContract"

headers = {
    "Authorization": f"Bearer {Globals.KEY_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

account_id  = 11357588
contract_id = "CON.F.US.GCE.Z25"

# Close half (1 lot out of 2)
payload = {
    "accountId": account_id,
    "contractId": contract_id,
    "size": 1   # number of contracts to close
}

resp = requests.post(POSITION_PARTIAL_CLOSE_URL, json=payload, headers=headers)

print("Status:", resp.status_code)
try:
    print("Partial Close Response:", resp.json())
except Exception:
    print("Raw Response:", resp.text)
