# test_caption.py
import asyncio, sys, os, json, argparse
from contextlib import AsyncExitStack
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

CAPTION_SERVER = "servers/caption_server.py"

def extract_payload(res):
    # 1) FastMCP가 구조화해서 준 결과가 있으면 그걸 그대로 사용
    sc = getattr(res, "structuredContent", None)
    if sc is not None:
        return sc
    # 2) content 리스트에서 json/text 순서로 시도
    for c in getattr(res, "content", []) or []:
        t = getattr(c, "type", None)
        if t == "json" and hasattr(c, "json"):
            return c.json
        if t == "text" and hasattr(c, "text"):
            return {"text": c.text}
    # 3) 마지막 수단: 간단 문자열화
    return {"raw": str(res)}

async def main():
    ap = argparse.ArgumentParser(description="Caption server single test")
    ap.add_argument("--image", "-i", default="bom.jpeg", help="이미지 파일 경로")
    args = ap.parse_args()

    if not os.path.isfile(args.image):
        print(f"[error] 이미지 파일이 없습니다: {args.image}", file=sys.stderr)
        sys.exit(1)

    async with AsyncExitStack() as stack:
        params = StdioServerParameters(
            command=sys.executable,
            args=[CAPTION_SERVER],
            cwd=os.getcwd(),
            env=os.environ.copy(),
        )
        read, write = await stack.enter_async_context(stdio_client(params))
        session = ClientSession(read, write)
        await stack.enter_async_context(session)

        # MCP 핸드셰이크
        await session.initialize()

        # (선택) 도구 확인 + 헬스체크
        tools = await session.list_tools()
        print("Tools:", [t.name for t in tools.tools])
        if any(t.name == "ping" for t in tools.tools):
            pong = await session.call_tool("ping")
            print("Ping:", extract_payload(pong))

        # 캡션 생성 호출 (중요: input 키로 감싸기)
        res = await session.call_tool("caption_image", {"input": {"path": args.image}})

        # JSON 직렬화 가능한 페이로드만 출력
        payload = extract_payload(res)
        print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
