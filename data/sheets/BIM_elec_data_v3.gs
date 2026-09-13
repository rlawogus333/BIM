/**
 * ============================================================
 * BIM_elec_data Google Sheets 자동 입력 스크립트 v3.0
 * ============================================================
 * 적용 기준:
 *   - KDS 31 17 00  철도 전기설비 설계기준
 *   - KDS 32 10 10  전기설비 일반사항
 *   - KDS 32 10 11  전기설비 관련 시설공간
 *   - KDS 32 17 10  전기설비 내진설계기준 (NEW)
 *   - KDS 32 20 20  예비전원설비 (UPS/자가발전)
 *   - KDS 32 25 10  간선 및 배선설비
 *   - KDS 32 25 20  동력설비 (NEW)
 *   - KDS 32 25 30  반송설비 - 엘리베이터/에스컬레이터 (NEW)
 *   - KEC (한국전기설비규정) 2024.10.24 제9차 개정
 *   - NFPC 303      유도등·유도표지 화재안전성능기준
 *   - 장애인편의시설  장애인·노인·임산부 편의증진 보장법 (NEW)
 *
 * 시트 구성 (총 6개):
 *   1. space_rules       – 공간별 전기설비 설계기준
 *   2. lighting_calc     – 조명 루멘법 산출 (실측 면적 기반)
 *   3. fixture_family    – Revit 조명기구 패밀리 DB
 *   4. seismic_req       – 내진설계 요구사항 (NEW)
 *   5. power_equip       – 동력·반송설비 전원 요구사항 (NEW)
 *   6. regulation_index  – 전체 법규 인덱스 (NEW)
 *
 * 사용법:
 *   1. Google Sheets → 확장 프로그램 → Apps Script
 *   2. 이 코드 전체 붙여넣기 (기존 코드 삭제 후)
 *   3. populateAll 선택 → ▶ 실행
 * ============================================================
 */

function populateAll() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  populateSpaceRules(ss);
  populateLightingCalc(ss);
  populateFixtureFamily(ss);
  populateSeismicReq(ss);
  populatePowerEquip(ss);
  populateRegulationIndex(ss);
  ss.toast('✅ 6개 시트 모두 입력 완료! (v3.0)', 'BIM_elec_data', 6);
}

// ============================================================
// 헬퍼: 시트 초기화
// ============================================================
function getOrCreateSheet(ss, name) {
  let sh = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  sh.clearContents();
  sh.clearFormats();
  return sh;
}

// 헬퍼: 교대 행 색상 적용
function applyRowColors(sheet, startRow, rowCount, colCount, color1, color2) {
  for (let i = 0; i < rowCount; i++) {
    sheet.getRange(startRow + i, 1, 1, colCount)
      .setBackground(i % 2 === 0 ? color1 : color2);
  }
}

// 헬퍼: 헤더 서식
function applyHeader(sheet, colCount, bgColor) {
  const hdr = sheet.getRange(1, 1, 1, colCount);
  hdr.setBackground(bgColor);
  hdr.setFontColor('#ffffff');
  hdr.setFontWeight('bold');
  hdr.setWrap(true);
}

