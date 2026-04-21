"""
05_place_emergency.py
Dynamo Python Script — 유도등·비상등 별도 회로 배치

04_place_fixtures.py와 별도로, 비상조명등과 유도등을
소방시설 설치기준에 따라 배치한다.

배치 규칙:
  - 비상조명등: 천장면 배치, 공간 면적 기반 수량 산출
  - 유도등: 벽면 배치, 통로·계단은 2m 간격, 기타 공간은 10m 간격
  - 모든 비상 기구는 "비상회로" 파라미터를 True로 설정

Dynamo 노드 입력:
    IN[0] = calc_results    (03번 노드 출력)
    IN[1] = rules_db_path   (rules_db.json 경로)
    IN[2] = dry_run         (bool)
Dynamo 노드 출력:
    OUT = [{"emergency_lights": [...], "guidance_signs": [...]}, ...]
"""

import clr
import json
import math

clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")
clr.AddReference("RevitNodes")

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    FamilySymbol,
    BuiltInCategory,
    BuiltInParameter,
    XYZ,
    Level,
    Structure,
)
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

doc = DocumentManager.Instance.CurrentDBDocument

# ──────────────────────────────────────────────
# 입력
# ──────────────────────────────────────────────
calc_results = IN[0]
rules_db_path = IN[1]
dry_run = IN[2] if len(IN) > 2 else False

with open(rules_db_path, "r", encoding="utf-8") as f:
    rules_db = json.load(f)

FIXTURE_FAMILIES = rules_db["fixture_families"]


# ──────────────────────────────────────────────
# 단위 변환
# ──────────────────────────────────────────────
def m_to_feet(m):
    return m / 0.3048


# ──────────────────────────────────────────────
# Family 심볼 조회
# ──────────────────────────────────────────────
_symbol_cache = {}

def find_symbol(family_name, categories=None):
    """FamilySymbol 검색 (조명 + 전기설비 카테고리)"""
    if family_name in _symbol_cache:
        return _symbol_cache[family_name]

    search_categories = categories or [
        BuiltInCategory.OST_LightingFixtures,
        BuiltInCategory.OST_ElectricalFixtures,
        BuiltInCategory.OST_FireAlarmDevices,
    ]

    for cat in search_categories:
        collector = (
            FilteredElementCollector(doc)
            .OfClass(FamilySymbol)
            .OfCategory(cat)
        )
        for symbol in collector:
            if family_name.lower() in symbol.Family.Name.lower():
                _symbol_cache[family_name] = symbol
                return symbol

    _symbol_cache[family_name] = None
    return None


def get_level_by_name(level_name):
    collector = FilteredElementCollector(doc).OfClass(Level)
    for lv in collector:
        if lv.Name == level_name:
            return lv
    levels = list(FilteredElementCollector(doc).OfClass(Level))
    return levels[0] if levels else None


# ──────────────────────────────────────────────
# 비상조명등 배치 포인트 생성
# ──────────────────────────────────────────────
def calc_emergency_light_points(space_data):
    """
    비상조명등 배치 포인트를 생성한다.

    산출 기준:
      - 비상조도(emergency_lux) × 면적 / (기구당 광속 × 보수율)
      - 최소 1개, 출입구 근처 우선
      - 천장면 배치

    간소화: 일반 조명 기구 수의 ~1/3 수준으로 배치
    """
    rules = space_data.get("rules")
    if not rules:
        return []

    emergency = rules.get("emergency", {})
    if not emergency.get("emergency_light_required", False):
        return []

    lighting = rules["lighting"]
    emergency_lux = lighting.get("emergency_lux", 10)
    design_lux = lighting.get("illuminance_lux", 200)

    # 비상 기구 수: 일반 기구 수 × (비상조도 / 설계조도), 최소 1개
    normal_fixtures = space_data.get("required_fixtures", 1)
    ratio = emergency_lux / design_lux if design_lux > 0 else 0.1
    n_emergency = max(1, int(math.ceil(normal_fixtures * ratio)))

    # 바운딩박스에서 균등 배치
    bb = space_data.get("bounding_box")
    if not bb or not bb.get("min") or not bb.get("max"):
        return []

    x_min, y_min, z_min = bb["min"]
    x_max, y_max, z_max = bb["max"]
    z_ceiling = z_max - 0.05

    points = []
    if n_emergency == 1:
        # 중앙 배치
        cx = (x_min + x_max) / 2.0
        cy = (y_min + y_max) / 2.0
        points.append((cx, cy, z_ceiling))
    else:
        # 균등 배치 (1줄)
        for i in range(n_emergency):
            t = (i + 0.5) / n_emergency
            x = x_min + (x_max - x_min) * t
            cy = (y_min + y_max) / 2.0
            points.append((x, cy, z_ceiling))

    return points, n_emergency


