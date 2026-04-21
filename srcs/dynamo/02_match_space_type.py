"""
02_match_space_type.py
Dynamo Python Script — 공간 유형 키워드 매칭

01_collect_spaces.py에서 수집한 Space 딕셔너리의 name 필드를
rules_db.json의 keywords와 매칭하여 space_key를 부여한다.

Dynamo 노드 입력:
    IN[0] = spaces_list   (01번 노드 출력)
    IN[1] = rules_db_path (rules_db.json 경로, 문자열)
Dynamo 노드 출력:
    OUT = [{"space_key": "concourse", "confidence": 1.0, ...}, ...]
"""

import clr
import json
import re

# ──────────────────────────────────────────────
# 입력
# ──────────────────────────────────────────────
spaces_list = IN[0]       # list[dict] — 01번 노드 출력
rules_db_path = IN[1]     # str — rules_db.json 절대 경로

# ──────────────────────────────────────────────
# rules_db 로드
# ──────────────────────────────────────────────
with open(rules_db_path, "r", encoding="utf-8") as f:
    rules_db = json.load(f)

SPACES_DB = rules_db["spaces"]   # {"concourse": {...}, "platform": {...}, ...}


# ──────────────────────────────────────────────
# 키워드 인덱스 구축
# ──────────────────────────────────────────────
def build_keyword_index(spaces_db):
    """
    rules_db.spaces 의 keywords 필드로부터
    { keyword_lower: space_key } 역색인을 생성한다.

    우선순위:
      1) 정확 매칭 (exact)
      2) 부분 매칭 (contains)
    """
    index = {}
    for space_key, space_data in spaces_db.items():
        for kw in space_data.get("keywords", []):
            index[kw.lower()] = space_key
    return index


KEYWORD_INDEX = build_keyword_index(SPACES_DB)

# 한국어 공간명 → space_key 직접 매핑 (폴백용)
DIRECT_NAME_MAP = {}
for sk, sd in SPACES_DB.items():
    name_ko = sd.get("space_name_ko", "")
    if name_ko:
        DIRECT_NAME_MAP[name_ko.lower()] = sk


# ──────────────────────────────────────────────
# 매칭 함수
# ──────────────────────────────────────────────
def match_space_type(space_name):
    """
    Revit Space 이름을 rules_db의 space_key로 매칭한다.

    매칭 전략 (우선순위):
      1. 정확 매칭: space_name이 keyword와 완전 일치
      2. 포함 매칭: space_name 안에 keyword가 포함
      3. 역방향 포함: keyword 안에 space_name이 포함
      4. 한국어 공간명 직접 매칭
      5. 매칭 실패 → None

    반환:
      (space_key, confidence, matched_keyword)
      - confidence: 1.0(정확), 0.8(포함), 0.6(역방향), 0.5(직접 이름), 0.0(실패)
    """
    if not space_name:
        return None, 0.0, None

    name_lower = space_name.strip().lower()

    # 전략 1: 정확 매칭
    if name_lower in KEYWORD_INDEX:
        return KEYWORD_INDEX[name_lower], 1.0, name_lower

    # 전략 2: 포함 매칭 (name 안에 keyword가 있는 경우)
    # 긴 키워드부터 매칭하여 더 구체적인 매칭 우선
    sorted_keywords = sorted(KEYWORD_INDEX.keys(), key=len, reverse=True)
    for kw in sorted_keywords:
        if kw in name_lower:
            return KEYWORD_INDEX[kw], 0.8, kw

    # 전략 3: 역방향 포함 (keyword 안에 name이 있는 경우)
    for kw in sorted_keywords:
        if name_lower in kw:
            return KEYWORD_INDEX[kw], 0.6, kw

    # 전략 4: 한국어 공간명 직접 매칭
    for ko_name, sk in DIRECT_NAME_MAP.items():
        if ko_name in name_lower or name_lower in ko_name:
            return sk, 0.5, ko_name

    # 전략 5: 매칭 실패
    return None, 0.0, None


def enrich_spaces_with_type(spaces):
    """
    수집된 공간 리스트에 space_key, confidence, matched_keyword,
    그리고 해당 공간의 rules_db 전체 규칙(rules)을 추가한다.
    """
    enriched = []
    unmatched = []

    for space in spaces:
        name = space.get("name", "")
        number = space.get("number", "")

        # 이름으로 먼저 매칭, 실패 시 번호로 재시도
        space_key, confidence, matched_kw = match_space_type(name)
        if space_key is None and number:
            space_key, confidence, matched_kw = match_space_type(number)

        # 결과 병합
        result = dict(space)  # 원본 복사
        result["space_key"] = space_key
        result["confidence"] = confidence
        result["matched_keyword"] = matched_kw

        if space_key and space_key in SPACES_DB:
            result["rules"] = SPACES_DB[space_key]
        else:
            result["rules"] = None
            unmatched.append({
                "name": name,
                "number": number,
                "element_id": space.get("element_id"),
            })

        enriched.append(result)

    # 매칭 실패 공간 경고
    if unmatched:
        import sys
        for u in unmatched:
            msg = "[WARN] 매칭 실패: name='{}' number='{}' (ElementId={})".format(
                u["name"], u["number"], u["element_id"]
            )
            print(msg)

    return enriched


# ──────────────────────────────────────────────
# 실행 & 출력
# ──────────────────────────────────────────────
result = enrich_spaces_with_type(spaces_list)

# 매칭 요약 출력
matched_count = sum(1 for r in result if r["space_key"] is not None)
total_count = len(result)
print("[INFO] 공간 매칭 완료: {}/{} ({:.0f}%)".format(
    matched_count, total_count,
    (matched_count / total_count * 100) if total_count > 0 else 0
))

for r in result:
    print("  {} ({}) → {} (confidence={})".format(
        r["name"], r["number"], r["space_key"], r["confidence"]
    ))

OUT = result