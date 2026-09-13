
# 📊 데이터 수집 및 Rules DB 설계 (Phase 1)

이 섹션은 프로젝트의 핵심이 되는 법규 데이터 수집 과정, 구글 시트 정규화 구조, 그리고 이를 활용한 조도 계산 및 DB 설계 명세를 다룹니다.

---

## 🔍 데이터 수집 개요
**수집 순서:** 1. KDS PDF 분석 → 2. KEC 조항 추출 → 3. 소방/장애인 기준 검토 → 4. 구글 시트 정규화 → 5. JSON 변환 (`rules_db.json`)

### 주요 출처 (Sources)
| 항목 | 출처 | 비고 |
| :--- | :--- | :--- |
| **KDS 31 17 00** | [국가건설기준센터(KCSC)](https://kcsc.re.kr) | 철도 전기설비 기준 |
| **KEC** | [산업통상자원부 / KEA](https://kec.kea.kr) | 한국전기설비규정 (KEC 241 등) |
| **소방시설 기준** | [법제처(National Law Information)](https://law.go.kr) | 유도등 및 비상조명등 설치 기준 |
| **교통약자 편의시설** | [법제처](https://law.go.kr) | 장애인 콘센트 설치 높이 등 |
| **표준 도면** | [빅데이터 엔지니어링](https://bigdata-eng.com) | 지하철역 표준 설계 데이터 |

---

## 📋 구글 시트 데이터 구조 (Normalization)

### Sheet 1: `space_rules` (공간별 설계 기준)
* **주요 컬럼:** `space_key`, `space_name_ko`, `keywords`, `illuminance_lux`, `emergency_lux`, `guidance_spacing_m`, `outlet_spacing_m`, `cctv_circuit`, `explosion_proof`, `kds_ref`, `kec_ref`

### Sheet 2: `lighting_calc` (조도 계산 변수)
* **주요 컬럼:** `space_key`, `mounting_height_m`, `ceiling_reflectance` (0.7), `wall_reflectance` (0.5), `floor_reflectance` (0.2), `maintenance_factor` (0.7~0.8), `flux_per_lamp_lm`

### Sheet 3: `fixture_family` (Revit 매핑)
* **주요 컬럼:** `fixture_type`, `revit_family_name`, `mount_face` (천장/벽/바닥), `space_keys`

---

## 🗄️ Rules DB 공간 유형 (5종 핵심 데이터)

| 공간 코드 | 공간 명칭 | 목표 조도 | 비상 조도 | 특이 사항 | 근거 법규 |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **concourse** | 대합실 | 300 lx | 30 lx | 콘센트 5m 간격, CCTV 회로 | KDS 31 17 00 (4.3.1) |
| **platform** | 승강장 | 200 lx | 20 lx | PSD 전원, CCTV 회로 | KDS 31 17 00 (4.3.2) |
| **corridor** | 통로/계단 | 150 lx | - | 유도등 간격 2.0m | KDS 31 17 00 (4.3.3) |
| **machinery** | 기계실 | 200 lx | - | 방폭 등급 적용, 접지 | KEC 241.2 |
| **station_office**| 역무실 | 500 lx | - | UPS 전원 필수 | KDS 31 17 00 (4.3.4) |

---

## 🔢 조도 계산 로직 (Lumen Method)

AI 엔진은 다음 공식을 통해 필요 조명기구 수($N$)를 산출합니다.

$$N = \frac{E \times A}{lm \times UF \times M}$$

* **$E$**: 목표 조도 (lux)
* **$A$**: 공간 면적 ($m^2$)
* **$lm$**: 기구당 광속 (lumen)
* **$UF$**: 조명률 (RCR 및 반사율 기반)
* **$M$**: 보수율 (0.7~0.8 권장)

---

## ✅ 필수 체크리스트 (Quality Gate)

- [ ] **비상전원**: 비상조명등 점등 유지시간 60분 이상 확보 확인
- [ ] **유도등**: 피난구 / 통로 / 계단 유도등 종류별 위치 구분
- [ ] **전용회로**: 비상방송 스피커 및 방화셔터 독립 회로 구성
- [ ] **BIM 매핑**: Revit Family 이름과 JSON 데이터의 키워드 일치 확인
- [ ] **편의시설**: 장애인용 콘센트 설치 높이 준수 (0.4m ~ 1.2m)
- [ ] **환경 설정**: 기계실 내 KEC 241에 따른 방폭 등급 적용 여부

---
**Reference:** [revit-mcp GitHub](https://github.com/mcp-servers-for-revit/revit-mcp)
