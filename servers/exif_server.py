########################################
# servers/exif_server.py (EXIF/위치/날씨 전용)
########################################
from mcp.server.fastmcp import FastMCP
from schemas import ImageInput, WeatherLookupInput, ExtractedMeta
from utils.exif_geo import extract_exif_meta, lookup_weather

app = FastMCP("exif-mcp")

@app.tool()
def extract_image_metadata(input: ImageInput, weather: WeatherLookupInput = WeatherLookupInput()) -> ExtractedMeta:
    if not input.path:
        raise ValueError("메타데이터 추출은 파일 경로(path)가 필요")
    base = extract_exif_meta(input.path)
    wx = None
    if weather.use_open_meteo and base.get("gps"):
        wx = lookup_weather(base["gps"]["lat"], base["gps"]["lon"], base.get("datetime"))
    return ExtractedMeta(datetime=base.get("datetime"), gps=base.get("gps"), address=None, weather=wx)

if __name__ == "__main__":
    app.run()