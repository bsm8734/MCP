 📦 프로젝트 구조 (마이크로서비스형 — "한 서버 = 한 역할")
 ├─ README.md
 ├─ servers/
 │   ├─ caption_server.py        # 이미지 캡션 전용
 │   ├─ playlist_server.py       # (숫자 피처 입력/Spotify) 플레이리스트 경향성 전용
 │   ├─ trackinfo_server.py      # 📄 텍스트 기반 트랙명 → 공개 API 조회 → 장르/무드 추론
 │   ├─ mbti_server.py           # MBTI 성향 전용
 │   ├─ diary_server.py          # 일기 요약/감정 전용
 │   ├─ exif_server.py           # EXIF/위치/날씨 전용
 │   └─ synth_server.py          # 최종 10~20자 요약 전용
 ├─ runner.py                    # 오케스트레이터 (여러 MCP 서버 호출)
 ├─ schemas.py                   # Pydantic 스키마 (공유)
 ├─ utils/
 │   ├─ playlist.py
 │   ├─ track_lookup.py          # iTunes/MusicBrainz 조회 + 장르→무드 매핑 보조
 │   ├─ exif_geo.py
 │   └─ style.py
 ├─ requirements.txt
 └─ .env.example

 ## 새 기능: 텍스트파일 기반 플레이리스트 분석
- `playlist_search_server.py` : 단순한 텍스트 파일(`가수 - 곡명` 줄 단위)을 받아서, 각 곡에 대해 구글 검색으로 분위기를 유추
- 결과를 종합해 전체 플레이리스트의 라벨(`잔잔한`, `신나는`, `파티` 등)을 반환

> ⚠️ 실제 서비스에서는 구글 스크래핑 대신 Last.fm, MusicBrainz API 등을 활용하는 것이 안정적이고 합법적임