# ──────────────────────────────────────────────
# 유도등 배치 포인트 생성 (벽면)
# ──────────────────────────────────────────────
def calc_guidance_sign_points(space_data):
    """
    유도등 배치 포인트를 생성한다.

    배치 규칙 (소방시설 설치기준 제11조):
      - 통로·계단: 2m 간격 (양쪽 벽면)
      - 기타 공간: 10m 간격
      - 높이: 바닥에서 1.0m (피난 유도)
      - 벽면 배치: 공간 둘레를 따라 등간격

    벽면 배치 전략:
      바운딩박스의 4면을 따라 간격에 맞게 배치한다.
    """
    rules = space_data.get("rules")
    if not rules:
        return [], 0

    emergency = rules.get("emergency", {})
    if not emergency.get("guidance_sign_required", False):
        return [], 0

    spacing_m = emergency.get("guidance_spacing_m", 10.0)

    bb = space_data.get("bounding_box")
    if not bb or not bb.get("min") or not bb.get("max"):
        return [], 0

    x_min, y_min, z_min = bb["min"]
    x_max, y_max, z_max = bb["max"]

    # 유도등 높이: 바닥에서 1.0m
    z_guide = z_min + 1.0

    # 벽 오프셋: 벽에서 안쪽으로 0.05m
    wall_offset = 0.05

    points = []

    # 4면 벽을 따라 배치
    walls = [
        # (시작점, 끝점, 벽 방향)
        # 남쪽 벽 (y_min)
        ((x_min, y_min + wall_offset, z_guide),
         (x_max, y_min + wall_offset, z_guide)),
        # 북쪽 벽 (y_max)
        ((x_min, y_max - wall_offset, z_guide),
         (x_max, y_max - wall_offset, z_guide)),
        # 서쪽 벽 (x_min)
        ((x_min + wall_offset, y_min, z_guide),
         (x_min + wall_offset, y_max, z_guide)),
        # 동쪽 벽 (x_max)
        ((x_max - wall_offset, y_min, z_guide),
         (x_max - wall_offset, y_max, z_guide)),
    ]

    for start, end in walls:
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        wall_length = math.sqrt(dx * dx + dy * dy)

        if wall_length < spacing_m:
            # 벽 길이 < 간격이면 중앙에 1개
            mid_x = (start[0] + end[0]) / 2.0
            mid_y = (start[1] + end[1]) / 2.0
            points.append((mid_x, mid_y, z_guide))
        else:
            n = int(math.ceil(wall_length / spacing_m))
            for i in range(n):
                t = (i + 0.5) / n
                px = start[0] + dx * t
                py = start[1] + dy * t
                points.append((px, py, z_guide))

    return points, len(points)


# ──────────────────────────────────────────────
# 비상회로 파라미터 설정
# ──────────────────────────────────────────────
def set_emergency_circuit_param(element, circuit_name="비상회로"):
    """
    배치된 기구에 '비상회로' 관련 파라미터를 설정한다.
    Revit 공유 파라미터 또는 프로젝트 파라미터로 사전 정의 필요.
    """
    try:
        # Comments 파라미터에 회로 정보 기록 (범용)
        param = element.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
        if param and not param.IsReadOnly:
            param.Set(circuit_name)
    except Exception:
        pass


# ──────────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────────
output = []

if not dry_run:
    TransactionManager.Instance.EnsureInTransaction(doc)

