from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.utils.http import url_has_allowed_host_and_scheme
from datetime import datetime, timedelta
from django.utils import timezone
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.contrib.auth.models import User
from .models import SpotifyProfile, PlaylistConfig
import time
import requests
import base64
import hashlib
import secrets
import urllib.parse

# --- KONFIGURATION ---
# Credentials aus settings.py laden (Sicherheit!)
SPOTIFY_CLIENT_ID = settings.SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET = settings.SPOTIFY_CLIENT_SECRET
SPOTIFY_REDIRECT_URI = settings.SPOTIFY_REDIRECT_URI

# ECHTE Spotify Endpunkte (Wichtig: HTTPS)
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

SESSION_ENGINE = "django.contrib.sessions.backends.db"

def home(request):
    return render(request, "home.html")

# --- HELPER FUNCTIONS ---

def refresh_access_token(refresh_token):
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET, 
    }
    headers = { "Content-Type": "application/x-www-form-urlencoded" }

    response = requests.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
    response.raise_for_status()
    return response.json()

def generate_code_verifier():
    return secrets.token_urlsafe(64)

def generate_code_challenge(code_verifier):
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")

def parse_release_date(date_str):
    # Spotify returns YYYY or YYYY-MM or YYYY-MM-DD
    formats = ["%Y-%m-%d", "%Y-%m", "%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

# --- CORE LOGIC ---

def get_valid_access_token(request):
    """
    Holt den Token aus der Datenbank (SpotifyProfile).
    Wenn er abgelaufen ist, wird er automatisch erneuert.
    """
    # Wenn User nicht eingeloggt ist, abbrechen
    if not request.user.is_authenticated:
        return None

    try:
        profile = request.user.spotifyprofile
    except SpotifyProfile.DoesNotExist:
        return None

    # Prüfen ob Token noch gültig ist (mit 60s Puffer)
    if profile.token_expires_at > timezone.now() + timedelta(seconds=60):
        return profile.access_token

    # --- Token ist abgelaufen: Refresh durchführen ---
    try:
        token_data = refresh_access_token(profile.refresh_token)
    except:
        return None # Refresh fehlgeschlagen (z.B. Revoked)

    # Datenbank Update
    profile.access_token = token_data["access_token"]
    expires_in = token_data["expires_in"]
    profile.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
    
    # Manchmal schickt Spotify bei Refresh keinen neuen Refresh-Token mit
    if "refresh_token" in token_data:
        profile.refresh_token = token_data["refresh_token"]
    
    profile.save()

    return profile.access_token


def spotify_login(request):
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Code Verifier in Session speichern für den Callback
    request.session["code_verifier"] = code_verifier

    # Scopes definieren
    scope = "user-read-private playlist-read-private user-top-read playlist-modify-public playlist-modify-private user-read-email"

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
        "client_secret": SPOTIFY_CLIENT_SECRET, 
    }
    headers = { "Content-Type": "application/x-www-form-urlencoded" }

    response = requests.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
    
    if response.status_code != 200:
        return redirect("home")
    
    token_data = response.json()
    
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data["expires_in"]
    
    # User Info von Spotify holen
    headers = { "Authorization": f"Bearer {access_token}" }
    user_resp = requests.get(f"{SPOTIFY_API_BASE}/me", headers=headers)
    
    if user_resp.status_code != 200:
        return redirect("home")
    
    spotify_user_data = user_resp.json()
    spotify_id = spotify_user_data["id"]
    email = spotify_user_data.get("email", "")

    # --- DATENBANK LOGIK ---
    
    # 1. Django User holen oder erstellen
    user, created = User.objects.get_or_create(username=spotify_id)
    if created:
        user.email = email
        user.save()

    # 2. SpotifyProfile erstellen oder updaten
    expires_at = timezone.now() + timedelta(seconds=expires_in)
    
    profile, _ = SpotifyProfile.objects.get_or_create(user=user)
    profile.spotify_id = spotify_id
    profile.access_token = access_token
    
    if refresh_token:
        profile.refresh_token = refresh_token
        
    profile.token_expires_at = expires_at
    profile.save()

    # 3. User in Django Session einloggen
    login(request, user)
    
    # 4. Market (Ländercode) in Session speichern für Songsuche später
    request.session["market"] = spotify_user_data.get("country", "DE") 
    
    # --- ENDE DATENBANK LOGIK ---

    next_url = request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('home')


@login_required(login_url='home')
def playlist_conf(request):
    start = time.time()
    
    access_token = get_valid_access_token(request)
    if not access_token:
        return redirect('spotify_login')

    headers = { "Authorization": f"Bearer {access_token}" }
    
    # Playlists holen
    playlists_resp = requests.get(f"{SPOTIFY_API_BASE}/me/playlists", headers=headers)
    
    if playlists_resp.status_code != 200:
        return redirect("home")
    
    end = time.time()
    # Debug Print (kannst du entfernen)
    print(f"Time to fetch playlists: {end-start}")
    
    return render(request, "playlist_conf.html", {
        "user": request.user, 
        "playlists": playlists_resp.json().get("items", []),
    })


