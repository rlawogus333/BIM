"""
Phase 3 — FastAPI MCP 서버 테스트
pytest test_phase3.py -v
"""
import math

import pytest
from fastapi.testclient import TestClient

from main import (
    app,
    calc_room_index,
    estimate_cu,
    select_breaker,
    select_panel_kva,
    rules_db,
)

client = TestClient(app)


# ────────────────────────────────────────────────
# 헬스 체크
# ────────────────────────────────────────────────

class TestHealthCheck:
    def test_root(self):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        # rules_db v2.0.0 부터 표준 항목이 "KDS 32 30 10 (옥내조명설비, 2024)" 형태로 기재됨
        joined = " ".join(data["standards"])
        assert "KDS" in joined and "KEC" in joined and "NFPC" in joined


# ────────────────────────────────────────────────
# get_rules Tool — 공간별 기준 조회
# ────────────────────────────────────────────────

class TestGetRules:
    def test_list_spaces(self):
        r = client.get("/spaces")
        assert r.status_code == 200
        data = r.json()
        assert "concourse" in data
        assert "platform" in data
        assert "corridor" in data
        assert "machinery" in data
        assert "station_office" in data

    @pytest.mark.parametrize("space_key,expected_lux", [
        ("concourse", 300),
        ("platform", 200),
        ("corridor", 150),
        ("machinery", 200),
        ("station_office", 500),
    ])
    def test_get_space(self, space_key, expected_lux):
        r = client.get(f"/spaces/{space_key}")
        assert r.status_code == 200
        data = r.json()
        assert data["lighting"]["illuminance_lux"] == expected_lux

    def test_get_space_not_found(self):
        r = client.get("/spaces/nonexistent")
        assert r.status_code == 404

    def test_list_fixtures(self):
        r = client.get("/fixtures")
        assert r.status_code == 200
        data = r.json()
        assert "ceiling_light" in data
        assert "explosion_proof_light" in data

    def test_list_validation_rules(self):
        r = client.get("/validation-rules")
        assert r.status_code == 200
        data = r.json()
        # v2.0.0 에서 V009~V012 추가 (지하역사 비상전원·바닥유도등·PSD·유도등 높이)
        assert len(data) == len(rules_db["validation_rules"])
        ids = [r["rule_id"] for r in data]
        assert ids[:8] == [f"V{n:03d}" for n in range(1, 9)]
        rule_ids = [r["rule_id"] for r in data]
        assert "V001" in rule_ids
        assert "V008" in rule_ids


# ────────────────────────────────────────────────
# 조명 계산
# ────────────────────────────────────────────────