// ============================================================
// 1. space_rules 시트
// ============================================================
function populateSpaceRules(ss) {
  const sheet = getOrCreateSheet(ss, 'space_rules');

  const headers = [
    'space_id',           // A
    'space_name_kr',      // B
    'space_name_en',      // C
    'area_ratio_%',       // D  공간 비율
    'sample_area_m2',     // E  섬식 B2 평균 7,216m² 기준
    'illuminance_lux',    // F
    'emergency_light',    // G  비상조명
    'exit_guide_light',   // H  유도등
    'guide_spacing_m',    // I  유도등 간격
    'exit_sign_type',     // J  피난구유도등 종류
    'cctv_power',         // K
    'ups_power',          // L
    'explosion_proof',    // M
    'grounding_required', // N
    'grounding_ohm',      // O
    'seismic_Ip',         // P  내진 중요도 계수 (KDS 32 17 10)
    'seismic_bracing',    // Q  내진 브레이싱 타입
    'cable_type',         // R  KDS 32 25 10
    'conduit_type',       // S
    'ip_rating_min',      // T
    'backup_power_min',   // U  비상전원 지속시간
    'circuit_class',      // V  간선 분류 (KDS 32 25 10)
    'panel_breaker_A',    // W  분기 차단기 규격
    'kds_clause',         // X
    'nfpc_clause',        // Y
    'accessibility',      // Z  장애인편의시설 해당여부
    'notes'               // AA
  ];

  const data = [
    [
      'SR-01', '대합실', 'Concourse',
      30, 2165,
      300, 'TRUE', 'TRUE', '-',
      '대형피난구유도등(대형)',
      'TRUE', 'FALSE', 'FALSE', 'TRUE', '100Ω 이하',
      1.0, '종방향+횡방향',
      'HIV 2.5mm² (450/750V)', 'CD관(PF관)',
      'IP20', 60,
      '상용 조명·전열용 / 비상용 조명용',
      '20A (2P)',
      'KDS 31 17 00 §4.2.1 / KDS 32 10 10',
      'NFPC 303 §5② §6①',
      'TRUE',
      '지하역사 필수: 대형피난구유도등 / 비상조명 / CCTV전원 / 전동보장구충전시설 / 비상전원 60분 이상 / 접지저항 100Ω 이하'
    ],
    [
      'SR-02', '승강장', 'Platform',
      20, 1443,
      200, 'TRUE', 'TRUE', '-',
      '대형피난구유도등(대형)',
      'TRUE', 'FALSE', 'FALSE', 'TRUE', '100Ω 이하',
      1.0, '종방향+횡방향',
      'HIV 2.5mm² (450/750V)', 'CD관(PF관)',
      'IP44', 60,
      '상용 조명·전열용 / 비상용 조명용',
      '20A (2P)',
      'KDS 31 17 00 §4.2.2 / KDS 32 10 10',
      'NFPC 303 §5② §6①',
      'TRUE',
      '승강장 200lux / CCTV전용전원 / IP44 이상(우천 고려) / 스크린도어 전원 연계 / 비상전원 60분 이상'
    ],
    [
      'SR-03', '통로·계단', 'Corridor & Stair',
      25, 1804,
      150, 'FALSE', 'TRUE', 20,
      '복도통로유도등 + 계단통로유도등',
      'FALSE', 'FALSE', 'FALSE', 'FALSE', '-',
      1.5, '4방향 내진브레이싱',
      'FR-8 1.5mm² (내화배선 3선식)', 'HFIX관(내화전선관)',
      'IP44', 60,
      '비상용 조명·전열용 (전용회로)',
      '15A (2P) 전용',
      'KDS 31 17 00 §4.3 / KDS 32 25 10',
      'NFPC 303 §6①-1(나) §6①-3',
      'FALSE',
      '지하역사 특례: 복도·통로 중앙 바닥 매립 / 보행거리 20m마다 / 계단참마다 1개 / 3선식 항시점등 / 내진Ip=1.5(피난경로 비상조명, 유도등)'
    ],
    [
      'SR-04', '기계실', 'Mechanical Room',
      8, 577,
      200, 'FALSE', 'FALSE', '-',
      '해당없음',
      'FALSE', 'FALSE', 'TRUE', 'TRUE', '10Ω 이하',
      1.5, '4방향 내진브레이싱',
      'HFIX 2.5mm² (내열 450/750V)', '금속제 강전선관(후강)',
      'IP67 (Ex e IIC T4)', '-',
      '방폭전용회로 (전기실 전용간선)',
      '20A (3P) MCCB',
      'KEC 242.2 / KDS 32 10 11 §3.3',
      '-',
      'TRUE',
      '방폭등(Ex e IIC T4 이상) 필수 / 접지저항 10Ω 이하 / 환기설비 연동 / 침수방지 IP67 / 내진Ip=1.5(소방부하 예비전원) / 방폭구역 Zone1 또는 Zone2'
    ],
    [
      'SR-05', '역무실', 'Station Office',
      5, 361,
      500, 'FALSE', 'FALSE', '-',
      '해당없음',
      'FALSE', 'TRUE', 'FALSE', 'TRUE', '100Ω 이하',
      1.5, '종방향+횡방향',
      'CV 6mm² (UPS간선)', 'CD관(PF관)',
      'IP20', '-',
      'UPS전용간선 + 상용 조명·전열용',
      '30A (2P) ELB',
      'KDS 32 20 20 §4.3 / KDS 31 17 00',
      '-',
      'FALSE',
      'UPS 무정전전원장치 필수 / 고조도 500lux / 전산·통신 장비 전원 이중화 / UPS출력: P=(출력/효율×λ)+축전지충전(6~10%) / 내진Ip=1.5(예비전원설비, 제어반)'
    ]
  ];

  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(2, 1, data.length, headers.length).setValues(data);
  applyHeader(sheet, headers.length, '#1a73e8');
  applyRowColors(sheet, 2, data.length, headers.length, '#e8f4fd', '#ffffff');
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, headers.length);
  Logger.log('✅ space_rules 입력 완료');
}

