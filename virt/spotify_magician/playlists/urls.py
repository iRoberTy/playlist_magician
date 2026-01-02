from django.urls import path
from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.spotify_login, name="spotify_login"),  # Login Spotify
    path("callback/", views.spotify_callback, name="spotify_callback"), # Login
    path("playlist_conf/", views.playlist_conf, name="playlist_conf"),  # User Playlist Configuration
    path("playlist_fav_songs/", views.playlist_fav_songs, name="playlist_fav_songs"), # Creates Fav Artist Playlist
    path("logout/", views.logout_view, name="logout"), # Logout
]
