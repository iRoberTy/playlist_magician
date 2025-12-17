from django.shortcuts import render
import base64
#import requests

def home(request):

  return render(request, "home.html", {"data": [1, 2, 3, 4]})
































'''CLIENT_ID = 'CLIENT_ID'  # Get from Spotify App
CLIENT_SECRET = None # Get from DB
REDIRECT_URI = 'http://127.0.0.1:8888/callback'
STATE = None

# Create random State string for safety reasons
def set_random_state():
    global STATE
    STATE = 4
    return
    
def get_authorization_code():
    global STATE
    scope = None
    
    url = "https://accounts.spotify.com/authorize?"
    parameters = {
        "client_id": CLIENT_ID,
        "response_type": 'code',
        "redirect_uri": REDIRECT_URI,
        #"scope": scope,
        #"state": STATE
    }
    
    response = requests.post(url, params=parameters)
    # Here the User has to login/authorize access -----------------------
    
    print(response.status_code)
    if response.status_code != 200: 
        return None
    print(response.text)
    print(response.json())
    
    response = response.json()
    print(response["state"])
    
    return {"code": response["code"], 
            "state": response["state"]}

# Get final access_token
def get_access_token():
    set_random_state()
    auth_resp = get_authorization_code()
    
    if auth_resp["code"] is None: 
        print("failed authorization")
        return
    elif auth_resp["state"] != STATE:
        print("States not matching!")
        return
    
    # --- Basic Auth erstellen ---
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_bytes = auth_str.encode("utf-8")
    auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

    # --- Token-Anfrage vorbereiten ---
    token_url = "https://accounts.spotify.com/api/token"
    data = {
        "code": auth_resp["code"],
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_base64}",
    }

    # --- POST-Request senden ---
    response = requests.post(token_url, data=data, headers=headers)
    
    # returns access_token, token_type, scope, expires_in, refresh_token + response.status_code: 200
    return response.json()
    
    
    

# Test Api Call
def api_call():
    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret"
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response = requests.post(url, data=data, headers=headers)'''