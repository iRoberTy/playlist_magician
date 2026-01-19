import random
from django.shortcuts import render, redirect
from django.conf import settings
from .sanitize import *
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.utils.http import url_has_allowed_host_and_scheme
from datetime import datetime, timedelta
from django.utils import timezone
from django.http import JsonResponse
import requests
import base64
import hashlib
import secrets
import urllib.parse
from .models import SpotifyUser

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token" # Refresh Access Token
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# Should be in Settings
SPOTIFY_CLIENT_ID = settings.SPOTIFY_CLIENT_ID
SPOTIFY_REDIRECT_URI = settings.SPOTIFY_REDIRECT_URI

def home(request):
    return render(request, "home.html")

def impressum(request):
    return render(request, "impressum.html")

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
def is_access_token_expired(user):
    return timezone.now() > user.token_expires_at # Returns True if expired

# Main Function for getting Access Token (after login)
def get_valid_access_token(request):
    user = request.user
    
    access_token = user.access_token
    refresh_token = user.refresh_token

    # If access token exists AND is still valid → use it
    if access_token and not is_access_token_expired(user):
        return access_token
    
    # Otherwise refresh
    try:
        token_data = refresh_access_token(refresh_token)
    except Exception as e:
        print(f"Refresh failed: {e}")
        return None

    expires_at = timezone.now() + timedelta(seconds=token_data["expires_in"])

    # --- Update DB ---
    SpotifyUser.objects.filter(spotify_id=user.id).update(
        access_token=token_data["access_token"],
        token_expires_at=expires_at
    )
    
    # Spotify may rotate refresh tokens --- DB UPDATE ---
    if "refresh_token" in token_data and token_data["refresh_token"] != request.user.refresh_token:
        request.user.refresh_token = token_data["refresh_token"]

    return token_data["access_token"]

# Main Login Function (redirect to Spotify Url for permissions)
def spotify_login(request):
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")

    request.session["code_verifier"] = code_verifier
    
    next_url = request.GET.get('next')
    if next_url:
        request.session['next_url'] = next_url  # In Session speichern
    
    # State für CSRF Schutz empfohlen (hier der Einfachheit halber optional, aber Best Practice)
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state

    scope = "user-read-private user-library-read playlist-read-private user-top-read playlist-modify-public playlist-modify-private"

    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": scope,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "state": state
    }

    url = f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return redirect(url)

