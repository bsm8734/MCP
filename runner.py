########################################
# runner.py (여러 MCP 서버를 동시에 붙여 호출하는 오케스트레이터)
########################################
import asyncio, sys, os, json
from contextlib import AsyncExitStack
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

USE_TEXT_PLAYLIST = True  # ← 텍스트 기반 플레이리스트 사용 시 True

# CallToolResult → dict 추출 유틸
def extract_payload(res):
    sc = getattr(res, "structuredContent", None)
    if sc is not None:
        return sc
    for c in getattr(res, "content", []) or []:
        t = getattr(c, "type", None)
        if t == "json" and hasattr(c, "json"):
            return c.json
        if t == "text" and hasattr(c, "text"):
            return {"text": c.text}
    return {"raw": str(res)}

async def spawn(stack: AsyncExitStack, path: str) -> ClientSession:
    params = StdioServerParameters(command=sys.executable, args=[path], cwd=os.getcwd(), env=os.environ.copy())
    read, write = await stack.enter_async_context(stdio_client(params))
    sess = ClientSession(read, write)
    await stack.enter_async_context(sess)
    await sess.initialize()
    return sess

async def main():
    async with AsyncExitStack() as stack:
        # 서버 프로세스 각각 띄우기
        caption = await spawn(stack, "servers/caption_server.py")
        playlist = await spawn(stack, "servers/playlist_server.py")
        trackinfo = await spawn(stack, "servers/trackinfo_server.py")
        mbti = await spawn(stack, "servers/mbti_server.py")
        diary = await spawn(stack, "servers/diary_server.py")
        exif = await spawn(stack, "servers/exif_server.py")
        synth = await spawn(stack, "servers/synth_server.py")

        # 1) 이미지 캡션 & 메타
        cap = extract_payload(await caption.call_tool("caption_image", {"input": {"path": "bom.jpeg"}}))
        meta = extract_payload(await exif.call_tool(
            "extract_image_metadata",
            {"input": {"path": "bom.jpeg"}},
            {"weather": {"use_open_meteo": True}},
        ))

        # # 2) 플레이리스트 분석 (텍스트 or 숫자 피처)
        # if USE_TEXT_PLAYLIST:
        #     pl_text = extract_payload(await trackinfo.call_tool(
        #         "resolve_text_playlist",
        #         {"input": {"lines": [
        #             "NewJeans - Super Shy",
        #             "Billie Eilish - ocean eyes",
        #             "Sigur Rós - Svefn-g-englar",
        #         ]}}
        #     ))
        #     playlist_for_synth = None  # 필요 시 변환
        # else:
        #     pl_stats = extract_payload(await playlist.call_tool(
        #         "analyze_playlist",
        #         {"input": {"tracks": [
        #             {"name":"Song A","artist":"X","energy":0.82,"valence":0.66,"danceability":0.72,"tempo":124},
        #             {"name":"Song B","artist":"Y","energy":0.77,"valence":0.59,"danceability":0.69,"tempo":118},
        #         ]}}
        #     ))
        #     playlist_for_synth = pl_stats

        # # 3) MBTI
        # m = extract_payload(await mbti.call_tool("infer_mbti_traits", {"input": {"mbti": "ENFP"}}))

        # # 4) 일기 요약
        # d = extract_payload(await diary.call_tool("summarize_diary", {"input": {"text": "오늘 가족들과 여수 여행~! 오랜만에 봄이도 함께해서 너무 좋았음.", "language": "ko"}}))

        # 5) 최종 합성
        final = extract_payload(await synth.call_tool("synthesize_dayline", {"input": {
            "caption": cap,
            # "playlist": playlist_for_synth,
            # "mbti": m,
            # "diary": d,
            "meta": meta,
            # "persona": {"age": 27, "gender": "female", "nationality": "KR"},
            # "target_chars": 14
        }}))

        print("✅ 최종 요약:", final.get("line"))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())