// ============================================================
// 2. lighting_calc 시트
// ============================================================
function populateLightingCalc(ss) {
  const sheet = getOrCreateSheet(ss, 'lighting_calc');

  const headers = [
    'space_id',           // A
    'space_name_kr',      // B
    'design_lux_E',       // C  설계 조도
    'area_m2',            // D  면적 (서울교통공사 섬식B2 평균 7,216m² 기준 비율 적용)
    'fixture_type',       // E
    'lumen_F',            // F  광속 (lm)
    'util_factor_U',      // G  조명률
    'maint_factor_M',     // H  보수율
    'fixture_count',      // I  =ROUNDUP((C*D)/(F*G*H),0)
    'ceiling_h_m',        // J  천장고
    'room_index_K',       // K  =D/(J*4*SQRT(D))
    'spacing_m',          // L  등간격 =ROUND(SQRT(D/I),1)
    'refl_ceiling_%',     // M  반사율 천장
    'refl_wall_%',        // N  반사율 벽
    'refl_floor_%',       // O  반사율 바닥
    'color_temp_K',       // P  색온도
    'CRI',                // Q  연색지수
    'watt_per_fixture_W', // R  등기구당 소비전력
    'total_load_W',       // S  =I*R
    'LPD_W_m2',           // T  조명전력밀도 =ROUND(S/D,1)
    'circuit_count',      // U  =ROUNDUP(S/(220*20*0.8),0)
    'data_source',        // V
    'notes'               // W
  ];

  // 실제 데이터: 서울교통공사 섬식B2 평균 7,216m² 기준
  // 공간 비율: 대합실30%, 승강장20%, 통로계단25%, 기계실8%, 역무실5%
  const data = [
    [
      'SR-01', '대합실',
      300, 2165,
      'LED 매입 패널라이트 600×600 (40W/5400lm)',
      5400, 0.60, 0.80,
      '', // I: formula
      4.5,
      '', // K: formula
      '', // L: formula
      70, 50, 20,
      4000, 80,
      40,
      '', // S: formula
      '', // T: formula
      '', // U: formula
      '서울교통공사 역사건축정보 20250310.csv / 섬식B2 평균7,216m²×30%',
      'KS A 3011 지하역사 조도기준 / CRI≥80 / 비상회로 30% 별도 추가'
    ],
    [
      'SR-02', '승강장',
      200, 1443,
      'LED 매입 패널라이트 600×600 (40W/5400lm)',
      5400, 0.55, 0.80,
      '',
      3.5,
      '', '', // K, L
      70, 50, 20,
      4000, 80,
      40,
      '', '', '', // S, T, U
      '서울교통공사 역사건축정보 20250310.csv / 섬식B2 평균7,216m²×20%',
      'KS A 3011 승강장 조도기준 / IP44 이상(우천 고려) / 스크린도어 조명 별도'
    ],
    [
      'SR-03', '통로·계단',
      150, 1804,
      'LED 다운라이트 Ø150 (15W/1800lm)',
      1800, 0.50, 0.75,
      '',
      3.0,
      '', '',
      60, 40, 10,
      4000, 80,
      15,
      '', '', '',
      '서울교통공사 역사건축정보 20250310.csv / 섬식B2 평균7,216m²×25%',
      'NFPC 303 §6 유도등 간격 별도 산출 / 비상조명 전용회로 / FR-8 내화배선'
    ],
    [
      'SR-04', '기계실',
      200, 577,
      '방폭형 LED Ø250 Ex e IIC T4 (30W/3600lm)',
      3600, 0.50, 0.70,
      '',
      3.0,
      '', '',
      30, 30, 10,
      5000, 70,
      30,
      '', '', '',
      '서울교통공사 역사건축정보 20250310.csv / 섬식B2 평균7,216m²×8%',
      'KEC 242 방폭설비 / IP67 필수 / 산업안전보건기준 §312조 / 환기설비 연동 고려'
    ],
    [
      'SR-05', '역무실',
      500, 361,
      'LED 매입 패널라이트 600×600 (40W/5400lm)',
      5400, 0.65, 0.80,
      '',
      2.8,
      '', '',
      70, 50, 20,
      5000, 85,
      40,
      '', '', '',
      '서울교통공사 역사건축정보 20250310.csv / 섬식B2 평균7,216m²×5%',
      'KS A 3011 사무공간 조도기준 / CRI≥85 / 눈부심 방지(UGR≤19) / UPS전원'
    ]
  ];

  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(2, 1, data.length, headers.length).setValues(data);

  // 수식 입력 (I열=9, K열=11, L열=12, S열=19, T열=20, U열=21)
  const fixtureCountFmls = [
    ['=ROUNDUP((C2*D2)/(F2*G2*H2),0)'],
    ['=ROUNDUP((C3*D3)/(F3*G3*H3),0)'],
    ['=ROUNDUP((C4*D4)/(F4*G4*H4),0)'],
    ['=ROUNDUP((C5*D5)/(F5*G5*H5),0)'],
    ['=ROUNDUP((C6*D6)/(F6*G6*H6),0)']
  ];
  sheet.getRange(2, 9, 5, 1).setFormulas(fixtureCountFmls);

  const roomIndexFmls = [
    ['=ROUND(D2/(J2*4*SQRT(D2)),2)'],
    ['=ROUND(D3/(J3*4*SQRT(D3)),2)'],
    ['=ROUND(D4/(J4*4*SQRT(D4)),2)'],
    ['=ROUND(D5/(J5*4*SQRT(D5)),2)'],
    ['=ROUND(D6/(J6*4*SQRT(D6)),2)']
  ];
  sheet.getRange(2, 11, 5, 1).setFormulas(roomIndexFmls);

  const spacingFmls = [
    ['=ROUND(SQRT(D2/I2),1)'],
    ['=ROUND(SQRT(D3/I3),1)'],
    ['=ROUND(SQRT(D4/I4),1)'],
    ['=ROUND(SQRT(D5/I5),1)'],
    ['=ROUND(SQRT(D6/I6),1)']
  ];
  sheet.getRange(2, 12, 5, 1).setFormulas(spacingFmls);

  const totalLoadFmls = [
    ['=I2*R2', '=ROUND(S2/D2,1)', '=ROUNDUP(S2/(220*20*0.8),0)'],
    ['=I3*R3', '=ROUND(S3/D3,1)', '=ROUNDUP(S3/(220*20*0.8),0)'],
    ['=I4*R4', '=ROUND(S4/D4,1)', '=ROUNDUP(S4/(220*20*0.8),0)'],
    ['=I5*R5', '=ROUND(S5/D5,1)', '=ROUNDUP(S5/(220*20*0.8),0)'],
    ['=I6*R6', '=ROUND(S6/D6,1)', '=ROUNDUP(S6/(220*20*0.8),0)']
  ];
  sheet.getRange(2, 19, 5, 3).setFormulas(totalLoadFmls);

  applyHeader(sheet, headers.length, '#137333');
  applyRowColors(sheet, 2, data.length, headers.length, '#e6f4ea', '#ffffff');
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, headers.length);
  Logger.log('✅ lighting_calc 입력 완료');
}

