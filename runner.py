########################################
# runner.py (여러 MCP 서버를 동시에 붙여 호출하는 오케스트레이터)
########################################
import asyncio
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
from schemas import (
    ImageInput, PlaylistInput, TextPlaylistInput, MBTIInput, DiaryInput, PersonaInput,
    WeatherLookupInput, DaylineInput
)

USE_TEXT_PLAYLIST = True  # ← 텍스트 기반 플레이리스트 사용 시 True

async def spawn(cmd: str, args: list[str]) -> ClientSession:
    read, write = await stdio_client(cmd, *args)
    session = ClientSession(read, write)
    await session.start()
    return session

async def main():
    # 서버 프로세스 각각 띄우기 (테스트용 동일 머신 subprocess)
    caption = await spawn("python", ["servers/caption_server.py"])
    playlist = await spawn("python", ["servers/playlist_server.py"])
    trackinfo = await spawn("python", ["servers/trackinfo_server.py"])
    mbti = await spawn("python", ["servers/mbti_server.py"])
    diary = await spawn("python", ["servers/diary_server.py"])
    exif = await spawn("python", ["servers/exif_server.py"])
    synth = await spawn("python", ["servers/synth_server.py"])

    # 1) 이미지 캡션 & 메타
    cap = await caption.call_tool("caption_image", ImageInput(path="/path/to/photo.jpg").model_dump())
    meta = await exif.call_tool("extract_image_metadata", ImageInput(path="/path/to/photo.jpg").model_dump(), WeatherLookupInput().model_dump())

    # 2) 플레이리스트 분석 (텍스트 or 숫자 피처)
    if USE_TEXT_PLAYLIST:
        text_pl = TextPlaylistInput(lines=[
            "NewJeans - Super Shy",
            "Billie Eilish - ocean eyes",
            "Sigur Rós - Svefn-g-englar",
        ])
        pl_text = await trackinfo.call_tool("resolve_text_playlist", text_pl.model_dump())
        playlist_for_synth = None  # 필요 시 변환해 넣을 수 있음
    else:
        pl_stats = await playlist.call_tool("analyze_playlist", PlaylistInput(tracks=[
            {"name":"Song A","artist":"X","energy":0.82,"valence":0.66,"danceability":0.72,"tempo":124},
            {"name":"Song B","artist":"Y","energy":0.77,"valence":0.59,"danceability":0.69,"tempo":118},
        ]).model_dump())
        playlist_for_synth = pl_stats

    # 3) MBTI
    m = await mbti.call_tool("infer_mbti_traits", MBTIInput(mbti="ENFP").model_dump())

    # 4) 일기 요약
    d = await diary.call_tool("summarize_diary", DiaryInput(text="오늘 친구들과 한강 라이딩. 피곤하지만 행복.").model_dump())

    # 5) 최종 합성
    persona = PersonaInput(age=27, gender="female", nationality="KR")
    line = await synth.call_tool("synthesize_dayline", DaylineInput(
        caption=cap, playlist=playlist_for_synth, mbti=m, diary=d, meta=meta, persona=persona, target_chars=14
    ).model_dump())

    print("✅ 최종 요약:", line["line"])  # dict 반환

    # 정리
    for s in [caption, playlist, trackinfo, mbti, diary, exif, synth]:
        await s.close()

if __name__ == "__main__":
    asyncio.run(main())
