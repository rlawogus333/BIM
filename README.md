# 🏆 지하철역 전기설비 BIM 자동화 프로젝트
> **엔지니어링 산업경진대회 BIM 부문 (8주 완성 프로젝트)**

철도 전기설비 설계기준(KDS) 및 한국전기설비규정(KEC)을 코드화하고, **Revit-MCP**를 통해 조명·콘센트·유도등을 자동 배치하며, **Claude API**로 설계 적합성을 검증하는 차세대 BIM 자동화 시스템입니다.

---

## 🚀 프로젝트 핵심 개요
본 프로젝트는 기존 Dynamo의 한계를 극복하기 위해 **Claude Desktop**과 **MCP(Model Context Protocol)** 서버를 활용하여 자연어 명령만으로 **[모델 생성 → 설계 계산 → 자동 배치 → 법규 검증 → 피드백]**을 일괄 수행하는 엔드투엔드(End-to-End) 파이프라인을 구축합니다.

---

## 🛠️ 기술 스택 (Tech Stack)

| 구분 | 기술 스택 | 역할 |
| :--- | :--- | :--- |
| **BIM Platform** | **Revit + revit-mcp** | 모델 조회, 요소 생성 및 수정 (Node.js 기반) |
| **Rule Engine** | **Python FastAPI** | KDS/KEC 기반 조도 계산 및 검증 MCP 서버 |
| **Data Logic** | **rules_db.json** | 법규 및 설계 수치 데이터 코드화 |
| **AI Orchestra** | **Claude 3.5 Sonnet** | 설계를 제어하고 자연어로 피드백 리포트 생성 |
| **Automation** | **Claude Desktop** | revit-mcp + FastAPI 이중 MCP 연결 및 제어 |

---

## 🔄 자동화 워크플로우 (revit-mcp 기반)

기존 **Dynamo 스크립트 6종**의 의존성을 제거하고 **24개의 전용 MCP Tool**로 대체하여 효율을 극대화했습니다.

1. **모델 조회**: `Claude Desktop`이 `revit-mcp`를 통해 현재 뷰와 공간 데이터 수집
2. **설계 계산**: `FastAPI` 서버가 `rules_db`를 참조하여 공간별 조도 및 필요 기구수 계산
3. **자동 배치**: `revit-mcp`를 호출하여 조명, 비상등, 유도등을 좌표에 맞춰 자동 생성
4. **법규 검증**: `FastAPI` 설계 검증 도구가 KDS/KEC 기준 위반 여부 체크
5. **AI 피드백**: `Claude`가 최종 설계안에 대한 개선안을 자연어 리포트로 출력

---

## 🏢 핵심 공간 유형 (5종)

| 공간 코드 | 명칭 | 목표 조도 | 주요 설비 및 규정 |
| :--- | :--- | :---: | :--- |
| **concourse** | 대합실 | 300 lx | 비상등, CCTV 전원 회로 구성 |
| **platform** | 승강장 | 200 lx | 비상등, CCTV, 스크린도어 전원 |
| **corridor** | 통로/계단 | 150 lx | 유도등 간격 2.0m 이내 배치 |
| **machinery** | 기계실 | 200 lx | KEC 241 방폭등 적용, 접지 의무 |
| **station_office**| 역무실 | 500 lx | 정밀 작업용 조도, UPS 전원 필수 |

---

## 💡 주요 개선 사항 (Revit-MCP 전환 효과)

* **자연어 인터페이스**: 복잡한 Dynamo 노드 연결 대신 "대합실에 KDS 기준 맞춰서 조명 배치해줘"로 실행.
* **통합성**: 분리되어 있던 계산 로직과 배치 로직을 Claude가 실시간으로 연결.
* **유연성**: C# 코드 직접 주입(`send_code_to_revit`) 기능을 통해 API 미지원 항목(MEP Space 등)까지 제어 가능.

---
**Kim Jaehyeon** | Project Lead & Electrical Engineer
