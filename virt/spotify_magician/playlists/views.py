from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.utils.http import url_has_allowed_host_and_scheme
from datetime import datetime, timedelta
from django.utils import timezone
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils.timezone import make_aware
import time
import requests
import base64
import hashlib
import secrets
import urllib.parse

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token" # Refresh Access Token
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# Should be in Settings
SPOTIFY_CLIENT_ID = "b90fcd35292d4b59983b191d99496714"
SPOTIFY_CLIENT_SECRET = "0110ec5d705f42e396e6f5f91b11ea12"
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8000/callback/"

SESSION_ENGINE = "django.contrib.sessions.backends.db"

def home(request):
    return render(request, "home.html")

# Helper Function for getting Access Token
def refresh_access_token(refresh_token):
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": SPOTIFY_CLIENT_ID,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
    response.raise_for_status()

    return response.json()

# Helper Function for getting Access Token
def is_access_token_valid(expires_in):
    if not expires_in:
        return False

    return time.time() < expires_in # Returns True if valid

# Main Function for getting Access Token (after login)
def get_valid_access_token(request):
    access_token = request.session.get("access_token")
    refresh_token = request.session.get("refresh_token")
    expires_in = request.session.get("expires_in")
    # Get from DB? ------------------------

    if not refresh_token:
        # Should never happen
        return None

    # If access token exists AND is still valid → use it
    if access_token and expires_in and is_access_token_valid(expires_in):
        return access_token

    # Otherwise refresh
    token_data = refresh_access_token(refresh_token)

    request.session["access_token"] = token_data["access_token"]
    expires_in = timezone.now() + timedelta(seconds=token_data["expires_in"])
    request.session["expires_in"] = int(expires_in.timestamp())

    # Spotify may rotate refresh tokens
    if "refresh_token" in token_data:
        request.session["refresh_token"] = token_data["refresh_token"]
        # Update DB? -------------------------

    return token_data["access_token"]

# Helper Function for Login
def generate_code_verifier():
    return secrets.token_urlsafe(64)

# Helper Function for Login
def generate_code_challenge(code_verifier):
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")

# Main Login Function (redirect to Spotify Url for permissions)
def spotify_login(request):
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    request.session["code_verifier"] = code_verifier

    scope = "user-read-private playlist-read-private user-top-read playlist-modify-public playlist-modify-private"

    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": scope,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
    }

    url = f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return redirect(url)

