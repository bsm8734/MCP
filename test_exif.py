# test_exif.py
import asyncio, sys, os, json, argparse
from contextlib import AsyncExitStack
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

EXIF_SERVER = "servers/exif_server.py"

def extract_payload(res):
    """CallToolResult → dict/text 로 안전 추출"""
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

async def main():
    ap = argparse.ArgumentParser(description="exif_server 단독 테스트")
    ap.add_argument("--image", "-i", default='bom.jpeg', help="이미지 파일 경로 (EXIF 포함 권장)")
    ap.add_argument("--weather", action="store_true", help="Open-Meteo 날씨 조회도 수행(GPS 필요)")
    ap.add_argument("--timeout", type=float, default=10.0, help="툴 호출 타임아웃(초)")
    args = ap.parse_args()

    if not os.path.isfile(args.image):
        print(f"[error] 이미지 파일이 없습니다: {args.image}", file=sys.stderr)
        sys.exit(1)

    async with AsyncExitStack() as stack:
        # servers/ 와 utils/ 가 같은 레벨 → PYTHONPATH에 프로젝트 루트 넣기
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd() + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        params = StdioServerParameters(
            command=sys.executable,
            args=[EXIF_SERVER],
            cwd=os.getcwd(),
            env=env,
        )

        read, write = await stack.enter_async_context(stdio_client(params))
        session = ClientSession(read, write)
        await stack.enter_async_context(session)

        # MCP 초기화
        await session.initialize()

        # (선택) 도구 목록 확인
        tools = await session.list_tools()
        print("Tools:", [t.name for t in tools.tools], file=sys.stderr)

        # arguments 단일 dict로 구성 (✅ dict 두 개 posarg로 넘기지 않음)
        arguments = {"input": {"path": args.image}}
        if args.weather:
            arguments["weather"] = {"use_open_meteo": True}

        # 호출
        try:
            res = await asyncio.wait_for(
                session.call_tool("extract_image_metadata", arguments),
                timeout=args.timeout,
            )
        except Exception as e:
            print(f"[error] call_tool 실패: {e}", file=sys.stderr)
            sys.exit(2)

        out = extract_payload(res)
        print(json.dumps(out, ensure_ascii=False, indent=2))

        # 안내 메시지
        if not out.get("gps"):
            print("[note] EXIF에 GPS가 없어 주소/날씨가 비어 있을 수 있어요.", file=sys.stderr)
        elif args.weather and not out.get("weather"):
            print("[note] GPS는 있으나 날씨 조회가 실패했거나 해당 날짜 데이터가 없었습니다.", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())
