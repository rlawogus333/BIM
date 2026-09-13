# rules_db.json 스키마 명세

**버전** v2.0.0 · **최종 갱신** 2026-04-18

전 시스템(`main.py`, `fastapi_mcp_wrapper.py`, `tests/`)이 참조하는 유일한 기준 데이터입니다. 법규가 개정되면 이 파일만 갱신하면 계산·검증·피드백에 즉시 반영됩니다.

---

## 최상위 구조

```jsonc
{
  "_meta":              { ... },  // 버전 · 적용 표준 목록 · 출처 주석
  "spaces":             { ... },  // 공간 5종별 설계 기준
  "fixture_families":   { ... },  // Revit Family 매핑 12종
  "validation_rules":   [ ... ],  // 검증 규칙 V001~V012
  "lighting_formula":   { ... },  // 광속법 공식 정의
  "standards_glossary": { ... },  // 표준별 조항 요약
  "compliance_matrix":  { ... }   // 공간 × 기준 빠른 참조표
}
```

---

## `_meta`

| 키 | 타입 | 설명 |
| :--- | :--- | :--- |
| `version` | string | 스키마 버전. `health_check` / `GET /` 응답에 노출 |
| `description` | string | DB 설명 |
| `standards` | string[] | 적용 표준 전체 목록 (16종) |
| `last_updated` | string | ISO 날짜 |
| `author` | string | 작성자 |
| `source_notes` | string | 값의 근거와 교차검증 방식 |

---

## `spaces`

키는 `concourse` / `platform` / `corridor` / `machinery` / `station_office` 5종입니다.

```jsonc
"concourse": {
  "space_key": "concourse",
  "space_name_ko": "대합실",
  "keywords": ["대합실", "concourse", "홀", "hall", "로비", "개찰구", "매표"],

  "lighting":             { ... },
  "lighting_calc":        { ... },
  "outlets":              { ... },
  "emergency":            { ... },
  "cctv":                 { ... },
  "load":                 { ... },
  "special_requirements": { ... }
}
```

`keywords`는 Revit Space 이름과의 자연어 매칭에 사용합니다 (예: "B1 개찰구 홀" → `concourse`).

### `lighting` — 조도 기준

| 필드 | 타입 | 설명 | 사용처 |
| :--- | :--- | :--- | :--- |
| `illuminance_lux` | number | 설계 조도 기준값 | V001 검증, 조도 계산의 기본 E |
| `illuminance_min_lux` / `illuminance_max_lux` | number | 허용 범위 | 참조용 |
| `emergency_lux` | number | 비상조명 조도 기준 | V006 검증 |
| `uniformity_ratio` | number | 균제도 | 참조용 |
| `color_rendering_index_ra` | number | 연색성 Ra | 참조용 |
| `color_temperature_K` | number | 색온도 | 참조용 |
| **`mounting_height_m`** | number | 광원 취부 높이 | **실지수 K 계산 (필수)** |
| `work_plane_height_m` | number | 작업면 높이 | 참조용 |
| `kds_ref` / `kec_ref` | string | 근거 조항 | 계산 응답에 첨부 |
| `calc_method` | string | 계산법 표기 | 참조용 |

### `lighting_calc` — 조도 계산 파라미터

| 필드 | 타입 | 설명 |
| :--- | :--- | :--- |
| `ceiling_reflectance` / `wall_reflectance` / `floor_reflectance` | number (0~1) | 반사율. 스프레드시트의 `refl_*_%`(0~100)가 비율로 변환됨 |
| **`maintenance_factor`** | number | 보수율 M |
| `utilization_factor_range` | [number, number] | 조명률 허용 범위 (참조용) |
| **`flux_per_lamp_lm`** | number | 램프당 광속 |
| **`lamps_per_fixture`** | number | 기구당 램프 수 |
| `lamp_type` | string | 광원 종류 |
| `ks_ref` | string | KS 규격 근거 |

기구당 총 광속 `F = flux_per_lamp_lm × lamps_per_fixture`

### `outlets` — 콘센트

| 필드 | 설명 |
| :--- | :--- |
| `spacing_m` | 콘센트 간격 기준 (V007 검증) |
| `height_from_floor_m` | 설치 높이 |
| `circuit_type` | 일반회로 / 전용회로 |
| `circuit_ampere`, `max_outlets_per_circuit` | 분기회로 설계값 |
| `outlet_type` | 방폭형 등 특수 타입 (기계실) |
| `ups_outlet_required`, `ups_outlet_color` | UPS 콘센트 (역무실) |

### `emergency` — 비상조명·유도등