# Get Data of User after permissions and Store Login Data
def spotify_callback(request):
    code = request.GET.get("code")
    code_verifier = request.session.get("code_verifier")
    
    if not code or not code_verifier or request.GET.get("state") != request.session.get("oauth_state"):
        return redirect("home")

    data = {
        "client_id": SPOTIFY_CLIENT_ID,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "code_verifier": code_verifier,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
    # Check if successful or hit rate Limit...
    if response.status_code != 200:
        return redirect("home")
    
    token_data = response.json()
    
    headers = {"Authorization": f"Bearer {token_data["access_token"]}"}
    user = requests.get(f"{SPOTIFY_API_BASE}/me", headers=headers)
    # Check if succesfully got user_id or hit rate Limit..
    if user.status_code != 200:
        return redirect("home")
    user = user.json()
    
    expires_in = timezone.now() + timedelta(seconds=token_data.get("expires_in", 3600))

    # --- DB SAVE ---
    user_db, created = SpotifyUser.objects.update_or_create(
        spotify_id=user["id"],
        defaults={
            'access_token': token_data["access_token"], 
            'refresh_token': token_data.get("refresh_token"),
            'country': user["country"],
            'token_expires_at': expires_in,
        }
    )
    if not created:
        redirect("home")
    
    # Log them in using Django session
    login(request, user_db)   # creates the sessionid cookie Django expects

    # get ?next= from the return URL
    next_url = request.session.pop('next_url', None)
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('home')  # fallback if no next param

@login_required
def playlist_conf(request): 
    access_token = get_valid_access_token(request)
    user_id = request.user.spotify_id
    
    if not access_token and not user_id:
        # Unknown Error
        redirect("home")
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # Get User playlists
    playlists = requests.get(f"{SPOTIFY_API_BASE}/me/playlists", headers=headers) # <--------------- Very Slow (500ms)
    
    # Check if succesfully got user_id or hit rate Limit..
    if playlists.status_code != 200:
        return redirect("home")

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

@login_required
def playlist_fav_songs(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request"})

    access_token = get_valid_access_token(request)
    user_id = request.user.spotify_id

    if not access_token or not user_id:
        # Unknown Error...
        return redirect("spotify_login")

    # Sanitize User Input
    form = playlist_fav_songs_form(request.POST)
    if not form.is_valid():
        return JsonResponse({"success": False, "error": "Invalid form data", "details": form.errors})
    fav_artist_count = form.cleaned_data["fav_artist_count"] # User Input
    song_count = form.cleaned_data["song_count"] # User Input

    # Backend Fetch Configuration
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "time_range": "medium_term", # Timerange of fav_artists/songs: long_term (1y) - medium_term (6m) - short_term (4w)
        "limit": fav_artist_count,
        "offset": 0
    }
    
    artists_resp = requests.get(f"{SPOTIFY_API_BASE}/me/top/artists", headers=headers, params=params) # ---------------- Get fav Artists --------------- (Users: "Get User's Top Items" - endpoint)
    
    # Check if succesfully got artists or hit rate Limit..
    if artists_resp.status_code != 200:
        print(f"/me/top/artists endpoint failed with status code: {albums_resp.status_code}")
        return JsonResponse({"success": False, "error": "Failed to fetch artists"})
    
    artists_list = artists_resp.json()
    
    # Get 50 Tracks
    PLAYLIST_MAX_TRACKS = song_count
    track_data = [] # Stores {uri, date}
    num_artists = len(artists_list["items"])
    if num_artists == 0:
         return JsonResponse({"success": False, "error": "No artists found"})

    tracks_per_artist = max(1, PLAYLIST_MAX_TRACKS // num_artists) # 50 Tracks evenly distributed between available artists (min 1 per)
    
    for artist in artists_list["items"]:
        params = {
            "include_groups": "album,single,appears_on", # album - single - appears_on - compilation
            "market": request.user.country,
            "limit": 10, 
            "offset": 0
        }
        albums_resp = requests.get(f"{SPOTIFY_API_BASE}/artists/{artist["id"]}/albums", headers=headers, params=params) # ---------- Get newest Single/Album of fav Artists ---------- (Artists: "Get Artist's Albums" - endpoint)
        
        # Check if succesfully got albums or hit rate Limit..
        if albums_resp.status_code != 200:
            print(f"/artists/(artistid)/albums endpoint failed with status code: {albums_resp.status_code}")
            return JsonResponse({"success": False, "error": "Failed to fetch albums"})
        
        albums_list = albums_resp.json()
        
        albums_sorted = sorted(
            albums_list["items"],
            key=lambda a: parse_release_date(a["release_date"]),
            reverse=True
        )

        # Collect tracks for this artist
        artist_tracks_found = 0
        for album in albums_sorted:
            if artist_tracks_found >= tracks_per_artist: break

            album_tracks_resp = requests.get(f"{SPOTIFY_API_BASE}/albums/{album['id']}/tracks",headers=headers) # ------------ Get Album Tracks --------- (Albums: "Get Album Tracks" - endpoint)

            if album_tracks_resp.status_code != 200:
                print(f"/albums/(albumid)/tracks endpoint failed with status code: {album_tracks_resp.status_code}")
                continue

            album_tracks = album_tracks_resp.json()["items"]

            for t in album_tracks:
                if artist_tracks_found >= tracks_per_artist:
                    break
                track_data.append({
                    "uri": t["uri"],
                    "date": album["release_date"]
                })
                artist_tracks_found += 1

    random.shuffle(track_data)
    
    final_uris = [t["uri"] for t in track_data]

    # Schauen wir in die Session, ob wir in DIESER Sitzung schon eine Playlist erstellt haben.
    playlist_id = request.session.get("current_session_playlist_id")
    
    # Check if Playlist exists
    if playlist_id:
        # Get Playlist Details to verify ownership
        playlist_resp = requests.get(f"{SPOTIFY_API_BASE}/playlists/{playlist_id}", headers=headers) # ---------------- Get Playlist Details --------------- (Playlists: "Get Playlist" - endpoint)
        
        if playlist_resp.status_code != 200:
            print(f"/playlists/(playlistid) endpoint failed with status code: {playlist_resp.status_code}")
            playlist_id = None  # Reset to create new
        
        else:
            playlist_info = playlist_resp.json()
            if playlist_info["owner"]["id"] != user_id:
                # Not the owner, cannot update
                playlist_id = None
            else:
                # Follow Playlist if not already following
                follow_pl = requests.get(f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/followers/contains", headers=headers)
                if follow_pl.status_code == 200:
                    is_following = follow_pl.json()[0]
                    if not is_following:
                        # Follow the playlist
                        follow_resp = requests.put(f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/followers", headers=headers)
                        if follow_resp.status_code != 200:
                            print(f"Failed to follow playlist with status code: {follow_resp.status_code}")
                else:
                    # Could not verify following status
                    playlist_id = None
                            
    # 4. Create Playlist if not found
    if not playlist_id: 
        # Create a new Playlist for User
        headers = { 
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json" 
        }
        params = {
            "name": "My Fav Artist Mix",
            "public": False, # needs scope "playlist-modify-private" or "playlist-modify-public"
            "collaborative": False, # needs scope "playlist-modify-private" or "playlist-modify-public"
            "description": "This Playlist includes your favourite Artists recent Tracks created by the Spotify Magician Website"
        }
        create_playlist_resp = requests.post(f"{SPOTIFY_API_BASE}/me/playlists", headers=headers, json=params) # ---------- Create new Playlist for User ---------- (Playlists: "Create Playlist" depreciated (so unknown source) - endpoint)
        
        if create_playlist_resp.status_code not in (201, 200):
            print(f"/users/(userid)/playlists endpoint failed with status code: {create_playlist_resp.status_code}")
            return JsonResponse({
                "success": False,
            })
        
        playlist_id = create_playlist_resp.json()["id"]
        request.session["current_session_playlist_id"] = playlist_id # Save for this session
        
    replace_url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    # PUT ersetzt den ganzen Inhalt -> Perfekt für Update
    add_resp = requests.put(replace_url, headers=headers, json={"uris": final_uris}) 
    
    if add_resp.status_code not in (200, 201):
        return JsonResponse({"success": False,})

    return JsonResponse({
        "success": True,
        "playlist_url": f"https://open.spotify.com/playlist/{playlist_id}"
    })

@login_required  
def jogging_playlist(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request"})

    access_token = get_valid_access_token(request)
    user_id = request.user.spotify_id

    if not access_token or not user_id:
        # Unknown Error
        return redirect("spotify_login")

    # -----------------------------
    # Eingaben aus Formular
    # -----------------------------
    
    # Sanitize User Input
    form = Jogging_Playlist_Form(request.POST)
    if not form.is_valid():
        return JsonResponse({"success": False, "error": form.errors["bpm_min"] if form.errors else "Eingabedaten falsch!"})
    bpm_min = form.cleaned_data["bpm_min"]
    bpm_max = form.cleaned_data["bpm_max"]
    energy_level = form.cleaned_data["energy_level"] / 100  # Spotify: 0.0–1.0
    max_playtime = form.cleaned_data["max_playtime"] * 60 * 1000  # Minuten → ms
    base_playlists = request.POST.getlist("source_playlists")
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # -----------------------------
    # 1. Tracks aus allen Playlists sammeln
    # -----------------------------
    tracks = []
    for playlist_id in base_playlists:
        url = f"{SPOTIFY_API_BASE}/playlists/{str(playlist_id)}/tracks"
        params = {"limit": 100}

        while url:
            r = requests.get(url, headers=headers, params=params).json()
            for item in r["items"]:
                track = item.get("track")
                if track and track.get("id") and track not in tracks:
                    tracks.append(track)
            url = r.get("next")

    if not tracks:
        return JsonResponse({"success": False, "error": "Keine Tracks gefunden"})
    
    # Randomize Track Order
    random.shuffle(tracks)

    # -----------------------------
    # 2. Audio-Features abrufen
    # -----------------------------
    track_ids = [t["id"] for t in tracks]
    features = {}
    track_count = 0
    for i in range(0, len(track_ids), 30):
        batch = track_ids[i:i+30]  # list of Spotify track IDs
        ids_param = ",".join(batch)
        
        headers = {"Accept": "application/json"}
        payload = {}
        r = requests.get(
            f"https://api.reccobeats.com/v1/audio-features?ids={ids_param}",
            headers=headers, data=payload
        )

        if r.status_code != 200:
            print(f"/audio-features endpoint failed with status code: {r.status_code}")
            return JsonResponse({"success": False})
        r = r.json()

        for f in r["content"]:
            if f:
                features[tracks[track_count]["id"]] = f
            track_count += 1

    # -----------------------------
    # 3. Filtern nach BPM & Energie
    # -----------------------------
    filtered = []

    for track in tracks:
        f = features.get(track["id"])
        if not f:   # This hits a lot (No Audio features found for track)
            print(f"No features for track {track['id']}")
            continue

        if bpm_min <= f["tempo"] <= bpm_max and f["energy"] >= energy_level:
            filtered.append({
                "id": track["id"],
                "name": track["name"],
                "tempo": f["tempo"],
                "duration": track["duration_ms"]
            })
        else:
            print(f"Track {track['id']} filtered out: tempo {f['tempo']}, energy {f['energy']}")

    if not filtered:
        return JsonResponse({"success": False, "error": "Keine passenden Songs gefunden"})

    # -----------------------------
    # 4. Sortieren (aufsteigend BPM)
    # -----------------------------
    filtered.sort(key=lambda x: x["tempo"])

    # -----------------------------
    # 5. Sliding window to maximize BPM span within duration
    # -----------------------------
    best_window = None
    best_span = -1  # difference between min and max BPM in window

    left = 0
    current_duration = 0

    for right in range(len(filtered)):
        current_duration += filtered[right]["duration"]

        # shrink window until duration fits
        while current_duration > max_playtime and left <= right:
            current_duration -= filtered[left]["duration"]
            left += 1

        # evaluate window
        if left <= right:
            bpm_span = filtered[right]["tempo"] - filtered[left]["tempo"]
            if bpm_span > best_span:
                best_span = bpm_span
                best_window = (left, right)

    # -----------------------------
    # 6. Build final tracks list from best window
    # -----------------------------
    ids = []
    final_tracks = []
    if best_window:
        start, end = best_window
        for t in filtered[start:end+1]:
            final_tracks.append(f"spotify:track:{t['id']}")
            ids.append({"id": t["id"], "name": t["name"], "tempo": t["tempo"]})
            
    for id in ids:
        print(id)   
        
    final_tracks = list(reversed(final_tracks)) # Weil Spotify in Spotify der erste Song ganz unten ist

    # -----------------------------
    # 7. Playlist erstellen
    # -----------------------------
    headers = { 
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json" 
    }
    params = {
        "name": "Jogging Playlist",
        "public": False, # needs scope "playlist-modify-private" or "playlist-modify-public"
        "collaborative": False, # needs scope "playlist-modify-private" or "playlist-modify-public"
        "description": "This is your Jogging Playlist created by the Spotify Magician Website"
    }
    create_playlist_resp = requests.post(f"{SPOTIFY_API_BASE}/me/playlists", headers=headers, json=params) # ---------- Create new Playlist for User ---------- (Playlists: "Create Playlist" depreciated (so unknown source) - endpoint)
    
    if create_playlist_resp.status_code not in (201, 200):
        print(f"/users/(userid)/playlists endpoint failed with status code: {create_playlist_resp.status_code}")
        return JsonResponse({"success": False,})
    
    playlist_id = create_playlist_resp.json()["id"]

    # -----------------------------
    # 8. Tracks hinzufügen
    # -----------------------------
    replace_url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    # PUT ersetzt den ganzen Inhalt -> Perfekt für Update
    headers = {"Authorization": f"Bearer {access_token}"}
    add_resp = requests.post(replace_url, headers=headers, json={"uris": final_tracks}) 
    if add_resp.status_code not in (200, 201):
        return JsonResponse({"success": False, "error": "Songs konnten nicht zur Playlist hinzugefügt werden."})

    # -----------------------------
    # 9. Erfolg zurückgeben
    # -----------------------------
    return JsonResponse({
        "success": True,
        "playlist_url": f"https://open.spotify.com/playlist/{playlist_id}"
    })

def logout_view(request):
    # DB logout -----------
    logout(request)
    return redirect("home")

