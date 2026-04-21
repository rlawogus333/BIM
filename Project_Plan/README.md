
# 🏗️ Revit-MCP 기반 AI 조명 설계 자동화 솔루션
> **KDS/KEC 전기설비 기술 기준 준수 및 Claude MCP를 활용한 BIM 자동 배치 프로젝트**

본 프로젝트는 기존의 복잡한 Dynamo 스크립트 기반 워크플로우를 **Claude Desktop**과 **revit-mcp** 환경으로 통합하여, 자연어 명령만으로 지하철역사 등 건축물의 조명 배치, 조도 계산, 그리고 법규 검증을 한 번에 수행하는 차세대 BIM 자동화 시스템입니다.

---

## 📅 프로젝트 타임라인 (8주)

| 단계 | 기간 | 상태 | 주요 내용 |
| :--- | :---: | :---: | :--- |
| **Phase 1** | 1~2주차 | ✅ | KDS/KEC 규칙 DB 구축 → rules_db.json + pytest |
| **Phase 2** | 3~5주차 | ✅ | Dynamo 자동배치 엔진 → revit-mcp 전환 중 |
| **Phase 3** | 6~7주차 | ✅ | Claude MCP 서버 검증 연동 → FastAPI 서버 + 피드백 |
| **Phase 4** | 8주차 | 🔄 | **revit-mcp 통합 + 최종 산출물 (진행 중)** |

---

## 🛠️ 주요 구현 현황

### 1. 규칙 DB 구축 (Phase 1) ✅
- [x] KDS 31 17 00 / KEC 전기설비기술기준 및 소방시설 조항 추출
- [x] 구글 시트 기반 3탭 구성 (space_rules / lighting_calc / fixture_family)
- [x] `excel_to_json.py` → `rules_db.json` 생성
- [x] `pytest` 단위 테스트 전체 통과 (129개)

### 2. Dynamo → Revit-MCP 전환 (Phase 2) ✅
기존 6종의 Dynamo 스크립트 로직을 **revit-mcp**로 완전히 대체하여 파이프라인을 간소화했습니다.

| 기존 스크립트 | 대체 방안 |
| :--- | :--- |
| 01_collect_spaces.py | revit-mcp `get_current_view_elements` |
| 02_match_space_type.py | FastAPI `/spaces` 직접 호출 |
| 03_lumen_calc.py | FastAPI `/calculate` 직접 호출 |
| 04~05_place_elements.py | revit-mcp `create_point_based_element` |
| 06_mcp_client.py | Claude Desktop ↔ FastAPI 직접 MCP 통합 |

### 3. MCP 서버 구축 (Phase 3) ✅
- [x] FastAPI 기반 MCP 도구 구성 (validate_design, get_rules, calc_load)
- [x] Claude API 연동을 통한 설계 적합성 자연어 피드백 시스템 구축

---

## 🚀 8주차 진행 상세 (Phase 4) 🔄

- [x] **4-A: 환경 준비**: Node.js 18+ 설치 및 revit-mcp 빌드 완료
- [ ] **4-B: Claude Desktop 설정**: `claude_desktop_config.json` 서버 등록 및 연결 확인
- [ ] **4-C: Revit 모델 자동 생성**: Level 생성, Wall 구획, MEP Space 생성 자동화
- [ ] **4-D: 조명 자동배치 파이프라인**: 공간 수집 → 계산 → 배치 → 검증 일괄 실행
- [ ] **4-E: E2E 테스트**: 5개 공간(대합실, 승강장 등) 유형별 조도 및 간격 기준 충족 확인
- [ ] **4-F: 최종 산출물**: 샘플 BIM 모델 완성 및 시연 영상(3분 이내) 제작

---

## 📐 시스템 아키텍처

```mermaid
graph TD
    A[Claude Desktop - AI Orchestra] --> B[MCP Connection #1: revit-mcp]
    A --> C[MCP Connection #2: FastAPI Server]
    
    subgraph "Revit Environment"
    B --> D[Node.js Server]
    D -- Socket -- > E[Revit Plugin]
    E --> F[BIM Model Manipulation]
    end
    
    subgraph "Logic & Rules"
    C --> G[KDS/KEC DB]
    C --> H[Lighting Calc Engine]
    C --> I[Design Validator]
    end