| 필드 | 설명 |
| :--- | :--- |
| `emergency_light_required` | 비상조명 필수 여부 |
| `emergency_backup_minutes` | 비상전원 백업 시간 (지하역사 60분) |
| `guidance_sign_required` | 유도등 필수 여부 |
| **`guidance_spacing_m`** | 프로젝트 설계 간격 (V002 검증 기준) |
| `guidance_spacing_regulatory_max_m` | 법규상 최대 간격 (corridor만) |
| `guidance_spacing_design_rationale` | 강화 설계 근거 서술 |
| `guidance_type` | 복도통로 / 거실통로 / 계단통로 유도등 |
| `guidance_mount_height_m` / `guidance_mount_height_max_m` | 설치 높이 |
| `guidance_floor_install_required` | 바닥 매립 필수 여부 (지하역사 특례) |
| `exit_sign_spacing_m` | 유도표지 간격 |
| `fire_code_ref` | NFPC 조항 |

> **설계 판단 기록**: `corridor`의 `guidance_spacing_m`은 2.0 m입니다. NFPC 303 §6①나가 정한 법규 최대값은 20 m(`guidance_spacing_regulatory_max_m`)이지만, 지하역사 피난 안전을 위해 10배 강화한 설계값을 적용했습니다. 두 값을 분리 기록해 "법규 위반"이 아니라 "자발적 강화"임을 명시합니다.

### `cctv`

| 필드 | 설명 |
| :--- | :--- |
| `cctv_circuit` | CCTV 전원 회로 존재 여부 |
| `power_per_camera_w` | 카메라당 소비전력 (부하 산출) |
| `circuit_type` | 전용회로 / UPS 전용회로 |

부하 계산 시 카메라 수는 `max(1, 면적 / 100)`으로 추정합니다 (100 m²당 1대).

### `load` — 부하 산출

| 필드 | 설명 |
| :--- | :--- |
| **`design_load_w_m2`** | 단위면적당 설계 부하 (W/m²) |
| **`power_factor`** | 역률 |
| `demand_factor` | 공간별 수요율 (참조용 — 실제 계산은 요청 파라미터 사용) |

`calc_space_load()`의 배분 비율: 조명 60 %, 콘센트 30 %, 나머지는 CCTV·특수부하로 별도 가산.

### `special_requirements`

| 필드 | 적용 | 설명 |
| :--- | :--- | :--- |
| `explosion_proof` | machinery | 방폭 필수 여부 (V003) |
| `explosion_proof_grade` | machinery | `Ex e IIC T4 이상` |
| `ups_required` | station_office | UPS 필수 여부 (V004) |
| `ups_capacity_kva`, `ups_backup_minutes` | station_office | UPS 사양 |
| `grounded` | machinery, station_office | 접지 필수 여부 (V008) |
| `grounding_type`, `grounding_resistance_ohm_max` | | 접지 방식·저항 |
| `screen_door_power`, `screen_door_power_w` | platform | PSD 전원 (V011) |
| `barrier_free` | | 교통약자 편의시설 대상 여부 |
| `access_floor_recommended` | station_office | 액세스플로어 권장 |

---

## `fixture_families`

Revit Family와 공간의 매핑입니다. 12종이 등록되어 있습니다.

```jsonc
"explosion_proof_light": {
  "fixture_type": "방폭형 LED 등기구",
  "revit_family_name": "Lighting Fixture - Explosion Proof LED",
  "mount_face": "천장",
  "space_keys": ["machinery"],
  "ks_ref": "KS C IEC 60079",
  "kec_ref": "KEC 242.2",
  "note": "Ex e IIC T4 이상 방폭 등급"
}
```

| 카테고리 | 키 |
| :--- | :--- |
| 일반 조명 | `ceiling_light`, `corridor_light`, `explosion_proof_light` |
| 비상조명 | `emergency_light` |
| 유도등 | `exit_sign_corridor`, `exit_sign_room`, `exit_sign_stair`, `guidance_sign_label` |
| 콘센트 | `outlet_standard`, `outlet_explosion_proof`, `outlet_ups` |

> **키 이름 규칙 주의**: `get_fixture_family_for_space()`는 키 이름에 `emergency` / `guidance` / `outlet`이 포함되지 않은 항목을 "주 조명기구"로 판단합니다. 따라서 **키 이름이 의미를 담고 있어야** 하며, `ff_01` 같은 일련번호 키를 쓰면 이 필터가 무력화됩니다.

---

## `validation_rules`

```jsonc
{
  "rule_id": "V002",
  "rule_name": "통로·계단 유도등 간격 초과",
  "description": "복도통로유도등 간격이 설계 기준(2m)을 초과할 경우 위반",
  "applies_to": ["corridor"],          // "all" 또는 space_key 배열
  "check_field": "guidance_actual_spacing_m",
  "condition": "guidance_actual_spacing_m > guidance_spacing_m",
  "severity": "error",                 // "error" | "warning"
  "reference": "NFPC 303 제6조1호나 + 프로젝트 설계기준(2m)",
  "feedback_template": "통로·계단 ... 간격({guidance_actual_spacing_m}m)이 ..."
}
```

