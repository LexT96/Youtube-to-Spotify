import googleapiclient.discovery
import youtube_dl
import json
import base64
import requests
from requests_oauthlib import OAuth2Session
# Get your own YOUTUBE_API from https://console.developers.google.com/
# Get your own SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET from https://developer.spotify.com/dashboard/applications
from secrets import YOUTUBE_API, YOUTUBE_ID, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_PLAYLIST_ID


def get_youtube_playlist_json():
    youtube = googleapiclient.discovery.build("youtube", "v3", 
                                              developerKey = YOUTUBE_API)
    request = youtube.playlistItems().list(
        part="snippet",
        playlistId= YOUTUBE_ID,
        maxResults = "50"
    )
    response = request.execute()
    return response

def get_video_ids(playlist_json):
    video_ids = []
    for i in range(len(playlist_json["items"])):
        item_dict = playlist_json["items"][i]
        video_id = item_dict["snippet"]["resourceId"]["videoId"]
        video_ids.append(video_id)
    return video_ids

def convert_ids_to_youtube_links(video_ids):
    base_link = "https://www.youtube.com/watch?v="
    for i in range(len(video_ids)):
        video_ids[i] = base_link + video_ids[i]
    return video_ids

def get_artist_and_track(youtube_link):
    info_dict = youtube_dl.YoutubeDL().extract_info(youtube_link,
                                                    download = False)
    try:
        artist = info_dict["artist"]
        track = info_dict["track"]
    except KeyError:
        return "",""
    return artist,track

def download_videos(download_links):
   options = {
  'format': 'bestaudio/best',
  'extractaudio' : True,
  'audioformat' : "mp3",  
  'outtmpl': '%USERPROFILE%\spotify\%(title)s.mp3',    
  'noplaylist' : True
   }   
   youtube_dl.YoutubeDL(options).download(download_links)
   
def get_new_spotify_authorization():
    scope = "playlist-modify-private"
    redirect_uri = "https://localhost/callback"
    oauth = OAuth2Session(SPOTIFY_CLIENT_ID, redirect_uri=redirect_uri,
                          scope=scope)
    authorization_url, state = oauth.authorization_url(
        'https://accounts.spotify.com/authorize',
        access_type="offline", prompt="select_account")
    print(f"Please go to {authorization_url} and authorize access.")
    authorization_response = input('Enter the full callback URL: ')
    return oauth,authorization_response

def fetch_new_spotify_access_token(oauth,authorization_response):
    token = oauth.fetch_token(
    'https://accounts.spotify.com/api/token',
    authorization_response=authorization_response,
    client_secret= SPOTIFY_CLIENT_SECRET)
    with open('creds.json', 'w') as f:
        json.dump(token,f)    

def get_current_spotify_access_token():
    try:
        f = open("creds.json")
    except FileNotFoundError:
        oauth,authorization_response = get_new_spotify_authorization()
        fetch_new_spotify_access_token(oauth,authorization_response)
    with open('creds.json', 'r+') as f:
            token = json.load(f)
            return token["access_token"]         
   
def refresh_spotify_access_token():
    base64_encoded_clientid_clientsecret = base64.b64encode(
        str.encode(f'{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}'))  
    base64_encoded_clientid_clientsecret = base64_encoded_clientid_clientsecret.decode('ascii')  
    headers = {"Authorization": f"Basic {base64_encoded_clientid_clientsecret}"}
    with open('creds.json', 'r') as f:
        token = json.load(f)
    data = {"grant_type": "refresh_token", "refresh_token": token["refresh_token"]}
    response = requests.post("https://accounts.spotify.com/api/token", data,
                             headers = headers)
    access_token = response.json()["access_token"]
    new_token = {"refresh_token": token["refresh_token"], "access_token": 
                 access_token}
    with open('creds.json', 'w+') as f:
        json.dump(new_token,f)  

def get_spotify_uri(access_token,artist,track):
    params = {"q": f"track: {track} artist: {artist}", "type": "track", "limit": "1"}
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get("https://api.spotify.com/v1/search", params = params,
                            headers = headers)
    if response.status_code == 401:
        refresh_spotify_access_token()
    if json.loads(response.text)["tracks"]["total"] > 0:
        spotify_json = response.json()
        spotify_uri = spotify_json["tracks"]["items"][0]["uri"]
        return (spotify_uri)

def add_to_spotify_pl(access_token,spotify_uris):
    params = {"uris": spotify_uris}
    headers = {"Authorization": f"Bearer {access_token}",
               'Content-Type': 'application/json'}
    requests.post(f"https://api.spotify.com/v1/playlists/{SPOTIFY_PLAYLIST_ID}/tracks", 
                  data = json.dumps(params), headers = headers)
    
def remove_duplicates (access_token,spotify_uris):
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"https://api.spotify.com/v1/playlists/{SPOTIFY_PLAYLIST_ID}/tracks",
                            headers = headers)
    playlist_items_json = response.json()
    for i in range(len(playlist_items_json["items"])):
        track_uri = playlist_items_json["items"][i]["track"]["uri"]
        if track_uri in spotify_uris:
            spotify_uris.remove(track_uri)
   
def add_to_spotify_or_download(youtube_links):
    download_links = []
    spotify_uris = []
    access_token = get_current_spotify_access_token()
    for link in youtube_links:
        artist, track = get_artist_and_track(link)
        if artist == "":
            download_links.append(link)
            continue;       
        spotify_uris.append(get_spotify_uri(access_token,artist,track))
    download_videos(download_links)
    remove_duplicates(access_token, spotify_uris)
    add_to_spotify_pl(access_token, spotify_uris)
    
def main():
    playlist_json = get_youtube_playlist_json()
    video_ids = get_video_ids(playlist_json)
    video_links = convert_ids_to_youtube_links(video_ids)
    add_to_spotify_or_download(video_links)
    
    
if __name__ == '__main__':
    main()

