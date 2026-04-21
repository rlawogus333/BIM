# 지하철역 전기설비 BIM 자동화 — revit-mcp 통합 설계서

> **프로젝트:** 지하철역 전기설비 BIM 자동화 시스템  
> **문서 버전:** 1.0.0  
> **작성일:** 2026-04-17  
> **기준 규격:** KDS 31 17 00 / KEC 전기설비기술기준 / 소방시설 설치기준  

---

## 목차

1. [아키텍처 개요](#1-아키텍처-개요)
2. [단계별 통합 방안](#2-단계별-통합-방안)
3. [revit-mcp 설치 및 설정](#3-revit-mcp-설치-및-설정)
4. [핵심 C# 코드 스니펫](#4-핵심-c-코드-스니펫)
5. [기존 vs 통합 비교](#5-기존-vs-통합-비교)
6. [리스크 및 대응](#6-리스크-및-대응)
7. [구현 체크리스트](#7-구현-체크리스트)

---

## 1. 아키텍처 개요

### 1.1 현행 시스템 구조

현재 시스템은 Revit에서 수동으로 모델을 작성한 뒤, Dynamo 스크립트 6개(IronPython)를 순차 실행하고, FastAPI 서버를 통해 KDS/KEC 검증 및 Claude AI 피드백을 받는 구조이다.

```
[Revit 수동 모델링]
        |
        v
[Dynamo 스크립트 01~06 (IronPython + Revit API)]
   01_collect_spaces.py    → 공간 수집
   02_match_space_type.py  → 공간 유형 매칭
   03_lumen_calc.py        → 조도 계산
   04_place_fixtures.py    → 조명기구 배치
   05_place_emergency.py   → 비상등/유도등 배치
   06_mcp_client.py        → FastAPI 서버 HTTP 호출
        |
        v
[FastAPI 서버 (main.py, port 8000)]
   - 규칙 조회 (/spaces)
   - 조도 계산 (/calculate)
   - 설계 검증 (/validate)
   - AI 분석 (/ai_analyze)
        |
        v
[Claude API → AI 피드백]
```

### 1.2 통합 후 시스템 구조

revit-mcp를 도입하면 Claude Desktop이 Revit 모델 생성/조회와 FastAPI 검증을 **동시에** 제어하는 완전 자동화 구조가 된다. Dynamo 의존성이 제거된다.

```
                    ┌─────────────────────┐
                    │   Claude Desktop    │
                    │   (AI 오케스트라)     │
                    └────┬───────────┬────┘
                         │           │
              MCP 연결 #1│           │MCP 연결 #2
            (stdio 방식)  │           │(SSE/HTTP 방식)
                         │           │
                         v           v
              ┌──────────────┐  ┌──────────────────┐
              │  revit-mcp   │  │  FastAPI 서버     │
              │  (Node.js)   │  │  (main.py:8000)  │
              │              │  │                  │
              │ 24개 도구:    │  │ - KDS/KEC 규칙   │
              │ - 모델 조회   │  │ - 조도 계산       │
              │ - 요소 생성   │  │ - 설계 검증       │
              │ - 요소 수정   │  │ - AI 피드백       │
              │ - 데이터 관리 │  │ - rules_db.json  │
              └──────┬───────┘  └──────────────────┘
                     │
          Socket 통신 │ (TCP/IP)
                     │
                     v
              ┌──────────────┐
              │ Revit 플러그인 │
              │ (revit-mcp-  │
              │  plugin.dll) │
              │              │
              │  Revit 모델   │
              └──────────────┘
```

### 1.3 두 MCP 연결의 협업 흐름

Claude Desktop은 두 MCP 서버를 **동일 대화(conversation)** 안에서 교차 호출할 수 있다.

| 단계 | MCP 서버 | 호출 도구 | 설명 |
|------|----------|-----------|------|
| 1 | revit-mcp | `get_current_view_elements` | Revit 모델에서 MEP Space 정보 수집 |
| 2 | FastAPI | `/spaces/{space_key}` | 해당 공간의 KDS/KEC 규칙 조회 |
| 3 | FastAPI | `/calculate` | 광속법 기반 조명기구 수량 산출 |
| 4 | revit-mcp | `create_point_based_element` | 산출된 수량만큼 조명기구 배치 |
| 5 | FastAPI | `/validate` | 배치 결과 기준 적합성 검증 |
| 6 | FastAPI | `/ai_analyze` | Claude AI 종합 피드백 |

---

## 2. 단계별 통합 방안

### Phase A: Revit 모델 자동 생성 (revit-mcp 활용)

revit-mcp의 도구를 사용하여 지하철역 골조 모델을 처음부터 자동으로 생성한다.

#### A-1. 레벨 생성

`create_level` 도구로 지하 1층, 지하 2층 레벨을 생성한다.

```json
// B1 레벨 생성 (-6m)
{
  "tool": "create_level",
  "args": {
    "elevation": -6.0,
    "name": "B1F-대합실층"
  }
}

// B2 레벨 생성 (-12m)
{
  "tool": "create_level",
  "args": {
    "elevation": -12.0,
    "name": "B2F-승강장층"
  }
}
```

#### A-2. 벽체 생성 (5개 공간 구획)

`create_line_based_element` 도구로 벽체를 배치하여 5가지 공간 유형을 구획한다.

| 공간 유형 | space_key | 기준 조도(lx) | 비상 조도(lx) |
|-----------|-----------|--------------|--------------|
| 대합실 | `concourse` | 300 | 30 |
| 승강장 | `platform` | 300 | 30 |
| 통로 | `corridor` | 150 | 15 |
| 기계실 | `machinery` | 200 | 20 |
| 역무실 | `station_office` | 400 | 40 |

```json
// 벽체 생성 예시 — 대합실 남측 벽
{
  "tool": "create_line_based_element",
  "args": {
    "family_name": "Basic Wall",
    "type_name": "Generic - 200mm",
    "start_point": {"x": 0, "y": 0, "z": -6.0},
    "end_point": {"x": 30, "y": 0, "z": -6.0},
    "level_name": "B1F-대합실층"
  }
}
```

#### A-3. 바닥 및 천장 생성

`create_surface_based_element` 도구로 바닥과 천장을 생성한다.

```json
// 바닥 생성 예시
{
  "tool": "create_surface_based_element",
  "args": {
    "family_name": "Floor",
    "type_name": "Generic Floor - 300mm",
    "boundary_points": [
      {"x": 0, "y": 0, "z": -6.0},
      {"x": 30, "y": 0, "z": -6.0},
      {"x": 30, "y": 15, "z": -6.0},
      {"x": 0, "y": 15, "z": -6.0}
    ],
    "level_name": "B1F-대합실층"
  }
}
```

#### A-4. MEP Space 생성 (send_code_to_revit 활용)

**핵심 제약사항:** revit-mcp의 `create_room` 도구는 건축 Room만 생성하며, MEP Space는 생성하지 못한다. 따라서 `send_code_to_revit` 도구를 사용하여 C# 코드를 직접 실행해야 한다.

```json
{
  "tool": "send_code_to_revit",
  "args": {
    "code": "/* MEP Space 생성 C# 코드 — 4장 상세 참조 */"
  }
}
```

> 상세 C# 코드는 [4장 핵심 C# 코드 스니펫](#4-핵심-c-코드-스니펫)에서 제공한다.

#### A-5. 조명기구 배치

FastAPI 서버에서 산출된 기구 수량과 배치 좌표를 기반으로, `create_point_based_element` 도구를 반복 호출하여 조명기구를 배치한다.

```json
// 조명기구 배치 예시
{
  "tool": "create_point_based_element",
  "args": {
    "family_name": "M_형광등 매입형",
    "type_name": "2x36W T8",
    "location": {"x": 5.0, "y": 3.75, "z": -2.5},
    "level_name": "B1F-대합실층"
  }
}
```

---

### Phase B: 기존 Dynamo 스크립트 연동 분석

기존 Dynamo 스크립트 6개를 revit-mcp 및 FastAPI 직접 통신으로 대체할 수 있는지 분석한다.

| 스크립트 | 기능 | 통합 후 상태 | 대체 방안 |
|----------|------|-------------|-----------|
| `01_collect_spaces.py` | MEP Space 수집 | **대체** | `get_current_view_elements` 또는 `send_code_to_revit`로 공간 데이터 수집 |
| `02_match_space_type.py` | 공간명 → space_key 매칭 | **로직 유지** | FastAPI의 `/spaces` 엔드포인트에서 키워드 매칭 수행, 데이터는 revit-mcp로 취득 |
| `03_lumen_calc.py` | 광속법 조도 계산 | **FastAPI 유지** | FastAPI `/calculate` 엔드포인트가 동일 로직 수행 |
| `04_place_fixtures.py` | 조명기구 Revit 배치 | **대체** | `create_point_based_element` 도구로 대체 |
| `05_place_emergency.py` | 비상등/유도등 배치 | **대체** | `create_point_based_element` 도구로 대체 |
| `06_mcp_client.py` | FastAPI HTTP 호출 | **대체** | Claude Desktop이 FastAPI MCP 서버와 직접 통신 (IronPython WebClient 불필요) |

**결론:** 6개 스크립트 중 4개는 완전 대체 가능하고, 2개(매칭/계산)는 FastAPI 서버에 이미 동일 로직이 존재하므로 Dynamo 없이도 동작한다.

---

### Phase C: 통합 워크플로우

Dynamo를 완전히 제거한 End-to-End 자동화 워크플로우이다.

```
Claude Desktop 대화 시작
│
├─ Step 1: 모델 생성 (revit-mcp)
│   ├─ create_level → B1F, B2F 생성
│   ├─ create_line_based_element → 벽체 구획
│   ├─ create_surface_based_element → 바닥/천장
│   └─ send_code_to_revit → MEP Space 생성
│
├─ Step 2: 공간 정보 수집 (revit-mcp)
│   ├─ get_current_view_elements → 전체 공간 목록
│   └─ send_code_to_revit → MEP Space 상세 속성 취득
│
├─ Step 3: 규칙 매칭 및 계산 (FastAPI)
│   ├─ GET /spaces/{space_key} → KDS/KEC 규칙 조회
│   └─ POST /calculate → 광속법 기구 수량 산출
│       ├─ 반사율 (천장 0.7, 벽 0.5, 바닥 0.2)
│       ├─ 보수율 0.75
│       └─ 실지수(Room Index) 자동 계산
│
├─ Step 4: 기구 배치 (revit-mcp)
│   ├─ create_point_based_element × N → 일반 조명기구
│   └─ create_point_based_element × M → 비상 조명기구
│
├─ Step 5: 설계 검증 (FastAPI)
│   └─ POST /validate → 기준 적합 여부 판정
│       ├─ 조도 기준 충족 여부
│       ├─ 비상등 간격 기준
│       └─ 유도등 설치 기준
│
└─ Step 6: AI 종합 피드백 (FastAPI)
    └─ POST /ai_analyze → Claude AI 분석 리포트
        ├─ 부적합 항목 개선 제안
        ├─ 에너지 효율 최적화 권고
        └─ KDS/KEC 조항별 근거 제시
```

**핵심 이점:** 사용자는 Claude Desktop에 자연어로 "B1층 대합실에 KDS 기준에 맞는 조명을 배치해줘"라고 요청하면, 위 전체 흐름이 자동으로 실행된다.

---

## 3. revit-mcp 설치 및 설정

### 3.1 사전 요구사항

| 항목 | 요구 버전 | 비고 |
|------|-----------|------|
| Node.js | 18 이상 | LTS 권장 |
| Revit | 2019 ~ 2024 | revit-mcp-plugin이 지원하는 버전 |
| Claude Desktop | 최신 | MCP 지원 버전 |
| Python | 3.10+ | FastAPI 서버용 |

### 3.2 revit-mcp 서버 설치

```bash
# 1. 저장소 클론
git clone https://github.com/mcp-servers-for-revit/revit-mcp.git
cd revit-mcp

# 2. 의존성 설치
npm install

# 3. 빌드
npm run build
```

### 3.3 Revit 플러그인 설치

1. `revit-mcp/plugin` 폴더에서 빌드된 `RevitMcpPlugin.dll`을 확인한다.
2. Revit의 Add-In 폴더에 복사한다:
   - 경로: `%APPDATA%\Autodesk\Revit\Addins\{버전}\`
3. `.addin` 매니페스트 파일을 동일 폴더에 배치한다.
4. Revit을 재시작하면 플러그인이 자동 로드된다.
5. Revit 하단 상태바 또는 외부 도구 탭에서 MCP 소켓 서버 시작을 확인한다.

### 3.4 Claude Desktop 설정 (claude_desktop_config.json)

두 MCP 서버를 동시에 등록한다. 파일 경로: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "revit-mcp": {
      "command": "node",
      "args": [
        "C:\\dev\\revit-mcp\\build\\index.js"
      ],
      "env": {
        "REVIT_MCP_HOST": "localhost",
        "REVIT_MCP_PORT": "8080"
      }
    },
    "subway-bim-fastapi": {
      "command": "python",
      "args": [
        "-m", "uvicorn", "main:app",
        "--host", "127.0.0.1",
        "--port", "8000"
      ],
      "cwd": "C:\\dev\\subway-bim",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

> **참고:** FastAPI 서버를 MCP 서버로 등록하려면 SSE(Server-Sent Events) 또는 stdio 기반 MCP 래퍼를 추가 구현해야 할 수 있다. 현재 FastAPI 서버는 REST API이므로, Claude Desktop에서 HTTP 호출이 가능한 MCP 래퍼(예: `mcp-server-fetch` 또는 커스텀 MCP 어댑터)를 사용하거나, FastAPI 자체에 MCP 프로토콜 지원을 추가하는 방안을 고려한다.

### 3.5 동시 실행 확인

```bash
# 터미널 1: FastAPI 서버 시작
cd C:\dev\subway-bim
uvicorn main:app --reload --port 8000

# 터미널 2: Revit에서 MCP 플러그인이 소켓 대기 중인지 확인
# Revit 실행 후 플러그인 패널에서 "Start MCP Server" 클릭

# Claude Desktop 실행 → 설정에서 두 MCP 서버가 "Connected" 상태인지 확인
```

---

## 4. 핵심 C# 코드 스니펫

`send_code_to_revit` 도구를 통해 실행할 C# 코드 예시이다. 이 코드들은 Revit API를 직접 호출하며, revit-mcp 플러그인이 내부적으로 컴파일하여 실행한다.

### 4.1 MEP Space 생성

```csharp
// MEP Space 생성 — 5개 공간 유형별로 호출
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Mechanical;

UIDocument uidoc = commandData.Application.ActiveUIDocument;
Document doc = uidoc.Document;

// 레벨 취득
Level level = new FilteredElementCollector(doc)
    .OfClass(typeof(Level))
    .Cast<Level>()
    .FirstOrDefault(l => l.Name == "B1F-대합실층");

if (level == null)
    throw new Exception("B1F-대합실층 레벨을 찾을 수 없습니다.");

using (Transaction tx = new Transaction(doc, "MEP Space 생성"))
{
    tx.Start();

    // UV 좌표로 Space 생성 (단위: feet, 1m = 3.28084ft)
    // 대합실: 중심점 (15m, 7.5m) = (49.21ft, 24.61ft)
    UV insertionPoint = new UV(49.21, 24.61);

    Space mepSpace = doc.Create.NewSpace(level, insertionPoint);
    mepSpace.Name = "대합실";
    mepSpace.Number = "S-B1-001";

    // MEP Space 속성 설정
    Parameter spaceType = mepSpace.LookupParameter("공간유형");
    if (spaceType != null)
        spaceType.Set("concourse");

    // 설계 조도 파라미터 설정
    Parameter designIlluminance = mepSpace.LookupParameter("설계조도");
    if (designIlluminance != null)
        designIlluminance.Set(300.0);  // lux

    tx.Commit();
}

return "MEP Space 생성 완료: 대합실 (S-B1-001)";
```

### 4.2 조명기구 배치 (특정 패밀리 지정)

```csharp
// 조명기구 배치 — 패밀리 타입 지정 및 좌표 배치
using Autodesk.Revit.DB;

UIDocument uidoc = commandData.Application.ActiveUIDocument;
Document doc = uidoc.Document;

// 패밀리 타입 검색
FamilySymbol fixtureType = new FilteredElementCollector(doc)
    .OfClass(typeof(FamilySymbol))
    .OfCategory(BuiltInCategory.OST_LightingFixtures)
    .Cast<FamilySymbol>()
    .FirstOrDefault(fs => fs.FamilyName == "M_형광등 매입형"
                       && fs.Name == "2x36W T8");

if (fixtureType == null)
    throw new Exception("조명기구 패밀리 'M_형광등 매입형 - 2x36W T8'을 찾을 수 없습니다.");

Level level = new FilteredElementCollector(doc)
    .OfClass(typeof(Level))
    .Cast<Level>()
    .FirstOrDefault(l => l.Name == "B1F-대합실층");

using (Transaction tx = new Transaction(doc, "조명기구 배치"))
{
    tx.Start();

    // 패밀리 타입 활성화
    if (!fixtureType.IsActive)
        fixtureType.Activate();

    // 배치 좌표 배열 (미터 → 피트 변환)
    double[][] positions = new double[][] {
        new double[] {5.0, 3.75},
        new double[] {10.0, 3.75},
        new double[] {15.0, 3.75},
        new double[] {20.0, 3.75},
        new double[] {25.0, 3.75},
        new double[] {5.0, 11.25},
        new double[] {10.0, 11.25},
        new double[] {15.0, 11.25},
        new double[] {20.0, 11.25},
        new double[] {25.0, 11.25}
    };

    int count = 0;
    foreach (var pos in positions)
    {
        double xFeet = pos[0] * 3.28084;
        double yFeet = pos[1] * 3.28084;
        double zFeet = -2.5 * 3.28084;  // 천장 매입 높이

        XYZ location = new XYZ(xFeet, yFeet, zFeet);
        FamilyInstance instance = doc.Create.NewFamilyInstance(
            location, fixtureType, level,
            Autodesk.Revit.DB.Structure.StructuralType.NonStructural);

        count++;
    }

    tx.Commit();
    return $"조명기구 {count}개 배치 완료";
}
```

### 4.3 비상등 회로 파라미터 설정

```csharp
// 비상등 회로 파라미터 설정 — 기존 비상등 요소에 회로 정보 기입
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Electrical;

UIDocument uidoc = commandData.Application.ActiveUIDocument;
Document doc = uidoc.Document;

// 비상등 카테고리 요소 수집
var emergencyLights = new FilteredElementCollector(doc)
    .OfCategory(BuiltInCategory.OST_LightingFixtures)
    .WhereElementIsNotElementType()
    .Cast<FamilyInstance>()
    .Where(fi => fi.Symbol.FamilyName.Contains("비상"))
    .ToList();

using (Transaction tx = new Transaction(doc, "비상등 회로 설정"))
{
    tx.Start();

    int updated = 0;
    foreach (var light in emergencyLights)
    {
        // 회로 유형 파라미터 설정
        Parameter circuitType = light.LookupParameter("회로유형");
        if (circuitType != null)
            circuitType.Set("비상전원회로");

        // 배터리 지속시간 파라미터 (소방법 기준: 20분 이상)
        Parameter batteryDuration = light.LookupParameter("배터리지속시간");
        if (batteryDuration != null)
            batteryDuration.Set(20.0);  // 분

        // 비상전원 자동전환 시간 (KEC 기준)
        Parameter switchoverTime = light.LookupParameter("전환시간");
        if (switchoverTime != null)
            switchoverTime.Set(3.0);  // 초

        // 패널명 할당
        Parameter panelName = light.LookupParameter("패널명");
        if (panelName != null)
            panelName.Set("EP-B1-01");  // Emergency Panel

        updated++;
    }

    tx.Commit();
    return $"비상등 {updated}개 회로 파라미터 설정 완료 (비상전원회로, 배터리 20분, 전환 3초)";
}
```

---

## 5. 기존 vs 통합 비교

### 5.1 워크플로우 비교

| 구분 | 기존 방식 | 통합 방식 |
|------|-----------|-----------|
| **모델 작성** | Revit에서 수동 모델링 | Claude → revit-mcp 자동 생성 |
| **공간 수집** | Dynamo `01_collect_spaces.py` | revit-mcp `get_current_view_elements` |
| **유형 매칭** | Dynamo `02_match_space_type.py` | FastAPI `/spaces` (Claude가 직접 호출) |
| **조도 계산** | Dynamo `03_lumen_calc.py` | FastAPI `/calculate` (Claude가 직접 호출) |
| **기구 배치** | Dynamo `04_place_fixtures.py` | revit-mcp `create_point_based_element` |
| **비상등 배치** | Dynamo `05_place_emergency.py` | revit-mcp `create_point_based_element` |
| **서버 통신** | Dynamo `06_mcp_client.py` (IronPython WebClient) | Claude Desktop ↔ FastAPI 직접 MCP 통신 |
| **AI 피드백** | FastAPI → Claude API (간접) | Claude Desktop 내장 (직접) |

### 5.2 기술 스택 비교

| 항목 | 기존 | 통합 후 |
|------|------|---------|
| Revit 자동화 | Dynamo + IronPython + Revit API | revit-mcp (Node.js + Socket + Revit Plugin) |
| 서버 통신 | System.Net.WebClient (IronPython) | MCP 프로토콜 (stdio/SSE) |
| 오케스트레이션 | 수동 (Dynamo 순차 실행) | Claude AI (자연어 기반 자동 실행) |
| 사용자 인터페이스 | Revit + Dynamo GUI | Claude Desktop 대화창 |

### 5.3 정량적 이점

| 지표 | 기존 | 통합 후 | 개선율 |
|------|------|---------|--------|
| 수동 작업 단계 | 8단계 (Revit 모델링 + Dynamo 6개 + 결과 확인) | 1단계 (Claude에 지시) | **87.5% 감소** |
| Dynamo 스크립트 의존성 | 6개 | 0개 | **100% 제거** |
| IronPython 호환성 이슈 | 있음 (Revit 버전별 차이) | 없음 | **해소** |
| 자연어 명령 지원 | 불가 | 가능 | **신규** |
| 설계 변경 반영 시간 | 30분~1시간 (수동) | 1~5분 (자동) | **90% 이상 단축** |

---

## 6. 리스크 및 대응

### 6.1 리스크 목록

| ID | 리스크 | 심각도 | 발생 가능성 | 대응 방안 |
|----|--------|--------|------------|-----------|
| R1 | **revit-mcp 저장소 아카이브** — 원본 저장소가 모노레포로 이전되어 아카이브될 수 있음 | 높음 | 중간 | 모노레포(`mcp-servers-for-revit`) 최신 상태 확인. 아카이브 시 fork 유지 또는 모노레포 내 패키지 참조로 전환 |
| R2 | **MEP Space 미지원** — revit-mcp의 `create_room`은 건축 Room만 생성 | 높음 | 확정 | `send_code_to_revit` 도구로 C# 코드 직접 실행하여 MEP Space 생성 (4.1절 참조) |
| R3 | **패밀리 미로드** — 조명기구 패밀리가 프로젝트에 없을 경우 배치 실패 | 중간 | 높음 | 사전에 필요 패밀리를 프로젝트 템플릿에 포함하거나, `send_code_to_revit`로 `doc.LoadFamily()` 실행 |
| R4 | **두 MCP 서버 동시 운영** — 포트 충돌, 리소스 경합 가능 | 낮음 | 낮음 | revit-mcp(소켓 8080)와 FastAPI(HTTP 8000)는 포트가 다르므로 충돌 없음. 메모리 모니터링 필요 |
| R5 | **Revit 버전 호환성** — revit-mcp 플러그인이 Revit 2019~2024만 지원 | 중간 | 중간 | 프로젝트 대상 Revit 버전을 확인하고, 필요 시 플러그인 소스 수정하여 지원 범위 확장 |
| R6 | **단위 변환 오류** — Revit 내부 단위(feet)와 설계 단위(meter) 불일치 | 중간 | 높음 | 모든 C# 코드에서 meter → feet 변환(x 3.28084)을 명시적으로 적용. 유틸리티 함수 작성 |
| R7 | **FastAPI MCP 래퍼 부재** — 현재 FastAPI는 REST API이며 MCP 프로토콜 미지원 | 중간 | 확정 | MCP Python SDK(`mcp` 패키지)를 활용하여 FastAPI 엔드포인트를 MCP 도구로 래핑하거나, `mcp-server-fetch` 도구를 활용하여 HTTP 호출 |

### 6.2 패밀리 사전 로드 C# 코드

R3 대응을 위한 패밀리 로드 코드:

```csharp
// 패밀리 파일 로드
using Autodesk.Revit.DB;

Document doc = commandData.Application.ActiveUIDocument.Document;

string familyPath = @"C:\ProgramData\Autodesk\RVT 2024\Libraries\Korea\전기\조명기구\M_형광등 매입형.rfa";

using (Transaction tx = new Transaction(doc, "패밀리 로드"))
{
    tx.Start();

    Family family = null;
    bool loaded = doc.LoadFamily(familyPath, out family);

    tx.Commit();

    if (loaded)
        return $"패밀리 로드 성공: {family.Name}";
    else
        return "패밀리가 이미 로드되어 있거나 로드에 실패했습니다.";
}
```

---

## 7. 구현 체크리스트

### Phase 0: 환경 준비

- [ ] Node.js 18+ 설치 확인
- [ ] revit-mcp 저장소 클론 및 빌드 (`npm install && npm run build`)
- [ ] revit-mcp-plugin을 대상 Revit 버전(2019~2024)에 설치
- [ ] Revit 실행 후 MCP 소켓 서버 정상 기동 확인
- [ ] FastAPI 서버 정상 작동 확인 (`uvicorn main:app --port 8000`)
- [ ] `rules_db.json` 5개 공간 유형 데이터 검증

### Phase 1: Claude Desktop 설정

- [ ] `claude_desktop_config.json`에 revit-mcp 서버 등록
- [ ] `claude_desktop_config.json`에 FastAPI MCP 서버(또는 래퍼) 등록
- [ ] Claude Desktop 재시작 후 두 MCP 서버 연결 상태 확인
- [ ] 간단한 테스트 명령으로 revit-mcp 통신 검증 (예: `get_current_view_info`)

### Phase 2: 모델 자동 생성 테스트

- [ ] `create_level`로 B1F(-6m), B2F(-12m) 레벨 생성 테스트
- [ ] `create_line_based_element`로 벽체 생성 테스트
- [ ] `create_surface_based_element`로 바닥/천장 생성 테스트
- [ ] `send_code_to_revit`로 MEP Space 생성 C# 코드 실행 테스트
- [ ] 5개 공간 유형(대합실, 승강장, 통로, 기계실, 역무실) 전체 구획 생성

### Phase 3: 조명 자동화 파이프라인

- [ ] revit-mcp로 공간 데이터 수집 → FastAPI `/calculate` 호출 → 기구 수량 산출 검증
- [ ] `create_point_based_element`로 일반 조명기구 배치 테스트
- [ ] `create_point_based_element`로 비상 조명기구 배치 테스트
- [ ] `send_code_to_revit`로 비상등 회로 파라미터 일괄 설정
- [ ] FastAPI `/validate`로 배치 결과 기준 적합성 검증

### Phase 4: End-to-End 통합 테스트

- [ ] 자연어 명령으로 전체 워크플로우 실행 테스트
- [ ] 모든 공간 유형별 조도 기준 충족 여부 확인
- [ ] 비상등 간격 기준(대합실 10m, 승강장 10m, 통로 8m) 충족 확인
- [ ] 유도등 설치 위치 기준 충족 확인
- [ ] AI 피드백 리포트 생성 및 품질 확인

### Phase 5: Dynamo 스크립트 단계적 제거

- [ ] `06_mcp_client.py` 비활성화 (Claude 직접 통신으로 대체 확인)
- [ ] `04_place_fixtures.py` 비활성화 (revit-mcp 배치로 대체 확인)
- [ ] `05_place_emergency.py` 비활성화 (revit-mcp 배치로 대체 확인)
- [ ] `01_collect_spaces.py` 비활성화 (revit-mcp 수집으로 대체 확인)
- [ ] `02_match_space_type.py` 비활성화 (FastAPI 직접 호출로 대체 확인)
- [ ] `03_lumen_calc.py` 비활성화 (FastAPI 직접 호출로 대체 확인)
- [ ] Dynamo 전체 비활성화 후 회귀 테스트 수행

### Phase 6: 문서화 및 배포

- [ ] 사용자 가이드 작성 (Claude Desktop 사용법)
- [ ] 프로젝트 템플릿 준비 (필수 패밀리 사전 로드)
- [ ] 단위 변환 유틸리티 함수 C# 코드 라이브러리화
- [ ] 팀 배포 및 교육

---

## 부록: revit-mcp 도구 전체 목록

참고용으로 revit-mcp에서 제공하는 24개 도구를 분류한다.

### 조회 도구 (Query)
| 도구명 | 용도 | 본 프로젝트 활용 |
|--------|------|-----------------|
| `get_current_view_info` | 현재 뷰 정보 | 작업 뷰 확인 |
| `get_current_view_elements` | 뷰 내 요소 목록 | 공간/기구 수집 |
| `get_available_family_types` | 사용 가능 패밀리 타입 | 조명기구 패밀리 확인 |
| `get_selected_elements` | 선택 요소 | 수동 선택 시 활용 |
| `get_material_quantities` | 자재 물량 | 물량 산출 |
| `ai_element_filter` | AI 기반 필터 | 조건부 요소 검색 |
| `analyze_model_statistics` | 모델 통계 | 품질 검증 |

### 생성 도구 (Create)
| 도구명 | 용도 | 본 프로젝트 활용 |
|--------|------|-----------------|
| `create_point_based_element` | 점 기반 요소 | **조명기구/비상등 배치** |
| `create_line_based_element` | 선 기반 요소 | **벽체 생성** |
| `create_surface_based_element` | 면 기반 요소 | **바닥/천장 생성** |
| `create_grid` | 그리드 | 구조 그리드 |
| `create_level` | 레벨 | **B1F/B2F 레벨 생성** |
| `create_room` | Room (건축) | MEP Space 대체 불가 |
| `create_structural_framing_system` | 구조 프레임 | 미사용 |
| `send_code_to_revit` | C# 코드 실행 | **MEP Space 생성, 패밀리 로드, 파라미터 설정** |

### 수정 도구 (Modify)
| 도구명 | 용도 | 본 프로젝트 활용 |
|--------|------|-----------------|
| `delete_element` | 요소 삭제 | 오배치 기구 삭제 |
| `operate_element` | 이동/색상/숨김 | 기구 위치 조정 |
| `color_elements` | 요소 색상 | 공간별 시각화 |
| `tag_all_walls` | 벽 태그 | 벽체 라벨링 |
| `tag_all_rooms` | Room 태그 | 공간 라벨링 |

### 데이터 도구 (Data)
| 도구명 | 용도 | 본 프로젝트 활용 |
|--------|------|-----------------|
| `store_project_data` | 프로젝트 데이터 저장 | KDS 규칙 캐싱 |
| `store_room_data` | 공간 데이터 저장 | 조도 계산 결과 저장 |
| `export_room_data` | 공간 데이터 내보내기 | 검증 보고서 |
| `query_stored_data` | 저장 데이터 조회 | 이력 조회 |

---

> **본 문서는 지하철역 전기설비 BIM 자동화 프로젝트의 revit-mcp 통합 설계 기준 문서이다.**  
> **문의:** 프로젝트 BIM 자동화 담당팀
