########################################
# smart_client.py (자동 라우팅 클라이언트; 어떤 서버를 쓸지 판단 + 장애내성)
########################################
import argparse, asyncio, json, os, sys
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from contextlib import AsyncExitStack
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

# --- 유틸: 결과 추출 ---
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

# --- 유틸: 간단 검출 로직 ---
def is_file(path: Optional[str]) -> bool:
    return bool(path and os.path.isfile(path))

def is_spotify_playlist(url: Optional[str]) -> bool:
    if not url: return False
    return "open.spotify.com/playlist" in url or url.startswith("spotify:playlist:")

# TextPlaylistMoodResult → PlaylistMoodResult 간이 변환 (synth 호환용)
def coerce_text_playlist_to_stats(tp: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not tp: return None
    label = tp.get("label")
    summary = tp.get("summary","text playlist")
    stats = {"energy":0.5, "valence":0.5, "danceability":0.5, "tempo":110}
    return {"label": label, "summary": summary, "stats": stats}

# --- 장애내성: 안전 호출 래퍼 ---
async def safe_call(label: str, session: ClientSession, tool: str, *payloads: List[Dict[str, Any]], timeout: float = 8.0):
    try:
        res = await asyncio.wait_for(session.call_tool(tool, *payloads), timeout=timeout)
        return extract_payload(res)
    except Exception as e:
        print(f"[warn] {label}::{tool} 실패 → 제외합니다: {e}", file=sys.stderr)
        return None

async def spawn(stack: AsyncExitStack, path: str) -> Optional[ClientSession]:
    try:
        params = StdioServerParameters(command=sys.executable, args=[path], cwd=os.getcwd(), env=os.environ.copy())
        read, write = await stack.enter_async_context(stdio_client(params))
        sess = ClientSession(read, write)
        await stack.enter_async_context(sess)
        await sess.initialize()
        return sess
    except Exception as e:
        print(f"[warn] 서버 스폰 실패({path}): {e}", file=sys.stderr)
        return None

async def main():
    load_dotenv()
    p = argparse.ArgumentParser(description="Smart MCP Client (auto-routing, fault-tolerant)")
    p.add_argument("--image", type=str, help="이미지 파일 경로", default=None)
    p.add_argument("--playlist", type=str, help="텍스트 파일 경로 또는 Spotify 플레이리스트 URL", default=None)
    p.add_argument("--mbti", type=str, help="ENFP, ISTJ ...", default=None)
    p.add_argument("--diary", type=str, help="일기 텍스트 파일 경로 또는 직접 텍스트", default=None)
    p.add_argument("--age", type=int, default=None)
    p.add_argument("--gender", type=str, choices=["male","female","nonbinary","unknown"], default="unknown")
    p.add_argument("--nation", type=str, default=None)
    p.add_argument("--target", type=int, default=14, help="최종 요약 글자 수(10~20 권장)")
    p.add_argument("--timeout", type=float, default=8.0, help="각 서버 호출 타임아웃(초)")
    p.add_argument("--allow_no_image", action="store_true", help="이미지 없이도 요약 허용")
    args = p.parse_args()

    sessions: dict[str, ClientSession] = {}

    async with AsyncExitStack() as stack:
        # 서버 기동 (없으면 스폰)
        for label, path in [
            ("caption", "servers/caption_server.py"),
            ("playlist", "servers/playlist_server.py"),
            ("trackinfo", "servers/trackinfo_server.py"),
            ("mbti", "servers/mbti_server.py"),
            ("diary", "servers/diary_server.py"),
            ("exif", "servers/exif_server.py"),
            ("synth", "servers/synth_server.py"),
        ]:
            if os.path.exists(path):
                sess = await spawn(stack, path)
                if sess:
                    sessions[label] = sess

        # --- 1) 이미지 입력 처리 ---
        caption_res = None
        meta_res = None
        if is_file(args.image) and sessions.get("caption") and sessions.get("exif"):
            caption_res = await safe_call("caption", sessions["caption"], "caption_image", {"input": {"path": args.image}}, timeout=args.timeout)
            meta_res = await safe_call("exif", sessions["exif"], "extract_image_metadata", {"input": {"path": args.image}}, {"weather": {"use_open_meteo": True}}, timeout=args.timeout)

        # --- 2) 플레이리스트 입력 처리 ---
        playlist_res_for_synth = None
        if args.playlist:
            if is_spotify_playlist(args.playlist) and sessions.get("playlist"):
                playlist_stats = await safe_call("playlist", sessions["playlist"], "analyze_playlist", {"input": {"spotify_url": args.playlist}}, timeout=args.timeout)
                playlist_res_for_synth = playlist_stats or None
            elif sessions.get("trackinfo"):
                if is_file(args.playlist):
                    tp = await safe_call("trackinfo", sessions["trackinfo"], "resolve_text_playlist", {"input": {"path": args.playlist}}, timeout=args.timeout)
                else:
                    lines = [s.strip() for s in args.playlist.replace(";", "").replace(",", "").splitlines() if s.strip()]
                    tp = await safe_call("trackinfo", sessions["trackinfo"], "resolve_text_playlist", {"input": {"lines": lines}}, timeout=args.timeout)
                playlist_res_for_synth = coerce_text_playlist_to_stats(tp) if tp else None

        # --- 3) MBTI 입력 처리 ---
        mbti_res = None
        if args.mbti and sessions.get("mbti"):
            mbti_res = await safe_call("mbti", sessions["mbti"], "infer_mbti_traits", {"input": {"mbti": args.mbti.upper()}}, timeout=args.timeout)

        # --- 4) 일기 입력 처리 ---
        diary_res = None
        if args.diary and sessions.get("diary"):
            if is_file(args.diary):
                try:
                    with open(args.diary, "r", encoding="utf-8") as f:
                        text = f.read()
                except Exception:
                    text = str(args.diary)
            else:
                text = args.diary
            diary_res = await safe_call("diary", sessions["diary"], "summarize_diary", {"input": {"text": text, "language": "ko"}}, timeout=args.timeout)

        # --- 5) 최종 합성 준비 (caption 없을 때 대체 캡션 생성) ---
        if not caption_res:
            if not args.allow_no_image:
                print("[warn] caption_server 사용 불가 또는 이미지 미제공: 기본 캡션으로 진행합니다. (--allow_no_image로 경고 무시 가능)", file=sys.stderr)
            caption_res = {"caption": "이미지 없음", "tags": []}

        persona = {"age": args.age, "gender": args.gender, "nationality": args.nation}
        payload = {
            "caption": caption_res,
            "playlist": playlist_res_for_synth,
            "mbti": mbti_res,
            "diary": diary_res,
            "meta": meta_res,
            "persona": persona,
            "target_chars": args.target
        }

        # --- 6) 합성: synth 서버 우선, 실패 시 로컬 LLM 폴백 ---
        final = None
        if sessions.get("synth"):
            final = await safe_call("synth", sessions["synth"], "synthesize_dayline", {"input": payload}, timeout=max(6.0, args.timeout))

        if not final:
            # 로컬 LLM 폴백 (OpenAI API 직접 호출)
            try:
                from openai import OpenAI
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                model = os.getenv("OPENAI_MODEL_TEXT", "gpt-4o-mini")
                sys_msg = (
                    "너는 사용자 하루를 10~20자 한글로 압축 요약하는 작가다. "
                    "문체는 style/나이/성별/국적을 반영한다. 제공된 데이터만 사용하라."
                )
                user_msg = "아래 JSON을 종합해 10~20자 요약 1개만 출력. 줄바꿈/해설 금지." + json.dumps(payload, ensure_ascii=False)
                resp = client.chat.completions.create(model=model, messages=[{"role":"system","content":sys_msg},{"role":"user","content":user_msg}], temperature=0.5)
                line = resp.choices[0].message.content.strip().replace("", " ")
                final = {"line": line}
                print("[info] synth_server 장애로 OpenAI 폴백 사용", file=sys.stderr)
            except Exception as e:
                print(f"[error] synth 폴백 실패: {e}", file=sys.stderr)
                print(json.dumps({"error":"요약 실패","reason":str(e)}, ensure_ascii=False))
                return

        # 결과 출력
        print(json.dumps({
            "dayline": final["line"] if isinstance(final, dict) else final,
            "used": {
                "caption": bool(caption_res and (caption_res.get("caption") or caption_res.get("text"))),
                "playlist": bool(playlist_res_for_synth),
                "mbti": bool(mbti_res),
                "diary": bool(diary_res),
                "meta": bool(meta_res),
                "fallback": "synth" not in sessions
            }
        }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
