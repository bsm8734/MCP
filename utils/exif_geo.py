# utils/exif_geo.py
from typing import Optional, Dict, Any
from PIL import Image, ExifTags
import requests
import datetime as dt

# ----- 내부 유틸: IFDRational/분수 안전 변환 -----
def _to_float(x):
    try:
        from PIL.TiffImagePlugin import IFDRational
        if isinstance(x, IFDRational):
            return float(x)
    except Exception:
        pass
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, tuple) and len(x) == 2:
        a, b = x
        return float(a) / float(b)
    return float(x)

def _dms_to_deg(dms):
    if isinstance(dms, (int, float)):
        return float(dms)
    d, m, s = (_to_float(dms[0]), _to_float(dms[1]), _to_float(dms[2]))
    return d + m/60.0 + s/3600.0

def _exif_date_to_iso(date_str: Optional[str]) -> Optional[str]:
    """EXIF 'YYYY:MM:DD HH:MM:SS' → 'YYYY-MM-DD'"""
    if not date_str:
        return None
    try:
        t = dt.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        return t.date().isoformat()
    except Exception:
        # 일부 단말 변형 대응: 앞 10자만 뽑고 : → - 치환
        return date_str[:10].replace(":", "-")

# ----- EXIF → datetime / GPS -----
def extract_exif_meta(path: str) -> Dict[str, Any]:
    """이미지에서 촬영시각/위치(GPS)만 추출."""
    with Image.open(path) as img:
        exif = img._getexif() or {}
    tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
    out: Dict[str, Any] = {
        "datetime": tag_map.get("DateTimeOriginal") or tag_map.get("DateTime"),
        "gps": None
    }
    gps_info = tag_map.get("GPSInfo")
    if isinstance(gps_info, dict):
        gps = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_info.items()}
        try:
            lat = _dms_to_deg(gps["GPSLatitude"])
            lon = _dms_to_deg(gps["GPSLongitude"])
            lat_ref = str(gps.get("GPSLatitudeRef", "N")).upper()
            lon_ref = str(gps.get("GPSLongitudeRef", "E")).upper()
            lat =  abs(lat) if lat_ref == "N" else -abs(lat)
            lon =  abs(lon) if lon_ref == "E" else -abs(lon)
            out["gps"] = {"lat": round(lat, 7), "lon": round(lon, 7)}
        except Exception:
            pass
    return out

# ----- Open-Meteo 날씨 조회 -----
def lookup_weather(lat: float, lon: float, exif_datetime: Optional[str]) -> Optional[Dict[str, Any]]:
    """GPS + EXIF 날짜 기준 일별 날씨 조회. 실패 시 None."""
    iso_date = _exif_date_to_iso(exif_datetime) or dt.date.today().isoformat()
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "weathercode"],
            "timezone": "auto",
            "start_date": iso_date,
            "end_date": iso_date,
        }
        r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
        if not r.ok:
            return None
        j = r.json()
        d = j.get("daily") or {}
        return {
            "date": (d.get("time") or [iso_date])[0],
            "tmax": (d.get("temperature_2m_max") or [None])[0],
            "tmin": (d.get("temperature_2m_min") or [None])[0],
            "precip": (d.get("precipitation_sum") or [None])[0],
            "code": (d.get("weathercode") or [None])[0],
        }
    except Exception:
        return None

# ----- 역지오코딩(Nominatim) -----
HEADERS_NOMINATIM = {
    "User-Agent": "dayline-mcp/1.0 (contact: you@example.com)"
}

def reverse_geocode(lat: float, lon: float, lang: str = "ko") -> Optional[str]:
    """GPS → 간결 주소 문자열. 실패 시 None."""
    try:
        if lat is None or lon is None:
            return None
        params = {
            "format": "jsonv2",
            "lat": lat,
            "lon": lon,
            "zoom": 14,               # 동/동네 수준
            "addressdetails": 1,
            "accept-language": lang,
        }
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params=params,
            headers=HEADERS_NOMINATIM,
            timeout=10,
        )
        if not r.ok:
            return None
        j = r.json()
        addr = j.get("address") or {}
        # 한국/도시권 기준: city/town/village/county → district/borough/suburb → neighbourhood/quarter
        city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county")
        district = addr.get("district") or addr.get("borough") or addr.get("suburb")
        hood = addr.get("neighbourhood") or addr.get("quarter")
        parts = [p for p in [city, district, hood] if p]
        if parts:
            # 중복 제거 후 간결 문자열
            return " ".join(dict.fromkeys(parts))
        return j.get("display_name")
    except Exception:
        return None
