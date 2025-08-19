########################################
# utils/playlist.py (공유)
########################################
from typing import Dict, Any, List
import statistics

MOOD_RULES = [
    ("파티", lambda e,v,d,t: e>0.7 and d>0.7 and t>120),
    ("신나는", lambda e,v,d,t: e>0.6 and v>0.6),
    ("격동적인", lambda e,v,d,t: e>0.75 and v<0.45),
    ("밝고경쾌", lambda e,v,d,t: v>0.7 and d>0.6),
    ("잔잔한", lambda e,v,d,t: e<0.4 and t<100),
    ("우울/차분", lambda e,v,d,t: v<0.35 and e<0.5),
]
DEFAULT_LABEL = "잔잔한"

# 텍스트 장르 기반 간이 매핑 규칙
GENRE_TO_MOOD = {
    "dance": "파티",
    "edm": "파티",
    "house": "파티",
    "electronic": "신나는",
    "k-pop": "밝고경쾌",
    "kpop": "밝고경쾌",
    "pop": "밝고경쾌",
    "indie": "밝고경쾌",
    "rock": "신나는",
    "metal": "격동적인",
    "punk": "격동적인",
    "hip hop": "신나는",
    "hip-hop": "신나는",
    "r&b": "밝고경쾌",
    "soul": "밝고경쾌",
    "jazz": "잔잔한",
    "lo-fi": "잔잔한",
    "lofi": "잔잔한",
    "ambient": "잔잔한",
    "acoustic": "잔잔한",
    "classical": "잔잔한",
    "ballad": "잔잔한",
    "blues": "우울/차분",
    "emo": "우울/차분",
}

def mood_from_genres(genres: List[str]) -> str:
    score = {"파티":0,"신나는":0,"격동적인":0,"밝고경쾌":0,"잔잔한":0,"우울/차분":0}
    for g in genres:
        g_low = g.lower()
        for key,lab in GENRE_TO_MOOD.items():
            if key in g_low:
                score[lab]+=1
    label = max(score, key=score.get)
    return label if score[label]>0 else DEFAULT_LABEL

def _avg(xs: List[float]) -> float:
    try:
        return float(statistics.fmean(xs))
    except Exception:
        return float(sum(xs)/max(1,len(xs)))

def summarize_features(tracks: List[Dict[str, Any]]) -> Dict[str, float]:
    e = _avg([t.get("energy",0.5) for t in tracks])
    v = _avg([t.get("valence",0.5) for t in tracks])
    d = _avg([t.get("danceability",0.5) for t in tracks])
    tempo = _avg([t.get("tempo",110) for t in tracks])
    return {"energy":e,"valence":v,"danceability":d,"tempo":tempo}

def label_mood(stats: Dict[str,float]) -> str:
    e,v,d,t = stats["energy"], stats["valence"], stats["danceability"], stats["tempo"]
    for name,rule in MOOD_RULES:
        if rule(e,v,d,t):
            return name
    return DEFAULT_LABEL