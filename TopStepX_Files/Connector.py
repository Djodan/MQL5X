import requests

import Globals

USERNAME = Globals.username
API_KEY = Globals.KEY_API_KEY_2

LOGIN_URL = "https://api.topstepx.com/api/Auth/loginKey"


def authenticate(username, api_key):
    payload = {
        "userName": username,
        "apiKey": api_key
    }
    headers = {"Content-Type": "application/json"}
    r = requests.post(LOGIN_URL, json=payload, headers=headers)
    try:
        data = r.json()
    except Exception:
        raise Exception(f"Non-JSON response: {r.status_code} {r.text}")

    if data.get("success"):
        return data["token"]
    else:
        raise Exception(
            f"Auth failed. "
            f"Code: {data.get('errorCode')}, "
            f"Message: {data.get('errorMessage')}, "
            f"Raw: {data}"
        )


if __name__ == "__main__":
    token = authenticate(USERNAME, API_KEY)
    print("Access Token:", token)
