"""
excel_to_json.py
구글 시트(또는 .xlsx)에서 rules_db.json을 생성하는 스크립트.

사용법:
    pip install openpyxl
    python excel_to_json.py --input BIM_elec_data.xlsx --output rules_db.json

지원 시트:
    - space_rules   : 공간별 전기설비 요건
    - lighting_calc : 조명 계산 파라미터
    - fixture_family: Revit 조명기구 패밀리 정보

컬럼명 매핑:
    BIM_elec_data.xlsx의 실제 컬럼명을 rules_db 내부 필드명으로 자동 변환합니다.
    SPACE_RULES_COL_MAP / LIGHTING_CALC_COL_MAP / FIXTURE_FAMILY_COL_MAP 참조.
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("[ERROR] openpyxl이 설치되지 않았습니다. 'pip install openpyxl'을 실행하세요.")
    sys.exit(1)


# ─────────────────────────────────────────────
# 컬럼명 매핑 딕셔너리
# Excel 실제 컬럼명(키) → 내부 처리용 필드명(값)
# ─────────────────────────────────────────────

SPACE_RULES_COL_MAP: dict[str, str] = {
    # 기본 식별자
    "space_id":             "space_key",
    "space_name_kr":        "space_name_ko",
    # 유도등
    "exit_guide_spacing_m": "guidance_spacing_m",
    # CCTV
    "cctv_power":           "cctv_circuit",
    # 특수 요건
    "ups_power":            "ups_required",
    "grounding_required":   "grounded",
    # 참조 조항
    "kds_clause":           "kds_ref",
    "nfpc_clause":          "nfpc_ref",
    # 이하는 이름이 같아 매핑 불필요하나, 명시적으로 포함
    "illuminance_lux":      "illuminance_lux",
    "explosion_proof":      "explosion_proof",
}

LIGHTING_CALC_COL_MAP: dict[str, str] = {
    "space_id":       "space_key",
    "ceiling_h_m":    "mounting_height_m",   # 취부 높이
    "maint_factor_M": "maintenance_factor",  # 감광 보수율 MF
    "util_factor_U":  "utilization_factor",  # 조명률 CU (직접 값)
    "lumen_F":        "flux_total_lm",       # 기구당 총 광속(lm)
    "lumen_lm":       "flux_total_lm",       # fixture_family 시트도 동일 처리
    "refl_ceil_%":    "ceiling_reflectance_pct",
    "refl_wall_%":    "wall_reflectance_pct",
    "refl_floor_%":   "floor_reflectance_pct",
    "LPD_W_m2":       "load_w_m2",           # 조명 전력밀도 → 설계 부하
}

FIXTURE_FAMILY_COL_MAP: dict[str, str] = {
    "family_id":        "fixture_id",
    "type_kr":          "fixture_type",
    "type_en":          "fixture_type_en",
    "revit_family":     "revit_family_name",
    "face_type":        "mount_face",
    "mount_height_m":   "mount_height_m",
    "applicable_space": "space_keys_kr",   # 한국어 공간명 → 후처리로 영문 키 변환
    "notes":            "note",
}


# ─────────────────────────────────────────────
# 보조 상수
# ─────────────────────────────────────────────

# 한국어 공간명 → rules_db space_key 변환
SPACE_KR_TO_KEY: dict[str, str] = {
    "대합실":                   "concourse",
    "승강장":                   "platform",
    "통로·계단":                "corridor",
    "통로":                     "corridor",
    "계단":                     "corridor",
    "통로·계단 (방화구획 경계)": "corridor",
    "기계실":                   "machinery",
    "역무실":                   "station_office",
}

# space_id 패턴(SR-01 등) → space_key 변환
# Excel의 space_rules 시트에서 space_id가 코드 형태일 경우 사용
SPACE_ID_TO_KEY: dict[str, str] = {
    "SR-01": "concourse",
    "SR-02": "platform",
    "SR-03": "corridor",
    "SR-04": "machinery",
    "SR-05": "station_office",
}

# 한국어 space_name → space_key (space_id 매핑 실패 시 폴백)
SPACE_NAME_KO_TO_KEY: dict[str, str] = {
    "대합실":    "concourse",
    "승강장":    "platform",
    "통로·계단": "corridor",
    "기계실":    "machinery",
    "역무실":    "station_office",
}

# Excel에 keywords 컬럼이 없을 때 사용하는 기본값
DEFAULT_KEYWORDS: dict[str, list[str]] = {
    "concourse":      ["대합실", "concourse", "홀", "hall", "로비", "lobby"],
    "platform":       ["승강장", "platform", "플랫폼", "역사", "스크린도어"],
    "corridor":       ["통로", "계단", "corridor", "stairs", "복도", "passage", "hallway"],
    "machinery":      ["기계실", "machinery", "전기실", "설비실", "펌프실", "MDF", "EPS"],
    "station_office": ["역무실", "station_office", "사무실", "office", "관제실", "control room"],
}


# ─────────────────────────────────────────────
# 헬퍼 함수
# ─────────────────────────────────────────────

def remap_row(row: dict, col_map: dict) -> dict:
    """
    col_map에 따라 딕셔너리 키를 변환한다.
    매핑에 없는 키는 원래 이름 그대로 유지한다.
    """
    return {col_map.get(k, k): v for k, v in row.items()}


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().upper() in ("TRUE", "Y", "YES", "1", "O")
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _float_or_none(value):
    """#DIV/0!, -, None 등 비정상 값은 None으로 처리."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in ("", "-", "#DIV/0!", "None", "N/A"):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _str_or_none(value):
    if value is None:
        return None
    s = str(value).strip()
    return None if s in ("", "-", "None", "N/A") else s


