# servers/exif_server.py
from fastmcp import FastMCP
# --- project-root import bootstrap ---
import sys, os
_ROOT = os.path.dirname(os.path.dirname(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
# --- end bootstrap ---

from schemas import ImageInput, WeatherLookupInput, ExtractedMeta
from utils.exif_geo import extract_exif_meta, lookup_weather, reverse_geocode

app = FastMCP("exif-mcp")

@app.tool()
def extract_image_metadata(
    input: ImageInput,
    weather: WeatherLookupInput = WeatherLookupInput(),
    address: bool = True,
) -> ExtractedMeta:
    if not input.path:
        raise ValueError("메타데이터 추출은 파일 경로(path)가 필요")
    base = extract_exif_meta(input.path)

    wx = None
    addr = None
    if base.get("gps"):
        lat = base["gps"]["lat"]; lon = base["gps"]["lon"]
        if address:
            addr = reverse_geocode(lat, lon, lang="ko")
        if weather.use_open_meteo:
            wx = lookup_weather(lat, lon, base.get("datetime"))

    return ExtractedMeta(
        datetime=base.get("datetime"),
        gps=base.get("gps"),
        address=addr,
        weather=wx
    )

if __name__ == "__main__":
    app.run()
