"""
지하철역 전기설비 BIM 자동화 - FastAPI 백엔드
KDS 31 17 00 / KEC 기준 준수

실행:
    uvicorn main:app --reload --port 8000

Swagger UI:
    http://localhost:8000/docs
"""

import json
import math
import os
from pathlib import Path
from typing import Any, Optional

import anthropic
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from excel_to_json import excel_bytes_to_rules_db
from pydantic import BaseModel, Field

# ──────────────────────────────────────────────
# 앱 초기화
# ──────────────────────────────────────────────
app = FastAPI(
    title="지하철역 전기설비 BIM 자동화 API",
    description="KDS/KEC 기반 전기설비 규칙 검증 및 조명 계산",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# 규칙 DB 로드
# ──────────────────────────────────────────────
RULES_DB_PATH = Path(__file__).parent / "rules_db.json"

def load_rules_db() -> dict:
    with open(RULES_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

rules_db: dict = load_rules_db()

# ──────────────────────────────────────────────
# Claude API 클라이언트 (lazy 초기화)
# ──────────────────────────────────────────────
_claude_client = None


def get_claude_client() -> anthropic.Anthropic:
    """Claude API 클라이언트 싱글턴 (최초 호출 시 생성)"""
    global _claude_client
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.",
        )
    if _claude_client is None:
        _claude_client = anthropic.Anthropic(api_key=api_key)
    return _claude_client

# ──────────────────────────────────────────────
# Pydantic 모델
# ──────────────────────────────────────────────

class SpaceInput(BaseModel):
    """공간 정보 입력"""
    space_key: str = Field(..., example="concourse",
        description="공간 키 (concourse / platform / corridor / machinery / station_office)")
    space_name: Optional[str] = Field(None, example="B1 대합실")
    area_m2: float = Field(..., gt=0, example=500.0, description="공간 면적 (m²)")
    length_m: float = Field(..., gt=0, example=25.0, description="공간 길이 (m)")
    width_m: float = Field(..., gt=0, example=20.0, description="공간 너비 (m)")


class LightingCalcRequest(BaseModel):
    """조명 계산 요청"""
    space_key: str = Field(..., example="concourse")
    area_m2: float = Field(..., gt=0, example=500.0)
    length_m: float = Field(..., gt=0, example=25.0)
    width_m: float = Field(..., gt=0, example=20.0)
    target_lux: Optional[float] = Field(None, description="목표 조도 override (기본: 공간 기준값)")
    custom_flux_lm: Optional[float] = Field(None, description="기구당 광속 override")
    custom_mf: Optional[float] = Field(None, description="감광보수율 override")


class LightingCalcResult(BaseModel):
    """조명 계산 결과"""
    space_key: str
    space_name_ko: str
    area_m2: float
    target_lux: float
    room_index_K: float
    utilization_factor_CU: float
    maintenance_factor_MF: float
    total_flux_per_fixture_lm: float
    required_fixtures: int
    actual_lux_estimate: float
    fixture_family: str
    kds_ref: Optional[str]
    formula: str


class ValidationInput(BaseModel):
    """설계 검증 입력"""
    space_key: str = Field(..., example="concourse")
    space_name: Optional[str] = Field(None, example="B1 대합실")
    # 조명
    calculated_lux: Optional[float] = Field(None, description="설계 조도 (lux)")
    emergency_calculated_lux: Optional[float] = Field(None, description="비상조명 조도 (lux)")
    fixture_type: Optional[str] = Field(None,
        description="조명기구 타입 (ceiling_light / explosion_proof_light / ...)")
    # 유도등
    guidance_actual_spacing_m: Optional[float] = Field(None, description="유도등 실제 간격 (m)")
    # 콘센트
    outlet_actual_spacing_m: Optional[float] = Field(None, description="콘센트 실제 간격 (m)")
    # 특수
    ups_connected: Optional[bool] = Field(None, description="UPS 연결 여부 (역무실)")
    cctv_circuit_dedicated: Optional[bool] = Field(None, description="CCTV 전용회로 여부")
    grounded: Optional[bool] = Field(None, description="접지 설치 여부 (기계실)")


class ValidationIssue(BaseModel):
    rule_id: str
    rule_name: str
    severity: str   # "error" | "warning"
    message: str


class ValidationResult(BaseModel):
    space_key: str
    space_name: Optional[str]
    pass_: bool = Field(..., alias="pass")
    issues: list[ValidationIssue]
    issue_count: int

    class Config:
        populate_by_name = True


class ClaudeAnalysisRequest(BaseModel):
    """Claude AI 분석 요청"""
    space_key: str
    validation_results: list[ValidationIssue]
    additional_context: Optional[str] = Field(None, description="추가 컨텍스트")


class LoadCalcRequest(BaseModel):
    """분전반 용량 산출 요청"""
    spaces: list[SpaceInput] = Field(..., description="공간 목록 (여러 공간 일괄 산출)")
    demand_factor: float = Field(0.7, ge=0.1, le=1.0,
        description="수요율 (기본 0.7, 도시철도 일반)")
    safety_margin: float = Field(1.25, ge=1.0, le=2.0,
        description="안전율 (기본 1.25)")
    voltage_v: int = Field(380, description="공급 전압 (V)")
    phase: int = Field(3, description="상수 (1상 또는 3상)")


class SpaceLoadDetail(BaseModel):
    """공간별 부하 상세"""
    space_key: str
    space_name_ko: str
    area_m2: float
    design_load_w_m2: float
    power_factor: float
    lighting_load_w: float
    outlet_load_w: float
    cctv_load_w: float
    special_load_w: float
    total_load_w: float
    total_load_kw: float


class LoadCalcResult(BaseModel):
    """분전반 용량 산출 결과"""
    spaces: list[SpaceLoadDetail]
    total_connected_load_kw: float
    demand_factor: float
    demand_load_kw: float
    safety_margin: float
    design_load_kw: float
    voltage_v: int
    phase: int
    design_current_a: float
    recommended_breaker_a: int
    recommended_panel_kva: float
    summary_ko: str


class ExcelImportResult(BaseModel):
    imported_count: int
    spaces_found: list[str]
    preview: list[dict]


# ──────────────────────────────────────────────
# 내부 유틸리티
# ──────────────────────────────────────────────

def get_space_rule(space_key: str) -> dict:
    """공간 키로 규칙 반환, 없으면 404"""
    space = rules_db["spaces"].get(space_key)
    if not space:
        raise HTTPException(
            status_code=404,
            detail=f"공간 키 '{space_key}'를 찾을 수 없습니다. "
                   f"사용 가능: {list(rules_db['spaces'].keys())}",
        )
    return space


def calc_room_index(length: float, width: float, mounting_height: float) -> float:
    """실지수 K = (L × W) / (H × (L + W))"""
    return (length * width) / (mounting_height * (length + width))


def estimate_cu(K: float, ceiling_r: float, wall_r: float) -> float:
    """조명률(CU) 근사: 실지수·반사율 기반 (0.4~0.7)"""
    base = 0.40 + 0.10 * min(K, 3.0) / 3.0
    refl_bonus = (ceiling_r * 0.15) + (wall_r * 0.05)
    return round(min(base + refl_bonus, 0.70), 3)


def get_fixture_family_for_space(space_key: str) -> str:
    """공간 키에 해당하는 주 조명 Revit Family 반환"""
    for fk, fv in rules_db["fixture_families"].items():
        if space_key in fv.get("space_keys", []):
            if not any(kw in fk for kw in ("emergency", "guidance", "outlet")):
                return fv["revit_family_name"]
    return "Lighting Fixture - Generic"


def run_validation_rules(data: ValidationInput, space_rule: dict) -> list[ValidationIssue]:
    """rules_db validation_rules 순회하여 위반 항목 수집"""
    issues: list[ValidationIssue] = []
    space_key = data.space_key
    space_name = data.space_name or space_rule.get("space_name_ko", space_key)
    lighting = space_rule["lighting"]

    for rule in rules_db["validation_rules"]:
        applies = rule["applies_to"]
        if applies != "all":
            if isinstance(applies, list) and space_key not in applies:
                continue

        rid = rule["rule_id"]
        triggered = False
        msg = ""

        # V001: 조도 기준 미달
        if rid == "V001" and data.calculated_lux is not None:
            std_lux = lighting["illuminance_lux"]
            if data.calculated_lux < std_lux:
                lc = rules_db["spaces"][space_key].get("lighting_calc", {})
                shortfall_count = max(1, math.ceil(
                    (std_lux - data.calculated_lux) * lc.get("flux_per_lamp_lm", 4000) / 8000
                ))
                msg = rule["feedback_template"].format(
                    space_name=space_name,
                    calculated_lux=data.calculated_lux,
                    illuminance_lux=std_lux,
                    shortfall_count=shortfall_count,
                )
                triggered = True

        # V002: 유도등 간격 초과
        elif rid == "V002" and data.guidance_actual_spacing_m is not None:
            std = space_rule["emergency"]["guidance_spacing_m"]
            if data.guidance_actual_spacing_m > std:
                msg = rule["feedback_template"].format(
                    guidance_actual_spacing_m=data.guidance_actual_spacing_m,
                    guidance_spacing_m=std,
                )
                triggered = True

        # V003: 방폭등 미설치
        elif rid == "V003" and data.fixture_type is not None:
            if data.fixture_type != "explosion_proof_light":
                msg = rule["feedback_template"]
                triggered = True

        # V004: UPS 전원 미연결
        elif rid == "V004" and data.ups_connected is not None:
            if not data.ups_connected:
                sr = space_rule.get("special_requirements", {})
                msg = rule["feedback_template"].format(
                    ups_capacity_kva=sr.get("ups_capacity_kva", "?"),
                    ups_backup_minutes=sr.get("ups_backup_minutes", "?"),
                )
                triggered = True

        # V005: CCTV 전용회로 미구성
        elif rid == "V005" and data.cctv_circuit_dedicated is not None:
            if not data.cctv_circuit_dedicated:
                msg = rule["feedback_template"].format(space_name=space_name)
                triggered = True

        # V006: 비상조명 조도 미달
        elif rid == "V006" and data.emergency_calculated_lux is not None:
            std_emg = lighting["emergency_lux"]
            if data.emergency_calculated_lux < std_emg:
                msg = rule["feedback_template"].format(
                    space_name=space_name,
                    emergency_calculated_lux=data.emergency_calculated_lux,
                    emergency_lux=std_emg,
                )
                triggered = True

        # V007: 콘센트 간격 초과
        elif rid == "V007" and data.outlet_actual_spacing_m is not None:
            std_out = space_rule["outlets"]["spacing_m"]
            if data.outlet_actual_spacing_m > std_out:
                msg = rule["feedback_template"].format(
                    space_name=space_name,
                    outlet_actual_spacing_m=data.outlet_actual_spacing_m,
                    outlet_spacing_m=std_out,
                )
                triggered = True

        # V008: 접지 미설치 (기계실)
        elif rid == "V008" and data.grounded is not None:
            if not data.grounded:
                msg = rule["feedback_template"]
                triggered = True

        if triggered:
            issues.append(ValidationIssue(
                rule_id=rid,
                rule_name=rule["rule_name"],
                severity=rule["severity"],
                message=msg,
            ))

    return issues


STANDARD_BREAKER_RATINGS = [15, 20, 30, 40, 50, 60, 75, 100, 125, 150, 175, 200, 225, 250, 300, 400, 500, 600, 800]
STANDARD_PANEL_KVA = [5, 10, 15, 20, 25, 30, 50, 75, 100, 150, 200, 300, 500]


def calc_space_load(space_input: SpaceInput, space_rule: dict) -> SpaceLoadDetail:
    """공간 한 개의 부하 상세 계산"""
    area = space_input.area_m2
    load_info = space_rule["load"]
    cctv_info = space_rule["cctv"]
    special = space_rule["special_requirements"]

    # 조명 부하: 설계부하 × 면적 × 0.6 (조명 비율 가정)
    lighting_w = area * load_info["design_load_w_m2"] * 0.6
    # 콘센트 부하: 설계부하 × 면적 × 0.3
    outlet_w = area * load_info["design_load_w_m2"] * 0.3
    # CCTV 부하
    cctv_w = 0.0
    if cctv_info.get("cctv_circuit"):
        num_cameras = max(1, int(area / 100))  # 100m²당 1대 가정
        cctv_w = num_cameras * cctv_info.get("power_per_camera_w", 30)
    # 특수 부하 (스크린도어, UPS 등)
    special_w = 0.0
    if special.get("screen_door_power"):
        special_w += special.get("screen_door_power_w", 500)
    if special.get("ups_required"):
        special_w += special.get("ups_capacity_kva", 10) * 1000 * 0.1  # UPS 자체 소비

    total_w = lighting_w + outlet_w + cctv_w + special_w

    return SpaceLoadDetail(
        space_key=space_input.space_key,
        space_name_ko=space_rule["space_name_ko"],
        area_m2=area,
        design_load_w_m2=load_info["design_load_w_m2"],
        power_factor=load_info["power_factor"],
        lighting_load_w=round(lighting_w, 1),
        outlet_load_w=round(outlet_w, 1),
        cctv_load_w=round(cctv_w, 1),
        special_load_w=round(special_w, 1),
        total_load_w=round(total_w, 1),
        total_load_kw=round(total_w / 1000, 2),
    )


def select_breaker(current_a: float) -> int:
    """설계 전류 이상인 최소 차단기 정격 선택"""
    for rating in STANDARD_BREAKER_RATINGS:
        if rating >= current_a:
            return rating
    return STANDARD_BREAKER_RATINGS[-1]


def select_panel_kva(load_kw: float, pf: float = 0.9) -> float:
    """부하 이상인 최소 분전반 용량 선택"""
    required_kva = load_kw / pf
    for kva in STANDARD_PANEL_KVA:
        if kva >= required_kva:
            return kva
    return STANDARD_PANEL_KVA[-1]


# ──────────────────────────────────────────────
# 라우터
# ──────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    """헬스 체크"""
    return {
        "status": "ok",
        "version": rules_db["_meta"]["version"],
        "standards": rules_db["_meta"]["standards"],
    }


# ── 규칙 DB 조회 ──────────────────────────────

@app.get("/spaces", tags=["Rules"])
def list_spaces():
    """지원 공간 목록 반환"""
    return {
        k: {
            "space_name_ko": v["space_name_ko"],
            "keywords": v["keywords"],
            "illuminance_lux": v["lighting"]["illuminance_lux"],
            "design_load_w_m2": v["load"]["design_load_w_m2"],
        }
        for k, v in rules_db["spaces"].items()
    }


@app.get("/spaces/{space_key}", tags=["Rules"])
def get_space(space_key: str):
    """특정 공간의 전체 규칙 반환"""
    return get_space_rule(space_key)


@app.get("/fixtures", tags=["Rules"])
def list_fixtures():
    """조명·설비 Revit Family 목록 반환"""
    return rules_db["fixture_families"]


@app.get("/validation-rules", tags=["Rules"])
def list_validation_rules():
    """검증 규칙(V001~V008) 목록 반환"""
    return rules_db["validation_rules"]


# ── 조명 계산 ─────────────────────────────────

@app.post("/calculate/lighting", response_model=LightingCalcResult, tags=["Calculate"])
def calculate_lighting(req: LightingCalcRequest):
    """
    루멘법으로 필요 조명기구 수 계산
    N = (E × A) / (F × CU × MF)
    """
    space = get_space_rule(req.space_key)
    lc = space["lighting_calc"]
    lighting = space["lighting"]

    E = req.target_lux or lighting["illuminance_lux"]
    A = req.area_m2
    H = lighting["mounting_height_m"]
    MF = req.custom_mf or lc["maintenance_factor"]
    F = req.custom_flux_lm or (lc["flux_per_lamp_lm"] * lc["lamps_per_fixture"])

    K = calc_room_index(req.length_m, req.width_m, H)
    CU = estimate_cu(K, lc["ceiling_reflectance"], lc["wall_reflectance"])

    N_raw = (E * A) / (F * CU * MF)
    N = math.ceil(N_raw)
    actual_lux = round((N * F * CU * MF) / A, 1)

    return LightingCalcResult(
        space_key=req.space_key,
        space_name_ko=space["space_name_ko"],
        area_m2=A,
        target_lux=E,
        room_index_K=round(K, 3),
        utilization_factor_CU=CU,
        maintenance_factor_MF=MF,
        total_flux_per_fixture_lm=F,
        required_fixtures=N,
        actual_lux_estimate=actual_lux,
        fixture_family=get_fixture_family_for_space(req.space_key),
        kds_ref=lighting.get("kds_ref") or lighting.get("kec_ref"),
        formula=f"N = ({E} x {A}) / ({F} x {CU} x {MF}) = {N_raw:.2f} -> {N}개",
    )


# ── 분전반 용량 산출 ─────────────────────────────

@app.post("/calculate/load", response_model=LoadCalcResult, tags=["Calculate"])
def calculate_load(req: LoadCalcRequest):
    """
    분전반(Panel Board) 용량 산출

    여러 공간의 부하를 합산하여 수요율·안전율 적용 후
    설계 전류, 권장 차단기, 분전반 용량을 산출한다.

    계산 순서:
    1. 공간별 부하 = 조명 + 콘센트 + CCTV + 특수부하
    2. 합계 설비용량 (Connected Load)
    3. 수요부하 = 설비용량 × 수요율
    4. 설계부하 = 수요부하 × 안전율
    5. 설계전류 I = P / (√3 × V × PF)  [3상]
                 I = P / (V × PF)        [1상]
    6. 차단기·분전반 용량 선정
    """
    space_details: list[SpaceLoadDetail] = []
    total_connected_w = 0.0
    weighted_pf_sum = 0.0

    for sp_input in req.spaces:
        space_rule = get_space_rule(sp_input.space_key)
        detail = calc_space_load(sp_input, space_rule)
        space_details.append(detail)
        total_connected_w += detail.total_load_w
        weighted_pf_sum += detail.total_load_w * detail.power_factor

    total_connected_kw = total_connected_w / 1000
    avg_pf = weighted_pf_sum / total_connected_w if total_connected_w > 0 else 0.9
    demand_kw = total_connected_kw * req.demand_factor
    design_kw = demand_kw * req.safety_margin
    design_w = design_kw * 1000

    # 설계 전류 계산
    if req.phase == 3:
        design_current_a = design_w / (math.sqrt(3) * req.voltage_v * avg_pf)
    else:
        design_current_a = design_w / (req.voltage_v * avg_pf)

    breaker_a = select_breaker(design_current_a)
    panel_kva = select_panel_kva(design_kw, avg_pf)

    summary = (
        f"총 {len(req.spaces)}개 공간 | "
        f"설비용량 {total_connected_kw:.1f}kW | "
        f"수요부하 {demand_kw:.1f}kW (수요율 {req.demand_factor}) | "
        f"설계부하 {design_kw:.1f}kW (안전율 {req.safety_margin}) | "
        f"설계전류 {design_current_a:.1f}A → "
        f"차단기 {breaker_a}AT / 분전반 {panel_kva}kVA 권장"
    )

    return LoadCalcResult(
        spaces=space_details,
        total_connected_load_kw=round(total_connected_kw, 2),
        demand_factor=req.demand_factor,
        demand_load_kw=round(demand_kw, 2),
        safety_margin=req.safety_margin,
        design_load_kw=round(design_kw, 2),
        voltage_v=req.voltage_v,
        phase=req.phase,
        design_current_a=round(design_current_a, 1),
        recommended_breaker_a=breaker_a,
        recommended_panel_kva=panel_kva,
        summary_ko=summary,
    )


# ── 설계 검증 ─────────────────────────────────

@app.post("/validate", response_model=ValidationResult, tags=["Validate"])
def validate_design(data: ValidationInput):
    """
    설계 데이터를 rules_db 기준으로 검증
    위반 항목(error / warning) 목록 반환
    """
    space = get_space_rule(data.space_key)
    issues = run_validation_rules(data, space)
    error_count = len([i for i in issues if i.severity == "error"])

    return ValidationResult(
        space_key=data.space_key,
        space_name=data.space_name or space["space_name_ko"],
        **{"pass": error_count == 0},
        issues=issues,
        issue_count=len(issues),
    )


@app.post("/validate/batch", tags=["Validate"])
def validate_batch(items: list[ValidationInput]):
    """여러 공간 일괄 검증"""
    results = []
    for item in items:
        space = get_space_rule(item.space_key)
        issues = run_validation_rules(item, space)
        results.append({
            "space_key": item.space_key,
            "space_name": item.space_name or space["space_name_ko"],
            "pass": len([i for i in issues if i.severity == "error"]) == 0,
            "issues": [i.dict() for i in issues],
            "issue_count": len(issues),
        })
    return {"total": len(results), "results": results}


# ── Excel / Google Sheets 가져오기 ────────────

@app.post("/import/excel", response_model=ExcelImportResult, tags=["Import"])
async def import_excel(
    file: UploadFile = File(...),
    apply: bool = False,
):
    """
    Excel 파일 업로드 → excel_to_json.py 변환 → 규칙 DB 갱신

    excel_to_json.excel_bytes_to_rules_db()를 호출하여
    업로드된 .xlsx 파일을 메모리에서 파싱하고 rules_db 형태로 변환한다.

    Args:
        file: .xlsx 파일
        apply: True이면 서버의 rules_db를 업로드 데이터로 교체 (기본 False = 미리보기만)

    Returns:
        - imported_count: 파싱된 공간 수
        - spaces_found: 파싱된 공간 키 목록
        - preview: 각 공간의 주요 기준값 미리보기
    """
    global rules_db

    contents = await file.read()
    filename = file.filename or "unknown.xlsx"

    if not filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다: {filename} — .xlsx 파일만 지원합니다.",
        )

    try:
        imported_db = excel_bytes_to_rules_db(contents)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Excel 파싱 중 오류: {str(e)}",
        )

    spaces = imported_db.get("spaces", {})
    fixtures = imported_db.get("fixtures_families", {})

    # 미리보기: 각 공간의 핵심 기준값 요약
    preview = []
    for key, sp in spaces.items():
        lighting = sp.get("lighting", {})
        calc = sp.get("lighting_calc", {})
        emergency = sp.get("emergency", {})
        special = sp.get("special_requirements", {})
        preview.append({
            "space_key": key,
            "space_name_ko": sp.get("space_name_ko", key),
            "illuminance_lux": lighting.get("illuminance_lux"),
            "maintenance_factor": calc.get("maintenance_factor"),
            "flux_per_lamp_lm": calc.get("flux_per_lamp_lm"),
            "guidance_spacing_m": emergency.get("guidance_spacing_m"),
            "explosion_proof": special.get("explosion_proof", False),
            "ups_required": special.get("ups_required", False),
        })

    # apply=True이면 서버 rules_db를 교체하고 파일에도 저장
    if apply:
        rules_db = imported_db
        try:
            with open(RULES_DB_PATH, "w", encoding="utf-8") as f:
                json.dump(rules_db, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # 메모리에는 반영되었으나 파일 저장 실패 경고
            preview.append({"warning": f"rules_db.json 파일 저장 실패: {e} (메모리에는 반영됨)"})

    return ExcelImportResult(
        imported_count=len(spaces),
        spaces_found=list(spaces.keys()),
        preview=preview,
    )


@app.post("/import/google-sheets", tags=["Import"])
def import_google_sheets(sheet_id: str, sheet_name: str = "Sheet1"):
    """
    Google Sheets → JSON 변환

    연동 방법:
        from excel_to_json import fetch_gsheet
        data = fetch_gsheet(sheet_id, sheet_name)

    Args:
        sheet_id: 스프레드시트 ID (URL의 /d/{id}/ 부분)
        sheet_name: 시트 이름
    """
    # TODO: excel_to_json.fetch_gsheet() 호출로 교체
    return {
        "status": "stub",
        "sheet_id": sheet_id,
        "sheet_name": sheet_name,
        "note": "excel_to_json.py의 fetch_gsheet() 연동 필요",
    }


# ── Claude AI 분석 ────────────────────────────

@app.post("/ai/analyze", tags=["AI"])
def ai_analyze(req: ClaudeAnalysisRequest):
    """
    검증 결과를 Claude에게 전달하여 한국어 개선 방안 생성
    환경변수 ANTHROPIC_API_KEY 필요
    """
    client = get_claude_client()

    space = get_space_rule(req.space_key)
    space_name = space["space_name_ko"]

    issues_text = "\n".join(
        f"[{i.severity.upper()}] {i.rule_id} {i.rule_name}: {i.message}"
        for i in req.validation_results
    ) or "검출된 위반 항목 없음"

    extra_ctx = (
        f"## 추가 컨텍스트\n{req.additional_context}"
        if req.additional_context else ""
    )

    prompt = f"""당신은 지하철역 전기설비 BIM 자동화 전문가입니다.
KDS 31 17 00 및 KEC 기준을 준수하여 아래 검증 결과를 분석하고,
각 위반 항목에 대한 구체적 개선 방안을 한국어로 작성해주세요.

## 공간 정보
- 공간: {space_name} ({req.space_key})

## 검증 결과
{issues_text}

{extra_ctx}

## 요청 사항
1. 각 ERROR 항목의 원인과 Revit/Dynamo 수정 방법
2. WARNING 항목의 권장 조치
3. 우선순위 순서로 정리
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return {
        "space_key": req.space_key,
        "space_name": space_name,
        "analysis": message.content[0].text,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }


@app.post("/ai/suggest-fixtures", tags=["AI"])
def ai_suggest_fixtures(space_input: SpaceInput):
    """
    공간 정보를 바탕으로 Claude가 조명기구 배치 제안
    환경변수 ANTHROPIC_API_KEY 필요
    """
    client = get_claude_client()

    space = get_space_rule(space_input.space_key)
    lc = space["lighting_calc"]
    lighting = space["lighting"]

    K = calc_room_index(space_input.length_m, space_input.width_m, lighting["mounting_height_m"])
    CU = estimate_cu(K, lc["ceiling_reflectance"], lc["wall_reflectance"])
    F = lc["flux_per_lamp_lm"] * lc["lamps_per_fixture"]
    N = math.ceil(
        (lighting["illuminance_lux"] * space_input.area_m2) / (F * CU * lc["maintenance_factor"])
    )

    prompt = f"""지하철역 {space["space_name_ko"]} 공간의 전기설비 BIM 배치를 제안해주세요.

## 공간 사양
- 면적: {space_input.area_m2}m2 ({space_input.length_m}m x {space_input.width_m}m)
- 기준 조도: {lighting["illuminance_lux"]}lux
- 계산된 필요 조명기구 수: {N}개
- Revit Family: {get_fixture_family_for_space(space_input.space_key)}

## 요청
1. Dynamo 스크립트로 자동 배치 시 권장 그리드 간격
2. 비상조명 및 유도등 추가 배치 위치 원칙
3. Revit 파라미터 설정 시 주의사항
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )

    return {
        "space_key": space_input.space_key,
        "required_fixtures": N,
        "suggestion": message.content[0].text,
    }


# ──────────────────────────────────────────────
# 로컬 실행 진입점
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
