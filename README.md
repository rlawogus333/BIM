# 지하철역 전기설비 BIM 자동화 시스템

> **AI-BIM 기반 전기설비 자동화 설계** — 자연어 한 마디로 조명·콘센트·유도등을 배치하고 KDS/KEC/NFPC 법규를 실시간 검증합니다.
>
> **TEAM BEST** · 엔지니어링 산업경진대회 BIM 부문 (1차 평가 통과)

철도 전기설비 설계기준(KDS)·한국전기설비규정(KEC)·화재안전성능기준(NFPC)을 JSON으로 코드화하고, **revit-mcp**로 Revit에 설비를 자동 배치한 뒤, **FastAPI MCP 서버**가 기준 위반을 검출해 **Claude API**가 자연어로 피드백하는 엔드투엔드 BIM 자동화 파이프라인입니다.

---

## 목차

- [핵심 아이디어](#핵심-아이디어)
- [시스템 아키텍처](#시스템-아키텍처)
- [대상 공간 5종](#대상-공간-5종)
- [저장소 구조](#저장소-구조)
- [빠른 시작](#빠른-시작)
- [Claude Desktop 이중 MCP 연결](#claude-desktop-이중-mcp-연결)
- [핵심 계산 로직](#핵심-계산-로직)
- [검증 규칙 V001~V012](#검증-규칙-v001v012)
- [테스트](#테스트)
- [문서](#문서)
- [참고 기준 및 문헌](#참고-기준-및-문헌)
- [팀 구성](#팀-구성)

---

## 핵심 아이디어

**법규를 코드가 아니라 데이터로 분리한다.** 기준이 개정되면 `rules_db.json` 한 파일만 갱신하면 계산·검증·피드백 전 과정에 즉시 반영됩니다.

| 구분 | 기존 방식 | 본 시스템 |
| :--- | :--- | :--- |
| 설계 방식 | 수동 배치 / Dynamo 스크립트 | 자연어 명령 → Claude 자동 배치 |
| 법규 검증 | 육안 검토 → 오류 빈번 | JSON 규칙 DB 기반 실시간 자동 검증 |
| 오류 대응 | 담당자 수동 재검토 | 자연어 피드백 + 자동 재설계 |
| 법규 개정 | 스크립트·도면 전면 수정 | `rules_db.json` 갱신 → 즉시 반영 |

기존 **Dynamo 스크립트 6종**을 revit-mcp의 **24개 MCP Tool + FastAPI MCP 10개 도구**로 대체해 파이프라인을 단순화했습니다. (Dynamo 원본은 `legacy/dynamo/`에 기록 보존)

---

## 시스템 아키텍처

```
┌───────────────────────────────────────────────────────────────┐
│                       Claude Desktop                          │
│                  (자연어 인터페이스 · 오케스트레이터)            │
└──────────────┬───────────────────────────┬────────────────────┘
               │ stdio                     │ stdio
     ┌─────────▼──────────┐      ┌─────────▼──────────────────┐
     │     revit-mcp      │      │   subway-bim-fastapi       │
     │   (Node.js MCP)    │      │      (Python MCP)          │
     │                    │      │                            │
     │ · 뷰/요소 조회      │      │ · 규칙 조회 (KDS/KEC/NFPC)  │
     │ · Level/Wall 생성   │      │ · 광속법 조도 계산          │
     │ · 조명·유도등 배치   │      │ · 설계 적합성 검증 (V001~)  │
     │ · C# 코드 직접 주입  │      │ · 분전반 용량·차단기 선정    │
     └─────────┬──────────┘      │ · Claude AI 자연어 피드백    │
               │ TCP 8080        └─────────┬──────────────────┘
     ┌─────────▼──────────┐                │
     │  revit-mcp-plugin  │      ┌─────────▼──────────────────┐
     │    (C# Revit API)  │      │    src/rules_db.json       │
     └─────────┬──────────┘      │  (KDS/KEC/NFPC 코드화)      │
               │                 └────────────────────────────┘
     ┌─────────▼──────────┐
     │   Autodesk Revit   │
     └────────────────────┘
```

### 실행 흐름

```
사용자 자연어 명령
  → Claude 의도 판단 및 계획
  → [revit-mcp]      Revit 3D 모델링 · 설비 자동 배치
  → [FastAPI MCP]    KDS/KEC/NFPC 규칙 검증
  → Claude           자연어 피드백 리포트
  → (위반 검출 시)    자동 재설계 루프
```

MCP 래퍼는 별도 uvicorn 프로세스를 띄우지 않고 `main.py`의 함수를 **in-process로 직접 호출**합니다. 포트 충돌이 없고 HTTP hop이 제거되어 응답이 빠릅니다.

자세한 내용은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 참고.

---

## 대상 공간 5종

| space_key | 공간 | 기준 조도 | 비상조명 | 핵심 요구사항 |
| :--- | :--- | ---: | ---: | :--- |
| `concourse` | 대합실 | 300 lux | 30 lux | CCTV 전용회로, 대형피난구유도등, BF 설계 |
| `platform` | 승강장 | 200 lux | 20 lux | CCTV 전용회로, 스크린도어(PSD) 무순단 전원 |
| `corridor` | 통로·계단 | 150 lux | 10 lux | 복도통로유도등 2 m 간격(강화설계), 바닥 매립 |
| `machinery` | 기계실 | 200 lux | 15 lux | 방폭등 Ex e IIC T4, 접지 10 Ω 이하 |
| `station_office` | 역무실 | 500 lux | 30 lux | UPS 10 kVA / 30분, 전용회로, 액세스플로어 |

> 지하역사는 NFPC 303 제10조②에 따라 **비상전원 60분 이상**이 전 공간 공통 적용됩니다.

---

## 저장소 구조

```
BIM/
├── src/                                 # 실행 코드
│   ├── main.py                          #   FastAPI 백엔드 (REST API)
│   ├── fastapi_mcp_wrapper.py           #   MCP stdio 래퍼 (Claude Desktop 연결)
│   ├── excel_to_json.py                 #   Excel → rules_db.json 변환기
│   └── rules_db.json                    #   규칙 DB v2.0.0 (런타임 로드 대상)
│
├── tests/                               # pytest 104개
│   ├── test_rules.py                    #   규칙 DB 무결성 (71개)
│   ├── test_phase3.py                   #   FastAPI 엔드포인트 (33개)
│   └── conftest.py                      #   src/ import 경로 설정
│
├── data/
│   ├── BIM_elec_data.xlsx               # 규칙 원본 스프레드시트 (6개 시트)
│   ├── sheets/                          #   구글 시트 Apps Script (.gs)
│   ├── standards/                       #   KDS·KEC 원문 PDF
│   └── stations/                        #   서울교통공사 역사 건축정보 공공데이터
│
├── docs/
│   ├── ARCHITECTURE.md                  # 시스템 구조 상세
│   ├── RULES_DB.md                      # rules_db.json 스키마 명세
│   ├── DATA_COLLECTION.md               # 법규 데이터 수집·정규화 과정
│   ├── CLAUDE_DESKTOP_SETUP.md          # 이중 MCP 연결 가이드
│   ├── PROJECT_PLAN.md                  # 8주 프로젝트 진행 기록
│   ├── KNOWN_ISSUES.md                  # 알려진 제약 및 개선 과제
│   ├── presentation/                    # 발표자료 (PDF, 15슬라이드)
│   └── references/                      # 참고 논문
│
├── config/
│   └── claude_desktop_config.example.json
│
├── legacy/dynamo/                       # revit-mcp 이전 Dynamo 스크립트 (보존용)
└── revit-mcp/                           # revit-mcp 배포본 및 연동 계획
```

### 데이터 흐름

```
data/BIM_elec_data.xlsx          src/excel_to_json.py          src/rules_db.json
(space_rules / seismic_req   →   (컬럼 매핑 · 단위 변환 ·   →   spaces
 power_equip / lighting_calc      검증 규칙 생성)                fixture_families
 fixture_family /                                               validation_rules
 regulation_index)                                              lighting_formula
                                                                standards_glossary
                                                                compliance_matrix
                                                                     ↓
                                                    main.py / fastapi_mcp_wrapper.py 로드
```

---

## 빠른 시작

### 요구사항

| 항목 | 버전 |
| :--- | :--- |
| Python | 3.10 이상 (`dict[str, str]`, `str \| None` 문법 사용) |
| Node.js | 18 이상 (revit-mcp 사용 시) |
| Autodesk Revit | 2025 + revit-mcp-plugin (3D 연동 시) |
| Anthropic API 키 | AI 피드백 기능 사용 시 |

### 설치

```bash
git clone https://github.com/rlawogus333/BIM.git
cd BIM
pip install -r requirements.txt

cp .env.example .env        # ANTHROPIC_API_KEY 입력
```

### FastAPI 서버 실행

```bash
cd src
uvicorn main:app --reload --port 8000
```

Swagger UI → <http://localhost:8000/docs>

```bash
curl http://localhost:8000/
# {"status":"ok","version":"2.0.0","standards":[...]}

curl -X POST http://localhost:8000/calculate/lighting \
  -H "Content-Type: application/json" \
  -d '{"space_key":"concourse","area_m2":2165,"length_m":60,"width_m":36}'
# → required_fixtures: 172,  actual_lux_estimate: 300.3
```

### 규칙 DB 재생성

```bash
cd src
python excel_to_json.py --input ../data/BIM_elec_data.xlsx --output rules_db.json
```

> ⚠️ 현재 `excel_to_json.py` 출력(v1.0.0 스키마)은 커밋된 `rules_db.json`(v2.0.0)보다 필드가 적어 그대로 덮어쓰면 서버가 동작하지 않습니다.
> 반드시 [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md)를 먼저 확인하세요.

---

## Claude Desktop 이중 MCP 연결

`config/claude_desktop_config.example.json`을 아래 위치에 복사하고 경로·API 키를 실제 값으로 바꿉니다.

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "subway-bim-fastapi": {
      "command": "python",
      "args": ["C:/dev/BIM/src/fastapi_mcp_wrapper.py"],
      "env": { "ANTHROPIC_API_KEY": "sk-ant-...", "PYTHONIOENCODING": "utf-8" }
    },
    "revit-mcp": {
      "command": "node",
      "args": ["C:/dev/revit-mcp/build/index.js"]
    }
  }
}
```

연결 확인 절차와 트러블슈팅은 [docs/CLAUDE_DESKTOP_SETUP.md](docs/CLAUDE_DESKTOP_SETUP.md) 참고.

### 사용 예시

```
"일반적인 지하철 대합실을 설계해줘"
  → Claude가 공간·벽체·천장·기둥을 판단해 Revit에서 3D 모델링

"대합실 전기설비를 설계하고 법규 검증해줘"
  → revit-mcp로 조명·콘센트·유도등 배치
  → calculate_lighting / validate_design 호출
  → 조도 미달 구역 자동 감지 → 자연어 피드백 → 실시간 재설계
```

---

## 핵심 계산 로직

### 광속법 조도 계산 (KDS 32 30 10 §4.7)

```
N = (E × A) / (F × U × M)

N : 필요 조명기구 수 (개)          E : 설계 조도 (lux)
A : 공간 면적 (m²)                F : 기구당 총 광속 (lm)
U : 조명률 (실지수·반사율로 결정)   M : 보수율 (청소주기·등기구 형태 반영)
```

실지수를 먼저 구하고, 조명률은 실지수와 천장·벽 반사율로 근사합니다.

```
K  = (L × W) / (H × (L + W))
U  = min( 0.40 + 0.10 × min(K, 3.0)/3.0 + 천장반사율 × 0.15 + 벽반사율 × 0.05 , 0.70 )
```

### 분전반 용량 산출 (KDS 32 25 10 §4.1.2)

```
공간별 부하 = 조명(60 %) + 콘센트(30 %) + CCTV + 특수부하(PSD·UPS)
설비용량 → 수요부하 (× 0.7) → 설계부하 (× 1.25)
설계전류 I = P / (√3 × V × PF)   [3상]   /   I = P / (V × PF)   [1상]
→ 표준 차단기(AT) · 분전반(kVA) 자동 선정
```

### MCP 도구 10종

| 도구 | 용도 |
| :--- | :--- |
| `health_check` | 규칙 DB 버전 / 공간 수 / 검증 규칙 수 |
| `list_spaces` | 5개 공간 유형 요약 |
| `get_space` | 특정 공간의 전체 KDS/KEC 규칙 |
| `list_fixtures` | 조명·설비 Revit Family 매핑 |
| `list_validation_rules` | 검증 규칙 목록 |
| `calculate_lighting` | 광속법 조명기구 수량 산출 |
| `calculate_load` | 분전반 용량·차단기 선정 |
| `validate_design` | 설계 데이터 KDS/KEC 검증 |
| `validate_batch` | 여러 공간 일괄 검증 |
| `ai_analyze` | Claude 자연어 개선 피드백 |

---

## 검증 규칙 V001~V012

| ID | 규칙 | 적용 공간 | 심각도 | 근거 | 구현 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| V001 | 조도 기준 미달 | 전체 | error | KDS 32 30 10 §4.3 / KS A 3011 | ✅ |
| V002 | 통로·계단 유도등 간격 초과 | corridor | error | NFPC 303 §6①나 + 프로젝트 강화기준 | ✅ |
| V003 | 방폭등 미설치 | machinery | error | KEC 242.2 | ✅ |
| V004 | UPS 전원 미연결 | station_office | error | KDS 32 20 20 §4.3 / KDS 47 40 45 §1.7.1 | ✅ |
| V005 | CCTV 전용회로 미구성 | concourse, platform | warning | KDS 31 10 21 §4.5 | ✅ |
| V006 | 비상조명 조도 미달 | 전체 | error | NFPC 303 / KS C 7654 | ✅ |
| V007 | 콘센트 간격 초과 | 전체 | warning | KDS 32 25 10 §4.1.2 | ✅ |
| V008 | 접지 미설치 | machinery | error | KEC 140·142 / KDS 32 40 20 | ✅ |
| V009 | 비상전원 백업시간 부족 | 전체 | error | NFPC 303 §10② | ⚠️ |
| V010 | 복도 바닥 유도등 미설치 | corridor | warning | NFPC 303 §6①다 단서 | ⚠️ |
| V011 | 스크린도어 무순단 전원 미공급 | platform | error | KDS 47 40 45 §1.7.1·1.7.2 | ⚠️ |
| V012 | 유도등 설치 높이 미준수 | 전체 | warning | NFPC 303 §5②·§6①다·§6③ | ⚠️ |

✅ = `main.py`에 검증 분기 구현 완료 · ⚠️ = `rules_db.json`에 정의만 있고 분기 미구현 ([KNOWN_ISSUES](docs/KNOWN_ISSUES.md) 참고)

> **V002 설계 판단**: NFPC 303이 규정한 복도통로유도등 최대 간격은 20 m이지만, 지하역사 피난 안전을 고려해 **2 m 간격 강화 설계**를 적용했습니다. 규정 최소값과 프로젝트 설계값을 `rules_db.json`에 각각 `guidance_spacing_regulatory_max_m` / `guidance_spacing_m`으로 분리 기록해 판단 근거를 남겼습니다.

---

## 테스트

```bash
pip install -r requirements.txt
pytest                # 저장소 루트에서 실행
```

```
tests/test_rules.py    71 passed   # rules_db.json 무결성·스키마·값 범위
tests/test_phase3.py   33 passed   # FastAPI 엔드포인트·계산 로직
─────────────────────────────────
                      104 passed
```

`legacy/dynamo/test_dynamo_offline.py`는 Dynamo 시절 오프라인 테스트로, 현재 파이프라인에서는 실행되지 않습니다.

---

## 문서

| 문서 | 내용 |
| :--- | :--- |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 4계층 구조, MCP 통신 방식, 모듈별 책임 |
| [RULES_DB.md](docs/RULES_DB.md) | `rules_db.json` 전체 스키마 명세 |
| [DATA_COLLECTION.md](docs/DATA_COLLECTION.md) | 법규 데이터 수집 출처 및 정규화 과정 |
| [CLAUDE_DESKTOP_SETUP.md](docs/CLAUDE_DESKTOP_SETUP.md) | 이중 MCP 연결·검증·트러블슈팅 |
| [PROJECT_PLAN.md](docs/PROJECT_PLAN.md) | 8주 단계별 진행 기록 |
| [KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | 알려진 제약, 재현 방법, 개선 방향 |

---

## 참고 기준 및 문헌

### 국가 표준

| 코드 | 제목 | 발행 |
| :--- | :--- | :--- |
| KDS 31 17 00 | 철도 전기설비 설계기준 | 국토교통부 |
| KDS 32 30 10 | 옥내조명설비 (2024) | 국토교통부 |
| KDS 32 20 20 | 예비전원설비 | 국토교통부 |
| KDS 32 25 10 | 간선 및 배선설비 | 국토교통부 |
| KDS 32 17 10 | 전기설비 내진설계기준 | 국토교통부 |
| KDS 47 40 45 | 철도 전원설비 (2019) | 국토교통부 |
| KEC | 한국전기설비규정 | 산업통상자원부 |
| NFPC 303 | 유도등 및 유도표지의 화재안전성능기준 (2024.1.1 시행) | 소방청 |
| KS A 3011 | 조도기준 | 한국표준협회 |

원문 PDF는 `data/standards/`, 조항별 정리는 `src/rules_db.json`의 `standards_glossary` 섹션과 [docs/RULES_DB.md](docs/RULES_DB.md)에 있습니다.

### 참고 논문

Elsayed, S., Ali, M., & Gupta, D. (2026). *Orchestrating LLM-Powered Workflows for Autodesk Revit via Model Context Protocol: A Multi-Agent Framework for Intelligent BIM Automation.* ICCCBE 2026, Taipei, Taiwan.
→ [docs/references/ICCCBE2026_Elsayed_LLM-Revit-MCP.pdf](docs/references/ICCCBE2026_Elsayed_LLM-Revit-MCP.pdf)

> 발표자료에 인용한 "설계 시간 75~80 % 단축 / 위반 검출률 90~95 %"는 **본 시스템의 측정치가 아니라 위 논문이 보고한 수치**입니다.

### 외부 프로젝트

- [revit-mcp](https://github.com/mcp-servers-for-revit/revit-mcp) — Node.js MCP 서버
- [revit-mcp-plugin](https://github.com/mcp-servers-for-revit/revit-mcp-plugin) — Revit C# 플러그인
- [mcp-servers-for-revit](https://github.com/mcp-servers-for-revit/mcp-servers-for-revit) — 배포본

---

## 팀 구성

**TEAM BEST**

| 이름 | 역할 |
| :--- | :--- |
| **김재현** (팀장) | 서버 구축 및 전체 프로세스 관리 — 기획·시스템 설계·구현 주도 |
| 김창민 | 법규 데이터 자료 수집 |
| 박환희 | 법규 데이터 JSON 코드화 |
| 이은준 | 데이터베이스 관리 및 자료조사 |

---

## 라이선스

MIT License — [LICENSE](LICENSE) 참고.

`data/standards/`, `data/stations/`, `docs/references/`, `revit-mcp/*.zip`은 각 원저작자에게 저작권이 있으며 참고·학술 목적으로 포함되어 있습니다.
