import os
import logging
from stringcase import alphanumcase, snakecase
from spotipy.exceptions import SpotifyException


def paginated(func, next_page):
    try:
        page = func()
        while page:
            yield page
            page = next_page(page) if page['next'] else None

    except SpotifyException as e:
        logger = logging.getLogger(__name__)
        logger.error(
            f"[Spotify] Could not fetch next page")
        logger.error(e)
        raise


class Playlist(object):
    def __init__(self, playlist_obj):
        self.playlist_obj = playlist_obj
        self.tracks = []

    @property
    def id(self):
        return self.playlist_obj['id']

    @property
    def name(self):
        return self.playlist_obj['name']

    @property
    def owner(self):
        return self.playlist_obj['owner']['id']

    def logfile(self, path=""):
        name = snakecase(alphanumcase(self.name))
        uid = self.id
        return os.path.join(path, f'{name}_{uid}.txt')

    def log_header(self):
        id = self.id
        name = self.name
        owner = self.owner
        return f"{id} - {name} by {owner}"

    def log_tracks(self):
        for track in sorted(self.tracks, key=lambda t: t['name']):
            yield self._log_track(track)

    def _log_track(self, track):
        artists = ', '.join([artist['name']
                             for artist in track['album']['artists']])
        return f"{track['id']} - {track['name']} by {artists}"
