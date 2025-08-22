########################################
# utils/track_lookup.py (iTunes/MusicBrainz 조회 + 퍼지 매칭)
########################################
from typing import List, Tuple
import requests
from rapidfuzz import fuzz

ITUNES_SEARCH = "https://itunes.apple.com/search"
MB_RECORDING = "https://musicbrainz.org/ws/2/recording/"
HEADERS = {"User-Agent":"dayline-mcp/1.0 (contact: dev@example.com)"}


def parse_line(line: str) -> Tuple[str,str]:
    s = line.strip()
    if " - " in s:
        a, t = s.split(" - ", 1)
        return a.strip(), t.strip()
    return "", s


def itunes_genre(artist: str, title: str) -> Tuple[str,float]:
    q = f"{artist} {title}".strip()
    params = {"term": q, "media":"music", "limit": 5}
    r = requests.get(ITUNES_SEARCH, params=params, headers=HEADERS, timeout=10)
    if not r.ok:
        return "",0.0
    items = r.json().get("results",[])
    if not items:
        return "",0.0
    best = max(items, key=lambda it: fuzz.token_set_ratio(q, f"{it.get('artistName','')} {it.get('trackName','')}") )
    score = fuzz.token_set_ratio(q, f"{best.get('artistName','')} {best.get('trackName','')}") / 100.0
    return (best.get("primaryGenreName","") or ""), float(score)


def mb_genre(artist: str, title: str) -> Tuple[str,float]:
    if not artist and not title:
        return "",0.0
    query = []
    if artist:
        query.append(f"artist:{artist}")
    if title:
        query.append(f"recording:{title}")
    params = {"query":" AND ".join(query), "fmt":"json", "limit":5}
    r = requests.get(MB_RECORDING, params=params, headers=HEADERS, timeout=10)
    if not r.ok:
        return "",0.0
    recs = r.json().get("recordings",[])
    if not recs:
        return "",0.0
    best = max(recs, key=lambda it: fuzz.token_set_ratio(f"{artist} {title}".strip(), f"{it.get('artist-credit',[{}])[0].get('name','')} {it.get('title','')}") )
    score = fuzz.token_set_ratio(f"{artist} {title}".strip(), f"{best.get('artist-credit',[{}])[0].get('name','')} {best.get('title','')}") / 100.0
    return "", float(score)
