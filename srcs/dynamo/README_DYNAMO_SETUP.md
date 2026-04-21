# Dynamo 자동배치 스크립트 가이드

## 파일 구성

```
dynamo_scripts/
├── 01_collect_spaces.py      # Step 1: Revit Space 수집
├── 02_match_space_type.py     # Step 2: 공간 유형 키워드 매칭
├── 03_lumen_calc.py           # Step 3: 루멘법 조도 계산
├── 04_place_fixtures.py       # Step 4: 조명기구 자동 배치
├── 05_place_emergency.py      # Step 5: 비상등·유도등 배치
├── 06_mcp_client.py           # Step 6: FastAPI 서버 HTTP 호출
├── test_dynamo_offline.py     # 오프라인 단위 테스트 (25개)
└── README_DYNAMO_SETUP.md     # 이 파일
```

## Dynamo 노드 연결 순서

```
[01_collect_spaces] ──→ [02_match_space_type] ──→ [03_lumen_calc] ─┬→ [04_place_fixtures]
                              ↑                                     └→ [05_place_emergency]
                        rules_db.json 경로                                    
                                                                   [06_mcp_client] (독립 호출)
```

## Dynamo 설정 방법

### 1. Python Script 노드 추가
각 .py 파일마다 Dynamo에서 `Python Script` 노드를 추가하고 코드를 붙여넣기합니다.

### 2. 노드별 입력(IN) 연결

| 노드 | IN[0] | IN[1] | IN[2] |
|------|-------|-------|-------|
| 01 | (없음 — 자동 수집) | — | — |
| 02 | 01번 출력 | rules_db.json 경로 (String) | — |
| 03 | 02번 출력 | — | — |
| 04 | 03번 출력 | rules_db.json 경로 | dry_run (Boolean) |
| 05 | 03번 출력 | rules_db.json 경로 | dry_run (Boolean) |
| 06 | API URL (String) | action (String) | payload (dict) |

### 3. rules_db.json 경로
Dynamo `String` 노드에 rules_db.json의 절대 경로를 입력합니다.
예: `C:\BIM_Project\rules_db.json`

### 4. dry_run 모드
- `True`: 기구를 배치하지 않고 좌표만 계산하여 반환 (미리보기)
- `False`: 실제 Revit 모델에 FamilyInstance 배치

**항상 dry_run=True로 먼저 테스트한 후, 결과 확인 후 False로 실행하세요.**

### 5. Revit Family 사전 로드
04, 05번 노드 실행 전, 아래 Family가 Revit에 로드되어 있어야 합니다:

| Family 이름 | 용도 |
|------------|------|
| Lighting Fixture - Fluorescent - Surface | 천장형 형광등 (대합실/승강장/역무실) |
| Lighting Fixture - Explosion Proof | 방폭등 (기계실) |
| Lighting Fixture - Corridor | 통로형 등기구 |
| Emergency Lighting - Battery | 비상조명등 |
| Exit Sign - LED | 유도등 |

## MCP 서버 (06번) 사용법

### 서버 시작
```bash
cd /path/to/project
uvicorn main:app --reload --port 8000
```

### Dynamo에서 호출
06번 노드 입력:
- IN[0] = `"http://localhost:8000"`
- IN[1] = 액션명 (아래 표 참고)
- IN[2] = 요청 데이터 (dict)

### 지원 액션

| 액션 | 메서드 | 설명 |
|------|--------|------|
| health | GET | 서버 상태 확인 |
| spaces | GET | 전체 공간 목록 |
| space_detail | GET | 특정 공간 상세 (payload: {"space_key": "concourse"}) |
| fixtures | GET | 조명기구 Family 목록 |
| calculate | POST | 루멘법 조도 계산 |
| validate | POST | 단일 공간 설계 검증 |
| validate_batch | POST | 다수 공간 일괄 검증 |
| ai_analyze | POST | Claude AI 위반 분석 |
| ai_suggest | POST | Claude AI 기구 배치 제안 |
| workflow | POST | 전체 워크플로우 (계산→검증→AI) |

### 워크플로우 예시
```
IN[1] = "workflow"
IN[2] = 02번 노드 출력 (enriched_spaces)
```
→ 각 공간별 조도 계산 → 설계 검증 → 위반 시 AI 분석까지 자동 수행

## 오프라인 테스트
```bash
pytest test_dynamo_offline.py -v
```
Revit 없이 핵심 로직(키워드 매칭, 루멘법, 그리드, 비상등 수량, MCP 액션)을 검증합니다.