# 비상등 / 유도등 Family 이름
EMERGENCY_FAMILY = FIXTURE_FAMILIES.get("emergency_light", {}).get(
    "revit_family_name", "Emergency Lighting - Battery"
)
GUIDANCE_FAMILY = FIXTURE_FAMILIES.get("guidance_sign", {}).get(
    "revit_family_name", "Exit Sign - LED"
)

for space_data in calc_results:
    space_key = space_data.get("space_key")
    name = space_data.get("name", "")

    if not space_key or "error" in space_data:
        output.append({
            "name": name,
            "space_key": space_key,
            "status": "skipped",
        })
        continue

    result = {
        "name": name,
        "space_key": space_key,
        "level_name": space_data.get("level_name", ""),
    }

    # ── 비상조명등 ──
    emg_data = calc_emergency_light_points(space_data)
    if emg_data:
        emg_points, emg_count = emg_data
    else:
        emg_points, emg_count = [], 0

    if dry_run:
        result["emergency_lights"] = {
            "count": emg_count,
            "family": EMERGENCY_FAMILY,
            "points_m": emg_points,
        }
    else:
        emg_symbol = find_symbol(EMERGENCY_FAMILY)
        level = get_level_by_name(space_data.get("level_name", ""))
        placed_emg = []

        if emg_symbol and level:
            if not emg_symbol.IsActive:
                emg_symbol.Activate()
                doc.Regenerate()

            for pt in emg_points:
                try:
                    xyz = XYZ(m_to_feet(pt[0]), m_to_feet(pt[1]), m_to_feet(pt[2]))
                    inst = doc.Create.NewFamilyInstance(
                        xyz, emg_symbol, level,
                        Structure.StructuralType.NonStructural,
                    )
                    set_emergency_circuit_param(inst, "비상조명회로")
                    placed_emg.append(inst.Id.IntegerValue)
                except Exception as e:
                    print("[ERROR] 비상등 배치 실패: {}".format(e))

        result["emergency_lights"] = {
            "count": len(placed_emg),
            "family": EMERGENCY_FAMILY,
            "element_ids": placed_emg,
        }

    # ── 유도등 ──
    guide_points, guide_count = calc_guidance_sign_points(space_data)

    if dry_run:
        result["guidance_signs"] = {
            "count": guide_count,
            "family": GUIDANCE_FAMILY,
            "spacing_m": space_data.get("rules", {}).get("emergency", {}).get("guidance_spacing_m"),
            "points_m": guide_points,
        }
    else:
        guide_symbol = find_symbol(GUIDANCE_FAMILY)
        level = get_level_by_name(space_data.get("level_name", ""))
        placed_guide = []

        if guide_symbol and level:
            if not guide_symbol.IsActive:
                guide_symbol.Activate()
                doc.Regenerate()

            for pt in guide_points:
                try:
                    xyz = XYZ(m_to_feet(pt[0]), m_to_feet(pt[1]), m_to_feet(pt[2]))
                    inst = doc.Create.NewFamilyInstance(
                        xyz, guide_symbol, level,
                        Structure.StructuralType.NonStructural,
                    )
                    set_emergency_circuit_param(inst, "유도등회로")
                    placed_guide.append(inst.Id.IntegerValue)
                except Exception as e:
                    print("[ERROR] 유도등 배치 실패: {}".format(e))

        result["guidance_signs"] = {
            "count": len(placed_guide),
            "family": GUIDANCE_FAMILY,
            "element_ids": placed_guide,
        }

    output.append(result)

    # 로그
    emg_n = result.get("emergency_lights", {}).get("count", 0)
    guide_n = result.get("guidance_signs", {}).get("count", 0)
    print("[EMRG] {} → 비상등 {}개, 유도등 {}개".format(name, emg_n, guide_n))

if not dry_run:
    TransactionManager.Instance.TransactionTaskDone()

# 요약
total_emg = sum(o.get("emergency_lights", {}).get("count", 0) for o in output)
total_guide = sum(o.get("guidance_signs", {}).get("count", 0) for o in output)
print("\n[SUMMARY] 비상조명등 {}개, 유도등 {}개 배치".format(total_emg, total_guide))

OUT = output