def _pct_to_ratio(value) -> float | None:
    """
    백분율(0~100 범위) → 비율(0.0~1.0) 변환.
    이미 0~1 범위이면 그대로 반환.
    """
    v = _float_or_none(value)
    if v is None:
        return None
    return round(v / 100.0, 3) if v > 1.0 else round(v, 3)


def _split_kds_kec(ref_str: str | None) -> tuple[str | None, str | None]:
    """
    'KEC 242.2 / KDS 32 10 11 §3.3' 처럼 혼합된 참조 문자열을
    (kds_ref, kec_ref) 튜플로 분리한다.
    순수 KDS 또는 KEC 단독 문자열도 처리한다.
    """
    if not ref_str:
        return None, None
    kds_part: str | None = None
    kec_part: str | None = None
    for token in ref_str.split("/"):
        t = token.strip()
        if not t:
            continue
        if t.startswith("KEC"):
            kec_part = t
        elif t.startswith("KDS") or t.startswith("NFPC"):
            kds_part = t
        else:
            kds_part = t  # 분류 불가 → KDS로 편입
    return kds_part, kec_part


def _kr_space_names_to_keys(raw: str | None) -> list[str]:
    """
    'applicable_space' 셀의 한국어 공간명 문자열을 space_key 리스트로 변환.
    예: '대합실, 승강장, 역무실' → ['concourse', 'platform', 'station_office']
    매핑되지 않는 공간명은 경고와 함께 건너뛴다.
    """
    if not raw:
        return []
    keys: list[str] = []
    seen: set[str] = set()
    for token in str(raw).split(","):
        token = token.strip()
        if not token or token in ("-", "전 구역 (주간선)", "전 구역"):
            continue
        matched = SPACE_KR_TO_KEY.get(token)
        if matched and matched not in seen:
            keys.append(matched)
            seen.add(matched)
        elif not matched:
            print(f"  [WARN] applicable_space 매핑 불가: '{token}' — SPACE_KR_TO_KEY에 추가하세요.")
    return keys


