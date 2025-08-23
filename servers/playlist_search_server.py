from mcp.server.fastmcp import FastMCP
from FinalProject.schemas import PlaylistMoodResult
from utils.playlist_search import analyze_textfile_tracks

app = FastMCP("playlist-search-mcp")

@app.tool()
def analyze_playlist_textfile(path: str) -> PlaylistMoodResult:
    """
    텍스트 파일 (예: "가수 - 곡명") 목록을 읽고, 웹 검색으로 각 곡 분위기를 추론하여 전체 mood 요약.
    """
    tracks = analyze_textfile_tracks(path)
    # mood 카운트 기반 다수결
    counter = {}
    for t in tracks:
        counter[t["mood"]] = counter.get(t["mood"],0)+1
    if counter:
        label = max(counter,key=counter.get)
    else:
        label = "잔잔한"
    summary = ", ".join([f"{t['artist']} - {t['title']} ({t['mood']})" for t in tracks[:5]])
    stats = {"total":len(tracks),"labels":counter}
    return PlaylistMoodResult(label=label, summary=summary, stats=stats)

if __name__ == "__main__":
    app.run()
