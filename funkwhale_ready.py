import hashlib
from config import plugins
from .funkwhale_startup import PLUGIN
from .client import PredatumScrobbler, Track


@plugins.register_hook(plugins.LISTENING_CREATED, PLUGIN)
def submit_listen(listening, conf, **kwargs):    
    username = conf.get("username")
    password = conf.get("password")
    if not username or not password:
        return
    client = PredatumScrobbler(username=username, password=password)
    track = get_track(listening.track)    
    client.submit(listening.creation_date.isoformat(), track)


def get_track(track):
    artist = track.artist.name
    title = track.title
    album = None
    additional_info = {
        "listening_from": "Funkwhale",
        "track_number": track.position,
        "disc_number": track.disc_number,
        "release_year": None
    }

    if track.album:
        if track.album.title:
            album = track.album.title
        if track.album.release_date:
            additional_info["release_year"] = track.album.release_date.year

    return Track(artist, title, album, additional_info)  