def sheet_to_dicts(ws) -> list[dict]:
    """워크시트의 첫 번째 행을 헤더로 사용해 딕셔너리 리스트로 변환."""
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
    result = []
    for row in rows[1:]:
        if all(v is None for v in row):
            continue  # 완전히 빈 행 스킵
        result.append(dict(zip(headers, row)))
    return result


# ─────────────────────────────────────────────
# Sheet 1: space_rules → spaces 섹션
# ─────────────────────────────────────────────

def parse_space_rules(rows: list[dict]) -> dict:
    """
    space_rules 시트를 파싱하여 spaces 딕셔너리를 반환한다.

    컬럼명은 SPACE_RULES_COL_MAP으로 자동 변환된다.
    Excel에 없는 필드(keywords, outlet_spacing_m 등)는
    기본값(DEFAULT_KEYWORDS) 또는 None으로 채워진다.
    """
    spaces: dict = {}
    for raw_row in rows:
        r = remap_row(raw_row, SPACE_RULES_COL_MAP)

        raw_id = _str_or_none(r.get("space_key"))
        if not raw_id:
            continue

        # space_id가 SR-01 같은 코드 형태이면 영문 key로 변환
        # 변환 우선순위: SPACE_ID_TO_KEY → space_name_ko 기반 폴백 → 원본 값 유지
        if raw_id in SPACE_ID_TO_KEY:
            key = SPACE_ID_TO_KEY[raw_id]
        else:
            name_ko = _str_or_none(r.get("space_name_ko")) or ""
            key = SPACE_NAME_KO_TO_KEY.get(name_ko, raw_id)

        # keywords: 컬럼이 없으면 DEFAULT_KEYWORDS 사용
        keywords_raw = r.get("keywords")
        if keywords_raw:
            keywords = [k.strip() for k in str(keywords_raw).split(",") if k.strip()]
        else:
            keywords = DEFAULT_KEYWORDS.get(key, [key])

        # kds_ref / kec_ref: 단일 셀에 혼합된 경우 자동 분리
        kds_ref_raw = _str_or_none(r.get("kds_ref"))
        kec_ref_raw = _str_or_none(r.get("kec_ref"))
        if kds_ref_raw and ("KEC" in kds_ref_raw or "/" in kds_ref_raw):
            kds_ref_raw, kec_ref_raw = _split_kds_kec(kds_ref_raw)

        spaces[key] = {
            "space_key":     key,
            "space_name_ko": _str_or_none(r.get("space_name_ko")) or key,
            "keywords":      keywords,
            "lighting": {
                "illuminance_lux":   _float_or_none(r.get("illuminance_lux")),
                "emergency_lux":     None,   # lighting_calc 시트에서 병합
                "mounting_height_m": None,   # lighting_calc 시트에서 병합
                "kds_ref":           kds_ref_raw,
                "kec_ref":           kec_ref_raw,
            },
            "outlets": {
                # outlet_spacing_m 컬럼이 Excel에 없음 → None (수동 입력 필요)
                "spacing_m": _float_or_none(r.get("outlet_spacing_m")),
            },
            "emergency": {
                "guidance_spacing_m": _float_or_none(r.get("guidance_spacing_m")),
            },
            "cctv": {
                "cctv_circuit": _bool(r.get("cctv_circuit")),
            },
            "load": {
                "design_load_w_m2": None,   # lighting_calc의 LPD_W_m2에서 병합
            },
            "special_requirements": {
                "explosion_proof": _bool(r.get("explosion_proof")),
                "ups_required":    _bool(r.get("ups_required")),
                "grounded":        _bool(r.get("grounded")),
            },
        }
    return spaces


# ─────────────────────────────────────────────
# Sheet 2: lighting_calc → spaces[].lighting_calc 병합
# ─────────────────────────────────────────────

