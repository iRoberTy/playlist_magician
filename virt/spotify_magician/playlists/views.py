from django.shortcuts import render
import base64
#import requests

def home(request):

  return render(request, "home.html", {"data": [1, 2, 3, 4]})

from django.db import models
from django.contrib.auth.models import User

# Erweiterung des Standard-Users um Spotify-Daten [cite: 221]
class SpotifyProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    spotify_id = models.CharField(max_length=255, unique=True)
    access_token = models.TextField()  # Speicherung verschlüsselt geplant [cite: 230]
    refresh_token = models.TextField()
    token_expires_at = models.DateTimeField()

    def __str__(self):
        return f"Spotify Profile of {self.user.username}"

# Speichert Einstellungen für die Playlist-Generierung [cite: 223, 224]
class PlaylistConfig(models.Model):
    PLAYLIST_TYPES = [
        ('JOGGING', 'Jogging Playlist'),
        ('RELEASE', 'Neuerscheinungen'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    config_type = models.CharField(max_length=20, choices=PLAYLIST_TYPES)
    
    # Für Jogging 
    target_bpm_min = models.IntegerField(default=120, null=True, blank=True)
    target_bpm_max = models.IntegerField(default=160, null=True, blank=True)
    target_energy = models.FloatField(default=0.7, null=True, blank=True) # 0.0 bis 1.0
    
    # Für Neuerscheinungen [cite: 223]
    artist_limit = models.IntegerField(default=5, null=True, blank=True) # Anzahl Songs pro Künstler
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.config_type} Config for {self.user.username}"






























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