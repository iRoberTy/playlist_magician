# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

# Erweiterung des Standard-Users um Spotify-Daten
class SpotifyUserManager(BaseUserManager):
    def create_user(self, spotify_id, password=None, **extra_fields):
        if not spotify_id:
            raise ValueError('Spotify ID is required')
        user = self.model(spotify_id=spotify_id, **extra_fields)
        if password:
            user.set_password(password)  # ← Wichtig! Hasht das Passwort
        user.save(using=self._db)
        return user
    
    def create_superuser(self, spotify_id, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(spotify_id, password, **extra_fields)

class SpotifyUser(AbstractBaseUser, PermissionsMixin):
    spotify_id = models.CharField(max_length=255, unique=True, primary_key=True)
    access_token = models.TextField(blank=True, default='')  # Für Superuser optional
    refresh_token = models.TextField(blank=True, default='')
    country = models.CharField(max_length=10, blank=True, default='')
    token_expires_at = models.DateTimeField(null=True, blank=True)  # Für Superuser optional
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Für Admin-Login
    email = models.EmailField(blank=True, default='')  # Optional, aber hilfreich
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)  # ← Wichtig für Permissions!
    
    objects = SpotifyUserManager()
    
    USERNAME_FIELD = 'spotify_id'
    REQUIRED_FIELDS = []  # Leer lassen, da spotify_id schon USERNAME_FIELD ist
    
    def __str__(self):
        return self.spotify_id
    
# Speichert Einstellungen für die Playlist-Generierung [cite: 223, 224]
'''class PlaylistConfig(models.Model):
    PLAYLIST_TYPES = [
        ('JOGGING', 'Jogging Playlist'),
        ('RELEASE', 'Neuerscheinungen'),
    ]
    
    user = models.ForeignKey(SpotifyUser, on_delete=models.CASCADE)
    config_type = models.CharField(max_length=20, choices=PLAYLIST_TYPES)
    
    # --- WICHTIGE ERGÄNZUNG FÜR AUTOMATISIERUNG ---
    # Damit wir wissen, welche Playlist auf Spotify wir updaten müssen:
    spotify_playlist_id = models.CharField(max_length=255, null=True, blank=True)
    # Soll diese Config aktiv regelmäßig ausgeführt werden?
    is_active = models.BooleanField(default=True)
    # Wann wurde sie zuletzt aktualisiert?
    last_updated = models.DateTimeField(auto_now=True)
    # -----------------------------------------------

    # Für Jogging 
    target_bpm_min = models.IntegerField(default=120, null=True, blank=True)
    target_bpm_max = models.IntegerField(default=160, null=True, blank=True)
    target_energy = models.FloatField(default=0.7, null=True, blank=True) # 0.0 bis 1.0
    
    # Für Neuerscheinungen [cite: 223]
    artist_limit = models.IntegerField(default=5, null=True, blank=True) # Anzahl Songs pro Künstler
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.config_type} Config for {self.user.username}"'''