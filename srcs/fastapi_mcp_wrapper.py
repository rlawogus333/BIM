"""
지하철역 전기설비 BIM 자동화 — FastAPI MCP 래퍼 (stdio)

본 스크립트는 main.py 의 FastAPI 핵심 로직(규칙 조회 / 조도 계산 / 검증 /
AI 피드백 / 분전반 용량 산출)을 Claude Desktop 에서 바로 호출할 수 있는
MCP(Model Context Protocol) 도구로 노출한다.

실행 방식
---------
Claude Desktop 이 stdio 로 직접 기동한다:
    "subway-bim-fastapi": {
        "command": "python",
        "args": ["C:\\\\dev\\\\subway-bim\\\\fastapi_mcp_wrapper.py"]
    }

내부 구현
---------
 - 별도의 uvicorn 프로세스는 띄우지 않는다. main.py 의 함수/Pydantic
   모델을 import 하여 in-process 로 호출한다. 따라서 포트 충돌 위험이
   없고, HTTP 네트워크 hop 이 제거되어 응답이 빠르다.
 - FastAPI 서버를 별도로 띄워 /docs 로 디버깅하고 싶다면 기존처럼
   `uvicorn main:app --port 8000` 을 그대로 실행하면 된다. 이 MCP
   래퍼와는 독립적으로 동작한다.

제공 도구 (tool)
-----------------
 1. list_spaces               — 지원 공간 목록
 2. get_space                 — 특정 공간 규칙 전체 반환
 3. list_validation_rules     — V001~V008 검증 규칙 목록
 4. calculate_lighting        — 광속법 조명기구 수량 산출
 5. calculate_load            — 분전반 용량·차단기 선정
 6. validate_design           — 설계 데이터 KDS/KEC 검증
 7. ai_analyze                — Claude AI 자연어 피드백
 8. health_check              — 규칙 DB 버전 / 기준 확인

의존성
-------
    pip install "mcp[cli]>=1.2.0" fastapi anthropic pydantic openpyxl
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional

# ──────────────────────────────────────────────
# main.py 경로 보장 (어디서 실행되든 안전하게 import)
# ──────────────────────────────────────────────
_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# main.py 의 로직 / 규칙 DB / Pydantic 모델 재사용
from main import (  # noqa: E402
    rules_db,
    get_space_rule,
    calc_room_index,
    estimate_cu,
    get_fixture_family_for_space,
    run_validation_rules,
    calc_space_load,
    select_breaker,
    select_panel_kva,
    get_claude_client,
    SpaceInput,
    LightingCalcRequest,
    LoadCalcRequest,
    ValidationInput,
    ValidationIssue,
    ClaudeAnalysisRequest,
)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:  # pragma: no cover
    sys.stderr.write(
        "FastMCP import 실패 — `pip install \"mcp[cli]>=1.2.0\"` 를 실행하세요.\n"
    )
    raise

import math

# ──────────────────────────────────────────────
# MCP 서버 인스턴스
# ──────────────────────────────────────────────
mcp = FastMCP(
    name="subway-bim-fastapi",
    instructions=(
        "지하철역 전기설비 BIM 자동화 검증/계산 서버. "
        "KDS 31 17 00, KEC 기준에 맞춰 조도 계산·분전반 용량 산출·설계 검증·"
        "Claude AI 피드백을 제공한다. revit-mcp 와 함께 사용하여 Revit 모델에서 "
        "수집한 공간 데이터를 본 서버로 검증하는 흐름을 권장한다."
    ),
)


# ──────────────────────────────────────────────
# 1. 헬스 / 메타
# ──────────────────────────────────────────────
@mcp.tool()
def health_check() -> dict[str, Any]:
    """서버 상태와 로드된 rules_db 메타(버전/기준 규격)를 반환한다."""
    return {
        "status": "ok",
        "version": rules_db["_meta"].get("version"),
        "standards": rules_db["_meta"].get("standards"),
        "spaces_loaded": list(rules_db["spaces"].keys()),
        "validation_rules_count": len(rules_db["validation_rules"]),
    }


# ──────────────────────────────────────────────
# 2. 규칙 조회 도구
# ──────────────────────────────────────────────
@mcp.tool()
def list_spaces() -> dict[str, Any]:
    """지원 공간 유형(대합실/승강장/통로/기계실/역무실) 요약 목록."""
    return {
        k: {
            "space_name_ko": v["space_name_ko"],
            "keywords": v["keywords"],
            "illuminance_lux": v["lighting"]["illuminance_lux"],
            "design_load_w_m2": v["load"]["design_load_w_m2"],
        }
        for k, v in rules_db["spaces"].items()
    }


@mcp.tool()
def get_space(space_key: str) -> dict[str, Any]:
    """특정 공간 키(concourse/platform/corridor/machinery/station_office)의 전체 KDS/KEC 규칙을 반환."""
    return get_space_rule(space_key)


@mcp.tool()
def list_fixtures() -> dict[str, Any]:
    """조명·설비 Revit Family 매핑 목록."""
    return rules_db["fixture_families"]


@mcp.tool()
def list_validation_rules() -> list[dict[str, Any]]:
    """검증 규칙 V001~V008 전체 목록."""
    return rules_db["validation_rules"]


# ──────────────────────────────────────────────
# 3. 조명 계산 (루멘법)
# ──────────────────────────────────────────────
@mcp.tool()
def calculate_lighting(
    space_key: str,
    area_m2: float,
    length_m: float,
    width_m: float,
    target_lux: Optional[float] = None,
    custom_flux_lm: Optional[float] = None,
    custom_mf: Optional[float] = None,
) -> dict[str, Any]:
    """
    광속법(Lumen Method) 으로 조명기구 필요 수량을 산출.

    공식: N = (E × A) / (F × CU × MF)

    Args:
        space_key: 공간 키 (concourse / platform / corridor / machinery / station_office)
        area_m2: 공간 면적 (m²)
        length_m: 공간 길이 (m)
        width_m: 공간 너비 (m)
        target_lux: 목표 조도 override (없으면 KDS 공간 기준값 사용)
        custom_flux_lm: 기구당 총 광속 override
        custom_mf: 감광보수율 override
    """
    space = get_space_rule(space_key)
    lc = space["lighting_calc"]
    lighting = space["lighting"]

    E = target_lux or lighting["illuminance_lux"]
    A = area_m2
    H = lighting["mounting_height_m"]
    MF = custom_mf or lc["maintenance_factor"]
    F = custom_flux_lm or (lc["flux_per_lamp_lm"] * lc["lamps_per_fixture"])

    K = calc_room_index(length_m, width_m, H)
    CU = estimate_cu(K, lc["ceiling_reflectance"], lc["wall_reflectance"])

    N_raw = (E * A) / (F * CU * MF)
    N = math.ceil(N_raw)
    actual_lux = round((N * F * CU * MF) / A, 1)

    return {
        "space_key": space_key,
        "space_name_ko": space["space_name_ko"],
        "area_m2": A,
        "target_lux": E,
        "room_index_K": round(K, 3),
        "utilization_factor_CU": CU,
        "maintenance_factor_MF": MF,
        "total_flux_per_fixture_lm": F,
        "required_fixtures": N,
        "actual_lux_estimate": actual_lux,
        "fixture_family": get_fixture_family_for_space(space_key),
        "kds_ref": lighting.get("kds_ref") or lighting.get("kec_ref"),
        "formula": f"N = ({E} x {A}) / ({F} x {CU} x {MF}) = {N_raw:.2f} -> {N}개",
    }


# ──────────────────────────────────────────────
# 4. 분전반 용량 산출
# ──────────────────────────────────────────────
@mcp.tool()
def calculate_load(
    spaces: list[dict[str, Any]],
    demand_factor: float = 0.7,
    safety_margin: float = 1.25,
    voltage_v: int = 380,
    phase: int = 3,
) -> dict[str, Any]:
    """
    분전반(Panel Board) 용량 산출.

    여러 공간의 부하를 합산하고 수요율·안전율을 적용해 설계 전류,
    권장 차단기(AT), 분전반(kVA) 용량을 산출한다.

    Args:
        spaces: [{space_key, space_name?, area_m2, length_m, width_m}, ...]
        demand_factor: 수요율 (기본 0.7)
        safety_margin: 안전율 (기본 1.25)
        voltage_v: 공급 전압 (기본 380 V)
        phase: 상수 (1 또는 3)
    """
    req = LoadCalcRequest(
        spaces=[SpaceInput(**s) for s in spaces],
        demand_factor=demand_factor,
        safety_margin=safety_margin,
        voltage_v=voltage_v,
        phase=phase,
    )

    space_details = []
    total_connected_w = 0.0
    weighted_pf_sum = 0.0

    for sp_input in req.spaces:
        space_rule = get_space_rule(sp_input.space_key)
        detail = calc_space_load(sp_input, space_rule)
        space_details.append(detail.dict())
        total_connected_w += detail.total_load_w
        weighted_pf_sum += detail.total_load_w * detail.power_factor

    total_connected_kw = total_connected_w / 1000
    avg_pf = weighted_pf_sum / total_connected_w if total_connected_w > 0 else 0.9
    demand_kw = total_connected_kw * req.demand_factor
    design_kw = demand_kw * req.safety_margin
    design_w = design_kw * 1000

    if req.phase == 3:
        design_current_a = design_w / (math.sqrt(3) * req.voltage_v * avg_pf)
    else:
        design_current_a = design_w / (req.voltage_v * avg_pf)

    breaker_a = select_breaker(design_current_a)
    panel_kva = select_panel_kva(design_kw, avg_pf)

    return {
        "spaces": space_details,
        "total_connected_load_kw": round(total_connected_kw, 2),
        "demand_factor": req.demand_factor,
        "demand_load_kw": round(demand_kw, 2),
        "safety_margin": req.safety_margin,
        "design_load_kw": round(design_kw, 2),
        "voltage_v": req.voltage_v,
        "phase": req.phase,
        "design_current_a": round(design_current_a, 1),
        "recommended_breaker_a": breaker_a,
        "recommended_panel_kva": panel_kva,
        "summary_ko": (
            f"총 {len(req.spaces)}개 공간 | "
            f"설비용량 {total_connected_kw:.1f}kW | "
            f"수요부하 {demand_kw:.1f}kW (수요율 {req.demand_factor}) | "
            f"설계부하 {design_kw:.1f}kW (안전율 {req.safety_margin}) | "
            f"설계전류 {design_current_a:.1f}A → "
            f"차단기 {breaker_a}AT / 분전반 {panel_kva}kVA 권장"
        ),
    }


# ──────────────────────────────────────────────
# 5. 설계 검증
# ──────────────────────────────────────────────
@mcp.tool()
def validate_design(
    space_key: str,
    space_name: Optional[str] = None,
    calculated_lux: Optional[float] = None,
    emergency_calculated_lux: Optional[float] = None,
    fixture_type: Optional[str] = None,
    guidance_actual_spacing_m: Optional[float] = None,
    outlet_actual_spacing_m: Optional[float] = None,
    ups_connected: Optional[bool] = None,
    cctv_circuit_dedicated: Optional[bool] = None,
    grounded: Optional[bool] = None,
) -> dict[str, Any]:
    """
    설계 데이터를 rules_db 기준으로 검증하고 위반 항목 목록을 반환.

    V001 조도 미달 / V002 유도등 간격 / V003 방폭등 / V004 UPS 연결 /
    V005 CCTV 전용회로 / V006 비상조명 조도 / V007 콘센트 간격 / V008 접지
    """
    data = ValidationInput(
        space_key=space_key,
        space_name=space_name,
        calculated_lux=calculated_lux,
        emergency_calculated_lux=emergency_calculated_lux,
        fixture_type=fixture_type,
        guidance_actual_spacing_m=guidance_actual_spacing_m,
        outlet_actual_spacing_m=outlet_actual_spacing_m,
        ups_connected=ups_connected,
        cctv_circuit_dedicated=cctv_circuit_dedicated,
        grounded=grounded,
    )

    space = get_space_rule(space_key)
    issues = run_validation_rules(data, space)
    error_count = sum(1 for i in issues if i.severity == "error")

    return {
        "space_key": space_key,
        "space_name": space_name or space["space_name_ko"],
        "pass": error_count == 0,
        "issue_count": len(issues),
        "issues": [i.dict() for i in issues],
    }


@mcp.tool()
def validate_batch(items: list[dict[str, Any]]) -> dict[str, Any]:
    """여러 공간을 한 번에 검증. items 는 validate_design 의 인자 dict 배열."""
    results = []
    for it in items:
        res = validate_design(**it)
        results.append(res)
    return {"total": len(results), "results": results}


# ──────────────────────────────────────────────
# 6. Claude AI 피드백
# ──────────────────────────────────────────────
@mcp.tool()
def ai_analyze(
    space_key: str,
    validation_results: list[dict[str, Any]],
    additional_context: Optional[str] = None,
) -> dict[str, Any]:
    """
    검증 결과(validate_design 의 issues) 를 Claude 에 전달하여
    한국어 개선 방안 리포트를 생성.

    환경변수 ANTHROPIC_API_KEY 가 설정되어 있어야 한다.
    """
    client = get_claude_client()
    space = get_space_rule(space_key)
    space_name = space["space_name_ko"]

    issues = [ValidationIssue(**v) for v in validation_results]
    issues_text = "\n".join(
        f"[{i.severity.upper()}] {i.rule_id} {i.rule_name}: {i.message}"
        for i in issues
    ) or "검출된 위반 항목 없음"

    extra_ctx = (
        f"## 추가 컨텍스트\n{additional_context}"
        if additional_context else ""
    )

    prompt = f"""당신은 지하철역 전기설비 BIM 자동화 전문가입니다.
KDS 31 17 00 및 KEC 기준을 준수하여 아래 검증 결과를 분석하고,
각 위반 항목에 대한 구체적 개선 방안을 한국어로 작성해주세요.

## 공간 정보
- 공간: {space_name} ({space_key})

## 검증 결과
{issues_text}

{extra_ctx}

## 요청 사항
1. 각 ERROR 항목의 원인과 Revit/revit-mcp 수정 방법
2. WARNING 항목의 권장 조치
3. 우선순위 순서로 정리
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return {
        "space_key": space_key,
        "space_name": space_name,
        "analysis": message.content[0].text,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }


# ──────────────────────────────────────────────
# 진입점 (stdio)
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # Claude Desktop 은 stdio 로 본 프로세스를 기동한다.
    # 로그는 stderr 로 흘려 MCP 프로토콜(stdout)과 충돌하지 않도록 한다.
    sys.stderr.write(
        f"[subway-bim-fastapi MCP] 기동 — rules_db v{rules_db['_meta'].get('version')} "
        f"| 공간 {len(rules_db['spaces'])}개 / 규칙 {len(rules_db['validation_rules'])}개\n"
    )
    mcp.run()
