"""
06_mcp_client.py
Dynamo Python Script — MCP 서버 HTTP 호출 노드

FastAPI 백엔드(main.py)와 통신하여 규칙 조회, 조도 계산,
설계 검증, AI 분석을 Dynamo 내에서 직접 호출한다.

IronPython 환경에서는 System.Net.WebClient를 사용한다.
(requests 라이브러리 사용 불가)

Dynamo 노드 입력:
    IN[0] = api_base_url   (str, 예: "http://localhost:8000")
    IN[1] = action          (str, 예: "validate" | "calculate" | "spaces" | "ai_analyze")
    IN[2] = payload         (dict 또는 list[dict], POST 요청 시 body)
Dynamo 노드 출력:
    OUT = API 응답 (dict 또는 list)
"""

import clr
import json

clr.AddReference("System")
clr.AddReference("System.Net")

from System.Net import WebClient, WebException
from System.Text import Encoding


# ──────────────────────────────────────────────
# 입력
# ──────────────────────────────────────────────
api_base_url = IN[0]     # str — "http://localhost:8000"
action = IN[1]           # str
payload = IN[2] if len(IN) > 2 else None


# ──────────────────────────────────────────────
# HTTP 클라이언트 래퍼
# ──────────────────────────────────────────────
class MCPClient:
    """
    System.Net.WebClient 기반 HTTP 클라이언트.

    IronPython(Dynamo) 환경에서 REST API를 호출하기 위해
    .NET의 WebClient를 사용한다.
    """

    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def _create_client(self):
        client = WebClient()
        client.Encoding = Encoding.UTF8
        client.Headers.Add("Content-Type", "application/json")
        client.Headers.Add("Accept", "application/json")
        return client

    def get(self, path):
        """GET 요청"""
        client = self._create_client()
        url = "{}/{}".format(self.base_url, path.lstrip("/"))
        try:
            response = client.DownloadString(url)
            return json.loads(response)
        except WebException as e:
            return {"error": str(e), "url": url}
        finally:
            client.Dispose()

    def post(self, path, data):
        """POST 요청 (JSON body)"""
        client = self._create_client()
        url = "{}/{}".format(self.base_url, path.lstrip("/"))
        body = json.dumps(data, ensure_ascii=False)
        try:
            response = client.UploadString(url, "POST", body)
            return json.loads(response)
        except WebException as e:
            return {"error": str(e), "url": url, "body": body}
        finally:
            client.Dispose()


# ──────────────────────────────────────────────
# 액션 라우터
# ──────────────────────────────────────────────

# 지원 액션과 엔드포인트 매핑
ACTION_MAP = {
    # GET 요청
    "health":           ("GET",  "/"),
    "spaces":           ("GET",  "/spaces"),
    "space_detail":     ("GET",  "/spaces/{space_key}"),
    "fixtures":         ("GET",  "/fixtures"),
    "validation_rules": ("GET",  "/validation-rules"),

    # POST 요청
    "calculate":        ("POST", "/calculate/lighting"),
    "validate":         ("POST", "/validate"),
    "validate_batch":   ("POST", "/validate/batch"),
    "ai_analyze":       ("POST", "/ai/analyze"),
    "ai_suggest":       ("POST", "/ai/suggest-fixtures"),
}


def route_action(client, action, payload):
    """
    액션 이름에 따라 적절한 HTTP 요청을 실행한다.
    """
    if action not in ACTION_MAP:
        return {
            "error": "알 수 없는 액션: '{}'".format(action),
            "available_actions": list(ACTION_MAP.keys()),
        }

    method, path = ACTION_MAP[action]

    # 경로에 변수가 있는 경우 payload에서 치환
    if "{" in path and payload and isinstance(payload, dict):
        for key, value in payload.items():
            placeholder = "{" + key + "}"
            if placeholder in path:
                path = path.replace(placeholder, str(value))

    if method == "GET":
        return client.get(path)
    else:
        return client.post(path, payload or {})


# ──────────────────────────────────────────────
# 편의 함수: Dynamo 노드에서 직접 호출 가능
# ──────────────────────────────────────────────

def get_space_rules(client, space_key):
    """특정 공간의 전체 규칙 조회"""
    return client.get("/spaces/{}".format(space_key))


def calculate_lighting(client, space_key, area_m2, length_m, width_m,
                       target_lux=None, custom_flux=None, custom_mf=None):
    """루멘법 조도 계산 요청"""
    body = {
        "space_key": space_key,
        "area_m2": area_m2,
        "length_m": length_m,
        "width_m": width_m,
    }
    if target_lux is not None:
        body["target_lux"] = target_lux
    if custom_flux is not None:
        body["custom_flux_lm"] = custom_flux
    if custom_mf is not None:
        body["custom_mf"] = custom_mf
    return client.post("/calculate/lighting", body)


def validate_design(client, space_key, **kwargs):
    """설계 검증 요청"""
    body = {"space_key": space_key}
    body.update(kwargs)
    return client.post("/validate", body)


def validate_batch(client, items):
    """일괄 검증 요청"""
    return client.post("/validate/batch", items)


def ai_analyze(client, space_key, issues, context=None):
    """Claude AI 분석 요청"""
    body = {
        "space_key": space_key,
        "validation_results": issues,
    }
    if context:
        body["additional_context"] = context
    return client.post("/ai/analyze", body)


# ──────────────────────────────────────────────
# Dynamo 워크플로우 통합 함수
# ──────────────────────────────────────────────

def run_full_workflow(client, spaces_list):
    """
    전체 워크플로우 실행:
    1. 각 공간별 조도 계산
    2. 설계 검증
    3. 위반 항목 수집
    4. AI 분석 (위반 있을 시)

    Args:
        client: MCPClient 인스턴스
        spaces_list: 02번 노드 출력 (enriched_spaces)

    Returns:
        list of workflow results
    """
    results = []

    for space in spaces_list:
        space_key = space.get("space_key")
        if not space_key:
            continue

        workflow = {"space_key": space_key, "name": space.get("name", "")}

        # 1. 조도 계산
        calc = calculate_lighting(
            client,
            space_key=space_key,
            area_m2=space.get("area_m2", 100),
            length_m=space.get("length_m", 10),
            width_m=space.get("width_m", 10),
        )
        workflow["lighting_calc"] = calc

        # 2. 설계 검증
        validation = validate_design(
            client,
            space_key=space_key,
            calculated_lux=calc.get("actual_lux_estimate"),
        )
        workflow["validation"] = validation

        # 3. 위반 항목 확인
        issues = validation.get("issues", [])
        workflow["has_issues"] = len(issues) > 0

        # 4. AI 분석 (위반 있을 때만)
        if issues:
            analysis = ai_analyze(client, space_key, issues)
            workflow["ai_analysis"] = analysis

        results.append(workflow)

    return results


# ──────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────
client = MCPClient(api_base_url)

# 액션 라우팅
if action == "workflow" and payload:
    # 전체 워크플로우 모드
    result = run_full_workflow(client, payload)
elif action:
    result = route_action(client, action, payload)
else:
    # 기본: 헬스 체크
    result = client.get("/")

print("[MCP] Action='{}' → {}".format(
    action,
    "OK" if "error" not in (result if isinstance(result, dict) else {}) else "ERROR"
))

OUT = result