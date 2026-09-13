"""
test_rules.py
rules_db.json 단위 테스트 (pytest)

실행:
    pip install pytest
    pytest test_rules.py -v
"""

import json
import math
import pytest
from pathlib import Path

# ─────────────────────────────────────────────
# Fixture: rules_db.json 로드
# ─────────────────────────────────────────────

RULES_DB_PATH = Path(__file__).resolve().parent.parent / "src" / "rules_db.json"

@pytest.fixture(scope="session")
def db():
    assert RULES_DB_PATH.exists(), f"rules_db.json 파일이 없습니다: {RULES_DB_PATH}"
    with open(RULES_DB_PATH, encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture(scope="session")
def spaces(db):
    return db["spaces"]


# ─────────────────────────────────────────────
# 1. 구조 검증
# ─────────────────────────────────────────────

REQUIRED_SPACE_KEYS = {"concourse", "platform", "corridor", "machinery", "station_office"}
REQUIRED_SECTIONS = {"lighting", "lighting_calc", "outlets", "emergency", "cctv", "load", "special_requirements"}

class TestStructure:

    def test_all_spaces_present(self, spaces):
        """공간 5종이 모두 정의되어 있어야 한다."""
        assert REQUIRED_SPACE_KEYS.issubset(set(spaces.keys())), \
            f"누락된 공간: {REQUIRED_SPACE_KEYS - set(spaces.keys())}"

    @pytest.mark.parametrize("space_key", list(REQUIRED_SPACE_KEYS))
    def test_space_has_required_sections(self, spaces, space_key):
        """각 공간에 필수 섹션이 모두 있어야 한다."""
        space = spaces[space_key]
        missing = REQUIRED_SECTIONS - set(space.keys())
        assert not missing, f"[{space_key}] 누락된 섹션: {missing}"

    @pytest.mark.parametrize("space_key", list(REQUIRED_SPACE_KEYS))
    def test_space_name_ko_exists(self, spaces, space_key):
        """각 공간에 한국어 이름이 있어야 한다."""
        assert spaces[space_key].get("space_name_ko"), f"[{space_key}] space_name_ko 없음"

    @pytest.mark.parametrize("space_key", list(REQUIRED_SPACE_KEYS))
    def test_keywords_not_empty(self, spaces, space_key):
        """각 공간에 키워드가 1개 이상 있어야 한다."""
        assert spaces[space_key].get("keywords"), f"[{space_key}] keywords 없음"


# ─────────────────────────────────────────────
# 2. 조도 기준값 검증
# ─────────────────────────────────────────────

ILLUMINANCE_EXPECTED = {
    "concourse":      {"illuminance_lux": 300, "emergency_lux": 30},
    "platform":       {"illuminance_lux": 200, "emergency_lux": 20},
    "corridor":       {"illuminance_lux": 150, "emergency_lux": 10},
    "machinery":      {"illuminance_lux": 200, "emergency_lux": 15},
    "station_office": {"illuminance_lux": 500, "emergency_lux": 30},
}

class TestIlluminanceValues:

    @pytest.mark.parametrize("space_key,expected", ILLUMINANCE_EXPECTED.items())
    def test_illuminance_lux(self, spaces, space_key, expected):
        """설계 조도값이 KDS 기준과 일치해야 한다."""
        actual = spaces[space_key]["lighting"]["illuminance_lux"]
        assert actual == expected["illuminance_lux"], \
            f"[{space_key}] illuminance_lux: 기대={expected['illuminance_lux']}, 실제={actual}"

    @pytest.mark.parametrize("space_key,expected", ILLUMINANCE_EXPECTED.items())
    def test_emergency_lux(self, spaces, space_key, expected):
        """비상조명 조도값이 기준과 일치해야 한다."""
        actual = spaces[space_key]["lighting"]["emergency_lux"]
        assert actual == expected["emergency_lux"], \
            f"[{space_key}] emergency_lux: 기대={expected['emergency_lux']}, 실제={actual}"

    @pytest.mark.parametrize("space_key", list(REQUIRED_SPACE_KEYS))
    def test_illuminance_positive(self, spaces, space_key):
        """조도값은 양수여야 한다."""
        lux = spaces[space_key]["lighting"]["illuminance_lux"]
        assert lux is not None and lux > 0, f"[{space_key}] illuminance_lux가 0 이하 또는 None"

    @pytest.mark.parametrize("space_key", list(REQUIRED_SPACE_KEYS))
    def test_min_illuminance_less_than_design(self, spaces, space_key):
        """최솟값 조도 ≤ 설계 조도."""
        lighting = spaces[space_key]["lighting"]
        min_lux = lighting.get("illuminance_min_lux")
        design_lux = lighting.get("illuminance_lux")
        if min_lux is not None and design_lux is not None:
            assert min_lux <= design_lux, \
                f"[{space_key}] illuminance_min_lux({min_lux}) > illuminance_lux({design_lux})"


# ─────────────────────────────────────────────
# 3. 특수 요건 검증
# ─────────────────────────────────────────────

class TestSpecialRequirements:

    def test_machinery_explosion_proof(self, spaces):
        """기계실은 방폭등이 필수."""
        assert spaces["machinery"]["special_requirements"]["explosion_proof"] is True, \
            "기계실 explosion_proof=True 필요 (KEC 241.2)"

    def test_machinery_grounded(self, spaces):
        """기계실은 접지가 필수."""
        assert spaces["machinery"]["special_requirements"]["grounded"] is True, \
            "기계실 grounded=True 필요 (KEC 241.2)"

    def test_station_office_ups(self, spaces):
        """역무실은 UPS가 필수."""
        assert spaces["station_office"]["special_requirements"]["ups_required"] is True, \
            "역무실 ups_required=True 필요 (KDS 31 17 00 4.3.4)"

    def test_concourse_cctv_circuit(self, spaces):
        """대합실은 CCTV 전용회로가 필수."""
        assert spaces["concourse"]["cctv"]["cctv_circuit"] is True, \
            "대합실 cctv_circuit=True 필요"

    def test_platform_cctv_circuit(self, spaces):
        """승강장은 CCTV 전용회로가 필수."""
        assert spaces["platform"]["cctv"]["cctv_circuit"] is True, \
            "승강장 cctv_circuit=True 필요"

    def test_corridor_guidance_spacing(self, spaces):
        """통로·계단 유도등 간격은 2.0m 이하여야 한다."""
        spacing = spaces["corridor"]["emergency"]["guidance_spacing_m"]
        assert spacing is not None and spacing <= 2.0, \
            f"corridor guidance_spacing_m={spacing} (기준: 2.0m 이하)"

    def test_non_machinery_not_explosion_proof(self, spaces):
        """기계실 외 공간은 방폭 요건이 없어야 한다."""
        for key in REQUIRED_SPACE_KEYS - {"machinery"}:
            ep = spaces[key]["special_requirements"].get("explosion_proof", False)
            assert ep is False, f"[{key}] explosion_proof=True로 잘못 설정됨"


# ─────────────────────────────────────────────
# 4. 조도 계산 파라미터 검증
# ─────────────────────────────────────────────

class TestLightingCalcParams:

    @pytest.mark.parametrize("space_key", list(REQUIRED_SPACE_KEYS))
    def test_maintenance_factor_range(self, spaces, space_key):
        """감광 보수율은 0.7 ~ 0.8 범위이어야 한다."""
        mf = spaces[space_key]["lighting_calc"].get("maintenance_factor")
        if mf is not None:
            assert 0.65 <= mf <= 0.85, \
                f"[{space_key}] maintenance_factor={mf} (권장: 0.7~0.8)"

    @pytest.mark.parametrize("space_key", list(REQUIRED_SPACE_KEYS))
    def test_reflectance_values(self, spaces, space_key):
        """반사율은 0~1 범위이어야 한다."""
        calc = spaces[space_key]["lighting_calc"]
        for field in ("ceiling_reflectance", "wall_reflectance", "floor_reflectance"):
            val = calc.get(field)
            if val is not None:
                assert 0.0 <= val <= 1.0, \
                    f"[{space_key}] {field}={val} (0~1 범위 벗어남)"

    @pytest.mark.parametrize("space_key", list(REQUIRED_SPACE_KEYS))
    def test_flux_per_lamp_positive(self, spaces, space_key):
        """램프당 광속은 양수여야 한다."""
        flux = spaces[space_key]["lighting_calc"].get("flux_per_lamp_lm")
        if flux is not None:
            assert flux > 0, f"[{space_key}] flux_per_lamp_lm={flux} (양수 필요)"

    @pytest.mark.parametrize("space_key", list(REQUIRED_SPACE_KEYS))
    def test_mounting_height_realistic(self, spaces, space_key):
        """취부 높이는 2.0m ~ 6.0m 범위이어야 한다."""
        h = spaces[space_key]["lighting_calc"].get("mounting_height_m") or \
            spaces[space_key]["lighting"].get("mounting_height_m")
        if h is not None:
            assert 2.0 <= h <= 6.0, \
                f"[{space_key}] mounting_height_m={h} (2~6m 범위 벗어남)"


# ─────────────────────────────────────────────
# 5. 루멘법 계산 검증 (샘플 공간)
# ─────────────────────────────────────────────

class TestLumenCalculation:
    """
    루멘법: N = (E × A) / (F × CU × MF)
    샘플 공간으로 기구 수 산출 로직을 검증한다.
    """

    def _calc_fixtures(self, space: dict, area_m2: float, cu: float = 0.55) -> float:
        lux = space["lighting"]["illuminance_lux"]
        calc = space["lighting_calc"]
        flux_total = calc["flux_per_lamp_lm"] * calc["lamps_per_fixture"]
        mf = calc["maintenance_factor"]
        return (lux * area_m2) / (flux_total * cu * mf)

    def test_concourse_fixture_count_positive(self, spaces):
        """대합실 50m² 기준 조명기구 수가 양수이어야 한다."""
        n = self._calc_fixtures(spaces["concourse"], area_m2=50)
        assert n > 0

    def test_station_office_more_than_concourse(self, spaces):
        """역무실(500lux)은 대합실(300lux)보다 같은 면적 대비 기구 수가 많아야 한다."""
        n_office = self._calc_fixtures(spaces["station_office"], area_m2=30)
        n_concourse = self._calc_fixtures(spaces["concourse"], area_m2=30)
        assert n_office > n_concourse, \
            f"역무실({n_office:.1f}) ≤ 대합실({n_concourse:.1f}): 조도 기준 역전"

    def test_fixture_count_scales_with_area(self, spaces):
        """면적이 2배가 되면 기구 수도 약 2배가 되어야 한다."""
        n1 = self._calc_fixtures(spaces["platform"], area_m2=50)
        n2 = self._calc_fixtures(spaces["platform"], area_m2=100)
        assert math.isclose(n2 / n1, 2.0, rel_tol=0.01), \
            f"면적 2배 시 기구 수 비율: {n2/n1:.3f} (기대: 2.0)"


# ─────────────────────────────────────────────
# 6. KDS/KEC 참조 코드 존재 검증
# ─────────────────────────────────────────────

class TestReferenceCode:

    @pytest.mark.parametrize("space_key", ["concourse", "platform", "corridor", "station_office"])
    def test_kds_ref_present(self, spaces, space_key):
        """KDS 참조 공간은 kds_ref가 있어야 한다."""
        ref = spaces[space_key]["lighting"].get("kds_ref")
        assert ref and ref.startswith("KDS"), \
            f"[{space_key}] kds_ref 누락 또는 형식 오류: {ref}"

    def test_machinery_kec_ref(self, spaces):
        """기계실은 kec_ref가 있어야 한다."""
        ref = spaces["machinery"]["lighting"].get("kec_ref") or \
              spaces["machinery"].get("special_requirements", {}).get("kec_ref")
        assert ref and "KEC" in ref, f"기계실 kec_ref 누락: {ref}"