- `condition`은 **문서용 표기**입니다. 실제 판정은 `main.py`의 `run_validation_rules()`가 `rule_id`별 분기로 수행합니다.
- `feedback_template`의 중괄호 변수는 검증 시 실제 값으로 `.format()` 치환됩니다.
- `applies_to`가 `"all"`이면 모든 공간, 배열이면 해당 `space_key`에만 적용됩니다.

전체 12개 규칙 목록과 구현 여부는 [README](../README.md#검증-규칙-v001v012) 및 [KNOWN_ISSUES.md](KNOWN_ISSUES.md) §1 참고.

---

## `lighting_formula`

광속법 공식 정의입니다. 계산 로직 자체는 `main.py`에 있고, 이 섹션은 **공식의 문서화·설명용**입니다.

```jsonc
{
  "method": "광속법 (Lumen Method)",
  "method_ref": "KDS 32 30 10 4.7(2)",
  "formula": "N = (E × A) / (F × U × M)",
  "variables":            { "N": "...", "E": "...", ... },
  "room_index_formula":   "K = (L × W) / (H × (L + W))",
  "room_index_variables": { "K": "...", "L": "...", ... },
  "work_plane_note":      "작업면 높이 KDS 32 30 10 4.3(3) ...",
  "alternative_method":   { "method": "축점법 (Point-by-Point)", ... },
  "cu_table_note":        "조명률 0.3~0.7 범위 ..."
}
```

---

## `standards_glossary`

표준별 주요 조항 요약입니다. Claude가 피드백을 생성할 때 근거 조항을 인용하는 데 사용됩니다.

```jsonc
"NFPC_303": {
  "title": "유도등 및 유도표지의 화재안전성능기준",
  "year": 2024,
  "issuer": "소방청",
  "effective_date": "2024-01-01",
  "key_clauses": {
    "제5조":   "피난구유도등 - 바닥 1.5m 이상",
    "제6조1호": "복도통로유도등 - 20m마다, 1m 이하 (지하역사는 바닥 중앙)",
    "제10조②": "비상전원 - 축전지 20분 이상, 지하역사는 60분 이상"
  }
}
```

수록 표준: `KDS_32_30_10`, `KDS_32_20_20`, `KDS_32_25_10`, `KDS_47_40_45`, `KDS_47_40_50`, `KDS_47_40_55`, `KEC`, `NFPC_303`

---

## `compliance_matrix`

공간 × 기준 빠른 참조표입니다. `validation_rules`의 보조 자료로, 어떤 공간이 어떤 표준의 적용을 받는지 한눈에 보여줍니다.

| | 조도기준 | 조명기구 | 콘센트 | 비상조명 | 유도등 | 접지 | UPS | 방폭 | CCTV |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 대합실 | KDS 32 30 10 | KS C 7653 | KDS 32 25 10 | NFPC 303 | NFPC 303 §6②	 | - | - | - | KDS 31 10 21 |
| 승강장 | KDS 32 30 10 | KS C 7653 | KDS 32 25 10 | NFPC 303 | NFPC 303 §6② | - | KDS 47 40 45 | - | KDS 47 40 75 |
| 통로·계단 | KDS 32 30 10 | KS C 7653 | KDS 32 25 10 | NFPC 303 | NFPC 303 §6①·③ | - | - | - | - |
| 기계실 | KDS 32 30 10 | KS C IEC 60079 | KEC 242.2 | NFPC 303 | NFPC 303 §6① | KEC 140·142 | - | KEC 242.2 | - |
| 역무실 | KDS 32 30 10 | KS C 7653 | KDS 32 25 10 | NFPC 303 | NFPC 303 §6② | KEC 140 | KDS 32 20 20 | - | KDS 31 10 21 |

---

## 무결성 검증

```bash
pytest tests/test_rules.py -v     # 71개 테스트
```

검증 항목: 최상위 키 존재, 공간 5종 모두 존재, 필수 필드 누락 여부, 조도 기준값 범위, 반사율 0~1 범위, `applies_to`의 `space_key` 유효성, `feedback_template` 변수명 일치 등.

---

## 값 개정 시 절차

1. `data/BIM_elec_data.xlsx`에서 해당 값을 수정합니다.
2. `src/rules_db.json`의 대응 필드를 함께 수정합니다.
   (현재 `excel_to_json.py`가 v2.0.0 스키마를 완전히 재현하지 못하므로 자동 변환에 의존하지 마세요 — [KNOWN_ISSUES.md](KNOWN_ISSUES.md) §2)
3. `_meta.last_updated`를 갱신하고, 값의 근거 조항을 해당 섹션의 `*_ref` 필드에 기록합니다.
4. `pytest`를 실행해 104개 테스트가 모두 통과하는지 확인합니다.