// ============================================================
// 3. fixture_family 시트
// ============================================================
function populateFixtureFamily(ss) {
  const sheet = getOrCreateSheet(ss, 'fixture_family');

  const headers = [
    'family_id',          // A
    'fixture_type_kr',    // B
    'fixture_type_en',    // C
    'revit_family',       // D
    'applicable_space',   // E
    'wattage_W',          // F
    'lumen_lm',           // G
    'voltage_V',          // H
    'ip_rating',          // I
    'explosion_proof',    // J
    'install_method',     // K
    'mount_height_m',     // L
    'spacing_rule',       // M
    'dimensions_mm',      // N
    'cable_type',         // O
    'conduit_type',       // P
    'circuit_type',       // Q
    'backup_min',         // R
    'seismic_Ip',         // S  내진 중요도 계수
    'seismic_anchor',     // T  내진앵커 방식
    'accessibility',      // U  장애인 관련
    'quantity_formula',   // V
    'kds_ref',            // W
    'nfpc_ref',           // X
    'notes'               // Y
  ];

  const data = [
    // FF-01: LED 패널라이트 (대합실·승강장·역무실)
    [
      'FF-01', 'LED 매입 패널라이트', 'LED Recessed Panel Light',
      'M_Lighting Fixture Recessed.rfa',
      '대합실, 승강장, 역무실',
      40, 5400, 220,
      'IP20', 'FALSE',
      '천장매입', '매입(천장면)',
      '루멘법 산출 / 등간격 배치',
      '600 × 600 × 80',
      'HIV 2.5mm²', 'CD관(PF관)',
      '상용 조명·전열용 회로',
      '-', 1.0,
      '상부고정대+하부고정대 (종방향)',
      'FALSE',
      'N = ROUNDUP((E×A)/(F×U×M),0)',
      'KDS 31 17 00 §4.2 / KDS 32 10 10',
      '-',
      'CRI≥80 / 색온도 4000K / Dynamo FamilyInstance 배치 / UGR≤22'
    ],
    // FF-02: 비상용 LED
    [
      'FF-02', '비상용 LED 조명', 'Emergency LED Light',
      'M_Emergency Light.rfa',
      '대합실, 승강장, 통로·계단',
      20, 2000, '220/DC24',
      'IP44', 'FALSE',
      '천장매입/노출', '0.3m 이상(바닥에서)',
      '비상구·피난통로 인접',
      '300 × 300 × 80',
      'FR-8 2.5mm² (내화배선)', 'HFIX관',
      '비상용 조명·전열용 전용회로',
      60, 1.5,
      '4방향 내진브레이싱 (피난경로)',
      'FALSE',
      '비상구·피난통로 인접 1개 이상',
      'KDS 31 17 00 §4.5 / KDS 32 17 10 §1.2②',
      'NFPC 303 §10②',
      '지하층 비상전원 60분 이상 / 내화배선 필수 / 내진Ip=1.5'
    ],
    // FF-03: 복도통로유도등
    [
      'FF-03', '복도통로유도등', 'Corridor Exit Guide Light',
      'M_Exit Light Corridor.rfa',
      '통로·계단',
      5, 400, '220/DC',
      'IP44', 'FALSE',
      '바닥매립 (지하역사 특례)',
      '바닥 중앙 매립 (지상 0.1m 이하)',
      '보행거리 20m마다',
      '400 × 120 × 30',
      'FR-8 1.5mm² (3선식 내화배선)', 'HFIX관(내화)',
      '비상용 전용회로 (3선식 항시점등)',
      60, 1.5,
      '4방향 내진브레이싱',
      'FALSE',
      'N = ROUNDUP(통로길이(m)/20, 0) + 1',
      'KDS 32 17 10 §1.2②',
      'NFPC 303 §6①-1(나)',
      '지하역사 특례: 복도·통로 중앙 바닥 매립 / 항시점등 3선식 / 내진Ip=1.5'
    ],
    // FF-04: 대형피난구유도등
    [
      'FF-04', '대형피난구유도등', 'Large Exit Sign',
      'M_Exit Sign Large.rfa',
      '대합실, 승강장, 통로',
      10, 800, '220/DC',
      'IP44', 'FALSE',
      '출입구 상단 벽부착/천장수직',
      '바닥 1.5m 이상',
      '출입구마다 1개',
      '600 × 200 × 40',
      'FR-8 1.5mm² (3선식)', 'HFIX관',
      '비상용 전용회로 (3선식)',
      60, 1.5,
      '4방향 내진브레이싱',
      'TRUE',
      '출입구 수량 × 1 (천장 수직 추가)',
      'KDS 32 17 10 §1.2②',
      'NFPC 303 §5②③',
      '지하역사 필수 (대형) / 천장에 수직방향 추가 §5③ / 장애인 시각정보 연계'
    ],
    // FF-05: 계단통로유도등
    [
      'FF-05', '계단통로유도등', 'Stairway Exit Guide Light',
      'M_Exit Light Stair.rfa',
      '통로·계단',
      5, 400, '220/DC',
      'IP44', 'FALSE',
      '벽면부착',
      '바닥 1m 이하',
      '각층 계단참마다',
      '300 × 100 × 30',
      'FR-8 1.5mm² (3선식)', 'HFIX관',
      '비상용 전용회로 (3선식)',
      60, 1.5,
      '앵커볼트 고정',
      'FALSE',
      '계단참 수 × 1',
      'KDS 32 17 10 §1.2②',
      'NFPC 303 §6①-3',
      '각층 경사로 참 또는 계단참마다 설치'
    ],
    // FF-06: 방폭형 LED
    [
      'FF-06', '방폭형 LED 조명', 'Explosion-Proof LED',
      'M_Lighting Fixture Explosion Proof.rfa',
      '기계실',
      30, 3600, 220,
      'IP67 (Ex e IIC T4)', 'TRUE',
      '천장 노출/매입', '천장매입 또는 노출',
      '루멘법 산출',
      '250 × 250 × 130',
      'HFIX 2.5mm² (내열)', '금속제 강전선관(후강)',
      '방폭전용회로',
      '-', 1.5,
      '4방향 내진브레이싱 + 방폭배관',
      'FALSE',
      'N = ROUNDUP((E×A)/(F×U×M),0)',
      'KEC 242.2 / KDS 32 10 11 §3.3 / KDS 32 17 10',
      '-',
      '방폭등급 Ex e IIC T4 이상 / 접지저항 10Ω / 산업안전보건기준 §312 / 내진Ip=1.5'
    ],
    // FF-07: CCTV 전용 콘센트
    [
      'FF-07', 'CCTV 전용 콘센트', 'CCTV Power Outlet',
      'M_Power Outlet CCTV.rfa',
      '대합실, 승강장',
      '-', '-', 220,
      'IP44', 'FALSE',
      '벽부착 노출', '바닥 0.3m~1.5m',
      'CCTV 설치위치 인접',
      '75 × 75 × 45',
      'HIV 2.5mm²', 'CD관',
      '상용 일반회로 (전용분기)',
      '-', 1.0,
      '앵커볼트 고정',
      'FALSE',
      'CCTV 대수 × 1',
      'KDS 31 17 00',
      '-',
      'CCTV 카메라당 1개 / 방수형 / 전용회로 분기'
    ],
    // FF-08: UPS 분기단자함
    [
      'FF-08', 'UPS 분기 단자함', 'UPS Distribution Terminal',
      'M_Electrical Panel UPS.rfa',
      '역무실',
      '-', '-', 220,
      'IP20', 'FALSE',
      '벽매입', '바닥 1.2m~1.5m',
      '역무실 전용 1개',
      '300 × 200 × 100',
      'CV 6mm² (UPS간선)', 'CD관',
      'UPS 전용간선',
      '-', 1.5,
      '상부고정대+하부고정대',
      'FALSE',
      '역무실 부하합계 × 수용률',
      'KDS 32 20 20 §4.3 / KDS 32 17 10',
      '-',
      'UPS 연결 / 전산·통신장비 전원 / 이중화 권장 / 내진Ip=1.5(제어반)'
    ],
    // FF-09: 전동보장구 충전시설 (장애인 편의)
    [
      'FF-09', '전동보장구 충전시설', 'Electric Mobility Charger',
      'M_Power Outlet Accessible.rfa',
      '대합실',
      '-', '-', 220,
      'IP44', 'FALSE',
      '벽부착/바닥고정', '바닥 0.3m~0.8m',
      '장애인 편의시설 인접',
      '150 × 200 × 80',
      'HIV 2.5mm²', 'CD관',
      '상용 일반회로',
      '-', 1.0,
      '앵커볼트 고정',
      'TRUE',
      '편의시설 면적 기준 / 법적 의무 설치',
      'KDS 31 17 00',
      '-',
      '장애인·노인·임산부 편의증진 보장법 §16① / 휠체어·전동보장구 충전 / 공공시설 의무 설치'
    ],
    // FF-10: 비상콘센트
    [
      'FF-10', '비상용 콘센트', 'Emergency Power Outlet',
      'M_Power Outlet Emergency.rfa',
      '통로·계단, 승강장',
      '-', '-', 220,
      'IP44', 'FALSE',
      '벽부착 노출', '바닥 0.8m~1.2m',
      '소방법: 반경 25m 이내',
      '75 × 75 × 45',
      'FR-8 2.5mm² (내화배선)', 'HFIX관',
      '비상용 전용회로 (소방)',
      60, 1.5,
      '앵커볼트 고정',
      'FALSE',
      '소방대 진입경로 25m 반경',
      'KDS 32 25 10 / 소방시설법',
      '-',
      '소방법상 비상콘센트 / 내화배선 필수 / 지하 2층 이하 필수'
    ]
  ];

  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(2, 1, data.length, headers.length).setValues(data);
  applyHeader(sheet, headers.length, '#b45309');
  applyRowColors(sheet, 2, data.length, headers.length, '#fef9c3', '#ffffff');
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, headers.length);
  Logger.log('✅ fixture_family 입력 완료');
}

