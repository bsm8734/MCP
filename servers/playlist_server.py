########################################
# servers/playlist_server.py (플레이리스트 경향성 — 숫자 피처 or Spotify)
########################################
import os
from fastmcp import FastMCP
from schemas import PlaylistInput, PlaylistMoodResult
from utils.playlist import summarize_features, label_mood

app = FastMCP("playlist-mcp")


@app.tool()
def analyze_playlist(input: PlaylistInput) -> PlaylistMoodResult:
    tracks = input.tracks or []
    if input.spotify_url and not tracks:
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyClientCredentials
            sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=os.getenv("SPOTIFY_CLIENT_ID"), client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")))
            pl_id = input.spotify_url.split("playlist/")[-1].split("?")[0]
            items = sp.playlist_items(pl_id, additional_types=['track'])
            ids = [it['track']['id'] for it in items['items'] if it.get('track') and it['track'].get('id')]
            feats = sp.audio_features(ids)
            tracks = []
            for tid, f in zip(ids, feats):
                if not f:
                    continue
                tr = sp.track(tid)
                tracks.append({
                    "name": tr['name'],
                    "artist": ", ".join(a['name'] for a in tr['artists']),
                    "energy": f["energy"],
                    "valence": f["valence"],
                    "danceability": f["danceability"],
                    "tempo": f["tempo"],
                })
        except Exception as e:
            raise RuntimeError(f"Spotify 조회 실패: {e}")
    if not tracks:
        raise ValueError("트랙 피처가 없습니다.")
    stats = summarize_features(tracks)
    label = label_mood(stats)
    summary = f"에너지 {stats['energy']:.2f}, 발란스 {stats['valence']:.2f}, 댄서빌리티 {stats['danceability']:.2f}, 템포 {stats['tempo']:.0f}"
    return PlaylistMoodResult(label=label, summary=summary, stats=stats)


if __name__ == "__main__":
    app.run()