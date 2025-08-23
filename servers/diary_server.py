########################################
# servers/diary_server.py (일기 요약/감정 전용)
########################################
import os
from fastmcp import FastMCP
from dotenv import load_dotenv
from openai import OpenAI
from FinalProject.schemas import DiaryInput, DiarySummary

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL_TEXT = os.getenv("OPENAI_MODEL_TEXT","gpt-4o-mini")
app = FastMCP("diary-mcp")


@app.tool()
def summarize_diary(input: DiaryInput) -> DiarySummary:
    sys = "당신은 섬세한 감정 분석가입니다. 핵심 사건 3~5개를 불릿으로, 감정은 한 단어(한국어)."
    resp = client.chat.completions.create(
        model=MODEL_TEXT,
        messages=[
            {"role":"system","content":sys},
            {"role":"user","content":f"원문({input.language}):{input.text}"}
        ],
        temperature=0.2,
    )
    text = resp.choices[0].message.content.strip()
    bullets = [ln[1:].strip() for ln in text.splitlines() if ln.strip().startswith("-")]
    mood = "중립"
    for ln in text.splitlines():
        if "감정" in ln:
            mood = ln.split(":")[-1].strip()
            break
    if not bullets:
        bullets = [text]
    return DiarySummary(bullet=bullets[:5], mood=mood)


if __name__ == "__main__":
    app.run()