class TestLightingCalc:
    def test_concourse_basic(self):
        r = client.post("/calculate/lighting", json={
            "space_key": "concourse",
            "area_m2": 500.0,
            "length_m": 25.0,
            "width_m": 20.0,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["target_lux"] == 300
        assert data["required_fixtures"] > 0
        assert data["actual_lux_estimate"] >= 300
        assert "KDS" in (data["kds_ref"] or "")

    def test_machinery_uses_kec(self):
        """기계실은 KEC 242.2(폭발위험장소) 근거를 보유해야 한다.

        calculate_lighting 의 kds_ref 는 `kds_ref or kec_ref` 순으로 반환하므로
        둘 다 있는 기계실은 KDS 값이 나온다. 방폭 근거는 공간 규칙에서 확인한다.
        """
        r = client.post("/calculate/lighting", json={
            "space_key": "machinery",
            "area_m2": 100.0,
            "length_m": 10.0,
            "width_m": 10.0,
        })
        assert r.status_code == 200
        assert r.json()["required_fixtures"] > 0

        space = client.get("/spaces/machinery").json()
        assert "KEC 242.2" in space["lighting"]["kec_ref"]
        assert space["special_requirements"]["explosion_proof"] is True

    def test_custom_overrides(self):
        r = client.post("/calculate/lighting", json={
            "space_key": "corridor",
            "area_m2": 200.0,
            "length_m": 40.0,
            "width_m": 5.0,
            "target_lux": 200,
            "custom_flux_lm": 5000,
            "custom_mf": 0.8,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["target_lux"] == 200
        assert data["maintenance_factor_MF"] == 0.8

    def test_invalid_space(self):
        r = client.post("/calculate/lighting", json={
            "space_key": "unknown",
            "area_m2": 100,
            "length_m": 10,
            "width_m": 10,
        })
        assert r.status_code == 404


# ────────────────────────────────────────────────
# calc_load Tool — 분전반 용량 산출
# ────────────────────────────────────────────────

class TestCalcLoad:
    def test_single_space(self):
        r = client.post("/calculate/load", json={
            "spaces": [
                {"space_key": "concourse", "area_m2": 500, "length_m": 25, "width_m": 20}
            ]
        })
        assert r.status_code == 200
        data = r.json()
        assert data["total_connected_load_kw"] > 0
        assert data["design_current_a"] > 0
        assert data["recommended_breaker_a"] > 0
        assert data["recommended_panel_kva"] > 0
        assert len(data["spaces"]) == 1

    def test_multi_space(self):
        r = client.post("/calculate/load", json={
            "spaces": [
                {"space_key": "concourse", "area_m2": 500, "length_m": 25, "width_m": 20},
                {"space_key": "platform", "area_m2": 400, "length_m": 80, "width_m": 5},
                {"space_key": "station_office", "area_m2": 50, "length_m": 10, "width_m": 5},
            ],
            "demand_factor": 0.7,
            "safety_margin": 1.25,
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["spaces"]) == 3
        assert data["demand_factor"] == 0.7
        assert data["design_load_kw"] > data["demand_load_kw"]

    def test_single_phase(self):
        r = client.post("/calculate/load", json={
            "spaces": [
                {"space_key": "station_office", "area_m2": 50, "length_m": 10, "width_m": 5}
            ],
            "phase": 1,
            "voltage_v": 220,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["phase"] == 1
        assert data["voltage_v"] == 220

    def test_special_loads_included(self):
        """승강장은 스크린도어 부하, 역무실은 UPS 부하 포함"""
        r = client.post("/calculate/load", json={
            "spaces": [
                {"space_key": "platform", "area_m2": 400, "length_m": 80, "width_m": 5},
            ]
        })
        data = r.json()
        platform_detail = data["spaces"][0]
        assert platform_detail["special_load_w"] > 0  # 스크린도어

        r2 = client.post("/calculate/load", json={
            "spaces": [
                {"space_key": "station_office", "area_m2": 50, "length_m": 10, "width_m": 5},
            ]
        })
        data2 = r2.json()
        office_detail = data2["spaces"][0]
        assert office_detail["special_load_w"] > 0  # UPS


# ────────────────────────────────────────────────
# validate_design Tool — KDS 기준 검증
# ────────────────────────────────────────────────

class TestValidateDesign:
    def test_all_pass(self):
        """모든 기준 통과 케이스"""
        r = client.post("/validate", json={
            "space_key": "concourse",
            "calculated_lux": 350,
            "emergency_calculated_lux": 40,
            "outlet_actual_spacing_m": 4.0,
            "cctv_circuit_dedicated": True,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["pass"] is True
        assert data["issue_count"] == 0

    def test_illuminance_fail(self):
        """V001: 조도 기준 미달"""
        r = client.post("/validate", json={
            "space_key": "concourse",
            "calculated_lux": 200,
        })
        data = r.json()
        assert data["pass"] is False
        issues = data["issues"]
        assert any(i["rule_id"] == "V001" for i in issues)

    def test_guidance_spacing_fail(self):
        """V002: 유도등 간격 초과 (통로)"""
        r = client.post("/validate", json={
            "space_key": "corridor",
            "guidance_actual_spacing_m": 5.0,
        })
        data = r.json()
        assert any(i["rule_id"] == "V002" for i in data["issues"])

    def test_explosion_proof_fail(self):
        """V003: 기계실에 일반 조명기구 사용"""
        r = client.post("/validate", json={
            "space_key": "machinery",
            "fixture_type": "ceiling_light",
        })
        data = r.json()
        assert any(i["rule_id"] == "V003" for i in data["issues"])

    def test_ups_fail(self):
        """V004: 역무실 UPS 미연결"""
        r = client.post("/validate", json={
            "space_key": "station_office",
            "ups_connected": False,
        })
        data = r.json()
        assert any(i["rule_id"] == "V004" for i in data["issues"])

    def test_cctv_circuit_warning(self):
        """V005: CCTV 전용회로 미구성 (warning)"""
        r = client.post("/validate", json={
            "space_key": "concourse",
            "cctv_circuit_dedicated": False,
        })
        data = r.json()
        warnings = [i for i in data["issues"] if i["severity"] == "warning"]
        assert any(i["rule_id"] == "V005" for i in warnings)

    def test_emergency_lux_fail(self):
        """V006: 비상조명 조도 미달"""
        r = client.post("/validate", json={
            "space_key": "platform",
            "emergency_calculated_lux": 5,
        })
        data = r.json()
        assert any(i["rule_id"] == "V006" for i in data["issues"])

    def test_grounding_fail(self):
        """V008: 기계실 접지 미설치"""
        r = client.post("/validate", json={
            "space_key": "machinery",
            "grounded": False,
        })
        data = r.json()
        assert any(i["rule_id"] == "V008" for i in data["issues"])

    def test_batch_validate(self):
        """일괄 검증"""
        r = client.post("/validate/batch", json=[
            {"space_key": "concourse", "calculated_lux": 350},
            {"space_key": "machinery", "fixture_type": "ceiling_light", "grounded": False},
        ])
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert data["results"][0]["pass"] is True
        assert data["results"][1]["pass"] is False


# ────────────────────────────────────────────────
# 내부 유틸리티 단위 테스트
# ────────────────────────────────────────────────

class TestUtilities:
    def test_room_index(self):
        K = calc_room_index(25, 20, 3.5)
        expected = (25 * 20) / (3.5 * (25 + 20))
        assert abs(K - expected) < 0.001

    def test_estimate_cu_range(self):
        """CU는 항상 0.4 ~ 0.7 범위"""
        for K in [0.5, 1.0, 2.0, 3.0, 5.0]:
            cu = estimate_cu(K, 0.7, 0.5)
            assert 0.4 <= cu <= 0.7

    def test_select_breaker(self):
        assert select_breaker(35) == 40
        assert select_breaker(100) == 100
        assert select_breaker(15) == 15
        assert select_breaker(0.5) == 15

    def test_select_panel_kva(self):
        assert select_panel_kva(8, 0.9) >= 8 / 0.9
        assert select_panel_kva(45, 0.9) == 50  # 45/0.9=50kVA


# ────────────────────────────────────────────────
# Claude AI 엔드포인트 (API 키 없으면 503)
# ────────────────────────────────────────────────

class TestClaudeAI:
    def test_analyze_no_key(self):
        """API 키 없을 때 503 반환"""
        import os
        original = os.environ.get("ANTHROPIC_API_KEY")
        os.environ.pop("ANTHROPIC_API_KEY", None)

        r = client.post("/ai/analyze", json={
            "space_key": "concourse",
            "validation_results": [
                {"rule_id": "V001", "rule_name": "조도 미달",
                 "severity": "error", "message": "테스트 메시지"}
            ],
        })
        assert r.status_code == 503

        if original:
            os.environ["ANTHROPIC_API_KEY"] = original

    def test_suggest_no_key(self):
        """API 키 없을 때 503 반환"""
        import os
        original = os.environ.get("ANTHROPIC_API_KEY")
        os.environ.pop("ANTHROPIC_API_KEY", None)

        r = client.post("/ai/suggest-fixtures", json={
            "space_key": "concourse",
            "area_m2": 500,
            "length_m": 25,
            "width_m": 20,
        })
        assert r.status_code == 503

        if original:
            os.environ["ANTHROPIC_API_KEY"] = original
