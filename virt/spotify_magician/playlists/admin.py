from django.contrib import admin

#Register your models here.
from django.contrib import admin
from .models import SpotifyProfile, PlaylistConfig

'''#Design für das Spotify Profil im Admin-Bereich
@admin.register(SpotifyProfile)
class SpotifyProfileAdmin(admin.ModelAdmin):
    # Diese Spalten werden in der Übersicht angezeigt
    list_display = ('user', 'spotify_id', 'token_expires_at')
    # Danach kann man suchen
    search_fields = ('userusername', 'spotify_id')

#Design für die Playlist Konfigurationen
@admin.register(PlaylistConfig)
class PlaylistConfigAdmin(admin.ModelAdmin):
    list_display = ('user', 'config_type', 'is_active', 'last_updated')
    list_filter = ('config_type', 'is_active') # Filter-Box an der Seite
    search_fields = ('userusername',)'''