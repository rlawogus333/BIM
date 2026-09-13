"""
04_place_fixtures.py
Dynamo Python Script — Revit FamilyInstance 자동 배치 (천장/벽)

03_lumen_calc.py 출력을 받아 각 공간의 바운딩박스 내부에
등간격 그리드로 조명기구 FamilyInstance를 자동 배치한다.

Dynamo 노드 입력:
    IN[0] = calc_results    (03번 노드 출력)
    IN[1] = rules_db_path   (rules_db.json 경로)
    IN[2] = dry_run         (bool, True이면 배치 없이 좌표만 반환)
Dynamo 노드 출력:
    OUT = [{"placed": [...], "count": N}, ...]
"""

import clr
import json
import math

clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")
clr.AddReference("RevitNodes")

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    Family,
    FamilySymbol,
    BuiltInCategory,
    XYZ,
    Line,
    Transaction,
    Structure,
    Level,
)
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

doc = DocumentManager.Instance.CurrentDBDocument

# ──────────────────────────────────────────────
# 입력
# ──────────────────────────────────────────────
calc_results = IN[0]              # list[dict] — 03번 노드 출력
rules_db_path = IN[1]             # str
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
# Family 심볼 조회 캐시
# ──────────────────────────────────────────────
_family_symbol_cache = {}

def find_family_symbol(family_name):
    """
    Revit 문서에서 family_name과 일치하는 FamilySymbol을 찾는다.
    부분 매칭도 지원하며, 결과를 캐시한다.
    """
    if family_name in _family_symbol_cache:
        return _family_symbol_cache[family_name]

    collector = (
        FilteredElementCollector(doc)
        .OfClass(FamilySymbol)
        .OfCategory(BuiltInCategory.OST_LightingFixtures)
    )

    # 1차: 정확 매칭
    for symbol in collector:
        if symbol.Family.Name == family_name:
            _family_symbol_cache[family_name] = symbol
            return symbol

    # 2차: 부분 매칭
    collector2 = (
        FilteredElementCollector(doc)
        .OfClass(FamilySymbol)
        .OfCategory(BuiltInCategory.OST_LightingFixtures)
    )
    for symbol in collector2:
        if family_name.lower() in symbol.Family.Name.lower():
            _family_symbol_cache[family_name] = symbol
            return symbol

    # 3차: 전기 설비 카테고리에서도 검색
    collector3 = (
        FilteredElementCollector(doc)
        .OfClass(FamilySymbol)
        .OfCategory(BuiltInCategory.OST_ElectricalFixtures)
    )
    for symbol in collector3:
        if family_name.lower() in symbol.Family.Name.lower():
            _family_symbol_cache[family_name] = symbol
            return symbol

    _family_symbol_cache[family_name] = None
    return None


def get_fixture_family_name(space_key):
    """
    space_key에 해당하는 주 조명 Revit Family 이름을 반환한다.
    (emergency, guidance 등 제외)
    """
    for fk, fv in FIXTURE_FAMILIES.items():
        if space_key in fv.get("space_keys", []):
            if not any(kw in fk for kw in ("emergency", "guidance", "outlet")):
                return fv["revit_family_name"]
    return None


# ──────────────────────────────────────────────
# 그리드 포인트 생성
# ──────────────────────────────────────────────
def generate_grid_points(space_data):
    """
    바운딩박스 내부에 등간격 그리드 포인트를 생성한다.

    배치 규칙:
      - 천장면(mount_face=천장): Z = ceiling_z - offset
      - 벽면(mount_face=벽): 별도 처리 (05번에서)
      - 가장자리에서 spacing/2 만큼 안쪽부터 배치 시작

    반환: list of XYZ (Revit 내부 단위 feet)
    """
    bb = space_data.get("bounding_box")
    if not bb or not bb.get("min") or not bb.get("max"):
        return []

    min_pt = bb["min"]  # (x, y, z) in meters
    max_pt = bb["max"]

    cols = space_data.get("grid_cols", 0)
    rows = space_data.get("grid_rows", 0)
    if cols <= 0 or rows <= 0:
        return []

    # 공간 범위 (m)
    x_min, y_min, z_min = min_pt
    x_max, y_max, z_max = max_pt

    L = x_max - x_min
    W = y_max - y_min

    # 간격
    spacing_x = L / cols
    spacing_y = W / rows

    # 천장 Z (바운딩박스 상단에서 약간 아래)
    ceiling_offset_m = 0.05  # 5cm 아래
    z_ceiling = z_max - ceiling_offset_m

    points = []
    for i in range(cols):
        for j in range(rows):
            x = x_min + spacing_x * (i + 0.5)
            y = y_min + spacing_y * (j + 0.5)
            z = z_ceiling

            # m → feet 변환하여 XYZ 생성
            pt = XYZ(m_to_feet(x), m_to_feet(y), m_to_feet(z))
            points.append(pt)

    return points


