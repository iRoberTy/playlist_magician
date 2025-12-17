from django.db import models

# Create your models here.
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