from django.contrib import admin
from .models import SpotifyUser# , PlaylistConfig

#Design für das Spotify Profil im Admin-Bereich
@admin.register(SpotifyUser)
class SpotifyProfileAdmin(admin.ModelAdmin):
    # Diese Spalten werden in der Übersicht angezeigt
    list_display = ('spotify_id', 'access_token', 'refresh_token', 'country', 'token_expires_at', 'created_at', 'updated_at')
    # Danach kann man suchen
    search_fields = ('spotify_id',)

#Design für die Playlist Konfigurationen
'''@admin.register(PlaylistConfig)
class PlaylistConfigAdmin(admin.ModelAdmin):
    list_display = ('user', 'config_type', 'is_active', 'last_updated')
    list_filter = ('config_type', 'is_active') # Filter-Box an der Seite
    search_fields = ('user__spotify_id',)'''