# Get Data of User after permissions and Store Login Data
def spotify_callback(request):
    code = request.GET.get("code")
    code_verifier = request.session.get("code_verifier")

    if not code or not code_verifier:
        return redirect("home")

    data = {
        "client_id": SPOTIFY_CLIENT_ID,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "code_verifier": code_verifier,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
    # Check if successful or hit rate Limit...
    if response.status_code != 200:
        return redirect("home")
    
    token_data = response.json()
    
    # Store Data in Session
    request.session["access_token"] = token_data["access_token"]
    request.session["refresh_token"] = token_data["refresh_token"]
    
    headers = {
        "Authorization": f"Bearer {token_data["access_token"]}"
    }
    user = requests.get(f"{SPOTIFY_API_BASE}/me", headers=headers)
    # Check if succesfully got user_id or hit rate Limit..
    if user.status_code != 200:
        return redirect("home")
    user = user.json()
    
    request.session["user_id"] = user["id"]
    request.session["market"] = user["country"] # For Region based Tracks ---------------
    
    expires_in = timezone.now() + timedelta(seconds=token_data["expires_in"])
    request.session["expires_in"] = int(expires_in.timestamp())
    
    print(token_data["scope"], token_data["expires_in"])
    
    # Store in DB (This code works if we have User DB field)
    '''# Get Spotify UserID
    # Get or create new user
    user, created = User.objects.get_or_create(
        id=user_id.json(),
        #defaults={'access_token': token_data["access_token"], 
        #        'refresh_token': token_data.get("refresh_token")}
    )
    
    # Log them in using Django session
    login(request, user)   # creates the sessionid cookie Django expects'''

    # get ?next= from the return URL
    next_url = request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('home')  # fallback if no next param

#@login_required # set LOGIN_URL in Settings
# Not used
def playlist_conf(request):
    start = time.time()
    
    access_token = get_valid_access_token(request)

    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    # Get Spotify UserID
    user_id = request.session.get("user_id")

    # Get User playlists
    playlists = requests.get(f"{SPOTIFY_API_BASE}/me/playlists", headers=headers) # <--------------- Very Slow (500ms)
    # Check if succesfully got user_id or hit rate Limit..
    if playlists.status_code != 200:
        return redirect("home")
    
    end = time.time()
    print(end-start)
    
    return render(request, "playlist_conf.html", {
        "user": user_id,
        "playlists": playlists.json().get("items", []),
    })

# Helper Function fpr "playlist_fav-songs"
def parse_release_date(date_str):
    # Spotify returns YYYY or YYYY-MM or YYYY-MM-DD
    formats = ["%Y-%m-%d", "%Y-%m", "%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

# Apply Playlist configuration (Aufgabe 1)
#@login_required
def playlist_fav_songs(request):
    access_token = get_valid_access_token(request)
    user_id = request.session.get("user_id")
    fav_artist_count = int(request.POST.get("fav_artist_count")) if request.POST.get("fav_artist_count") else 5  # Optional User Input
    regelmäßig_aktualisieren = True
    print(fav_artist_count)
    # Backend Fetch Configuration
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "time_range": "medium_term", # Timerange of fav_artists/songs: long_term (1y) - medium_term (6m) - short_term (4w)
        "limit": fav_artist_count,
        "offset": 0
    }
    
    artists_resp = requests.get(f"{SPOTIFY_API_BASE}/me/top/artists", headers=headers, params=params) # ---------------- Get fav Artists --------------- (Users: "Get User's Top Items" - endpoint)
    
    # Check if succesfully got artists or hit rate Limit..
    if artists_resp.status_code != 200:
        print(f"/me/top/artists endpoint failed with status code: {albums_resp.status_code}")
        return JsonResponse({
            "success": False,
        })
    
    artists_list = artists_resp.json()
    
    # Check if artists count == fav_artist_count
    if len(artists_list.get("items")) != fav_artist_count:
        print("actually existing artist count doesnt match the user given number")
        return JsonResponse({
            "success": False,
        })
    
    # Get 50 Tracks
    PLAYLIST_MAX_TRACKS = 50
    track_uris = []
    num_artists = len(artists_list["items"])

    tracks_per_artist = max(1, PLAYLIST_MAX_TRACKS // num_artists) # 50 Tracks evenly distributed between available artists (min 1 per)
    print(tracks_per_artist)
    for artist in artists_list["items"]:
        params = {
            "include_groups": "album, single", # album - single - appears_on - compilation
            "market": request.session.get("market"),
            "limit": 10, 
            "offset": 0
        }
        albums_resp = requests.get(f"{SPOTIFY_API_BASE}/artists/{artist["id"]}/albums", headers=headers, params=params) # ---------- Get newest Single/Album of fav Artists ---------- (Artists: "Get Artist's Albums" - endpoint)
        
        # Check if succesfully got albums or hit rate Limit..
        if albums_resp.status_code != 200:
            print(f"/artists/(artistid)/albums endpoint failed with status code: {albums_resp.status_code}")
            return JsonResponse({
                "success": False,
            })
        
        albums_list = albums_resp.json()
        
        albums_sorted = sorted(
            albums_list["items"],
            key=lambda a: parse_release_date(a["release_date"]),
            reverse=True
        )

        # Collect tracks for this artist
        artist_track_ids = []

        for album in albums_sorted:
            if len(artist_track_ids) >= tracks_per_artist:
                break

            album_tracks_resp = requests.get(f"{SPOTIFY_API_BASE}/albums/{album['id']}/tracks",headers=headers) # ------------ Get Album Tracks --------- (Albums: "Get Album Tracks" - endpoint)

            if album_tracks_resp.status_code != 200:
                print(f"/albums/(albumid)/tracks endpoint failed with status code: {album_tracks_resp.status_code}")
                continue

            album_tracks = album_tracks_resp.json()["items"]

            for t in album_tracks:
                if len(artist_track_ids) >= tracks_per_artist:
                    break
                artist_track_ids.append(t["uri"])

        # Add to global list
        track_uris.extend(artist_track_ids)

    # Trim to exactly 50 if needed
    track_uris = track_uris[:50]

    # Create a new Playlist for User
    headers = { 
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json" 
    }
    params = {
        "name": "Fav Artists Songs",
        "public": True, # needs scope "playlist-modify-private" or "playlist-modify-public"
        "collaborative": False, # needs scope "playlist-modify-private" or "playlist-modify-public"
        "description": "This Playlist includes your favourite Artists recent Tracks"
    }
    create_playlist_resp = requests.post(f"{SPOTIFY_API_BASE}/me/playlists", headers=headers, json=params) # ---------- Create new Playlist for User ---------- (Playlists: "Create Playlist" depreciated (so unknown source) - endpoint)
    
    if create_playlist_resp.status_code not in (201, 200):
        print(f"/users/(userid)/playlists endpoint failed with status code: {create_playlist_resp.status_code}")
        return JsonResponse({
            "success": False,
        })
    
    playlist_id = create_playlist_resp.json()["id"]

    # Add Tracks to the created Playlist
    uris = [uri for uri in track_uris]   # Comma seperated uris list
    params = {
            "playlist_id": playlist_id,
            "position": 0, # which position in the Playlist List to append
            "uris": uris
        }
    create_playlist_resp = requests.post(f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks", headers=headers, json=params) # ---------- Add Tracks to the created Playlist ---------- (Playlists: "Add Items to Playlist" - endpoint)
    
    if create_playlist_resp.status_code not in (200, 201):
        print(f"/playlists/(playlist_id)/tracks endpoint failed with status code: {create_playlist_resp.status_code}")
        return JsonResponse({
            "success": False,
        })
    
    # Store Configuration Data in DB here for regelmäßig Playlist ändern
    
    print("successfully create Playlist")
    return JsonResponse({
        "success": True,
        "playlist_url": f"https://open.spotify.com/playlist/{playlist_id}"
    })
        
    
    
def logout_view(request):
    request.session.flush() # Same as logout
    #logout(request)
    return redirect("home")

# Fragen zu klären
# access_token + refresh_token nur in db speichern, wenn wir die Eigenschaft mit "Playlists fortlaufend updaten" erfüllen wollen 
# ODER Konfiguration speichern, sonst --> Sicherheitsrisiko (Ist nur mit Cookies/Session umsetzbar)