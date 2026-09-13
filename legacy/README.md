# legacy — 보존용 구현

현재 파이프라인에서 **사용하지 않는** 과거 구현을 기록 목적으로 보존합니다.

## dynamo/

Phase 2에서 작성한 Dynamo 자동배치 스크립트 6종입니다. Phase 4에서 revit-mcp로 전면 대체되었습니다.

| 기존 스크립트 | 현재 대체 방안 |
| :--- | :--- |
| `01_collect_spaces.py` | revit-mcp `get_current_view_elements` |
| `02_match_space_type.py` | FastAPI `/spaces` |
| `03_lumen_calc.py` | FastAPI `/calculate/lighting` |
| `04_place_fixtures.py` | revit-mcp `create_point_based_element` |
| `05_place_emergency.py` | revit-mcp `create_point_based_element` |
| `06_mcp_client.py` | Claude Desktop ↔ FastAPI 직접 MCP 연결 |

**전환 이유**: Dynamo는 노드 6개를 수동 연결해야 하고, 파라미터가 바뀌면 스크립트를 고쳐야 하며, Revit API 미지원 항목(MEP Space 등)을 우회할 수 없었습니다. revit-mcp는 자연어 명령으로 호출 조합을 Claude가 결정하고, `send_code_to_revit`으로 C# 코드를 직접 주입할 수 있습니다.

`test_dynamo_offline.py`는 당시의 오프라인 테스트로, `pytest.ini`의 `testpaths = tests` 설정에 의해 현재 테스트 실행에서 제외됩니다.
