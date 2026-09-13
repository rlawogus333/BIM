# 알려진 제약 및 개선 과제

공모전 제출 시점의 실제 상태를 그대로 기록합니다. 모든 항목은 재현 방법과 함께 검증된 내용입니다.

---

## 1. V009~V012가 실제로는 동작하지 않음

### 현상

`rules_db.json`에는 검증 규칙이 12개 정의되어 있지만, `main.py`의 `run_validation_rules()`는 **V001~V008만 분기가 구현**되어 있습니다.

```bash
$ python -c "import json; print(len(json.load(open('src/rules_db.json'))['validation_rules']))"
12
$ grep -c 'rid == "V0' src/main.py
8
```

### 원인

`ValidationInput` Pydantic 모델에 V009~V012가 요구하는 입력 필드가 없습니다.

| 규칙 | 필요한 입력 필드 | `ValidationInput` 존재 여부 |
| :--- | :--- | :---: |
| V009 비상전원 백업시간 부족 | `emergency_backup_actual_minutes` | ❌ |
| V010 복도 바닥 유도등 미설치 | `guidance_floor_installed` | ❌ |
| V011 PSD 무순단 전원 미공급 | `psd_power_redundant` | ❌ |
| V012 유도등 설치 높이 미준수 | `guidance_mount_height_m` | ❌ |

따라서 `list_validation_rules`는 12개를 반환하지만 `validate_design`은 절대 V009~V012를 트리거하지 않습니다. **미검출을 "합격"으로 오해할 수 있는 지점**이라 명시합니다.

### 개선 방향

- **단기**: `ValidationInput`에 4개 필드를 추가하고 `run_validation_rules()`에 분기 4개를 추가.
- **중기**: `rule["condition"]` 문자열을 안전하게 평가하는 범용 규칙 엔진으로 전환해, JSON에 규칙을 추가하면 코드 수정 없이 동작하도록 변경. (현재 `condition`은 문서용 표기일 뿐 실행되지 않음)

---

## 2. `excel_to_json.py` 출력과 `rules_db.json` v2.0.0 스키마 불일치

### 현상

```bash
cd src
python excel_to_json.py --input ../data/BIM_elec_data.xlsx --output /tmp/gen.json
```

정상 실행되어 공간 5종·조명기구 12종·검증 규칙 8개가 생성되지만, 출력은 **v1.0.0 스키마**이며 `main.py`가 요구하는 필드가 누락되어 있습니다. 이 파일로 `src/rules_db.json`을 덮어쓰면 서버가 동작하지 않습니다.

### 누락·불일치 필드

| 필드 | 스크립트 출력 | `main.py` 사용처 | 결과 |
| :--- | :--- | :--- | :--- |
| `lighting.mounting_height_m` | `null` | `calc_room_index()` | **TypeError — 조도 계산 실패** |
| `load.power_factor` | 없음 | `calc_space_load()` | **KeyError — 부하 계산 실패** |
| `lighting.emergency_lux` | `null` | V006 검증 | 비교 실패 |
| `outlets.spacing_m` | `null` | V007 검증 | 비교 실패 |
| `emergency.guidance_spacing_m` | `null` | V002 검증 | 비교 실패 |
| `load.design_load_w_m2` | `4.6` | 분전반 산출 | **의미가 다른 값** — 아래 설명 참고 |
| `fixture_families` 키 | `ff_01`~`ff_12` | `get_fixture_family_for_space()` | 키 이름 기반 필터 무력화 |
| `cctv.power_per_camera_w` | 없음 | 부하 산출 | `.get(…, 30)` 기본값으로 대체됨 |

### `design_load_w_m2` 값 차이에 대하여

스크립트는 `lighting_calc` 시트의 `LPD_W_m2`(조명 전력밀도)를 `design_load_w_m2`에 그대로 복사합니다. 대합실 기준 **4.6 W/m²**입니다.

그러나 `design_load_w_m2`는 조명·콘센트·CCTV·특수부하를 모두 포함한 **단위면적당 총 설계 부하**여야 하며, v2.0.0은 **30 W/m²**를 사용합니다. LPD는 그 중 조명 성분만 나타내는 별개 지표입니다. 자동 변환 결과를 그대로 쓰면 분전반 용량이 약 1/6로 과소 산정됩니다.

### 그래서 현재 `rules_db.json`은 어떻게 만들어졌나

