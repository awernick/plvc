import pdb
import os
import json
import spotipy
import pprint
from dotenv import load_dotenv
from git import Repo
from github import Github
from spotipy.oauth2 import SpotifyOAuth
from spotipy.oauth2 import SpotifyClientCredentials
from playlist import Playlist


load_dotenv()
# Setup local repo from CWD
repo_dir = os.environ['PLAYLIST_REPO_DIR']
repo = Repo.init(os.environ['PLAYLIST_REPO_DIR'])

# Assert we have access to origin
if 'origin' not in repo.remotes:
    origin = repo.create_remote(
        'origin', os.environ['PLAYLIST_REPO_REMOTE_URL'])
else:
    origin = repo.remotes['origin']

origin.fetch()

# Set master to track origin/master and fetch latest
if 'master' not in origin.refs:
    init_file = os.path.join(repo_dir, '.init')
    open(init_file, 'w').close()
    repo.index.add([init_file])
    repo.index.commit('init')
    repo.create_head('master')
    repo.heads.master.checkout()
    repo.git.push('--set-upstream', origin, repo.heads.master)
elif 'master' not in repo.heads:
    repo.create_head('master', origin.refs.master)
    repo.heads.master.set_tracking_branch(origin.refs.master)
    repo.heads.master.checkout()
else:
    repo.heads.master.checkout()

origin.pull()


# Fetch list of playlists from Spotify
scope = 'playlist-read-collaborative playlist-read-private'
auth_manager = SpotifyOAuth(client_id=os.environ['SPOTIFY_CLIENT_ID'],
                            client_secret=os.environ['SPOTIFY_CLIENT_SECRET'],
                            redirect_uri=os.environ['SPOTIFY_REDIRECT_URI'],
                            username=os.environ['SPOTIFY_USERNAME'],
                            scope=scope)

spotify = spotipy.Spotify(auth_manager=auth_manager)
playlist_cursor = spotify.current_user_playlists()
playlists = []

while playlist_cursor:
    for i, playlist_item in enumerate(playlist_cursor['items']):
        playlists.append(Playlist(playlist_item))
        print(f'playlist name: {playlists[-1].logfile(path=repo_dir)}')
    if playlist_cursor['next']:
        playlist_cursor = spotify.next(playlist_cursor)
    else:
        playlist_cursor = None

for playlist in playlists:
    logfile = open(playlist.logfile(path=repo_dir), 'w')
    logfile.write(playlist.log_header())
    logfile.write("\n\n")

    track_cursor = spotify.playlist_tracks(playlist.id)
    while track_cursor:
        for i, track_item in enumerate(track_cursor['items']):
            # pprint.pprint(track_item['track'])
            playlist.tracks.append(track_item['track'])

        if track_cursor['next']:
            track_cursor = spotify.next(track_cursor)
        else:
            track_cursor = None

    for logline in playlist.log_tracks():
        logfile.write(logline)
        # print(f'{logline}')
        logfile.write("\n")
    # print()

    logfile.close()

# github = Github(os.environ['GITHUB_ACCESS_TOKEN'])
# guser = github.get_user()
# repo = guser.get_repo(os.environ['GITHUB_PLAYLIST_REPO_ID'])