def merge_lighting_calc(spaces: dict, rows: list[dict]) -> None:
    """
    lighting_calc 시트 데이터를 spaces에 병합한다.

    주요 변환 규칙:
      - refl_*_% 컬럼: 백분율(0~100) → 비율(0.0~1.0) 자동 변환
      - lumen_F: 기구당 총 광속(lm) → flux_per_lamp_lm 저장, lamps_per_fixture=1
        (Excel에는 램프/기구 분리 정보가 없으므로 총 광속을 1등으로 처리)
      - LPD_W_m2: load.design_load_w_m2에 복사
      - ceiling_h_m: lighting.mounting_height_m에 복사
    """
    for raw_row in rows:
        r = remap_row(raw_row, LIGHTING_CALC_COL_MAP)

        raw_id = _str_or_none(r.get("space_key"))
        if not raw_id:
            continue
        # space_rules와 동일하게 SR-01 → concourse 변환
        if raw_id in SPACE_ID_TO_KEY:
            key = SPACE_ID_TO_KEY[raw_id]
        else:
            name_ko = _str_or_none(r.get("space_name_kr") or r.get("space_name_ko")) or ""
            key = SPACE_NAME_KO_TO_KEY.get(name_ko, raw_id)

        if key not in spaces:
            continue

        ceil_r  = _pct_to_ratio(r.get("ceiling_reflectance_pct"))
        wall_r  = _pct_to_ratio(r.get("wall_reflectance_pct"))
        floor_r = _pct_to_ratio(r.get("floor_reflectance_pct"))
        mf      = _float_or_none(r.get("maintenance_factor"))
        flux    = _float_or_none(r.get("flux_total_lm"))
        h       = _float_or_none(r.get("mounting_height_m"))
        lpd     = _float_or_none(r.get("load_w_m2"))

        spaces[key]["lighting_calc"] = {
            "mounting_height_m":   h,
            "ceiling_reflectance": ceil_r,
            "wall_reflectance":    wall_r,
            "floor_reflectance":   floor_r,
            "maintenance_factor":  mf,
            # lumen_F = 기구당 총 광속 → lamps_per_fixture=1로 통합 저장
            "flux_per_lamp_lm":    flux,
            "lamps_per_fixture":   1,
        }

        # lighting 섹션에 mounting_height_m 복사
        if h is not None and spaces[key]["lighting"].get("mounting_height_m") is None:
            spaces[key]["lighting"]["mounting_height_m"] = h

        # load 섹션에 LPD_W_m2 복사
        if lpd is not None:
            spaces[key]["load"]["design_load_w_m2"] = lpd


# ─────────────────────────────────────────────
# Sheet 3: fixture_family → fixture_families 섹션
# ─────────────────────────────────────────────

def parse_fixture_families(rows: list[dict]) -> dict:
    """
    fixture_family 시트를 파싱하여 fixture_families 딕셔너리를 반환한다.

    applicable_space 컬럼의 한국어 공간명은 SPACE_KR_TO_KEY를 통해
    영문 space_key 리스트로 자동 변환된다.
    """
    families: dict = {}
    for raw_row in rows:
        r = remap_row(raw_row, FIXTURE_FAMILY_COL_MAP)

        fixture_type = _str_or_none(r.get("fixture_type"))
        if not fixture_type:
            continue

        # fixture_id 우선 사용, 없으면 fixture_type → snake_case 키 생성
        fixture_id = _str_or_none(r.get("fixture_id"))
        if fixture_id:
            fk = fixture_id.lower().replace("-", "_")
        else:
            fk = fixture_type.replace(" ", "_").replace("-", "_").lower()

        # applicable_space: 한국어 공간명 → 영문 space_key 리스트
        space_keys_raw = r.get("space_keys_kr") or r.get("space_keys", "")
        space_keys = _kr_space_names_to_keys(str(space_keys_raw))

        families[fk] = {
            "fixture_type":      fixture_type,
            "revit_family_name": _str_or_none(r.get("revit_family_name")),
            "mount_face":        _str_or_none(r.get("mount_face")),
            "space_keys":        space_keys,
            "note":              _str_or_none(r.get("note")),
        }
    return families


