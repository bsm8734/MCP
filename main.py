import os, sys, json, asyncio
from contextlib import AsyncExitStack
from typing import Optional, Dict, Any, TypedDict, List

# ---------- .env 로드 ----------
from dotenv import load_dotenv
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ---------- LangGraph / LangChain ----------
from typing_extensions import Annotated
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage, BaseMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

# ---------- MCP client ----------
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

# ---------- 경로/모델/서버 ---------- .env
CONFIG_PATH = os.environ.get("DAYLINE_CONFIG", "config.json")
CAPTION_SERVER = "servers/caption_server.py"
EXIF_SERVER    = "servers/exif_server.py"

OPENAI_MODEL = os.getenv("OPENAI_MODEL_TEXT", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# =========================================================
# 공통 유틸
# =========================================================
def _extract_payload(res):
    """CallToolResult → dict/text 로 평탄화"""
    sc = getattr(res, "structuredContent", None)
    if sc is not None:
        return sc
    for c in getattr(res, "content", []) or []:
        typ = getattr(c, "type", None)
        if typ == "json" and hasattr(c, "json"):
            return c.json
        if typ == "text" and hasattr(c, "text"):
            return {"text": c.text}
    return {"raw": str(res)}

async def _call_mcp_tool(server_py: str, tool_name: str, arguments: Dict[str, Any], timeout: float = 20.0) -> Dict[str, Any]:
    """
    서버를 stdio로 스폰해 단일 tool 호출을 수행하고 결과 dict로 반환.
    (데모 단순화를 위해 매 호출마다 스폰; 실제 서비스는 세션 재사용 권장)
    """
    env = os.environ.copy()
    # servers/ 와 utils/ 가 같은 레벨 → 루트를 PYTHONPATH에 추가
    env["PYTHONPATH"] = os.getcwd() + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    params = StdioServerParameters(command=sys.executable, args=[server_py], cwd=os.getcwd(), env=env) # 서브프로세스 생성

    async with AsyncExitStack() as stack:
        read, write = await stack.enter_async_context(stdio_client(params))
        session = ClientSession(read, write) 
        await stack.enter_async_context(session)
        await session.initialize()

        res = await asyncio.wait_for(session.call_tool(tool_name, arguments), timeout=timeout)
        return _extract_payload(res)

# =========================================================
# LangChain Tools (LLM이 호출할 “툴” 래퍼)
# =========================================================
@tool("caption_image_tool")
def caption_image_tool(path: str) -> str:
    """이미지 파일 경로(path)를 받아 한 줄 캡션과 해시태그를 생성한다. 반환은 JSON 문자열."""
    async def _run(p):
        return await _call_mcp_tool(
            CAPTION_SERVER,
            "caption_image",
            {"input": {"path": p}},
        )
    out = asyncio.run(_run(path))
    return json.dumps(out, ensure_ascii=False)

@tool("exif_metadata_tool")
def exif_metadata_tool(path: str, weather: bool = True, address: bool = True) -> str:
    """이미지 경로에서 EXIF(시간/GPS) + 옵션(날씨/주소)을 추출. 반환은 JSON 문자열."""
    async def _run(p, w, a):
        args = {"input": {"path": p}}
        if w:
            args["weather"] = {"use_open_meteo": True}
        # exif_server.py가 address 토글을 인자로 받도록 구현되어 있어야 함
        args["address"] = bool(a)
        return await _call_mcp_tool(EXIF_SERVER, "extract_image_metadata", args)
    out = asyncio.run(_run(path, weather, address))
    return json.dumps(out, ensure_ascii=False)

ALL_TOOLS = [caption_image_tool, exif_metadata_tool]

# =========================================================
# State & Planner (프롬프트 → Plan)
# =========================================================
class Plan(BaseModel):
    need_caption: bool = Field(True, description="캡션 생성이 필요한가?")
    need_exif: bool    = Field(True, description="EXIF/메타가 필요한가?")
    want_weather: bool = Field(True, description="날씨 조회를 포함할 것인가?")
    want_address: bool = Field(True, description="역지오코딩(주소)을 포함할 것인가?")

class State(TypedDict, total=False):
    image_path: str
    prompt: str
    plan: dict
    messages: Annotated[List[BaseMessage], add_messages]  # ✅ append merge (tool_calls 규약 만족)
    caption: Dict[str, Any]
    meta: Dict[str, Any]
    diary: str

# pydantic v2 + function_calling 방식
_planner_llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0.0, api_key=OPENAI_API_KEY)
Planner = _planner_llm.with_structured_output(Plan, method="function_calling")

