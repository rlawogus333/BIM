"""
01_collect_spaces.py
Dynamo Python Script — Revit Space 객체 수집

Revit 모델의 모든 Space(공간) 요소를 수집하고,
각 공간의 이름·번호·면적·치수·바운딩박스를 딕셔너리로 반환한다.

Dynamo 노드 입력: 없음 (현재 문서에서 자동 수집)
Dynamo 노드 출력: OUT = [{"name", "number", "area_m2", ...}, ...]
"""

import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")
clr.AddReference("RevitNodes")

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    SpatialElement,
    BuiltInCategory,
    BuiltInParameter,
    UnitUtils,
    DisplayUnitType,
)
from RevitServices.Persistence import DocumentManager

# ──────────────────────────────────────────────
# 현재 Revit 문서
# ──────────────────────────────────────────────
doc = DocumentManager.Instance.CurrentDBDocument


# ──────────────────────────────────────────────
# 단위 변환: Revit 내부 단위(feet) → 미터
# ──────────────────────────────────────────────
def feet_to_m(feet_val):
    """Revit 내부 단위(feet) → m 변환"""
    return feet_val * 0.3048


def sqfeet_to_m2(sqfeet_val):
    """Revit 내부 단위(ft²) → m² 변환"""
    return sqfeet_val * 0.092903


# ──────────────────────────────────────────────
# Space 수집
# ──────────────────────────────────────────────
def collect_spaces():
    """
    현재 문서의 모든 Space 요소를 수집하여
    딕셔너리 리스트로 반환한다.

    반환 필드:
        - element_id   : Revit ElementId (int)
        - name         : 공간 이름 (str)
        - number       : 공간 번호 (str)
        - level_name   : 레벨 이름 (str)
        - area_m2      : 면적 (m²)
        - perimeter_m  : 둘레 (m)
        - height_m     : 천장 높이 (m) — 바운딩박스 기반
        - length_m     : 바운딩박스 X 방향 길이 (m)
        - width_m      : 바운딩박스 Y 방향 너비 (m)
        - center_x     : 중심점 X (m)
        - center_y     : 중심점 Y (m)
        - center_z     : 중심점 Z (m)
        - bounding_box : (min_pt, max_pt) 튜플
        - revit_element: 원본 Revit Element 참조
    """
    collector = (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_MEPSpaces)
        .WhereElementIsNotElementType()
    )

    spaces = []

    for space in collector:
        # 면적이 0인 공간(배치되지 않은 공간) 스킵
        area_param = space.get_Parameter(BuiltInParameter.ROOM_AREA)
        if area_param is None:
            continue
        area_sqft = area_param.AsDouble()
        if area_sqft <= 0:
            continue

        # 기본 속성
        name = space.get_Parameter(BuiltInParameter.ROOM_NAME)
        number = space.get_Parameter(BuiltInParameter.ROOM_NUMBER)
        level = space.Level

        name_str = name.AsString() if name else ""
        number_str = number.AsString() if number else ""
        level_name = level.Name if level else ""

        # 둘레
        perimeter_param = space.get_Parameter(BuiltInParameter.ROOM_PERIMETER)
        perimeter_ft = perimeter_param.AsDouble() if perimeter_param else 0

        # 바운딩박스 → 치수 산출
        bb = space.get_BoundingBox(None)
        if bb:
            min_pt = bb.Min
            max_pt = bb.Max
            length_ft = abs(max_pt.X - min_pt.X)
            width_ft = abs(max_pt.Y - min_pt.Y)
            height_ft = abs(max_pt.Z - min_pt.Z)
            center_x = (min_pt.X + max_pt.X) / 2.0
            center_y = (min_pt.Y + max_pt.Y) / 2.0
            center_z = (min_pt.Z + max_pt.Z) / 2.0
        else:
            length_ft = width_ft = height_ft = 0
            center_x = center_y = center_z = 0

        spaces.append({
            "element_id":    space.Id.IntegerValue,
            "name":          name_str,
            "number":        number_str,
            "level_name":    level_name,
            "area_m2":       round(sqfeet_to_m2(area_sqft), 2),
            "perimeter_m":   round(feet_to_m(perimeter_ft), 2),
            "height_m":      round(feet_to_m(height_ft), 2),
            "length_m":      round(feet_to_m(length_ft), 2),
            "width_m":       round(feet_to_m(width_ft), 2),
            "center_x":      round(feet_to_m(center_x), 3),
            "center_y":      round(feet_to_m(center_y), 3),
            "center_z":      round(feet_to_m(center_z), 3),
            "bounding_box":  {
                "min": (round(feet_to_m(min_pt.X), 3),
                        round(feet_to_m(min_pt.Y), 3),
                        round(feet_to_m(min_pt.Z), 3)) if bb else None,
                "max": (round(feet_to_m(max_pt.X), 3),
                        round(feet_to_m(max_pt.Y), 3),
                        round(feet_to_m(max_pt.Z), 3)) if bb else None,
            },
            "revit_element": space,
        })

    return spaces


# ──────────────────────────────────────────────
# Dynamo 출력
# ──────────────────────────────────────────────
result = collect_spaces()

# Dynamo 출력: 공간 리스트
OUT = result