# ──────────────────────────────────────────────
# FamilyInstance 배치
# ──────────────────────────────────────────────
def place_fixtures_in_space(space_data, points, family_symbol, level):
    """
    주어진 포인트에 FamilyInstance를 배치한다.

    반환: 배치된 Element 리스트
    """
    placed = []

    # FamilySymbol 활성화
    if not family_symbol.IsActive:
        family_symbol.Activate()
        doc.Regenerate()

    for pt in points:
        try:
            instance = doc.Create.NewFamilyInstance(
                pt,
                family_symbol,
                level,
                Structure.StructuralType.NonStructural,
            )
            placed.append(instance)
        except Exception as e:
            print("[ERROR] 배치 실패 at ({:.1f}, {:.1f}, {:.1f}): {}".format(
                pt.X, pt.Y, pt.Z, str(e)
            ))

    return placed


def get_level_by_name(level_name):
    """레벨 이름으로 Level 요소를 찾는다."""
    collector = FilteredElementCollector(doc).OfClass(Level)
    for lv in collector:
        if lv.Name == level_name:
            return lv
    # 못 찾으면 첫 번째 레벨 반환
    levels = list(FilteredElementCollector(doc).OfClass(Level))
    return levels[0] if levels else None


# ──────────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────────
output = []

if not dry_run:
    TransactionManager.Instance.EnsureInTransaction(doc)

for space_data in calc_results:
    space_key = space_data.get("space_key")
    name = space_data.get("name", "")

    if not space_key or "error" in space_data:
        output.append({
            "name": name,
            "space_key": space_key,
            "status": "skipped",
            "reason": space_data.get("error", "space_key 없음"),
            "placed_count": 0,
        })
        continue

    # Family 이름 조회
    family_name = get_fixture_family_name(space_key)
    if not family_name:
        output.append({
            "name": name,
            "space_key": space_key,
            "status": "skipped",
            "reason": "fixture_family 매핑 없음",
            "placed_count": 0,
        })
        continue

    # 그리드 포인트 생성
    points = generate_grid_points(space_data)

    if dry_run:
        # 드라이런: 좌표만 반환
        output.append({
            "name": name,
            "space_key": space_key,
            "status": "dry_run",
            "family_name": family_name,
            "required_fixtures": space_data.get("required_fixtures", 0),
            "grid": "{}x{}".format(
                space_data.get("grid_cols", 0),
                space_data.get("grid_rows", 0),
            ),
            "points_count": len(points),
            "points_m": [
                (round(p.X * 0.3048, 3), round(p.Y * 0.3048, 3), round(p.Z * 0.3048, 3))
                for p in points
            ],
            "formula": space_data.get("formula", ""),
        })
        continue

    # FamilySymbol 찾기
    symbol = find_family_symbol(family_name)
    if not symbol:
        output.append({
            "name": name,
            "space_key": space_key,
            "status": "error",
            "reason": "FamilySymbol '{}' 을 찾을 수 없음 — Revit에 로드 필요".format(family_name),
            "placed_count": 0,
        })
        continue

    # Level 찾기
    level = get_level_by_name(space_data.get("level_name", ""))

    # 배치 실행
    placed = place_fixtures_in_space(space_data, points, symbol, level)

    output.append({
        "name": name,
        "space_key": space_key,
        "status": "placed",
        "family_name": family_name,
        "required_fixtures": space_data.get("required_fixtures", 0),
        "placed_count": len(placed),
        "grid": "{}x{}".format(
            space_data.get("grid_cols", 0),
            space_data.get("grid_rows", 0),
        ),
        "element_ids": [e.Id.IntegerValue for e in placed],
    })

    print("[PLACE] {} → {} '{}' {}개 배치 완료".format(
        name, space_key, family_name, len(placed)
    ))

if not dry_run:
    TransactionManager.Instance.TransactionTaskDone()

# 요약
total_placed = sum(o.get("placed_count", 0) for o in output)
print("\n[SUMMARY] 총 {}개 공간, {}개 기구 배치".format(len(output), total_placed))

OUT = output