def plan_node(state: State) -> Dict:
    user_prompt = state.get("prompt") or ""
    sys_msg = (
        "너는 툴 라우터다. 사용자의 한국어 요청을 읽고 아래 필드를 결정해 JSON으로만 답하라.\n"
        "- need_caption: 캡션이 필요한지\n"
        "- need_exif: EXIF/메타가 필요한지\n"
        "- want_weather: 날씨 포함 여부\n"
        "- want_address: 역지오코딩(주소) 포함 여부\n"
        "명시가 없으면 True를 기본으로 한다."
    )
    plan: Plan = Planner.invoke([SystemMessage(content=sys_msg), HumanMessage(content=user_prompt)])
    return {"plan": plan.model_dump()}

# =========================================================
# Agent (선택된 툴만 바인딩하여 호출)
# =========================================================
SYS_PROMPT = (
    "너는 이미지 메타/캡션 분석 비서다.\n"
    "- plan에 기재된 툴만 호출하라.\n"
    "- 각 툴은 최대 한 번만 호출한다.\n"
    "- exif_metadata_tool 인자는 (path, weather, address)로 전달한다.\n"
    "- 결과 요약은 하지 말고, 툴 호출만 결정하라."
)

def _build_agent_messages(state: State) -> List[BaseMessage]:
    msgs: List[BaseMessage] = [SystemMessage(content=SYS_PROMPT)]
    prev = state.get("messages") or []

    plan = state.get("plan") or {}
    enabled = {
        "caption": bool(plan.get("need_caption", True)),
        "exif": bool(plan.get("need_exif", True)),
        "want_weather": bool(plan.get("want_weather", True)),
        "want_address": bool(plan.get("want_address", True)),
    }

    if not prev:
        # 첫 턴: state/plan을 Human으로 명시해 LLM이 정확한 인자로 tool_calls 생성하도록 유도
        ctx = {
            "image_path": state.get("image_path"),
            "call_hints": {
                "exif_args": {"weather": enabled["want_weather"], "address": enabled["want_address"]}
            },
            "enabled_tools": enabled
        }
        msgs.append(HumanMessage(content=json.dumps(ctx, ensure_ascii=False)))
        return msgs

    msgs.extend(prev)
    return msgs

def agent_node(state: State) -> Dict:
    plan = state.get("plan") or {}
    enabled_tools = []
    if plan.get("need_caption", True):
        enabled_tools.append(caption_image_tool)
    if plan.get("need_exif", True):
        enabled_tools.append(exif_metadata_tool)

    llm_local = ChatOpenAI(model=OPENAI_MODEL, temperature=0.2, api_key=OPENAI_API_KEY).bind_tools(enabled_tools)
    msgs = _build_agent_messages(state)
    ai = llm_local.invoke(msgs)
    return {"messages": [ai]}

# =========================================================
# 도구 실행/수집/루프
# =========================================================
tool_node = ToolNode(ALL_TOOLS)

def _has_tool_result(state: State, tool_name: str) -> bool:
    for m in state.get("messages", []):
        if isinstance(m, ToolMessage) and (m.name or "") == tool_name:
            return True
    if tool_name == "caption_image_tool" and state.get("caption"):
        return True
    if tool_name == "exif_metadata_tool" and state.get("meta"):
        return True
    return False

def should_continue(state: State):
    plan = state.get("plan") or {}
    need_cap = plan.get("need_caption", True)
    need_ex  = plan.get("need_exif", True)

    have_cap = _has_tool_result(state, "caption_image_tool") if need_cap else True
    have_ex  = _has_tool_result(state, "exif_metadata_tool") if need_ex else True

    if have_cap and have_ex:
        return "collect"

    last_ai = next((m for m in reversed(state.get("messages", [])) if isinstance(m, AIMessage)), None)
    if last_ai and getattr(last_ai, "tool_calls", None):
        return "tools"
    return "agent"