# ─────────────────────────────────────────────
# validation_rules 자동 생성
# ─────────────────────────────────────────────

def build_validation_rules() -> list[dict]:
    """
    KDS/KEC/소방시설 기준에 기반한 설계 검증 규칙(V001~V008)을 반환한다.

    규칙은 공간 데이터에 독립적이며, spaces 섹션의 기준값을 런타임에 참조한다.
    feedback_template의 중괄호 변수는 검증 시 실제 값으로 치환된다.
    """
    return [
        {
            "rule_id": "V001",
            "rule_name": "조도 기준 미달",
            "description": "설계 조도가 공간 기준값(illuminance_lux)보다 낮을 경우 위반",
            "applies_to": "all",
            "check_field": "calculated_lux",
            "condition": "calculated_lux < illuminance_lux",
            "severity": "error",
            "feedback_template": (
                "{space_name} 공간의 설계 조도({calculated_lux}lux)가 "
                "KDS 기준({illuminance_lux}lux)에 미달합니다. "
                "조명기구를 {shortfall_count}개 추가하거나 고출력 기구로 교체하십시오."
            ),
        },
        {
            "rule_id": "V002",
            "rule_name": "유도등 간격 초과",
            "description": "유도등 간격이 기준값(guidance_spacing_m)을 초과할 경우 위반",
            "applies_to": ["corridor"],
            "check_field": "guidance_actual_spacing_m",
            "condition": "guidance_actual_spacing_m > guidance_spacing_m",
            "severity": "error",
            "feedback_template": (
                "통로·계단 유도등 간격({guidance_actual_spacing_m}m)이 "
                "기준({guidance_spacing_m}m)을 초과합니다. 유도등을 추가 설치하십시오."
            ),
        },
        {
            "rule_id": "V003",
            "rule_name": "방폭등 미설치",
            "description": "기계실에 일반 조명기구 사용 시 위반",
            "applies_to": ["machinery"],
            "check_field": "fixture_type",
            "condition": "fixture_type != 'explosion_proof_light'",
            "severity": "error",
            "feedback_template": (
                "기계실에 방폭등(Ex e IIC T4 이상)이 설치되지 않았습니다. "
                "KEC 242.2에 따라 방폭 조명기구로 교체하십시오."
            ),
        },
        {
            "rule_id": "V004",
            "rule_name": "UPS 전원 미연결",
            "description": "역무실 전원이 UPS에 연결되지 않은 경우 위반",
            "applies_to": ["station_office"],
            "check_field": "ups_connected",
            "condition": "ups_connected == false",
            "severity": "error",
            "feedback_template": (
                "역무실 전원이 UPS({ups_capacity_kva}kVA, {ups_backup_minutes}분)에 "
                "연결되지 않았습니다. KDS 31 17 00 4.3.4에 따라 UPS 전원 회로를 구성하십시오."
            ),
        },
        {
            "rule_id": "V005",
            "rule_name": "CCTV 전용회로 미구성",
            "description": "대합실·승강장 CCTV가 전용회로를 사용하지 않는 경우 위반",
            "applies_to": ["concourse", "platform"],
            "check_field": "cctv_circuit_dedicated",
            "condition": "cctv_circuit_dedicated == false",
            "severity": "warning",
            "feedback_template": (
                "{space_name} CCTV 전원이 전용회로로 분리되지 않았습니다. "
                "보안장비 전원 안정성을 위해 전용회로를 구성하십시오."
            ),
        },
        {
            "rule_id": "V006",
            "rule_name": "비상조명 조도 미달",
            "description": "비상조명 조도가 기준값(emergency_lux)보다 낮을 경우 위반",
            "applies_to": "all",
            "check_field": "emergency_calculated_lux",
            "condition": "emergency_calculated_lux < emergency_lux",
            "severity": "error",
            "feedback_template": (
                "{space_name} 비상조명 조도({emergency_calculated_lux}lux)가 "
                "기준({emergency_lux}lux)에 미달합니다. "
                "소방시설 설치기준 제11조를 확인하십시오."
            ),
        },
        {
            "rule_id": "V007",
            "rule_name": "콘센트 간격 초과",
            "description": "콘센트 간격이 공간 기준(outlet_spacing_m)을 초과할 경우 위반",
            "applies_to": "all",
            "check_field": "outlet_actual_spacing_m",
            "condition": "outlet_actual_spacing_m > outlet_spacing_m",
            "severity": "warning",
            "feedback_template": (
                "{space_name} 콘센트 간격({outlet_actual_spacing_m}m)이 "
                "기준({outlet_spacing_m}m)을 초과합니다. 콘센트를 추가 설치하십시오."
            ),
        },
        {
            "rule_id": "V008",
            "rule_name": "접지 미설치 (기계실)",
            "description": "기계실 접지가 설치되지 않은 경우 위반",
            "applies_to": ["machinery"],
            "check_field": "grounded",
            "condition": "grounded == false",
            "severity": "error",
            "feedback_template": (
                "기계실에 접지(특수 접지, 10Ω 이하)가 설치되지 않았습니다. "
                "KEC 242.2에 따라 접지 공사를 시행하십시오."
            ),
        },
    ]


