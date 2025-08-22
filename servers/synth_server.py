########################################
# servers/synth_server.py (최종 10~20자 요약 전용)
########################################
import os, json
from fastmcp import FastMCP
from dotenv import load_dotenv
from openai import OpenAI
from schemas import DaylineInput, DaylineOutput
from utils.style import style_tokens

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL_TEXT = os.getenv("OPENAI_MODEL_TEXT","gpt-4o-mini")
app = FastMCP("synth-mcp")


@app.tool()
def synthesize_dayline(input: DaylineInput) -> DaylineOutput:
    style = style_tokens(
        age=input.persona.age if input.persona else None,
        gender=input.persona.gender if input.persona else None,
        nationality=input.persona.nationality if input.persona else None,
    )
    payload = {
        "caption": input.caption.model_dump(),
        "playlist": input.playlist.model_dump() if input.playlist else None,
        "mbti": input.mbti.model_dump() if input.mbti else None,
        "diary": input.diary.model_dump() if input.diary else None,
        "meta": input.meta.model_dump() if input.meta else None,
        "style": style,
        "target_chars": input.target_chars,
    }
    sys = (
        "너는 사용자 하루를 10~20자 한글로 압축 요약하는 작가다. "
        "문체는 style 토큰을 반영한다. 제공된 데이터만 사용하라."
    )
    user = "아래 JSON을 종합해 10~20자 요약 1개만 출력. 줄바꿈/해설 금지." + json.dumps(payload, ensure_ascii=False)
    resp = client.chat.completions.create(model=MODEL_TEXT, messages=[{"role":"system","content":sys},{"role":"user","content":user}], temperature=0.5)
    line = resp.choices[0].message.content.strip().replace(""," ")
    return DaylineOutput(line=line)


if __name__ == "__main__":
    app.run()