// ============================================================
// 4. seismic_req 시트 (KDS 32 17 10 기반)
// ============================================================
function populateSeismicReq(ss) {
  const sheet = getOrCreateSheet(ss, 'seismic_req');

  const headers = [
    'item_id',            // A
    'equipment_kr',       // B  설비 명칭
    'equipment_en',       // C
    'applicable_space',   // D
    'seismic_Ip',         // E  중요도 계수
    'Ip_reason',          // F  Ip=1.5 사유
    'bracing_type',       // G  내진지지대 종류
    'anchor_type',        // H  앵커 방식
    'flexible_joint',     // I  유연성 이음장치 필요여부
    'stopper_required',   // J  내진스토퍼
    'kds_clause',         // K
    'installation_note'   // L
  ];

  const data = [
    [
      'SQ-01', '소방·비상 예비전원설비 (UPS/발전기)', 'Emergency Power Supply',
      '기계실, 역무실',
      1.5, 'KDS 32 17 10 §1.2①: 소방부하/비상부하 예비전원설비',
      '4방향 내진브레이싱 (리지드형)',
      '앵커볼트(M12 이상) + 상부구속',
      'TRUE', 'TRUE',
      'KDS 32 17 10 §1.2①',
      '지진 후에도 기능 유지 / 콘크리트 앵커 매입 깊이 ≥ 75mm'
    ],
    [
      'SQ-02', '배분전반·제어반·배선설비', 'Distribution Panel & Control Panel',
      '기계실, 역무실',
      1.5, 'KDS 32 17 10 §1.2①: 인명안전 기능유지 필요',
      '4방향 내진브레이싱 (리지드형)',
      '앵커볼트(M10 이상) + 하부고정',
      'TRUE', 'TRUE',
      'KDS 32 17 10 §1.2①',
      '전후·좌우 4방향 지지 / 유연성 이음장치로 케이블트레이 연결'
    ],
    [
      'SQ-03', '피난경로 비상조명등', 'Emergency Lighting (Evacuation Route)',
      '통로·계단, 대합실',
      1.5, 'KDS 32 17 10 §1.2②: 피난경로 확보 비상조명',
      '케이블식 내진브레이싱 또는 리지드형',
      '천장 앵커볼트(M8 이상)',
      'FALSE', 'FALSE',
      'KDS 32 17 10 §1.2②',
      '피난경로 전 구간 연속 설치 / 지진 후 60분 이상 점등 유지'
    ],
    [
      'SQ-04', '피난경로 유도등·배선설비', 'Exit Guide Lights (Evacuation Route)',
      '통로·계단, 대합실, 승강장',
      1.5, 'KDS 32 17 10 §1.2②: 피난경로 유도등',
      '케이블식 또는 리지드형 내진브레이싱',
      '벽·바닥 앵커볼트(M8 이상)',
      'FALSE', 'FALSE',
      'KDS 32 17 10 §1.2②',
      '지하역사 바닥 매립형 추가 고려 / 배선설비 유연성 이음장치 구간 별도 설계'
    ],
    [
      'SQ-05', '케이블트레이·버스덕트·전선관', 'Cable Tray / Bus Duct / Conduit',
      '전 구역 (주간선)',
      1.5, 'KDS 32 17 10 §1.2①: 인명안전 배선설비',
      '횡방향+종방향 내진지지대 (12m 이하 간격)',
      '상부고정대 앵커볼트(M10)',
      'TRUE', 'FALSE',
      'KDS 32 17 10 §2',
      '단부·방향전환점 내진지지대 추가 / 유연성 이음장치: 상대변위 발생 구간 / 세장비(L/r) 검토 필수'
    ],
    [
      'SQ-06', '일반 조명기구 (비피난경로)', 'General Lighting (Non-Evacuation)',
      '대합실, 승강장, 역무실',
      1.0, 'KDS 32 17 10 §1.2(2): Ip=1.0 적용',
      '종방향 내진지지대',
      '천장 앵커볼트(M8)',
      'FALSE', 'FALSE',
      'KDS 32 17 10 §1.2(2)',
      'Ip=1.0 내진설계 / KDS 41 17 00 §18.1.1(2) 해당 시 내진 불요'
    ],
    [
      'SQ-07', 'CCTV·콘센트·소형기기', 'CCTV / Outlet / Small Equipment',
      '대합실, 승강장',
      1.0, 'KDS 32 17 10: Ip=1.0 적용',
      '앵커볼트 단순고정',
      '벽면 앵커볼트(M6)',
      'FALSE', 'FALSE',
      'KDS 32 17 10 §1.2(2)',
      '중량이 작은 비구조요소 / KDS 41 17 00 기준 확인'
    ]
  ];

  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(2, 1, data.length, headers.length).setValues(data);
  applyHeader(sheet, headers.length, '#7b1fa2');
  applyRowColors(sheet, 2, data.length, headers.length, '#f3e5f5', '#ffffff');
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, headers.length);
  Logger.log('✅ seismic_req 입력 완료');
}

