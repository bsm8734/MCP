########################################
# schemas.py (공유 스키마)
########################################
from pydantic import BaseModel
from typing import List, Optional, Literal, Dict, Any

class ImageInput(BaseModel):
    path: Optional[str] = None
    data_url: Optional[str] = None

class PlaylistInput(BaseModel):
    spotify_url: Optional[str] = None
    tracks: Optional[List[Dict[str, Any]]] = None  # 직접 피처 입력

class TextPlaylistInput(BaseModel):
    path: Optional[str] = None            # 줄바꿈으로 트랙 라인 나열된 .txt 파일 경로
    lines: Optional[List[str]] = None     # ["Artist - Title", "Title - Artist", ...]

class MBTIInput(BaseModel):
    mbti: Literal[
        "INTJ","INTP","ENTJ","ENTP","INFJ","INFP","ENFJ","ENFP",
        "ISTJ","ISFJ","ESTJ","ESFJ","ISTP","ISFP","ESTP","ESFP"
    ]

class DiaryInput(BaseModel):
    text: str
    language: Optional[str] = "ko"

class PersonaInput(BaseModel):
    age: Optional[int] = None
    gender: Optional[Literal["male","female","nonbinary","unknown"]] = "unknown"
    nationality: Optional[str] = None

class WeatherLookupInput(BaseModel):
    use_open_meteo: bool = True

class ExtractedMeta(BaseModel):
    datetime: Optional[str] = None
    gps: Optional[Dict[str, float]] = None
    address: Optional[str] = None
    weather: Optional[Dict[str, Any]] = None

class CaptionResult(BaseModel):
    caption: str
    tags: List[str] = []

class PlaylistMoodResult(BaseModel):
    label: Literal["잔잔한","신나는","격동적인","파티","우울/차분","밝고경쾌"]
    summary: str
    stats: Dict[str, float]

class TrackInfo(BaseModel):
    title: str
    artist: Optional[str] = None
    genre: Optional[str] = None
    source: Optional[str] = None  # itunes/musicbrainz
    confidence: float = 0.0

class TextPlaylistMoodResult(BaseModel):
    label: Literal["잔잔한","신나는","격동적인","파티","우울/차분","밝고경쾌"]
    summary: str
    tracks: List[TrackInfo]

class MBTITraits(BaseModel):
    traits: List[str]
    summary: str

class DiarySummary(BaseModel):
    bullet: List[str]
    mood: str

class DaylineInput(BaseModel):
    caption: CaptionResult
    playlist: Optional[PlaylistMoodResult]
    mbti: Optional[MBTITraits]
    diary: Optional[DiarySummary]
    meta: Optional[ExtractedMeta]
    persona: Optional[PersonaInput]
    target_chars: int = 14

class DaylineOutput(BaseModel):
    line: str
    reasoning: Optional[str] = None
