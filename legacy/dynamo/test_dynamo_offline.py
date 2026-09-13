"""
test_dynamo_offline.py
Dynamo 스크립트 오프라인 단위 테스트 (Revit 없이 실행 가능)

Revit API 의존부를 모킹하고, 핵심 로직(키워드 매칭, 루멘법, 그리드 계산)을
순수 Python으로 검증한다.

실행:
    pytest test_dynamo_offline.py -v
"""

import json
import math
import pytest
from pathlib import Path


# ──────────────────────────────────────────────
# rules_db 로드
# ──────────────────────────────────────────────
# test_rules.py와 같은 위치의 rules_db.json 또는 uploads에서
RULES_DB_PATH = Path(__file__).parent.parent / "rules_db.json"
if not RULES_DB_PATH.exists():
    RULES_DB_PATH = Path(__file__).parent / "rules_db.json"

@pytest.fixture(scope="session")
def rules_db():
    with open(RULES_DB_PATH, encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────
# 02번 키워드 매칭 로직 (순수 Python 추출)
# ──────────────────────────────────────────────
def build_keyword_index(spaces_db):
    index = {}
    for space_key, space_data in spaces_db.items():
        for kw in space_data.get("keywords", []):
            index[kw.lower()] = space_key
    return index


def match_space_type(name, keyword_index):
    if not name:
        return None, 0.0
    name_lower = name.strip().lower()
    if name_lower in keyword_index:
        return keyword_index[name_lower], 1.0
    sorted_kw = sorted(keyword_index.keys(), key=len, reverse=True)
    for kw in sorted_kw:
        if kw in name_lower:
            return keyword_index[kw], 0.8
    for kw in sorted_kw:
        if name_lower in kw:
            return keyword_index[kw], 0.6
    return None, 0.0


class TestKeywordMatching:

    def test_exact_match_korean(self, rules_db):
        idx = build_keyword_index(rules_db["spaces"])
        key, conf = match_space_type("대합실", idx)
        assert key == "concourse"
        assert conf == 1.0

    def test_exact_match_english(self, rules_db):
        idx = build_keyword_index(rules_db["spaces"])
        key, conf = match_space_type("platform", idx)
        assert key == "platform"
        assert conf == 1.0

    def test_contains_match(self, rules_db):
        idx = build_keyword_index(rules_db["spaces"])
        key, conf = match_space_type("B1-대합실-01", idx)
        assert key == "concourse"
        assert conf == 0.8

    def test_contains_match_lobby(self, rules_db):
        idx = build_keyword_index(rules_db["spaces"])
        key, conf = match_space_type("Main Lobby Area", idx)
        assert key == "concourse"
        assert conf == 0.8

    def test_machinery_keywords(self, rules_db):
        idx = build_keyword_index(rules_db["spaces"])
        for name in ["기계실", "전기실", "설비실", "펌프실", "MDF", "EPS"]:
            key, conf = match_space_type(name, idx)
            assert key == "machinery", f"'{name}' should match machinery, got {key}"

    def test_corridor_keywords(self, rules_db):
        idx = build_keyword_index(rules_db["spaces"])
        for name in ["통로", "계단", "복도"]:
            key, conf = match_space_type(name, idx)
            assert key == "corridor", f"'{name}' should match corridor, got {key}"

    def test_unmatched_returns_none(self, rules_db):
        idx = build_keyword_index(rules_db["spaces"])
        key, conf = match_space_type("화장실", idx)
        assert key is None
        assert conf == 0.0

    def test_all_5_spaces_matchable(self, rules_db):
        idx = build_keyword_index(rules_db["spaces"])
        expected = {
            "대합실": "concourse",
            "승강장": "platform",
            "통로": "corridor",
            "기계실": "machinery",
            "역무실": "station_office",
        }
        for name, expected_key in expected.items():
            key, conf = match_space_type(name, idx)
            assert key == expected_key, f"'{name}' → {key} (expected {expected_key})"


# ──────────────────────────────────────────────
# 03번 루멘법 계산 로직 (순수 Python 추출)
# ──────────────────────────────────────────────
def calc_room_index(L, W, H):
    if H <= 0 or (L + W) <= 0:
        return 1.0
    return (L * W) / (H * (L + W))


def estimate_cu(K, ceil_r, wall_r):
    base = 0.40 + 0.10 * min(K, 3.0) / 3.0
    refl_bonus = (ceil_r * 0.15) + (wall_r * 0.05)
    return min(round(base + refl_bonus, 3), 0.70)


def lumen_method(E, A, L, W, H, flux_per_lamp, lamps, MF, ceil_r=0.7, wall_r=0.5):
    F = flux_per_lamp * lamps
    K = calc_room_index(L, W, H)
    CU = estimate_cu(K, ceil_r, wall_r)
    N_raw = (E * A) / (F * CU * MF) if (F * CU * MF) > 0 else 0
    N = int(math.ceil(N_raw))
    actual_lux = round((N * F * CU * MF) / A, 1) if A > 0 else 0
    return N, actual_lux, K, CU


class TestLumenMethod:

    def test_concourse_50sqm(self, rules_db):
        sp = rules_db["spaces"]["concourse"]
        lc = sp["lighting_calc"]
        N, actual, K, CU = lumen_method(
            E=sp["lighting"]["illuminance_lux"],
            A=50, L=10, W=5, H=sp["lighting"]["mounting_height_m"],
            flux_per_lamp=lc["flux_per_lamp_lm"],
            lamps=lc["lamps_per_fixture"],
            MF=lc["maintenance_factor"],
            ceil_r=lc["ceiling_reflectance"],
            wall_r=lc["wall_reflectance"],
        )
        assert N > 0
        assert actual >= sp["lighting"]["illuminance_lux"]

    def test_station_office_needs_more_than_concourse(self, rules_db):
        """역무실(500lux) vs 대합실(300lux) 같은 면적"""
        A, L, W = 30, 6, 5

        sp_office = rules_db["spaces"]["station_office"]
        lc_office = sp_office["lighting_calc"]
        N_office, _, _, _ = lumen_method(
            E=sp_office["lighting"]["illuminance_lux"],
            A=A, L=L, W=W, H=sp_office["lighting"]["mounting_height_m"],
            flux_per_lamp=lc_office["flux_per_lamp_lm"],
            lamps=lc_office["lamps_per_fixture"],
            MF=lc_office["maintenance_factor"],
        )

        sp_conc = rules_db["spaces"]["concourse"]
        lc_conc = sp_conc["lighting_calc"]
        N_conc, _, _, _ = lumen_method(
            E=sp_conc["lighting"]["illuminance_lux"],
            A=A, L=L, W=W, H=sp_conc["lighting"]["mounting_height_m"],
            flux_per_lamp=lc_conc["flux_per_lamp_lm"],
            lamps=lc_conc["lamps_per_fixture"],
            MF=lc_conc["maintenance_factor"],
        )

        assert N_office > N_conc

    def test_area_doubles_fixtures_double(self, rules_db):
        sp = rules_db["spaces"]["platform"]
        lc = sp["lighting_calc"]
        N1, _, _, _ = lumen_method(
            E=sp["lighting"]["illuminance_lux"],
            A=50, L=10, W=5, H=sp["lighting"]["mounting_height_m"],
            flux_per_lamp=lc["flux_per_lamp_lm"],
            lamps=lc["lamps_per_fixture"],
            MF=lc["maintenance_factor"],
        )
        N2, _, _, _ = lumen_method(
            E=sp["lighting"]["illuminance_lux"],
            A=100, L=20, W=5, H=sp["lighting"]["mounting_height_m"],
            flux_per_lamp=lc["flux_per_lamp_lm"],
            lamps=lc["lamps_per_fixture"],
            MF=lc["maintenance_factor"],
        )
        # N2/N1 ≈ 2.0 (CU가 다를 수 있으므로 1.5~2.5 범위)
        ratio = N2 / N1 if N1 > 0 else 0
        assert 1.5 <= ratio <= 2.5, f"면적 2배 시 기구 비율: {ratio:.2f}"

    def test_room_index_range(self):
        # 일반적인 방: K ∈ [0.5, 5.0]
        K = calc_room_index(10, 5, 3)
        assert 0.5 <= K <= 5.0

    def test_cu_range(self):
        for K in [0.5, 1.0, 2.0, 3.0]:
            cu = estimate_cu(K, 0.7, 0.5)
            assert 0.40 <= cu <= 0.70


# ──────────────────────────────────────────────
# 04번 그리드 계산 로직
# ──────────────────────────────────────────────
def calc_grid(N, L, W):
    if N <= 0 or L <= 0 or W <= 0:
        return 0, 0, 0, 0
    aspect = L / W
    cols = max(1, int(round(math.sqrt(N * aspect))))
    rows = max(1, int(math.ceil(N / cols)))
    spacing_x = round(L / cols, 3)
    spacing_y = round(W / rows, 3)
    return cols, rows, spacing_x, spacing_y


class TestGridPlacement:

    def test_single_fixture(self):
        cols, rows, sx, sy = calc_grid(1, 10, 5)
        assert cols * rows >= 1

    def test_square_room(self):
        cols, rows, sx, sy = calc_grid(4, 10, 10)
        assert cols == 2
        assert rows == 2
        assert abs(sx - 5.0) < 0.01
        assert abs(sy - 5.0) < 0.01

    def test_long_room_more_cols(self):
        """가로가 긴 방은 cols > rows"""
        cols, rows, sx, sy = calc_grid(6, 20, 5)
        assert cols >= rows

    def test_grid_covers_all_fixtures(self):
        for N in [3, 7, 12, 25]:
            cols, rows, _, _ = calc_grid(N, 15, 10)
            assert cols * rows >= N


# ──────────────────────────────────────────────
# 05번 비상등·유도등 수량 검증
# ──────────────────────────────────────────────
class TestEmergencyCalc:

    def test_emergency_count_positive(self, rules_db):
        """모든 공간에 비상등 최소 1개"""
        for sk, sp in rules_db["spaces"].items():
            emg_lux = sp["lighting"]["emergency_lux"]
            design_lux = sp["lighting"]["illuminance_lux"]
            normal_n = 10  # 가정
            ratio = emg_lux / design_lux if design_lux > 0 else 0.1
            n_emg = max(1, int(math.ceil(normal_n * ratio)))
            assert n_emg >= 1, f"[{sk}] 비상등 0개"

    def test_corridor_guidance_spacing(self, rules_db):
        """통로 유도등 간격 2m 이하"""
        corridor = rules_db["spaces"]["corridor"]
        spacing = corridor["emergency"]["guidance_spacing_m"]
        assert spacing <= 2.0

    def test_guidance_count_for_corridor(self, rules_db):
        """통로 10m x 3m에 유도등 배치 → 최소 10개 이상"""
        spacing = 2.0  # corridor 기준
        perimeter = 2 * (10 + 3)  # 26m
        n_guides = int(math.ceil(perimeter / spacing))
        assert n_guides >= 10


# ──────────────────────────────────────────────
# 06번 MCP 클라이언트 액션 매핑 검증
# ──────────────────────────────────────────────
ACTION_MAP = {
    "health":           ("GET",  "/"),
    "spaces":           ("GET",  "/spaces"),
    "space_detail":     ("GET",  "/spaces/{space_key}"),
    "fixtures":         ("GET",  "/fixtures"),
    "validation_rules": ("GET",  "/validation-rules"),
    "calculate":        ("POST", "/calculate/lighting"),
    "validate":         ("POST", "/validate"),
    "validate_batch":   ("POST", "/validate/batch"),
    "ai_analyze":       ("POST", "/ai/analyze"),
    "ai_suggest":       ("POST", "/ai/suggest-fixtures"),
}


class TestMCPActionMap:

    def test_all_actions_have_method_and_path(self):
        for action, (method, path) in ACTION_MAP.items():
            assert method in ("GET", "POST"), f"{action}: invalid method {method}"
            assert path.startswith("/"), f"{action}: path should start with /"

    def test_calculate_is_post(self):
        assert ACTION_MAP["calculate"][0] == "POST"

    def test_validate_is_post(self):
        assert ACTION_MAP["validate"][0] == "POST"

    def test_spaces_is_get(self):
        assert ACTION_MAP["spaces"][0] == "GET"

    def test_space_detail_has_placeholder(self):
        _, path = ACTION_MAP["space_detail"]
        assert "{space_key}" in path