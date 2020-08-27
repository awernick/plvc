import os
from stringcase import alphanumcase, snakecase


class Playlist(object):
    def __init__(self, playlist_obj):
        self.playlist_obj = playlist_obj
        self.tracks = []

    @property
    def id(self):
        return self.playlist_obj['id']

    def logfile(self, path=""):
        name = snakecase(alphanumcase(self.playlist_obj['name']))
        uid = self.playlist_obj['id']
        return os.path.join(path, f'{name}_{uid}.txt')

    def log_header(self):
        id = self.playlist_obj['id']
        name = self.playlist_obj['name']
        owner = self.playlist_obj['owner']['id']
        return f"{id} - {name} by {owner}"

    def log_tracks(self):
        for track in sorted(self.tracks, key=lambda t: t['name']):
            yield self._log_track(track)

    def _log_track(self, track):
        artists = ', '.join([artist['name']
                             for artist in track['album']['artists']])
        return f"{track['id']} - {track['name']} by {artists}"