# ─────────────────────────────────────────────
# lighting_formula 자동 생성
# ─────────────────────────────────────────────

def build_lighting_formula() -> dict:
    """
    루멘법(Lumen Method) 공식 정의를 반환한다.

    Dynamo 스크립트(03_lumen_calc.py)와 FastAPI 서버(main.py)에서
    동일 공식으로 조도 계산을 수행하기 위한 참조 정보이다.
    """
    return {
        "method": "루멘법 (Lumen Method)",
        "formula": "N = (E × A) / (F × CU × MF)",
        "variables": {
            "N":  "필요 조명기구 수 (개)",
            "E":  "설계 조도 (lux)",
            "A":  "공간 면적 (m²)",
            "F":  "조명기구당 총 광속 (lm) = flux_per_lamp_lm × lamps_per_fixture",
            "CU": "조명률 (이용률, 공간 반사율과 실지수로 결정)",
            "MF": "감광 보수율 (maintenance_factor)",
        },
        "room_index_formula": "K = (L × W) / (H × (L + W))",
        "room_index_variables": {
            "K": "실지수",
            "L": "공간 길이 (m)",
            "W": "공간 너비 (m)",
            "H": "작업면에서 광원까지 높이 (m)",
        },
        "cu_estimation": {
            "method": "근사 보간 (실지수 + 반사율 기반)",
            "formula": "CU = base + refl_bonus",
            "base": "0.40 + 0.10 × min(K, 3.0) / 3.0",
            "refl_bonus": "(ceiling_r × 0.15) + (wall_r × 0.05)",
            "range": "0.40 ~ 0.70",
        },
        "cu_table_note": "조명률(CU)은 실지수(K)와 천장·벽·바닥 반사율에 따라 0.4~0.7 범위 적용",
    }


# ─────────────────────────────────────────────
# 바이트 스트림에서 직접 변환 (FastAPI 업로드 연동용)
# ─────────────────────────────────────────────

