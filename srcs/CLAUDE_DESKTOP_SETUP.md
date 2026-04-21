# Phase 4-B: Claude Desktop MCP 설정 가이드

> 대상: 지하철역 전기설비 BIM 자동화 (revit-mcp + subway-bim-fastapi 이중 MCP 구성)

본 가이드는 Claude Desktop 에 두 개의 MCP 서버를 동시에 연결하고, 간단한
테스트로 통신이 정상인지 검증하는 절차를 설명한다.

---

## 0. 사전 확인

| 항목 | 확인 방법 |
|------|-----------|
| Node.js 18+ | `node --version` |
| Python 3.10+ | `python --version` |
| Claude Desktop | 최신 버전 설치 (Settings → Developer → Edit Config 메뉴 존재 확인) |
| Revit + revit-mcp-plugin | Revit 에서 MCP 소켓 서버 "Running" 상태 |
| 프로젝트 파이썬 패키지 | `pip install -r requirements.txt` |

`mcp[cli]` 패키지는 requirements.txt 에 추가됨. 혹시 수동 설치가 필요하면:

```bash
pip install "mcp[cli]>=1.2.0"
```

---

## 1. claude_desktop_config.json 등록

Claude Desktop 설정 파일 위치:

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

본 프로젝트 루트의 `claude_desktop_config.json` 을 위 경로로 복사한 뒤,
다음 3개 값을 **실제 로컬 경로/키**로 수정한다.

| 치환 대상 | 예시 |
|-----------|------|
| `C:\\dev\\revit-mcp\\build\\index.js` | revit-mcp 저장소의 빌드된 index.js 절대경로 |
| `C:\\dev\\subway-bim\\fastapi_mcp_wrapper.py` | 본 프로젝트의 `fastapi_mcp_wrapper.py` 절대경로 |
| `sk-ant-여기에-실제키-입력` | 본인의 Anthropic API 키 |

Windows 경로는 반드시 **역슬래시 2개(`\\`)** 또는 슬래시(`/`)로 작성한다
(JSON escape 규칙). 예: `"C:\\dev\\subway-bim\\fastapi_mcp_wrapper.py"`.

### 설정 파일 구조 요약

```
mcpServers
 ├─ revit-mcp              ← Node stdio (Revit 소켓 8080 으로 연결)
 └─ subway-bim-fastapi     ← Python stdio (main.py 로직을 in-process 호출)
```

두 서버 모두 **stdio** 방식이므로 포트 충돌은 없다. 내부 구현은 다음과 같다:

- **revit-mcp** — Node.js MCP 서버가 Revit 플러그인과 TCP 소켓(8080) 으로 통신
- **subway-bim-fastapi** — `fastapi_mcp_wrapper.py` 가 main.py 의 함수를
  직접 import 하여 실행 (uvicorn 별도 기동 불필요)

> FastAPI 의 `/docs` Swagger UI 를 병행해서 디버그하고 싶다면 별도 터미널에서
> `uvicorn main:app --port 8000` 을 그대로 띄워도 된다. MCP 래퍼와 독립적으로
> 동작한다.

---

## 2. 연결 상태 확인

1. Claude Desktop 을 **완전히 종료** (트레이에서 Quit) 후 재시작.
2. 새 대화를 열고 입력창 하단 **🔌 / 망치 아이콘**을 클릭.
3. 다음이 모두 **Connected** 로 표시되어야 한다:

   - ☑ `revit-mcp` (도구 20+개)
   - ☑ `subway-bim-fastapi` (도구 9개: health_check / list_spaces /
     get_space / list_fixtures / list_validation_rules / calculate_lighting /
     calculate_load / validate_design / validate_batch / ai_analyze)

### 연결 실패 시 디버그

| 증상 | 원인 & 조치 |
|------|-------------|
| `failed to connect` / 도구 목록이 뜨지 않음 | 경로 오타. `claude_desktop_config.json` 의 `args[0]` 가 실제 파일을 가리키는지 확인 |
| subway-bim-fastapi 만 실패 | 터미널에서 직접 실행 검증: `python C:\dev\subway-bim\fastapi_mcp_wrapper.py` — ImportError 로그가 stderr 로 뜨면 `pip install -r requirements.txt` |
| revit-mcp 만 실패 | Revit 이 실행 중인지, 플러그인 패널에서 MCP Server "Running" 상태인지 확인 |
| 한글 깨짐 | 설정의 `"PYTHONIOENCODING": "utf-8"` 유지 |

