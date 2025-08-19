########################################
# utils/exif_geo.py (공유)
########################################
from typing import Optional, Dict, Any
from PIL import Image, ExifTags
import requests

def _ratio_to_deg(value):
    d = value[0][0]/value[0][1]
    m = value[1][0]/value[1][1]
    s = value[2][0]/value[2][1]
    return d + m/60 + s/3600


def extract_exif_meta(path: str) -> Dict[str, Any]:
    img = Image.open(path)
    exif = img._getexif() or {}
    tag_map = { ExifTags.TAGS.get(k,k): v for k,v in exif.items() }
    out: Dict[str,Any] = {
        "datetime": tag_map.get("DateTimeOriginal") or tag_map.get("DateTime"),
        "gps": None
    }
    gps_info = tag_map.get("GPSInfo")
    if gps_info:
        gps = { ExifTags.GPSTAGS.get(k,k): v for k,v in gps_info.items() }
        try:
            lat = _ratio_to_deg(gps["GPSLatitude"]) * (1 if gps.get("GPSLatitudeRef","N")=="N" else -1)
            lon = _ratio_to_deg(gps["GPSLongitude"]) * (1 if gps.get("GPSLongitudeRef","E")=="E" else -1)
            out["gps"] = {"lat":lat, "lon":lon}
        except Exception:
            pass
    return out


def lookup_weather(lat: float, lon: float, iso_date: Optional[str]) -> Optional[Dict[str,Any]]:
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ["temperature_2m_max","temperature_2m_min","precipitation_sum","weathercode"],
            "timezone": "auto"
        }
        if iso_date:
            params["start_date"] = iso_date[:10]
            params["end_date"] = iso_date[:10]
        r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
        if r.ok:
            j = r.json()
            daily = j.get("daily",{})
            if daily:
                return {
                    "tmax": daily.get("temperature_2m_max",[None])[0],
                    "tmin": daily.get("temperature_2m_min",[None])[0],
                    "precip": daily.get("precipitation_sum",[None])[0],
                    "code": daily.get("weathercode",[None])[0]
                }
    except Exception:
        return None
    return None