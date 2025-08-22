########################################
# servers/trackinfo_server.py (텍스트 플레이리스트 전용)
########################################
from fastmcp import FastMCP
from schemas import TextPlaylistInput, TextPlaylistMoodResult, TrackInfo
from utils.track_lookup import parse_line, itunes_genre, mb_genre
from utils.playlist import mood_from_genres

app = FastMCP("trackinfo-mcp")


@app.tool()
def resolve_text_playlist(input: TextPlaylistInput) -> TextPlaylistMoodResult:
    if not input.path and not input.lines:
        raise ValueError("path 또는 lines 중 하나가 필요합니다.")
    lines = input.lines or []
    if input.path:
        with open(input.path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
    resolved = []
    genres = []
    for ln in lines:
        artist, title = parse_line(ln)
        g, conf = itunes_genre(artist, title)
        src = "itunes"
        if not g:
            g2, conf2 = mb_genre(artist, title)
            if g2:
                g, conf, src = g2, conf2, "musicbrainz"
        genres.append(g or "unknown")
        resolved.append(TrackInfo(title=title or ln, artist=artist or None, genre=g or None, source=src, confidence=float(conf)))
    label = mood_from_genres([g for g in genres if g and g != "unknown"])
    from collections import Counter
    top = ", ".join([f"{g}×{c}" for g,c in Counter([g or "unknown" for g in genres]).most_common(3)])
    summary = f"장르 분포: {top}"
    return TextPlaylistMoodResult(label=label, summary=summary, tracks=resolved)


if __name__ == "__main__":
    app.run()