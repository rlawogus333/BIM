# 시스템 아키텍처

지하철역 전기설비 BIM 자동화 시스템의 계층 구조, 모듈별 책임, 통신 방식을 정리한 문서입니다.

---

## 1. 4계층 구조

```
┌────────────────────────────────────────────────────────────────┐
│ Layer 1 — 오케스트레이션                                         │
│   Claude Desktop                                               │
│   · 사용자 자연어 입력 해석                                       │
│   · 어떤 MCP 도구를 어떤 순서로 호출할지 계획(planning)            │
│   · 두 MCP 서버의 응답을 종합해 자연어 리포트 생성                 │
└───────────────┬───────────────────────────┬────────────────────┘
                │ stdio (MCP)               │ stdio (MCP)
┌───────────────▼─────────────┐ ┌───────────▼────────────────────┐
│ Layer 2a — BIM 실행          │ │ Layer 2b — 규칙 엔진            │
│   revit-mcp (Node.js)       │ │   subway-bim-fastapi (Python)  │
│   · MCP 도구 24종 노출        │ │   · MCP 도구 10종 노출           │
│   · Revit 플러그인에 명령 전달 │ │   · main.py 로직 in-process 호출 │
└───────────────┬─────────────┘ └───────────┬────────────────────┘
                │ TCP 8080                  │ 함수 호출
┌───────────────▼─────────────┐ ┌───────────▼────────────────────┐
│ Layer 3 — BIM 플랫폼         │ │ Layer 3 — 규칙 데이터            │
│   revit-mcp-plugin (C#)     │ │   rules_db.json                │
│   Autodesk Revit            │ │   · spaces / fixture_families  │
│   · Level, Wall, Space 생성  │ │   · validation_rules           │
│   · FamilyInstance 배치      │ │   · lighting_formula           │
└─────────────────────────────┘ └────────────────────────────────┘
```

---

## 2. 모듈별 책임

### `src/main.py` — FastAPI 백엔드

REST API와 핵심 계산 로직을 모두 보유한 단일 모듈입니다. MCP 래퍼가 이 모듈의 함수를 직접 import 하므로, **비즈니스 로직의 유일한 출처(single source of truth)** 역할을 합니다.

| 구역 | 내용 |
| :--- | :--- |
| Pydantic 모델 | `SpaceInput`, `LightingCalcRequest`, `ValidationInput`, `LoadCalcRequest` 등 |
| 내부 유틸리티 | `get_space_rule`, `calc_room_index`, `estimate_cu`, `run_validation_rules`, `calc_space_load`, `select_breaker`, `select_panel_kva` |
| 라우터 | `/spaces`, `/fixtures`, `/validation-rules`, `/calculate/*`, `/validate/*`, `/import/*`, `/ai/*` |

규칙 DB는 모듈 로드 시점에 `rules_db` 전역 변수로 한 번 읽습니다(`load_rules_db()`). `/import/excel?apply=true` 호출 시에만 메모리와 파일이 함께 교체됩니다.

### `src/fastapi_mcp_wrapper.py` — MCP stdio 래퍼

`FastMCP`로 MCP 서버를 구성하고, `main.py`의 함수·Pydantic 모델을 import 해 도구로 노출합니다.

설계 판단:

- **별도 uvicorn 프로세스를 띄우지 않음** — 포트 충돌이 없고 HTTP hop이 제거되어 응답이 빠릅니다.
- **로그는 stderr로** — MCP 프로토콜이 stdout을 사용하므로 stdout 오염을 피합니다.
- **`.env` 자동 로드** — Claude Desktop이 stdio로 기동할 때 CWD가 불확실하므로, 래퍼와 같은 폴더의 `.env`를 강제로 읽습니다. `python-dotenv` 미설치는 치명적이지 않습니다.

디버깅 목적으로 `uvicorn main:app --port 8000`을 별도 터미널에서 병행 실행해도 MCP 래퍼와 독립적으로 동작합니다.

### `src/excel_to_json.py` — 규칙 DB 변환기

스프레드시트 컬럼명을 내부 필드명으로 매핑하고, 단위를 변환하며(백분율→비율), 검증 규칙과 조도 공식 정의를 코드에서 생성합니다.

| 매핑 테이블 | 역할 |
| :--- | :--- |
| `SPACE_RULES_COL_MAP` | `space_id` → `space_key`, `cctv_power` → `cctv_circuit` 등 |
| `LIGHTING_CALC_COL_MAP` | `maint_factor_M` → `maintenance_factor`, `refl_ceil_%` → 비율 변환 |
| `FIXTURE_FAMILY_COL_MAP` | `revit_family` → `revit_family_name`, `applicable_space` → 영문 키 리스트 |
| `SPACE_ID_TO_KEY` | `SR-01` → `concourse` |
| `SPACE_KR_TO_KEY` | `대합실` → `concourse` |

`excel_bytes_to_rules_db(data: bytes)`는 파일 I/O 없이 메모리에서 처리하므로 FastAPI의 `UploadFile`과 직접 연결됩니다(`/import/excel`).

> ⚠️ 현 시점 이 스크립트의 출력은 `rules_db.json` v2.0.0 스키마를 완전히 충족하지 않습니다. [KNOWN_ISSUES.md](KNOWN_ISSUES.md) §2 참고.

### `src/rules_db.json` — 규칙 데이터베이스

