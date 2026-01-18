from django import forms

# Sanitize forms user inputs ----------------------------

class playlist_fav_songs_form(forms.Form):
    fav_artist_count = forms.IntegerField(min_value=1, max_value=50)
    song_count = forms.IntegerField(min_value=10, max_value=100)
    
class Jogging_Playlist_Form(forms.Form):
    bpm_min = forms.IntegerField(min_value=0, max_value=300)
    bpm_max = forms.IntegerField(min_value=0, max_value=300)
    energy_level = forms.FloatField(min_value=0, max_value=100)
    max_playtime = forms.IntegerField(min_value=10, max_value=200)  # minutes

    def clean(self):
        cleaned = super().clean()

        bpm_min = cleaned.get("bpm_min")
        bpm_max = cleaned.get("bpm_max")

        # Only validate if both fields are present
        if bpm_min is not None and bpm_max is not None:
            if bpm_min >= bpm_max:
                self.add_error(
                    "bpm_min",
                    "Minimum BPM muss kleiner sein als maximum BPM."
                )

        return cleaned