**스크립트 출력물이 아니라, `data/standards/`의 KDS·KEC·NFPC 원문과 KS A 3011 조도기준표를 교차 검증해 수작업으로 보강한 결과물**입니다. `excel_to_json.py`는 Phase 1의 초기 구조화 산출물로 보존하고 있습니다.

### 개선 방향

1. `data/BIM_elec_data.xlsx`의 `space_rules` 시트에 누락 컬럼 추가
   → `mounting_height_m`, `emergency_lux`, `power_factor`, `outlet_spacing_m`, `design_load_w_m2`(LPD와 별도 컬럼)
2. `space_rules`의 `exit_guide_spacing_m`이 대합실·승강장에서 `-`로 비어 있음 → 실제 값 입력
3. `FIXTURE_FAMILY_COL_MAP`의 키 생성 규칙을 일련번호(`ff_01`)가 아닌 의미 기반(`ceiling_light`, `explosion_proof_light` …)으로 변경
4. 변환 후 `pytest tests/test_rules.py`를 통과해야 적용하는 절차를 CI로 강제

---

## 3. `lighting_calc` 시트의 `room_index_K` 컬럼이 `#DIV/0!`

`data/BIM_elec_data.xlsx`의 `lighting_calc` 시트에서 `room_index_K` 열 전체가 `#DIV/0!`입니다. `ceiling_h_m` 컬럼이 비어 있어 실지수 수식이 0으로 나누기 때문입니다.

실제 계산에는 영향이 없습니다 — `main.py`가 런타임에 `calc_room_index()`로 직접 계산하고, `excel_to_json.py`의 `_float_or_none()`이 `#DIV/0!`를 `None`으로 처리합니다. 다만 스프레드시트만 보면 값이 깨져 보이므로 `ceiling_h_m`을 채워두는 편이 낫습니다.

---

## 4. 조명률(CU) 근사식의 한계

`estimate_cu()`는 조명률 표를 보간하지 않고 아래 근사식을 씁니다.

```python
base       = 0.40 + 0.10 × min(K, 3.0) / 3.0
refl_bonus = 천장반사율 × 0.15 + 벽반사율 × 0.05
CU         = min(base + refl_bonus, 0.70)
```

실지수가 3.0을 넘으면 `base`가 포화되어 대공간(대합실 K≈6.4)에서 실제보다 보수적인 값이 나옵니다. 안전 측 오차이지만 기구 수가 과다 산정될 수 있습니다.

**개선 방향**: 제조사 배광 데이터 기반 조명률 표를 `rules_db.json`에 추가하고 실지수·반사율 2차원 보간으로 대체. 각 공간의 `utilization_factor_range`가 이미 준비되어 있습니다.

---

## 5. 기타

| 항목 | 내용 |
| :--- | :--- |
| `main.py` `/import/excel` | `imported_db.get("fixtures_families")` 오타 (`fixture_families`가 맞음). 해당 변수가 이후 사용되지 않아 동작에는 영향 없음 |
| `/import/google-sheets` | 스텁 상태 — `excel_to_json.fetch_gsheet()` 연동 필요 |
| Pydantic V2 경고 | `Field(..., example=...)`, `class Config`, `.dict()` 사용으로 DeprecationWarning 발생. V3에서 제거 예정이므로 `json_schema_extra` / `ConfigDict` / `.model_dump()`로 이전 필요 |
| `ANTHROPIC_API_KEY` 미설정 | `/ai/*` 엔드포인트가 503 반환. 나머지 계산·검증 기능은 정상 동작 |
| AI 피드백 모델 | `claude-sonnet-4-20250514` 하드코딩. 설정값으로 분리 권장 |
| `legacy/dynamo/test_dynamo_offline.py` | Dynamo 시절 테스트로 현재 파이프라인에서 실행되지 않음 (`pytest.ini`의 `testpaths=tests`로 제외됨) |

---

## 향후 확장 방향

발표자료 기준 4가지 도약 목표입니다.

1. **소방·통신설비로 영역 확장** — 스프링클러 전원, 무선통신보조설비 등
2. **공간 유형 추가** — 환승통로, 주차장, 상가, 승강기 기계실
3. **실시간 설계 변경 자동 반영** — Revit 모델 변경 이벤트를 감지해 재검증
4. **다중 역사 일괄 검증 자동화** — `data/stations/`의 서울교통공사 공공데이터를 입력으로 여러 역사를 배치 검증
