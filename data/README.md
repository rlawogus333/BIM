# data — 규칙 원본 및 참고 데이터

`src/rules_db.json`의 근거가 되는 원본 자료입니다.

## BIM_elec_data.xlsx

규칙 DB의 원본 스프레드시트. 6개 시트로 구성됩니다.

| 시트 | 행 | 내용 |
| :--- | ---: | :--- |
| `space_rules` | 5 | 공간별 조도·비상전원·유도등·접지·내진·케이블·차단기 등 29개 컬럼 |
| `seismic_req` | 7 | 설비별 내진 요구사항 (KDS 32 17 10, Ip=1.0/1.5) |
| `power_equip` | 6 | 동력설비 사양 (환기팬·엘리베이터·에스컬레이터·펌프·AHU·전동보장구 충전시설) |
| `regulation_index` | 16 | 참조 법규 색인 — 코드·제목·조항·`data/standards/` 파일 대응 |
| `lighting_calc` | 5 | 조도 계산 파라미터 (설계조도·광속·조명률·보수율·반사율·LPD) |
| `fixture_family` | 12 | Revit Family 매핑 (패밀리명·면 타입·설치높이·수량 산식·근거 조항) |

변환: `python src/excel_to_json.py --input data/BIM_elec_data.xlsx --output src/rules_db.json`

> ⚠️ 현재 변환 스크립트 출력은 `rules_db.json` v2.0.0 스키마를 완전히 충족하지 않습니다.
> [docs/KNOWN_ISSUES.md](../docs/KNOWN_ISSUES.md) §2를 먼저 확인하세요.

## sheets/

구글 시트에서 위 데이터를 생성·채우는 Apps Script입니다.

| 파일 | 용도 |
| :--- | :--- |
| `BIM_elec_data_v3.gs` | 시트 구조(헤더·검증·서식) 생성 |
| `BIM_elec_data_populate.gs` | 기준값 데이터 입력 |

## standards/

KDS·KEC 등 국가 표준 원문 PDF입니다. 각 파일과 조항의 대응은 `BIM_elec_data.xlsx`의 `regulation_index` 시트와 `src/rules_db.json`의 `standards_glossary`를 참고하세요.

## stations/

서울교통공사 역사 건축정보 공공데이터(CSV/XLSX). `lighting_calc` 시트의 면적 산정 근거입니다 — 섬식 B2 평균 7,216 m²에 공간별 면적비(대합실 30 %, 승강장 20 %, 통로·계단 25 %, 기계실 8 %, 역무실 5 %)를 적용했습니다.

---

이 폴더의 자료는 각 원저작자(국토교통부·산업통상자원부·소방청·서울교통공사)에게 저작권이 있으며, 참고 목적으로 포함되어 있습니다.
