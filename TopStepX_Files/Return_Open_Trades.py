import requests
import Globals

# API Endpoint
POSITION_SEARCHOPEN_URL = "https://api.topstepx.com/api/Position/searchOpen"

headers = {
    "Authorization": f"Bearer {Globals.KEY_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# Practice account ID
account_id = 11357588

payload = {
    "accountId": account_id
}

resp = requests.post(POSITION_SEARCHOPEN_URL, json=payload, headers=headers)

print("Status:", resp.status_code)
try:
    data = resp.json()
    print("Open Trades Response:", data)
except Exception:
    print("Raw Response:", resp.text)
