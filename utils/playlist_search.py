import requests, re
from bs4 import BeautifulSoup
from typing import List, Dict

# 간단한 웹 스크래핑 기반 음악 분위기 추론기
# 실제 서비스에서는 API 사용 권장 (예: Last.fm, Spotify, MusicBrainz)

MOOD_KEYWORDS = {
    "잔잔한": ["calm","relax","ballad","soft"],
    "신나는": ["upbeat","happy","energetic","dance"],
    "격동적인": ["intense","rock","metal","hard"],
    "파티": ["club","edm","party","dancefloor"],
    "우울/차분": ["sad","melancholy","blues","low"],
    "밝고경쾌": ["bright","cheerful","pop","fun"],
}

DEFAULT_LABEL = "잔잔한"


def search_song_mood(title: str, artist: str = "") -> str:
    query = f"{title} {artist} song mood"
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if not r.ok:
            return DEFAULT_LABEL
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True).lower()
        for label, keywords in MOOD_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return label
    except Exception:
        return DEFAULT_LABEL
    return DEFAULT_LABEL


def analyze_textfile_tracks(path: str) -> List[Dict[str,str]]:
    tracks = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            if "-" in line:
                artist, title = [x.strip() for x in line.split("-",1)]
            else:
                artist, title = "", line.strip()
            mood = search_song_mood(title, artist)
            tracks.append({"artist":artist,"title":title,"mood":mood})
    return tracks