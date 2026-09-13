"""
pytest 공통 설정.

tests/ 디렉터리에서 src/ 의 모듈(main.py 등)을 import 할 수 있도록
sys.path 에 src 를 등록한다. 이 파일 덕분에 저장소 루트에서
`pytest` 만 실행해도 테스트가 동작한다.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
