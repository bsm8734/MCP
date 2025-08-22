########################################
# test_caption.py (캡션 서버 단독 테스트; argparse → config.json)
########################################
import asyncio, sys, os, json
from contextlib import AsyncExitStack
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

CONFIG_PATH = os.environ.get("DAYLINE_CONFIG", "config.json")
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
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {}
    image = cfg.get("image", "sample.jpg")

    if not os.path.isfile(image):
        print(f"[error] 이미지 파일이 없습니다: {image}", file=sys.stderr)
        os._exit(1)

    async with AsyncExitStack() as stack:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd() + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        params = StdioServerParameters(
            command=sys.executable,
            args=[CAPTION_SERVER],
            cwd=os.getcwd(),
            env=env,
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

        res = await session.call_tool("caption_image", {"input": {"path": image}})
        payload = extract_payload(res)
        print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())