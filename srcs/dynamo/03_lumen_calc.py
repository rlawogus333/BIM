"""
03_lumen_calc.py
Dynamo Python Script — 루멘법 조도 계산 → 조명기구 수량 산출

02_match_space_type.py 출력을 받아 각 공간별로
루멘법(N = E×A / F×CU×MF) 계산을 수행한다.

Dynamo 노드 입력:
    IN[0] = enriched_spaces (02번 노드 출력)
Dynamo 노드 출력:
    OUT = [{"required_fixtures": N, "grid_cols": c, "grid_rows": r, ...}, ...]
"""

import clr
import math

# ──────────────────────────────────────────────
# 입력
# ──────────────────────────────────────────────
enriched_spaces = IN[0]   # list[dict] — 02번 노드 출력


# ──────────────────────────────────────────────
# 실지수(Room Index) 계산
# ──────────────────────────────────────────────
def calc_room_index(length_m, width_m, mounting_height_m):
    """
    실지수 K = (L × W) / (H × (L + W))

    K값이 클수록 공간이 넓고 낮음 → 조명률(CU)이 높아짐
    """
    if mounting_height_m <= 0 or (length_m + width_m) <= 0:
        return 1.0  # 안전 기본값
    return (length_m * width_m) / (mounting_height_m * (length_m + width_m))


# ──────────────────────────────────────────────
# 조명률(CU) 추정
# ──────────────────────────────────────────────
def estimate_cu(K, ceiling_r, wall_r):
    """
    조명률(CU) 근사 계산

    실지수(K)와 천장·벽 반사율에 기반한 보간 공식.
    CU 범위: 0.40 ~ 0.70

    참고: 실무에서는 조명기구 제조사의 CU 테이블을 사용하나,
    자동화 스크립트에서는 근사값으로 충분함.
    """
    base = 0.40 + 0.10 * min(K, 3.0) / 3.0
    refl_bonus = (ceiling_r * 0.15) + (wall_r * 0.05)
    return min(round(base + refl_bonus, 3), 0.70)


# ──────────────────────────────────────────────
# 루멘법 계산
# ──────────────────────────────────────────────
def lumen_method(space):
    """
    루멘법으로 필요 조명기구 수량을 산출한다.

    공식: N = (E × A) / (F × CU × MF)
      E  = 목표 조도 (lux)
      A  = 공간 면적 (m²)
      F  = 기구당 총 광속 (lm) = flux_per_lamp × lamps_per_fixture
      CU = 조명률 (실지수·반사율 기반)
      MF = 감광 보수율

    추가 산출:
      - grid_cols, grid_rows: 등간격 배치 그리드 (행·열)
      - grid_spacing_x, grid_spacing_y: 그리드 간격 (m)
      - actual_lux: 실제 예상 조도 (올림 기구 수 기준)
    """
    rules = space.get("rules")
    if rules is None:
        return {
            "error": "rules 없음 — 매칭 실패 공간",
            "space_key": space.get("space_key"),
            "name": space.get("name"),
        }

    lighting = rules["lighting"]
    calc = rules["lighting_calc"]

    # 입력값 추출
    E = lighting["illuminance_lux"]
    A = space["area_m2"]
    L = space["length_m"]
    W = space["width_m"]
    H = lighting.get("mounting_height_m") or calc.get("mounting_height_m") or 3.0
    MF = calc["maintenance_factor"]
    flux_per_lamp = calc["flux_per_lamp_lm"]
    lamps = calc["lamps_per_fixture"]
    F = flux_per_lamp * lamps

    ceil_r = calc.get("ceiling_reflectance", 0.7)
    wall_r = calc.get("wall_reflectance", 0.5)

    # 실지수 & 조명률
    K = calc_room_index(L, W, H)
    CU = estimate_cu(K, ceil_r, wall_r)

    # 필요 기구 수 (올림)
    if F * CU * MF == 0:
        N_raw = 0
        N = 0
    else:
        N_raw = (E * A) / (F * CU * MF)
        N = int(math.ceil(N_raw))

    # 실제 조도 (올림 기구 수 기준)
    actual_lux = round((N * F * CU * MF) / A, 1) if A > 0 else 0

    # 등간격 그리드 배치 계산
    # 가로·세로 비율을 유지하면서 N개를 배치
    if N > 0 and L > 0 and W > 0:
        aspect = L / W
        grid_cols = max(1, int(round(math.sqrt(N * aspect))))
        grid_rows = max(1, int(math.ceil(N / grid_cols)))
        # 실제 배치 수량을 grid로 재조정
        grid_total = grid_cols * grid_rows
        grid_spacing_x = round(L / grid_cols, 3)
        grid_spacing_y = round(W / grid_rows, 3)
    else:
        grid_cols = grid_rows = 0
        grid_total = 0
        grid_spacing_x = grid_spacing_y = 0

    return {
        # 원본 공간 정보 유지
        "element_id":      space.get("element_id"),
        "name":            space.get("name"),
        "number":          space.get("number"),
        "space_key":       space.get("space_key"),
        "level_name":      space.get("level_name"),
        "area_m2":         A,
        "length_m":        L,
        "width_m":         W,
        "center_x":        space.get("center_x"),
        "center_y":        space.get("center_y"),
        "center_z":        space.get("center_z"),
        "bounding_box":    space.get("bounding_box"),
        "rules":           rules,
        "revit_element":   space.get("revit_element"),

        # 계산 결과
        "target_lux":      E,
        "mounting_height_m": H,
        "room_index_K":    round(K, 3),
        "cu":              CU,
        "maintenance_factor": MF,
        "flux_per_fixture_lm": F,
        "required_fixtures_raw": round(N_raw, 2),
        "required_fixtures": N,
        "actual_lux":      actual_lux,

        # 그리드 배치
        "grid_cols":       grid_cols,
        "grid_rows":       grid_rows,
        "grid_total":      grid_total,
        "grid_spacing_x":  grid_spacing_x,
        "grid_spacing_y":  grid_spacing_y,

        # 수식 문자열 (디버그용)
        "formula": "N = ({E} x {A}) / ({F} x {CU} x {MF}) = {Nraw:.2f} -> {N}".format(
            E=E, A=A, F=F, CU=CU, MF=MF, Nraw=N_raw, N=N
        ),
    }


# ──────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────
results = []
for space in enriched_spaces:
    calc_result = lumen_method(space)
    results.append(calc_result)

    # 디버그 출력
    if "error" not in calc_result:
        print("[CALC] {} ({}) → {}개 기구, {:.1f}lux (목표 {}lux), 그리드 {}x{}".format(
            calc_result["name"],
            calc_result["space_key"],
            calc_result["required_fixtures"],
            calc_result["actual_lux"],
            calc_result["target_lux"],
            calc_result["grid_cols"],
            calc_result["grid_rows"],
        ))
    else:
        print("[SKIP] {} — {}".format(calc_result["name"], calc_result["error"]))

OUT = results