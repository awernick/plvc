import pdb
import os
import sys
import json
import spotipy
import pprint
from datetime import date
from dotenv import load_dotenv
from git import Repo
from github import Github, PullRequest, GithubException
from spotipy.oauth2 import SpotifyOAuth
from spotipy.oauth2 import SpotifyClientCredentials
from playlist import Playlist
from uuid import uuid4


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

today = date.today()
log_batch_id = today.strftime("%b-%d-%Y")
if log_batch_id not in origin.refs:
    repo.create_head(log_batch_id)
repo.heads[log_batch_id].checkout()

# Fetch list of playlists from Spotify
scope = 'playlist-read-collaborative playlist-read-private user-library-read'
auth_manager = SpotifyOAuth(client_id=os.environ['SPOTIFY_CLIENT_ID'], client_secret=os.environ['SPOTIFY_CLIENT_SECRET'],
                            redirect_uri=os.environ['SPOTIFY_REDIRECT_URI'], username=os.environ['SPOTIFY_USERNAME'], scope=scope)

spotify = spotipy.Spotify(auth_manager=auth_manager)
playlist_cursor = spotify.current_user_playlists()
playlists = []

while playlist_cursor:
    for i, playlist_item in enumerate(playlist_cursor['items']):
        playlists.append(Playlist(playlist_item))
    if playlist_cursor['next']:
        playlist_cursor = spotify.next(playlist_cursor)
    else:
        playlist_cursor = None

for playlist in playlists:
    logfile_dir = playlist.logfile(path=repo_dir)
    print(f"[Spotify] Processing {playlist.name} at {logfile_dir}")
    logfile = open(logfile_dir, 'w')
    logfile.write(playlist.log_header())
    logfile.write("\n\n")

    track_cursor = spotify.playlist_tracks(playlist.id)
    while track_cursor:
        try:
            for i, track_item in enumerate(track_cursor['items']):
                # pprint.pprint(track_item['track'])
                playlist.tracks.append(track_item['track'])
        except:
            e = sys.exc_info()[0]
            print(f"[Spotify] Could not log. Error: {e}")

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
    repo.index.add([logfile_dir])


if not repo.index.diff(repo.head.commit):
    print(f'[Git] No change in playlists. Exiting...')
    exit(0)

repo.index.commit(log_batch_id)
repo.git.push(origin, repo.heads[log_batch_id])

try:
    print(f"[Github] Opening PR and merging: {log_batch_id}")
    github = Github(os.environ['GITHUB_ACCESS_TOKEN'])
    guser = github.get_user()
    repo = github.get_repo(os.environ['GITHUB_PLAYLIST_REPO_ID'])

    open_prs = repo.get_pulls(state='open', base='master', head=log_batch_id)
    if open_prs.totalCount > 0:
        print(f'[Github] PR {log_batch_id} already exists. Merging...')
        pr = open_prs[0]
    else:
        pr = repo.create_pull(title=log_batch_id, body=log_batch_id,
                              base='master', head=log_batch_id)
    pr.merge()
except GithubException as e:
    print(f"[Github] Could not open PR. Error: {e}")