// ============================================================
// 5. power_equip 시트 (KDS 32 25 20 동력설비 + KDS 32 25 30 반송설비)
// ============================================================
function populatePowerEquip(ss) {
  const sheet = getOrCreateSheet(ss, 'power_equip');

  const headers = [
    'equip_id',           // A
    'equip_type_kr',      // B
    'equip_type_en',      // C
    'applicable_space',   // D
    'rated_power_kW',     // E  정격 출력
    'rated_voltage_V',    // F
    'phase',              // G  상수
    'rated_current_A',    // H  =E*1000/(F*SQRT(G)*0.85)  (PF=0.85)
    'starter_type',       // I  기동방식
    'control_type',       // J  제어방식
    'cable_type',         // K  KDS 32 25 10
    'cable_size_mm2',     // L
    'breaker_A',          // M  차단기 규격
    'protection_class',   // N  보호계전기
    'seismic_Ip',         // O
    'backup_required',    // P  비상전원 필요
    'kds_clause',         // Q
    'quantity_note',      // R
    'notes'               // S
  ];

  const data = [
    // 환기·공조 팬 (기계실)
    [
      'PE-01', '환기팬 (기계실)', 'Ventilation Fan (Mechanical Room)',
      '기계실',
      5.5, 380, 3,
      '', // H: formula
      'Y-△ 기동 (직입 5.5kW 이하 가능)',
      'MCCB + MC + THR (열동계전기)',
      'CV', '2.5mm²',
      '20A MCCB (3P)',
      'THR(과부하) + EOCR(과전류)',
      1.5, 'TRUE',
      'KDS 32 25 20 §2.1 / KDS 32 10 11',
      '기계실당 최소 2대 (주1+예비1)',
      '방폭구역 팬은 방폭형 전동기 Ex e IIC 적용 / 비상전원 연계 / 내진Ip=1.5(소방부하)'
    ],
    // 승강기 (엘리베이터) - KDS 32 25 30
    [
      'PE-02', '승객용 엘리베이터', 'Passenger Elevator',
      '대합실 ↔ 승강장',
      11, 380, 3,
      '',
      'VVVF 인버터 기동',
      'MCC + 인버터 + 전용제어반',
      'CV', '6mm²',
      '50A MCCB (3P)',
      'OCGR + 과부하보호',
      1.5, 'TRUE',
      'KDS 32 25 30 §1.6.1 / 승강기안전관리법',
      '정격하중 630kg 이상 / 속도 1.00m/s 이상 (군 운영 시)',
      '비상전원 연계 / 장애인 전용 엘리베이터 의무 / KS B ISO 4190 / 내진Ip=1.5'
    ],
    // 에스컬레이터 - KDS 32 25 30
    [
      'PE-03', '에스컬레이터', 'Escalator',
      '대합실 ↔ 승강장',
      15, 380, 3,
      '',
      'Y-△ 또는 VVVF 기동',
      'MCC + 전용제어반 + 역전방지',
      'CV', '6mm²',
      '63A MCCB (3P)',
      'OCGR + 제동기 과열보호',
      1.0, 'FALSE',
      'KDS 32 25 30 §1.6.2 / 승강기안전관리법',
      '역사당 2대 이상 (상행+하행)',
      'KS B 6918 안전기준 / 역전방지 브레이크 / EMC 적합 / 정격속도 0.5m/s 이하'
    ],
    // 수중펌프 (침수 배수)
    [
      'PE-04', '배수 수중펌프', 'Submersible Drainage Pump',
      '기계실 (지하 피트)',
      3.7, 220, 1,
      '',
      '직입 기동',
      'MCC + 수위자동제어',
      'CV', '2.5mm²',
      '20A MCCB (2P)',
      'THR + 수위검출릴레이',
      1.5, 'TRUE',
      'KDS 32 25 20 §2.3 / KDS 32 10 11',
      '주1 + 예비1 자동교대운전',
      '지하역사 침수방지 필수 / 비상전원 연계 / IP68 전동기 / 내진Ip=1.5(소방부하)'
    ],
    // 전동보장구 충전기 (장애인 편의)
    [
      'PE-05', '전동보장구 충전시설', 'Electric Mobility Charger',
      '대합실',
      1.5, 220, 1,
      '',
      '단순 플러그인',
      '전용 콘센트 + ELB',
      'HIV', '2.5mm²',
      '15A ELB (2P)',
      'ELB(누전차단기)',
      1.0, 'FALSE',
      '장애인·노인·임산부 편의증진 보장법 §16①',
      '대합실당 1개소 이상 / 법적 의무',
      '장애인 편의시설 의무 설치 / 공공시설 / 높이 0.3m~0.8m / 접근 통로 확보'
    ],
    // 공조기 (AHU)
    [
      'PE-06', '공기조화기 (AHU)', 'Air Handling Unit',
      '기계실',
      22, 380, 3,
      '',
      'Y-△ 기동 또는 인버터',
      'MCC + VFD + BAS 연동',
      'CV', '10mm²',
      '100A MCCB (3P)',
      'THR + OCGR + 과부하',
      1.5, 'TRUE',
      'KDS 32 25 20 §2.1 / KDS 32 10 11',
      '기계실 환경에 따라 대수 결정',
      '비상전원 연계 (정전 시 배기운전) / BAS(건물자동화시스템) 연동 / 내진Ip=1.5'
    ]
  ];

  // rated_current 수식 입력 (H열=8): I = P*1000/(V*√phase*PF)
  // 단상: I = P*1000/(V*PF) / 3상: I = P*1000/(V*√3*PF)
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(2, 1, data.length, headers.length).setValues(data);

  // 전류 수식 (H열=8)
  const currentFormulas = [
    ['=ROUND(E2*1000/(F2*IF(G2=3,SQRT(3),1)*0.85),1)'],
    ['=ROUND(E3*1000/(F3*IF(G3=3,SQRT(3),1)*0.85),1)'],
    ['=ROUND(E4*1000/(F4*IF(G4=3,SQRT(3),1)*0.85),1)'],
    ['=ROUND(E5*1000/(F5*IF(G5=3,SQRT(3),1)*0.85),1)'],
    ['=ROUND(E6*1000/(F6*IF(G6=3,SQRT(3),1)*0.85),1)'],
    ['=ROUND(E7*1000/(F7*IF(G7=3,SQRT(3),1)*0.85),1)']
  ];
  sheet.getRange(2, 8, data.length, 1).setFormulas(currentFormulas);

  applyHeader(sheet, headers.length, '#c62828');
  applyRowColors(sheet, 2, data.length, headers.length, '#ffebee', '#ffffff');
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, headers.length);
  Logger.log('✅ power_equip 입력 완료');
}

