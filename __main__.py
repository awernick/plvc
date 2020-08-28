import os
import sys
import json
import spotipy
import logging
from datetime import date
from dotenv import load_dotenv
from git import Repo
from github import Github, GithubException
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from util import paginated, Playlist

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Load from .env
load_dotenv()

# Setup local repo from CWD
repo_dir = os.environ['PLAYLIST_REPO_DIR']
repo = Repo.init(repo_dir)

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

# Authenticate with Spotify
logger.info("[Spotify] Authenticating via OAuth")

if not os.path.exists('token-info.json'):
    try:
        scope = 'playlist-read-collaborative playlist-read-private user-library-read'
        auth_manager = SpotifyOAuth(client_id=os.environ['SPOTIFY_CLIENT_ID'],
                                    client_secret=os.environ['SPOTIFY_CLIENT_SECRET'],
                                    redirect_uri=os.environ['SPOTIFY_REDIRECT_URI'],
                                    username=os.environ['SPOTIFY_USERNAME'],
                                    scope=scope)
        token_info = auth_manager.get_access_token()

        with open('token-info.json', 'w') as f:
            json.dump(token_info, f)

    except SpotifyException as e:
        logger.error("[Spotify] Could not get access token.")
        logger.error(e)
        exit(1)

try:
    with open('token-info.json', 'r') as f:
        token_info = json.load(f)
        spotify = spotipy.Spotify(token_info['access_token'])
        spotify_user = spotify.current_user()

except SpotifyException as e:
    logger.error("[Spotify] Could not get retrive current user.")
    logger.error(e)
    exit(1)


# Fetch current user's playlists
playlists = []
for playlist_page in paginated(lambda: spotify.current_user_playlists(), next_page=spotify.next):
    playlists += [Playlist(playlist_item)
                  for playlist_item in playlist_page['items']]

# Fetch tracks for playlists
for playlist in playlists:
    logger.info(f"[Spotify] Fetching {playlist.name} by {playlist.owner}")
    for track_page in paginated(lambda: spotify.playlist_tracks(playlist.id), next_page=spotify.next):
        for track_item in track_page['items']:
            track = track_item['track']
            playlist.tracks.append(track)
            logger.debug(f"\tAdding:  {track['id']} - {track['name']}")

# Fetch tracks saved in "Liked Songs" playlist
personal_playlist = Playlist(
    {'id': spotify_user['id'], 'name': 'Liked Songs', 'owner': spotify_user})
logger.info(f"[Spotify] Downloading {personal_playlist.name}")

for track_page in paginated(lambda: spotify.current_user_saved_tracks(), next_page=spotify.next):
    for track_item in track_page['items']:
        personal_playlist.tracks.append(track_item['track'])

playlists.append(personal_playlist)

# Log playlist tracks and diff changes
for playlist in playlists:
    logfile_dir = playlist.logfile(path=repo_dir)
    logger.info(f"[Spotify] Diffing {playlist.name} at {logfile_dir}")

    with open(logfile_dir, 'w') as logfile:
        logger.debug(playlist.log_header()+"\n")
        logfile.write(playlist.log_header())
        logfile.write("\n\n")

        for logline in playlist.log_tracks():
            logger.debug(logline)
            logfile.write(logline)
            logfile.write("\n")

        logger.debug("")

    repo.index.add([logfile_dir])

if not repo.index.diff(repo.head.commit):
    logger.warning('[Git] No change in playlists. Exiting...')
    exit(0)

repo.index.commit(log_batch_id)
repo.git.push(origin, repo.heads[log_batch_id])

# Open a PR against Github
try:
    logger.info(f"[Github] Opening PR and merging: {log_batch_id}")
    github = Github(os.environ['GITHUB_ACCESS_TOKEN'])
    guser = github.get_user()
    repo = github.get_repo(os.environ['GITHUB_PLAYLIST_REPO_ID'])

    open_prs = repo.get_pulls(
        state='open', base='master', head=log_batch_id)
    if open_prs.totalCount > 0:
        logger.warning(
            f'[Github] PR {log_batch_id} already exists. Merging...')
        pr = open_prs[0]
    else:
        pr = repo.create_pull(title=log_batch_id, body=log_batch_id,
                              base='master', head=log_batch_id)
    pr.merge()
except GithubException as e:
    logger.error(f"[Github] Could not open PR.")
    logger.error(e)