전 시스템이 참조하는 유일한 기준 데이터입니다. 스키마는 [RULES_DB.md](RULES_DB.md)에 정리되어 있습니다.

---

## 3. 통신 방식

### Claude Desktop ↔ MCP 서버 (stdio)

두 서버 모두 **stdio** 전송을 사용하므로 포트 충돌이 없습니다. Claude Desktop이 프로세스를 직접 기동하고 표준 입출력으로 JSON-RPC를 주고받습니다.

```
mcpServers
 ├─ revit-mcp             ← Node.js 프로세스, 내부에서 Revit 소켓 8080 연결
 └─ subway-bim-fastapi    ← Python 프로세스, main.py 함수 in-process 호출
```

### revit-mcp ↔ Revit (TCP 8080)

revit-mcp(Node.js)가 클라이언트, Revit 플러그인이 서버입니다. Revit 패널에서 MCP Server가 "Running" 상태여야 연결됩니다.

---

## 4. 대표 시나리오 — 대합실 설계 및 검증

```
① 사용자
   "B1 대합실 전기설비를 설계하고 KDS 기준으로 검증해줘"

② Claude Desktop
   → revit-mcp: get_current_view_elements
     (현재 뷰의 Space 요소와 면적·치수 수집)

③ Claude Desktop
   → subway-bim-fastapi: calculate_lighting(
         space_key="concourse", area_m2=2165, length_m=60, width_m=36)
     ← required_fixtures=172, actual_lux_estimate=300.3,
       fixture_family="Lighting Fixture - LED Ceiling"

④ Claude Desktop
   → revit-mcp: create_point_based_element × 172
     (계산된 그리드 좌표에 조명기구 FamilyInstance 배치)

⑤ Claude Desktop
   → subway-bim-fastapi: validate_design(
         space_key="concourse", calculated_lux=300.3,
         cctv_circuit_dedicated=False, ...)
     ← issues: [V005 CCTV 전용회로 미구성 (warning)]

⑥ Claude Desktop
   → subway-bim-fastapi: ai_analyze(space_key, validation_results)
     ← 위반 원인 · Revit 수정 방법 · 우선순위 한국어 리포트

⑦ (위반 시) ③~⑥ 재실행 — 자동 재설계 루프
```

---

## 5. 설계 판단 기록

### 왜 Dynamo를 걷어냈는가

| 항목 | Dynamo 방식 | revit-mcp 방식 |
| :--- | :--- | :--- |
| 진입 장벽 | Python 노드 6개 수동 연결, 스크립트 전문성 필요 | 자연어 명령 |
| 파라미터 변경 | 고정 로직 → 스크립트 수정 필요 | Claude가 상황에 맞게 호출 조합 |
| API 미지원 항목 | 우회 불가 | `send_code_to_revit`으로 C# 직접 주입 |
| 디버깅 | 노드 단위 추적 어려움 | MCP 로그 + stderr |

Dynamo 스크립트 원본은 `legacy/dynamo/`에 기록으로 보존했습니다.

| 기존 스크립트 | 대체 방안 |
| :--- | :--- |
| `01_collect_spaces.py` | revit-mcp `get_current_view_elements` |
| `02_match_space_type.py` | FastAPI `/spaces` |
| `03_lumen_calc.py` | FastAPI `/calculate/lighting` |
| `04~05_place_*.py` | revit-mcp `create_point_based_element` |
| `06_mcp_client.py` | Claude Desktop ↔ FastAPI 직접 MCP 연결 |

### 왜 MCP 래퍼가 HTTP를 쓰지 않는가

MCP 래퍼가 `httpx`로 로컬 FastAPI를 호출하는 구조도 가능하지만, 그러면 사용자가 **uvicorn을 항상 띄워두어야** 하고 포트 관리 부담이 생깁니다. `main.py`를 import 해 in-process로 호출하면 Claude Desktop이 프로세스 하나만 관리하면 됩니다.

### 왜 규칙을 코드가 아닌 JSON에 두는가

법규는 코드보다 자주, 그리고 코드와 무관한 이유로 바뀝니다. 조도 기준값이 `if space == "concourse": return 300` 형태로 코드에 박히면 개정 시 코드 리뷰·테스트·배포가 모두 필요하지만, JSON이면 데이터 변경 한 번으로 끝나고 `tests/test_rules.py`가 무결성을 지켜줍니다.

---

## 6. 개발 중 해결한 주요 이슈

| 이슈 | 원인 | 해결 |
| :--- | :--- | :--- |
| `commandRegistry.json` 설정 오류 | MCP 서버와 Revit 플러그인 간 명령어 등록 매핑 불일치 | 설정 파일 재구성으로 명령어 이름·핸들러 매핑 정렬 |
| GUID 충돌 | Revit 요소 생성 시 중복 GUID 발생 | 식별 로직 개선 |
| Face-hosted 조명 패밀리 제약 | 일부 조명 패밀리가 반드시 면(Face)에 종속되어야 배치 가능 | 호스트 요소(천장) 배치 순서를 앞당겨 우회 |
| 한글 깨짐 | Claude Desktop stdio 기동 시 인코딩 미지정 | `PYTHONIOENCODING=utf-8` 환경변수 설정 |
| `.env` 미로드 | stdio 기동 시 CWD가 프로젝트 폴더가 아님 | 래퍼가 `Path(__file__).parent / ".env"`를 명시적으로 로드 |
