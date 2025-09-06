 ```
 📦 프로젝트 구조 (마이크로서비스형 — "한 서버 = 한 역할")  
 ├─ README.md  
 ├─ servers/  
 │   ├─ ✅caption_server.py        # 이미지 캡션
 │   └─ ✅exif_server.py           # EXIF/위치/날씨 전용
 ├─ ✅main.py                      # 오케스트레이터 (여러 MCP 서버 호출)
 ├─ ✅schemas.py                   # Pydantic 스키마 (공유)
 ├─ utils/
 │   └─ ✅exif_geo.py
 ├─ requirements.txt
 └─ .env
```

# main.py

- def `_call_mcp_tool`
  - 서버를 stdio로 스폰하여 단일 tool 호출을 수행하고 결과 dict로 반환
    - stdio로 스폰: main.py가 MCP 서버 파이썬 파일을 서브프로세스로 실행하고, 표준입출력(standard input/output) 파이프를 통해 데이터를 주고받음 (네트워크 소켓 없이 로컬 파이프로 통신)
    ```python
    async def _call_mcp_tool(server_py, tool_name, arguments):
        # 1) 서버 프로세스 띄우기 (stdio)
        params = StdioServerParameters(command=sys.executable, args=[server_py], env=env)
        async with AsyncExitStack() as stack:
            # 2) stdio 파이프 붙이기
            read, write = await stack.enter_async_context(stdio_client(params))
            session = ClientSession(read, write)
            await stack.enter_async_context(session)
            # 3) MCP 초기화
            await session.initialize()
            # 4) tool 호출
            res = await session.call_tool(tool_name, arguments)
            # 5) payload 추출 → dict 반환
            return _extract_payload(res)
    ```
- def `_extract_payload`
  - _call_mcp_tool 결과물을 → dict/text 로 평탄화

# schemas.py

- Pydantic
  - FastAPI의 입출력을 정의, 데이터를 검증
  - 입출력 항목의 갯수와 타입 설정
  - 입출력 항목의 필수값 체크
  - 입출력 항목의 데이터 검증
  - Pydantic을 사용하기 위해 출력 스키마를 생성해야 함
- 스키마
  - 출력 스키마는 해당 도메인에서 schema.py로 관리
  - 데이터의 구조와 명세(출력항목 개수, 제약조건 등)
- [참고](https://rudaks.tistory.com/entry/python-pydantic%EB%9E%80-%EB%AC%B4%EC%97%87%EC%9D%B8%EA%B0%80)