def collect_node(state: State) -> Dict:
    caption_out: Optional[Dict[str, Any]] = None
    meta_out: Optional[Dict[str, Any]] = None

    for m in state.get("messages", []):
        if isinstance(m, ToolMessage):
            name = (m.name or "").strip()
            try:
                data = json.loads(m.content)
            except Exception:
                data = {"text": m.content}
            if name == "caption_image_tool":
                caption_out = data
            elif name == "exif_metadata_tool":
                meta_out = data

    updates: Dict[str, Any] = {}
    if caption_out is not None:
        updates["caption"] = caption_out
    if meta_out is not None:
        updates["meta"] = meta_out
    return updates

# =========================================================
# ✨ 일기 작성 노드 (LLM만 사용, 툴 호출 없음)
# =========================================================
def compose_diary_node(state: State) -> Dict:
    """
    caption/meta를 바탕으로 5~7문장 한국어 일기 생성.
    - 없는 정보는 추측/날조 금지
    - 주소는 구/동 수준까지만 서술
    - 날씨 있으면 1회 언급
    """
    caption = state.get("caption") or {}
    meta    = state.get("meta") or {}

    facts = {
        "caption": caption.get("caption"),
        "tags": caption.get("tags") or [],
        "datetime": meta.get("datetime"),
        "address": meta.get("address"),
        "weather": (meta.get("weather") or None),
        "gps": (meta.get("gps") or None),
    }

    sys_prompt = (
        "너는 섬세한 한국어 일기 비서다. 주어진 JSON의 사실만 사용해 5~7문장으로 일기를 쓴다.\n"
        "- 첫 문장: 촬영/기록 시각 또는 장소가 있으면 자연스럽게 녹여라.\n"
        "- 본문: caption과 tags에서 떠오르는 장면·활동·느낌을 사실 기반으로 묘사한다.\n"
        "- 날씨가 있으면 한 번 언급(맑음/비/기온 느낌 등).\n"
        "- 장소(address)가 있으면 과도한 상세 주소는 피하고 구/동 정도만.\n"
        "- 없는 정보는 추측하지 않는다(모르면 언급하지 않음).\n"
        "- 마지막 문장: 오늘을 한 줄로 정리하는 여운.\n"
        "출력은 순수 일기 본문만; 제목/불릿/해시태그/이모지는 쓰지 마라."
    )
    legend = {
        "caption": "이미지에서 얻은 한 줄 장면 설명",
        "tags": "장면을 떠올리게 하는 핵심 키워드들",
        "datetime": "촬영/기록시각 'YYYY:MM:DD HH:MM:SS' 또는 없을 수 있음",
        "address": "역지오코딩으로 얻은 대략의 지명(구/동 수준)",
        "weather": "해당 날짜의 요약(최고/최저/강수량/날씨코드). 없으면 제외",
        "gps": "위도/경도 숫자. 본문에 수치로 쓰지 말 것",
    }
    payload = {"facts": facts, "legend": legend}

    llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0.4, api_key=OPENAI_API_KEY)
    resp = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=json.dumps(payload, ensure_ascii=False))])
    diary_text = resp.content.strip()
    return {"diary": diary_text}

# =========================================================
# 그래프 컴파일
# =========================================================
graph = StateGraph(State)
graph.add_node("plan", plan_node)
graph.add_node("agent", agent_node)
graph.add_node("tools", tool_node)
graph.add_node("collect", collect_node)
graph.add_node("compose", compose_diary_node)

graph.set_entry_point("plan")
graph.add_edge("plan", "agent")
graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "agent": "agent", "collect": "collect"})
graph.add_edge("tools", "agent")
graph.add_edge("collect", "compose")  # ✅ 수집 후 일기 작성
graph.add_edge("compose", END)

app = graph.compile()

# =========================================================
# 메인 실행
# =========================================================
async def _run_from_config():
    if not OPENAI_API_KEY:
        print("[error] OPENAI_API_KEY가 설정되어 있지 않습니다.", file=sys.stderr)
        return

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {}

    image_path = cfg.get("image", "sample.jpg")
    user_prompt = cfg.get("prompt", "둘 다 켜줘")  # 기본: caption+exif 모두

    if not os.path.isfile(image_path):
        print(json.dumps({"error": "이미지 파일을 찾지 못했습니다.", "path": image_path}, ensure_ascii=False), file=sys.stderr)
        return

    state: State = {
        "image_path": image_path,
        "prompt": user_prompt,
        "messages": []
    }
    result = await app.ainvoke(state)

    out = {
        "plan": result.get("plan"),
        "caption": result.get("caption"),
        "meta": result.get("meta"),
        "diary": result.get("diary"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(_run_from_config())