def excel_bytes_to_rules_db(data: bytes) -> dict:
    """
    Excel 파일의 바이트 데이터를 받아 rules_db 딕셔너리를 반환한다.

    FastAPI의 UploadFile.read()로 읽은 바이트를 직접 전달하면 된다.
    파일 I/O 없이 메모리에서 처리하므로 서버 환경에 적합하다.

    사용법:
        contents = await file.read()
        db = excel_bytes_to_rules_db(contents)
    """
    import io
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    sheet_names = wb.sheetnames

    def find_sheet(keywords: list[str]):
        for name in sheet_names:
            if any(k.lower() in name.lower() for k in keywords):
                return wb[name]
        return None

    ws_space   = find_sheet(["space_rules", "space", "공간"])
    ws_calc    = find_sheet(["lighting_calc", "lighting", "조도"])
    ws_fixture = find_sheet(["fixture_family", "fixture", "조명기구"])

    if not ws_space:
        raise ValueError("space_rules 시트를 찾을 수 없습니다.")

    spaces = parse_space_rules(sheet_to_dicts(ws_space))

    if ws_calc:
        merge_lighting_calc(spaces, sheet_to_dicts(ws_calc))

    fixture_families: dict = {}
    if ws_fixture:
        fixture_families = parse_fixture_families(sheet_to_dicts(ws_fixture))

    return {
        "_meta": {
            "version": "1.0.0",
            "description": "지하철역 전기설비 BIM 자동화 규칙 데이터베이스 (자동 생성)",
            "standards": ["KDS 31 17 00", "KEC 전기설비기술기준", "소방시설 설치기준"],
        },
        "spaces": spaces,
        "fixture_families": fixture_families,
        "validation_rules": build_validation_rules(),
        "lighting_formula": build_lighting_formula(),
    }


# ─────────────────────────────────────────────
# 메인 변환 함수
# ─────────────────────────────────────────────

def excel_to_rules_db(input_path: str, output_path: str) -> dict:
    wb = openpyxl.load_workbook(input_path, data_only=True)
    sheet_names = wb.sheetnames
    print(f"[INFO] 시트 목록: {sheet_names}")

    def find_sheet(keywords: list[str]):
        for name in sheet_names:
            if any(k.lower() in name.lower() for k in keywords):
                return wb[name]
        return None

    ws_space   = find_sheet(["space_rules", "space", "공간"])
    ws_calc    = find_sheet(["lighting_calc", "lighting", "조도"])
    ws_fixture = find_sheet(["fixture_family", "fixture", "조명기구"])

    if not ws_space:
        raise ValueError("space_rules 시트를 찾을 수 없습니다.")

    spaces = parse_space_rules(sheet_to_dicts(ws_space))

    if ws_calc:
        merge_lighting_calc(spaces, sheet_to_dicts(ws_calc))
    else:
        print("[WARN] lighting_calc 시트를 찾지 못했습니다. 조도 계산 파라미터가 누락됩니다.")

    fixture_families: dict = {}
    if ws_fixture:
        fixture_families = parse_fixture_families(sheet_to_dicts(ws_fixture))
    else:
        print("[WARN] fixture_family 시트를 찾지 못했습니다.")

    rules_db = {
        "_meta": {
            "version": "1.0.0",
            "description": "지하철역 전기설비 BIM 자동화 규칙 데이터베이스 (자동 생성)",
            "standards": ["KDS 31 17 00", "KEC 전기설비기술기준", "소방시설 설치기준"],
            "generated_from": Path(input_path).name,
        },
        "spaces": spaces,
        "fixture_families": fixture_families,
        "validation_rules": build_validation_rules(),
        "lighting_formula": build_lighting_formula(),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rules_db, f, ensure_ascii=False, indent=2)

    print(f"[OK] {output_path} 저장 완료")
    print(f"     공간 유형: {len(spaces)}개 — {list(spaces.keys())}")
    print(f"     조명기구 패밀리: {len(fixture_families)}개")
    print(f"     검증 규칙: {len(rules_db['validation_rules'])}개 (V001~V008)")
    print(f"     조도 계산 공식: {rules_db['lighting_formula']['method']}")
    return rules_db


# ─────────────────────────────────────────────
# CLI 진입점
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="구글 시트 xlsx → rules_db.json 변환기")
    parser.add_argument("--input",  "-i", required=True,            help="입력 xlsx 파일 경로")
    parser.add_argument("--output", "-o", default="rules_db.json",  help="출력 JSON 파일 경로 (기본: rules_db.json)")
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"[ERROR] 파일을 찾을 수 없습니다: {args.input}")
        sys.exit(1)

    excel_to_rules_db(args.input, args.output)


if __name__ == "__main__":
    main()