Claude Desktop 의 MCP 로그 위치:

- Windows: `%APPDATA%\Claude\logs\mcp-server-<name>.log`
- macOS: `~/Library/Logs/Claude/mcp-server-<name>.log`

---

## 3. 통신 검증 테스트

다음 3가지 짧은 명령을 Claude Desktop 대화창에 차례로 입력한다.

### 테스트 1: revit-mcp 통신 — `get_current_view_info`

> Revit 을 실행하고 임의의 뷰를 연 상태에서 수행한다.

**프롬프트:**
```
revit-mcp 의 get_current_view_info 도구를 호출해서 현재 뷰 정보를 알려줘.
```

**기대 응답:** 현재 뷰의 이름, 뷰 타입(FloorPlan/3D/Section 등),
축척, 레벨 정보가 JSON 으로 반환됨. 예:

```json
{
  "view_name": "Level 1",
  "view_type": "FloorPlan",
  "scale": 100,
  "level": "Level 1"
}
```

### 테스트 2: FastAPI MCP 통신 — `health_check` + `list_spaces`

**프롬프트:**
```
subway-bim-fastapi 의 health_check 와 list_spaces 도구를 호출해서
규칙 DB 가 잘 로드됐는지 확인해줘.
```

**기대 응답:**

- `health_check`: `{ status: "ok", version: "1.0.0", spaces_loaded: [...5개...] }`
- `list_spaces`: concourse / platform / corridor / machinery / station_office
  5개 공간이 각각 `illuminance_lux`(300/200/150/200/500) 값과 함께 반환

### 테스트 3: 두 MCP 교차 호출 — 조도 계산

**프롬프트:**
```
지하 1층 대합실(30m × 15m, 면적 450㎡)에 대해
subway-bim-fastapi 의 calculate_lighting 을 호출해서
필요한 조명기구 수량을 알려줘.
```

**기대 응답:** `required_fixtures`, `actual_lux_estimate`, `formula` 가
포함된 계산 결과 JSON. 이 수치를 다음 단계에서 revit-mcp 의
`create_point_based_element` 에 좌표와 함께 전달하게 된다.

---

## 4. 체크리스트 (Phase 4-B 완료 기준)

- [ ] `claude_desktop_config.json` 에 `revit-mcp` 서버 등록 ✅
- [ ] `claude_desktop_config.json` 에 `subway-bim-fastapi` 서버 등록 ✅
- [ ] Claude Desktop 재시작 후 두 서버 **Connected** 표시 확인
- [ ] 테스트 1 `get_current_view_info` 성공
- [ ] 테스트 2 `health_check` + `list_spaces` 성공
- [ ] 테스트 3 `calculate_lighting` 성공

모두 통과하면 **Phase 4-B 종료**. 다음은 Phase 4-C 에서 `create_level` /
`create_line_based_element` 로 실제 모델 자동 생성에 들어간다.

---

## 부록: 제공 도구 요약

### revit-mcp (Node.js, Revit Plugin 소켓 8080)

주요 도구 — `get_current_view_info`, `get_current_view_elements`,
`create_level`, `create_line_based_element`, `create_surface_based_element`,
`create_point_based_element`, `send_code_to_revit`, `delete_element`,
`operate_element`, `get_available_family_types`, `analyze_model_statistics`
등 총 24개.

### subway-bim-fastapi (Python stdio, main.py 로직 래핑)

| 도구 | 용도 |
|------|------|
| `health_check` | 규칙 DB 버전 / 공간 수 / 검증 규칙 수 확인 |
| `list_spaces` | 5개 공간 유형 요약 |
| `get_space` | 특정 공간의 전체 KDS/KEC 규칙 |
| `list_fixtures` | 조명·설비 Revit Family 매핑 |
| `list_validation_rules` | V001~V008 검증 규칙 목록 |
| `calculate_lighting` | 광속법 조명기구 수량 산출 |
| `calculate_load` | 분전반 용량·차단기 선정 |
| `validate_design` | 설계 데이터 KDS/KEC 검증 |
| `validate_batch` | 여러 공간 일괄 검증 |
| `ai_analyze` | Claude 자연어 개선 피드백 |