// ============================================================
// 6. regulation_index 시트 (전체 법규 인덱스)
// ============================================================
function populateRegulationIndex(ss) {
  const sheet = getOrCreateSheet(ss, 'regulation_index');

  const headers = [
    'reg_id',         // A
    'code_number',    // B  법규·기준 번호
    'title_kr',       // C  명칭(한글)
    'title_en',       // D  명칭(영문)
    'category',       // E  분류
    'issuer',         // F  발령 기관
    'latest_ver',     // G  최신 개정
    'applicable_to',  // H  적용 공간/설비
    'key_clauses',    // I  주요 조항
    'file_in_folder', // J  폴더 내 파일 여부
    'notes'           // K
  ];

  const data = [
    // ── 설계기준 (KDS) ──────────────────────────────────────
    [
      'RI-01', 'KDS 31 17 00', '철도 전기설비 설계기준',
      'Railway Electrical Equipment Design Standard',
      'KDS (설계기준)', '국토교통부',
      '-',
      '대합실, 승강장, 통로·계단, 기계실, 역무실',
      '§4.2 조도기준 / §4.5 비상조명 / 공간별 전기설비 요구사항',
      'FALSE', '경진대회 핵심 기준 / JSON 인코딩 대상'
    ],
    [
      'RI-02', 'KDS 32 10 10', '전기설비 일반사항',
      'General Requirements for Electrical Installations',
      'KDS (설계기준)', '국토교통부',
      '-',
      '전 공간',
      '§3 설계단계별 업무 / §4 설계도서 / 수변전설비 일반',
      'TRUE', '폴더 파일: KDS_32_10_10_전기설비일반사항.pdf'
    ],
    [
      'RI-03', 'KDS 32 10 11', '전기설비 관련 시설공간',
      'Facility Spaces for Electrical Installations',
      'KDS (설계기준)', '국토교통부',
      '-',
      '기계실, 전기실',
      '§3.3 방폭 장소 기준 / 전기실 설계기준 / 발전설비실',
      'TRUE', '폴더 파일: KDS_32_10_11_전기설비관련시설.pdf'
    ],
    [
      'RI-04', 'KDS 32 17 10', '전기설비 내진설계기준',
      'Seismic Design for Electrical Installations',
      'KDS (설계기준)', '국토교통부',
      '-',
      '비상전원설비, 배분전반, 피난경로 설비 전체',
      '§1.2①② Ip=1.5 대상 / 내진지지대 종류 / 유연성 이음장치',
      'TRUE', '폴더 파일: KDS_32_17_10_내진설비.pdf (NEW)'
    ],
    [
      'RI-05', 'KDS 32 20 20', '예비전원설비',
      'Standby Power Systems (UPS & Generator)',
      'KDS (설계기준)', '국토교통부',
      '-',
      '역무실, 기계실',
      '§4.3 UPS 설계 / P=(출력/효율×λ)+충전용량 / 자가발전 설계',
      'TRUE', '폴더 파일: KDS_32_20_20_예비전원설비.pdf'
    ],
    [
      'RI-06', 'KDS 32 25 10', '간선 및 배선설비',
      'Main Lines and Wiring Installations',
      'KDS (설계기준)', '국토교통부',
      '-',
      '전 공간 (배선)',
      '§3 간선 분류(6종) / 케이블 종류 HIV/FR-8/CV / 설계순서도',
      'TRUE', '폴더 파일: KDS_32_25_10_간선및배선설비.pdf'
    ],
    [
      'RI-07', 'KDS 32 25 20', '동력설비',
      'Power Equipment (Motor Driven)',
      'KDS (설계기준)', '국토교통부',
      '-',
      '기계실 (팬, 펌프, AHU)',
      '§2.1 전동기 전원공급 / 보호계전기 / 기동방식',
      'TRUE', '폴더 파일: KDS_32_25_20_동력설비.pdf (NEW)'
    ],
    [
      'RI-08', 'KDS 32 25 30', '반송설비',
      'Conveying Equipment (Elevator & Escalator)',
      'KDS (설계기준)', '국토교통부',
      '-',
      '대합실 ↔ 승강장 (엘리베이터·에스컬레이터)',
      '§1.6.1 엘리베이터 대수·속도 / §1.6.2 에스컬레이터 / 장애인이동편의',
      'TRUE', '폴더 파일: KDS_32_25_30_반송설비.pdf (NEW)'
    ],
    // ── 시공기준 (KCS) ──────────────────────────────────────
    [
      'RI-09', 'KCS 31 60 05 ~ 85', '철도 전기설비 시공기준 (다수)',
      'Railway Electrical Installation Construction Standards',
      'KCS (시공기준)', '국토교통부',
      '-',
      '전 공간 (시공)',
      '조명/전력/신호/통신/접지 시공 세부기준',
      'TRUE', '폴더 파일: KCS 31 60 05~85 HWP 다수 (NEW)'
    ],
    [
      'RI-10', 'KCS 31 10 21', '철도건축 부대시설 설계기준',
      'Railway Architectural Ancillary Facilities',
      'KCS (시공기준)', '국토교통부',
      '-',
      '전 공간',
      '역사 건축 부대시설 일반',
      'TRUE', '폴더 파일: KCS 31 10 21 HWP (NEW)'
    ],
    // ── 한국전기설비규정 (KEC) ──────────────────────────────
    [
      'RI-11', 'KEC (한국전기설비규정)', '한국전기설비규정',
      'Korean Electrical Code (KEC)',
      'KEC', '산업통상자원부',
      '2024.10.24 (제9차 개정, 공고 제2024-749호)',
      '전 공간 (전기설비 전반)',
      '§121~122 전선 선정 / §141~143 접지시스템 / §151~153 피뢰시스템 / §242 방폭설비',
      'TRUE', '폴더 파일: KEC_1.pdf, KEC_2.pdf (NEW) / 2024년 최신 개정'
    ],
    // ── 소방 기준 ──────────────────────────────────────────
    [
      'RI-12', 'NFPC 303', '유도등·유도표지 화재안전성능기준',
      'Fire Safety Performance Standard for Exit Lights',
      '소방 (NFPC)', '소방청',
      '-',
      '통로·계단, 대합실, 승강장',
      '§5② 지하역사 대형피난구유도등 / §6① 복도통로유도등 20m / 바닥 매립 / 3선식 / 60분',
      'TRUE', '폴더 파일: light.pdf'
    ],
    // ── 접근성·편의시설 ────────────────────────────────────
    [
      'RI-13', '장애인·노인·임산부 편의증진 보장법', '장애인 편의시설 설치 의무',
      'Act on Guarantee of Promotion of Convenience for Persons with Disabilities',
      '복지법령', '보건복지부',
      '-',
      '대합실 (공공시설)',
      '§3 편의시설 설치의무 / §16① 전동보장구충전시설 / 편의시설 종류 및 기준',
      'TRUE', '폴더 파일: disabled.pdf (NEW) / 지하철역 공공시설 의무 적용'
    ],
    // ── 역사 데이터 ────────────────────────────────────────
    [
      'RI-14', '서울교통공사_역사건축정보_20250310.csv', '서울 지하철역사 건축현황',
      'Seoul Metro Station Architecture Data',
      '참고 데이터', '서울교통공사',
      '2025.03.10',
      '면적 산출 기준',
      '276개역 / 섬식B2 평균 7,216m² / 승강장 유형·면적·층수·준공연도',
      'TRUE', '폴더 파일: 서울교통공사_역사건축정보_20250310.csv / 조명 루멘법 면적 기준'
    ],
    [
      'RI-15', '서울교통공사_역사현황(9호선포함).xlsx', '서울 지하철역사 현황 (XLSX)',
      'Seoul Metro Station Status (XLSX)',
      '참고 데이터', '서울교통공사',
      '-',
      '면적 산출 참고',
      '9호선 포함 역사 현황',
      'TRUE', '폴더 파일: 서울교통공사_역사현황(9호선2_3단계포함).xlsx (NEW)'
    ],
    // ── KDS 31 시리즈 (철도 설계기준) ──────────────────────
    [
      'RI-16', 'KDS 31 60 10 ~ 31 85 70', '철도 전기설비 설계기준 (조명·전력·신호)',
      'Railway Electrical Design Standards (Lighting, Power, Signal)',
      'KDS (설계기준)', '국토교통부',
      '-',
      '전 공간',
      '조명설비/전력설비/신호설비/통신설비/접지설비 설계기준',
      'TRUE', '폴더 파일: KDS 31 60~85 HWP 다수 (NEW)'
    ]
  ];

  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(2, 1, data.length, headers.length).setValues(data);
  applyHeader(sheet, headers.length, '#37474f');
  applyRowColors(sheet, 2, data.length, headers.length, '#eceff1', '#ffffff');

  // 분류별 색상 구분
  const catColors = {
    'KDS (설계기준)': '#e3f2fd',
    'KCS (시공기준)': '#e8f5e9',
    'KEC': '#fff3e0',
    '소방 (NFPC)': '#fce4ec',
    '복지법령': '#f3e5f5',
    '참고 데이터': '#f5f5f5'
  };
  for (let i = 0; i < data.length; i++) {
    const cat = data[i][4];
    const color = catColors[cat] || '#ffffff';
    sheet.getRange(i + 2, 5, 1, 1).setBackground(color);
  }

  // J열 (파일 여부): TRUE/FALSE 색상
  for (let i = 0; i < data.length; i++) {
    const cell = sheet.getRange(i + 2, 10);
    if (data[i][9] === 'TRUE') {
      cell.setBackground('#c8e6c9').setFontWeight('bold');
    } else {
      cell.setBackground('#ffcdd2');
    }
  }

  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, headers.length);
  Logger.log('✅ regulation_index 입력 완료');
}
