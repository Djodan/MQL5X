import requests
import Globals

API_URL = "https://api.topstepx.com/api/Account/search"

headers = {
    "Authorization": f"Bearer {Globals.KEY_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

payload = {
    "onlyActiveAccounts": False   # set to True if you only want active ones
}

response = requests.post(API_URL, json=payload, headers=headers)

print("Status:", response.status_code)
try:
    print("Response:", response.json())
except Exception:
    print("Raw Response:", response.text)