@login_required(login_url='home')
def playlist_fav_songs(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Only POST allowed"})

    access_token = get_valid_access_token(request)
    if not access_token:
        return JsonResponse({"success": False, "error": "No Token"})

    # Input validieren
    try:
        fav_artist_count = int(request.POST.get("fav_artist_count", 5))
    except ValueError:
        fav_artist_count = 5

    print(f"Generating playlist for top {fav_artist_count} artists")

    headers = { "Authorization": f"Bearer {access_token}" }
    
    # 1. Top Artists holen
    params = {
        "time_range": "medium_term",
        "limit": fav_artist_count,
        "offset": 0
    }
    artists_resp = requests.get(f"{SPOTIFY_API_BASE}/me/top/artists", headers=headers, params=params)
    
    if artists_resp.status_code != 200:
        print(f"/me/top/artists endpoint failed with status code: {artists_resp.status_code}")
        return JsonResponse({"success": False, "error": "Failed to fetch artists"})
    
    artists_list = artists_resp.json().get("items", [])
    
    if len(artists_list) != fav_artist_count:
        print("Warning: Artist count mismatch")
        # Wir machen trotzdem weiter, auch wenn es weniger sind

    if not artists_list:
        return JsonResponse({"success": False, "error": "No top artists found"})

    # 2. Tracks sammeln
    PLAYLIST_MAX_TRACKS = 50
    track_uris = []
    
    # Berechnung wie viele Tracks pro Artist
    tracks_per_artist = max(1, PLAYLIST_MAX_TRACKS // len(artists_list))
    print(f"Tracks per artist: {tracks_per_artist}")

    for artist in artists_list:
        # Neueste Alben/Singles holen
        album_params = {
            "include_groups": "album,single",
            "limit": 10, 
            "market": request.session.get("market", "DE"), # Fallback auf DE
            "offset": 0
        }
        albums_resp = requests.get(f"{SPOTIFY_API_BASE}/artists/{artist['id']}/albums", headers=headers, params=album_params)
        
        if albums_resp.status_code != 200:
            print(f"Failed to fetch albums for artist {artist['id']}")
            continue
            
        albums_list_data = albums_resp.json().get("items", [])
        
        # Sortieren nach Datum (Neueste zuerst)
        albums_sorted = sorted(
            albums_list_data,
            key=lambda a: parse_release_date(a["release_date"]) or datetime.min,
            reverse=True
        )

        artist_track_ids = []

        for album in albums_sorted:
            if len(artist_track_ids) >= tracks_per_artist:
                break
            
            # Tracks vom Album holen
            tracks_resp = requests.get(f"{SPOTIFY_API_BASE}/albums/{album['id']}/tracks", headers=headers, params={"limit": 5})
            if tracks_resp.status_code == 200:
                tracks = tracks_resp.json().get("items", [])
                for t in tracks:
                    if len(artist_track_ids) >= tracks_per_artist:
                        break
                    artist_track_ids.append(t["uri"])
        
        track_uris.extend(artist_track_ids)

    # Auf 50 begrenzen
    track_uris = track_uris[:PLAYLIST_MAX_TRACKS]

    if not track_uris:
         return JsonResponse({"success": False, "error": "No tracks found"})

    # 3. Playlist erstellen
    user_spotify_id = request.user.spotifyprofile.spotify_id 
    
    create_params = {
        "name": "Magician: Fav Artists Release",
        "public": True, # Public erlaubt, solange Scope passt
        "description": "Erstellt vom Playlist Magician mit deinen Top Künstlern"
    }
    create_resp = requests.post(f"{SPOTIFY_API_BASE}/users/{user_spotify_id}/playlists", headers=headers, json=create_params)
    
    if create_resp.status_code not in (200, 201):
        print(f"Create playlist failed: {create_resp.status_code}")
        return JsonResponse({"success": False, "error": "Could not create playlist"})
    
    playlist_id = create_resp.json()["id"]

    # 4. Tracks hinzufügen
    # Spotify erlaubt maximal 100 URIs pro Request, wir haben max 50, also alles in einem Rutsch
    add_tracks_resp = requests.post(f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks", headers=headers, json={"uris": track_uris})

    if add_tracks_resp.status_code not in (200, 201):
        print(f"Add tracks failed: {add_tracks_resp.status_code}")
        return JsonResponse({"success": False, "error": "Could not add tracks"})

    # --- DATENBANK: KONFIGURATION SPEICHERN ---
    PlaylistConfig.objects.create(
        user=request.user,
        config_type='RELEASE',
        spotify_playlist_id=playlist_id,
        artist_limit=fav_artist_count,
        is_active=True
    )

    print("Successfully created Playlist")
    return JsonResponse({
        "success": True,
        "playlist_url": f"https://open.spotify.com/playlist/{playlist_id}"
    })

def logout_view(request):
    logout(request)
    return redirect("home")