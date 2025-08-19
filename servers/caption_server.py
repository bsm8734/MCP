########################################
# servers/caption_server.py (이미지 캡션 전용)
########################################
import os, io, base64
from typing import Optional
from fastmcp import FastMCP
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image
from schemas import ImageInput, CaptionResult


load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL_VISION = os.getenv("OPENAI_MODEL_VISION","gpt-4o-mini")
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "30"))
MAX_SIDE = int(os.getenv("CAPTION_MAX_SIDE", "1280"))
app = FastMCP("caption-mcp")


def _to_data_url(path: Optional[str], data_url: Optional[str]) -> str:
    if data_url:
        return data_url
    if not path:
        raise ValueError("path 또는 data_url 중 하나는 필요")
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        m = max(w, h)
        if m > MAX_SIDE:
            scale = MAX_SIDE / m
            im = im.resize((int(w * scale), int(h * scale)))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


@app.tool()
def ping() -> str:
    return "ok"


@app.tool()
def caption_image(input: ImageInput) -> CaptionResult:
    url = _to_data_url(input.path, input.data_url)
    content = [
        {"type": "text", "text": "사진을 한 문장으로 묘사하고, 해시태그 5개를 한국어로."},
        {"type": "image_url", "image_url": {"url": url}},
    ]
    resp = client.chat.completions.create(
        model=MODEL_VISION,
        messages=[{"role": "user", "content": content}],
        temperature=0.2,
        timeout=OPENAI_TIMEOUT,
    )
    txt = resp.choices[0].message.content.strip()
    parts = txt.split("#")
    caption = parts[0].strip()
    tags = [p.strip().replace("#", "") for p in parts[1:]] if len(parts) > 1 else []
    return CaptionResult(caption=caption or "설명 없음", tags=tags[:5])


if __name__ == "__main__":
    app.run()
