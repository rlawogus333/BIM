/**
 * BIM_elec_data Google Sheets 자동 입력 스크립트 v2
 * ─────────────────────────────────────────────────
 * 근거 법령:
 *   · KDS 31 17 00  철도 전기설비 설계기준
 *   · KDS 32 10 10  전기설비 일반사항
 *   · KDS 32 10 11  전기설비 관련 시설공간
 *   · KDS 32 20 20  예비전원설비 (UPS, 자가발전)
 *   · KDS 32 25 10  간선 및 배선설비
 *   · KEC 242       방폭설비 기준
 *   · NFPC 303      유도등·유도표지 화재안전성능기준
 *
 * 면적 기준:
 *   · 서울교통공사 역사건축정보(2025.03.10) 섬식 B2층 평균 7,216 m²
 *   · 공간 비율: 대합실 30%, 승강장 20%, 통로·계단 25%, 기계실 8%, 역무실 5%
 *
 * 사용법:
 *   1. 스프레드시트 → 확장 프로그램 → Apps Script
 *   2. 기존 코드 전체 삭제 후 이 코드 붙여넣기
 *   3. 함수 선택: populateAll → ▶ 실행
 */

// ══════════════════════════════════════════════════
//  메인 실행 함수
// ══════════════════════════════════════════════════
function populateAll() {
  populateSpaceRules();
  populateLightingCalc();
  populateFixtureFamily();
  SpreadsheetApp.getActiveSpreadsheet()
    .toast('✅ space_rules / lighting_calc / fixture_family 입력 완료!', 'BIM_elec_data v2', 6);
}

// ══════════════════════════════════════════════════
//  공통 유틸
// ══════════════════════════════════════════════════
function applyHeader(sheet, headers, bgColor) {
  const r = sheet.getRange(1, 1, 1, headers.length);
  r.setValues([headers]);
  r.setBackground(bgColor);
  r.setFontColor('#ffffff');
  r.setFontWeight('bold');
  r.setHorizontalAlignment('center');
  sheet.setFrozenRows(1);
}

function applyRowColors(sheet, rows, col, color1, color2) {
  for (let i = 0; i < rows; i++) {
    sheet.getRange(i + 2, 1, 1, col)
      .setBackground(i % 2 === 0 ? color1 : color2);
  }
}

// ══════════════════════════════════════════════════
//  1. space_rules 시트
//     공간별 전기설비 규칙 (규정 근거 포함)
// ══════════════════════════════════════════════════
function populateSpaceRules() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName('space_rules');
  if (!sh) sh = ss.insertSheet('space_rules');
  sh.clearContents();

  const headers = [
    'space_id',           // A
    'space_name_kr',      // B
    'space_name_en',      // C
    'illuminance_lux',    // D
    'emergency_light',    // E  비상조명
    'exit_guide_light',   // F  통로유도등
    'exit_guide_spacing_m', // G  유도등 간격
    'exit_sign_type',     // H  피난구유도등 종류
    'cctv_power',         // I
    'ups_power',          // J
    'explosion_proof',    // K  방폭등
    'grounding_required', // L  접지 의무
    'grounding_resistance_ohm', // M
    'circuit_type',       // N  간선 회로 분류
    'cable_type',         // O  전선 종류
    'conduit_type',       // P  전선관
    'ip_rating_min',      // Q  방수등급
    'backup_power_min',   // R  비상전원 최소(분)
    'panel_circuit',      // S  분전반 회로 구분
    'regulation_source',  // T
    'kds_clause',         // U
    'nfpc_clause',        // V
    'notes'               // W
  ];

  const data = [
    // ─── 대합실 ─────────────────────────────────────────────────────
    [
      'SR-01', '대합실', 'Concourse',
      300,
      'TRUE',                        // 비상조명
      'FALSE',                       // 유도등(통로형)
      '-',                           // 간격
      '대형피난구유도등',             // NFPC303 §4 지하역사
      'TRUE',                        // CCTV전원
      'FALSE',                       // UPS
      'FALSE',                       // 방폭
      'FALSE',                       // 접지
      '-',
      '상용 조명·전열용 간선 + 비상용 조명·전열용 간선', // KDS 32 25 10 §1.7.2
      'HIV 2.5mm² (상용) / FR-8 2.5mm² (비상)',
      'CD전선관 (천장매입)',
      'IP20 (일반) / IP44 (비상)',
      60,                            // 지하층 60분 이상 NFPC303 §10②
      'MDP-1 (상용 조명회로) / EDP-1 (비상 조명회로)',
      'KDS 31 17 00 / KDS 32 25 10 / NFPC 303',
      'KDS 31 17 00 §4.2.1',
      'NFPC 303 §4, §5, §10②',
      '지하역사: 대형피난구유도등 필수 / 비상전원 60분 이상 내화배선 / 조도기준 KS A 3011'
    ],
    // ─── 승강장 ─────────────────────────────────────────────────────
    [
      'SR-02', '승강장', 'Platform',
      200,
      'TRUE',
      'FALSE',
      '-',
      '대형피난구유도등',
      'TRUE',
      'FALSE',
      'FALSE',
      'FALSE',
      '-',
      '상용 조명·전열용 간선 + 비상용 조명·전열용 간선',
      'HIV 2.5mm² (상용) / FR-8 2.5mm² (비상)',
      'CD전선관 (천장매입)',
      'IP44',
      60,
      'MDP-2 (상용 조명회로) / EDP-2 (비상 조명회로)',
      'KDS 31 17 00 / KDS 32 25 10 / NFPC 303',
      'KDS 31 17 00 §4.2.2',
      'NFPC 303 §4, §10②',
      '승강장 전체 균일조도 확보 / CCTV 전용분기 / 비상전원 60분'
    ],
    // ─── 통로·계단 ──────────────────────────────────────────────────
    [
      'SR-03', '통로·계단', 'Corridor & Stair',
      150,
      'FALSE',
      'TRUE',                        // 통로유도등
      2,                             // 2m 간격
      '복도통로유도등 + 계단통로유도등',
      'FALSE',
      'FALSE',
      'FALSE',
      'FALSE',
      '-',
      '비상용 조명·전열용 간선 (3선식)',
      'FR-8 1.5mm² (유도등 전용)',
      'HFIX관 (내화)',
      'IP44',
      60,
      'EDP-3 (유도등 전용회로)',
      'KDS 31 17 00 / KDS 32 25 10 / NFPC 303',
      '-',
      'NFPC 303 §6①-1(나), §6①-3',
      '지하역사 특례: 복도·통로 중앙 바닥 매립 / 계단참마다 1개 / 보행거리 20m마다 / 3선식 배선 내화배선'
    ],
    // ─── 기계실 ─────────────────────────────────────────────────────
    [
      'SR-04', '기계실', 'Mechanical Room',
      200,
      'FALSE',
      'FALSE',
      '-',
      '-',
      'FALSE',
      'FALSE',
      'TRUE',                        // 방폭등
      'TRUE',                        // 접지 의무
      10,                            // 10Ω 이하
      '방폭전용 조명·전열용 간선',
      'HFIX 2.5mm² (방폭배선)',
      '금속전선관 (폭발위험장소)',
      'IP67 (Ex e IIC 이상)',
      '-',
      'MDP-4 (방폭 전용회로)',
      'KEC 242 / KDS 32 10 11 / KDS 32 25 10',
      'KDS 32 10 11 §4.1.2(2)',
      'KEC 242.2',
      '방폭등급 Ex e IIC T4 이상 / 접지저항 10Ω 이하 / 환기설비 연동 / 폭발위험장소 전기설비 별도 회로'
    ],
    // ─── 역무실 ─────────────────────────────────────────────────────
    [
      'SR-05', '역무실', 'Station Office',
      500,
      'FALSE',
      'FALSE',
      '-',
      '-',
      'FALSE',
      'TRUE',                        // UPS전원
      'FALSE',
      'FALSE',
      '-',
      'UPS 전용간선 + 상용 조명·전열용 간선',
      'HIV 2.5mm² (상용) / CV 6mm² (UPS 간선)',
      'CD전선관 (천장매입)',
      'IP20',
      '-',
      'MDP-5 (상용 조명) / UPS-1 (무정전 전원)',
      'KDS 31 17 00 / KDS 32 20 20 / KDS 32 25 10',
      'KDS 31 17 00 §4.3',
      'KDS 32 20 20 §4.3',
      'UPS 무정전전원장치 필수 / 전산·통신 장비 이중화 전원 / 고조도 작업환경 500lux / 역무원 상주공간'
    ]
  ];

  applyHeader(sh, headers, '#1a73e8');
  sh.getRange(2, 1, data.length, headers.length).setValues(data);
  applyRowColors(sh, data.length, headers.length, '#e8f4fd', '#ffffff');
  sh.autoResizeColumns(1, headers.length);
  Logger.log('✅ space_rules 완료');
}

// ══════════════════════════════════════════════════
//  2. lighting_calc 시트
//     루멘법 조명 계산 (실제 역사 면적 반영)
//     N = (E × A) / (F × U × M)
//     서울교통공사 역사건축정보(2025) 섬식 B2 평균 7,216 m² 기준
// ══════════════════════════════════════════════════
function populateLightingCalc() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName('lighting_calc');
  if (!sh) sh = ss.insertSheet('lighting_calc');
  sh.clearContents();

  const headers = [
    'space_id',           // A
    'space_name_kr',      // B
    'design_lux_E',       // C  설계조도
    'area_m2',            // D  면적 (실제 역사 비율 적용)
    'area_basis',         // E  면적 산출 근거
    'lamp_type',          // F  램프 종류
    'lamp_lumen_F',       // G  1등당 광속(lm)
    'utilization_factor_U', // H 조명률
    'maintenance_factor_M', // I 보수율
    'fixture_count_N',    // J  등기구 수 (계산값)
    'fixture_spacing_m',  // K  등간격(m) 추정
    'ceiling_height_m',   // L  천장고
    'room_index_K',       // M  실지수 K
    'reflectance_ceiling_%', // N 천장 반사율
    'reflectance_wall_%', // O  벽 반사율
    'reflectance_floor_%',// P  바닥 반사율
    'color_temp_K',       // Q  색온도
    'CRI',                // R  연색지수
    'watt_per_fixture_W', // S  등기구 1개 소비전력
    'total_load_W',       // T  총 소비전력
    'power_density_W_m2', // U  전력밀도
    'circuit_count',      // V  회로 수 (20A 기준)
    'regulation_basis'    // W  조도 기준 법령
  ];

  // 실제 역사 면적: 서울교통공사 섬식 B2 평균 7,216 m² 기준
  // 대합실 30%=2165, 승강장 20%=1443, 통로계단 25%=1804, 기계실 8%=577, 역무실 5%=361
  const data = [
    [
      'SR-01', '대합실',
      300,                            // E: lux
      2165,                           // A: m²
      '서울교통공사 역사건축정보(2025) 섬식B2 평균 7,216 m² × 30%',
      'LED 매입 패널라이트 600×600',
      5400,                           // F: lm
      0.60,                           // U
      0.80,                           // M (보수율: LED 0.8)
      '=ROUNDUP((C2*D2)/(G2*H2*I2),0)', // N 수식
      '=ROUND(SQRT(D2/J2),1)',        // 등간격 추정
      4.5,                            // 천장고
      '=ROUND(D2/(L2*4*SQRT(D2)),2)',  // 실지수
      70, 50, 20,                     // 반사율
      4000, 80,                       // 색온도, CRI
      40,                             // W/등
      '=J2*S2',                       // 총 부하
      '=ROUND(T2/D2,1)',              // 전력밀도
      '=ROUNDUP(T2/(220*20*0.8),0)',  // 회로수 (20A, 역률0.8)
      'KDS 31 17 00 §4.2.1 / KS A 3011 대합실 300lux'
    ],
    [
      'SR-02', '승강장',
      200,
      1443,
      '서울교통공사 역사건축정보(2025) 섬식B2 평균 7,216 m² × 20%',
      'LED 매입 패널라이트 600×600',
      5400,
      0.55,
      0.80,
      '=ROUNDUP((C3*D3)/(G3*H3*I3),0)',
      '=ROUND(SQRT(D3/J3),1)',
      3.5,
      '=ROUND(D3/(L3*4*SQRT(D3)),2)',
      70, 50, 20,
      4000, 80,
      40,
      '=J3*S3',
      '=ROUND(T3/D3,1)',
      '=ROUNDUP(T3/(220*20*0.8),0)',
      'KDS 31 17 00 §4.2.2 / KS A 3011 승강장 200lux'
    ],
    [
      'SR-03', '통로·계단',
      150,
      1804,
      '서울교통공사 역사건축정보(2025) 섬식B2 평균 7,216 m² × 25%',
      'LED 다운라이트 Ø150',
      1800,
      0.50,
      0.75,
      '=ROUNDUP((C4*D4)/(G4*H4*I4),0)',
      '=ROUND(SQRT(D4/J4),1)',
      3.0,
      '=ROUND(D4/(L4*4*SQRT(D4)),2)',
      60, 40, 10,
      4000, 80,
      15,
      '=J4*S4',
      '=ROUND(T4/D4,1)',
      '=ROUNDUP(T4/(220*20*0.8),0)',
      'KDS 31 17 00 / NFPC 303 §6 유도등 보행거리 20m마다'
    ],
    [
      'SR-04', '기계실',
      200,
      577,
      '서울교통공사 역사건축정보(2025) 섬식B2 평균 7,216 m² × 8%',
      '방폭형 LED Ex e IIC Ø250',
      3600,
      0.50,
      0.70,
      '=ROUNDUP((C5*D5)/(G5*H5*I5),0)',
      '=ROUND(SQRT(D5/J5),1)',
      3.0,
      '=ROUND(D5/(L5*4*SQRT(D5)),2)',
      30, 30, 10,
      5000, 70,
      30,
      '=J5*S5',
      '=ROUND(T5/D5,1)',
      '=ROUNDUP(T5/(220*20*0.8),0)',
      'KEC 242.2 방폭설비 / KDS 32 10 11 §4.1.2'
    ],
    [
      'SR-05', '역무실',
      500,
      361,
      '서울교통공사 역사건축정보(2025) 섬식B2 평균 7,216 m² × 5%',
      'LED 매입 패널라이트 600×600',
      5400,
      0.65,
      0.80,
      '=ROUNDUP((C6*D6)/(G6*H6*I6),0)',
      '=ROUND(SQRT(D6/J6),1)',
      2.8,
      '=ROUND(D6/(L6*4*SQRT(D6)),2)',
      70, 50, 20,
      5000, 85,
      40,
      '=J6*S6',
      '=ROUND(T6/D6,1)',
      '=ROUNDUP(T6/(220*20*0.8),0)',
      'KDS 31 17 00 §4.3 / KS A 3011 사무공간 500lux'
    ]
  ];

  applyHeader(sh, headers, '#137333');
  sh.getRange(2, 1, data.length, data[0].length).setValues(data);

  // J열 (fixture_count_N) 수식 재입력
  const countFormulas = [
    ['=ROUNDUP((C2*D2)/(G2*H2*I2),0)'],
    ['=ROUNDUP((C3*D3)/(G3*H3*I3),0)'],
    ['=ROUNDUP((C4*D4)/(G4*H4*I4),0)'],
    ['=ROUNDUP((C5*D5)/(G5*H5*I5),0)'],
    ['=ROUNDUP((C6*D6)/(G6*H6*I6),0)']
  ];
  sh.getRange(2, 10, 5, 1).setFormulas(countFormulas);

  // K열 (등간격), M열 (실지수), T열 (총부하), U열 (전력밀도), V열 (회로수)
  sh.getRange(2, 11, 5, 1).setFormulas([
    ['=ROUND(SQRT(D2/J2),1)'], ['=ROUND(SQRT(D3/J3),1)'],
    ['=ROUND(SQRT(D4/J4),1)'], ['=ROUND(SQRT(D5/J5),1)'],
    ['=ROUND(SQRT(D6/J6),1)']
  ]);
  sh.getRange(2, 13, 5, 1).setFormulas([
    ['=ROUND(D2/(L2*4*SQRT(D2)),2)'], ['=ROUND(D3/(L3*4*SQRT(D3)),2)'],
    ['=ROUND(D4/(L4*4*SQRT(D4)),2)'], ['=ROUND(D5/(L5*4*SQRT(D5)),2)'],
    ['=ROUND(D6/(L6*4*SQRT(D6)),2)']
  ]);
  sh.getRange(2, 20, 5, 1).setFormulas([
    ['=J2*S2'], ['=J3*S3'], ['=J4*S4'], ['=J5*S5'], ['=J6*S6']
  ]);
  sh.getRange(2, 21, 5, 1).setFormulas([
    ['=ROUND(T2/D2,1)'], ['=ROUND(T3/D3,1)'], ['=ROUND(T4/D4,1)'],
    ['=ROUND(T5/D5,1)'], ['=ROUND(T6/D6,1)']
  ]);
  sh.getRange(2, 22, 5, 1).setFormulas([
    ['=ROUNDUP(T2/(220*20*0.8),0)'], ['=ROUNDUP(T3/(220*20*0.8),0)'],
    ['=ROUNDUP(T4/(220*20*0.8),0)'], ['=ROUNDUP(T5/(220*20*0.8),0)'],
    ['=ROUNDUP(T6/(220*20*0.8),0)']
  ]);

  applyRowColors(sh, data.length, headers.length, '#e6f4ea', '#ffffff');
  sh.autoResizeColumns(1, headers.length);
  Logger.log('✅ lighting_calc 완료');
}

// ══════════════════════════════════════════════════
//  3. fixture_family 시트
//     Revit Family + 기구 제원 (KDS/KEC 기준)
// ══════════════════════════════════════════════════
function populateFixtureFamily() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName('fixture_family');
  if (!sh) sh = ss.insertSheet('fixture_family');
  sh.clearContents();

  const headers = [
    'family_id',          // A
    'fixture_type_kr',    // B
    'fixture_type_en',    // C
    'revit_family_name',  // D  Revit family 파일명
    'revit_type_name',    // E  Type 이름
    'applicable_space',   // F  적용 공간
    'wattage_W',          // G
    'lumen_output_lm',    // H
    'efficacy_lm_W',      // I  효율
    'voltage_V',          // J
    'ip_rating',          // K
    'explosion_proof',    // L
    'install_method',     // M  설치방법
    'install_height_m',   // N  설치 높이/위치
    'spacing_rule',       // O  배치 규칙
    'dimensions_mm',      // P  기구 치수
    'circuit_type',       // Q  회로 종류
    'wire_type',          // R  사용 전선
    'conduit_type',       // S  전선관
    'emergency_backup_min', // T  비상전원(분)
    'quantity_formula',   // U  수량 산출식
    'dynamo_node',        // V  Dynamo 노드 메모
    'kds_reference',      // W
    'nfpc_reference',     // X
    'notes'               // Y
  ];

  const data = [
    // ── FF-01: LED 패널라이트 (대합실·승강장·역무실) ──────────────
    [
      'FF-01',
      'LED 매입 패널라이트',
      'LED Recessed Panel Light',
      'M_Lighting Fixture - Recessed.rfa',
      'LED Panel 600x600_40W',
      '대합실, 승강장, 역무실',
      40, 5400, 135,
      220,
      'IP20',
      'FALSE',
      '천장 매입 (T-BAR 천장)',
      '천장면 (매입)',
      '루멘법 N=(E×A)/(F×U×M) 산출',
      '595 × 595 × 85',
      '상용 조명·전열용 간선 / HIV 2.5mm²',
      'HIV 2.5mm²',
      'CD전선관 Ø16',
      '-',
      'N = ROUNDUP((E×A)/(5400×U×M), 0)',
      'FamilyInstance.ByPoint → AdaptiveComponent / Space.Boundaries 이용 격자 배치',
      'KDS 31 17 00 §4.2 / KDS 32 25 10 §1.7.2',
      '-',
      'CRI ≥ 80, 색온도 4000K(대합실·승강장) / 5000K(역무실) / 에너지절약 LED 적용'
    ],
    // ── FF-02: 비상용 LED (대합실·승강장) ─────────────────────────
    [
      'FF-02',
      '비상용 LED 조명',
      'Emergency LED Light',
      'M_Emergency Light - Ceiling.rfa',
      'Emergency LED 300x300_20W',
      '대합실, 승강장',
      20, 2000, 100,
      '220V AC / DC 24V',
      'IP44',
      'FALSE',
      '천장 매입 / 노출',
      '바닥 2.0m 이상 (천장 매입 우선)',
      '비상구·피난통로 인접 설치, 개별 공간 균일 배치',
      '295 × 295 × 80',
      '비상용 조명·전열용 간선 / 내화배선 FR-8',
      'FR-8 2.5mm² (내화배선)',
      'HFIX관 (내화전선관)',
      60,
      '비상구 인접 필수 / 공간당 최소 1개 이상',
      'FamilyInstance.ByPoint → 비상구 좌표 기준 오프셋 배치',
      'KDS 31 17 00 §4.5 / KDS 32 20 20',
      'NFPC 303 §10②',
      '지하층 비상전원 60분 이상 / 내화배선 사용 필수 / 자동전환장치 설치'
    ],
    // ── FF-03: 복도통로유도등 (통로) ──────────────────────────────
    [
      'FF-03',
      '복도통로유도등',
      'Corridor Exit Guide Light',
      'M_Exit Light - Corridor.rfa',
      'Corridor Guide_5W_Floor',
      '통로·계단',
      5, 400, 80,
      '220V AC / DC',
      'IP44',
      'FALSE',
      '벽면 부착 / 바닥 매립 (지하역사)',
      '바닥 1.0m 이하 / 지하역사: 복도·통로 중앙 바닥 매립',
      '보행거리 20m마다 1개 / 구부러진 모퉁이 추가',
      '400 × 120 × 30',
      '비상전용 (3선식) 내화배선',
      'FR-8 1.5mm² (3선식)',
      'HFIX관 (내화)',
      60,
      'N = ROUNDUP(통로길이 / 20, 0) + 모퉁이수',
      'Wall.GetParameterValueByName("길이") / 20 → FamilyInstance 등간격 배치',
      'KDS 32 25 10 §1.7.2',
      'NFPC 303 §6①-1(나)(다)',
      '지하역사 특례: 바닥 중앙 매립 (NFPC §6①-1다) / 3선식 항시 점등 / 내화배선'
    ],
    // ── FF-04: 피난구유도등 대형 (대합실·승강장 출입구) ────────────
    [
      'FF-04',
      '대형피난구유도등',
      'Large Exit Sign (Escape Route)',
      'M_Exit Sign - Large.rfa',
      'Exit Sign Large_10W',
      '대합실, 승강장, 통로 출입구',
      10, 800, 80,
      '220V AC / DC',
      'IP44',
      'FALSE',
      '출입구 상단 벽 부착 / 천장 추가',
      '바닥 1.5m 이상 (출입구 인접) / 천장에 수직방향 추가 (§5③)',
      '출입구마다 1개 필수',
      '600 × 200 × 40',
      '비상전용 (3선식) 내화배선',
      'FR-8 1.5mm²',
      'HFIX관',
      60,
      'N = 출입구 수 × 1 (+ 천장 추가분)',
      'Door.GetConnectorManager → 출입구 위치 +1500mm 오프셋 배치',
      '-',
      'NFPC 303 §5②③ / §4(3항 지하역사)',
      '지하역사 필수 대형 / 피난층 방향 천장 수직 추가 설치 필수'
    ],
    // ── FF-05: 계단통로유도등 ──────────────────────────────────────
    [
      'FF-05',
      '계단통로유도등',
      'Stairway Exit Guide Light',
      'M_Exit Light - Stair.rfa',
      'Stair Guide_5W',
      '통로·계단',
      5, 400, 80,
      '220V AC / DC',
      'IP44',
      'FALSE',
      '벽면 부착',
      '바닥 1.0m 이하 / 계단참 위치',
      '각층 계단참마다 1개',
      '300 × 100 × 30',
      '비상전용 (3선식) 내화배선',
      'FR-8 1.5mm²',
      'HFIX관',
      60,
      'N = 계단참 수 × 1',
      'Stair.GetStairLandings → FamilyInstance 배치',
      '-',
      'NFPC 303 §6①-3',
      '경사로 참 또는 계단참마다 / 바닥 1m 이하'
    ],
    // ── FF-06: 방폭형 LED (기계실) ────────────────────────────────
    [
      'FF-06',
      '방폭형 LED 조명',
      'Explosion-Proof LED',
      'M_Lighting Fixture - Explosion Proof.rfa',
      'Ex LED Ø250_30W_IIC',
      '기계실',
      30, 3600, 120,
      220,
      'IP67 (Ex e IIC T4 Gc)',
      'TRUE',
      '천장 직부 / 강관 고정',
      '천장면 직부',
      '루멘법 N=(E×A)/(F×U×M) 산출',
      '250 × 250 × 130',
      '방폭전용 / HFIX 2.5mm²',
      'HFIX 2.5mm²',
      '금속제 강전선관 (후강)',
      '-',
      'N = ROUNDUP((200×577)/(3600×0.5×0.7), 0)',
      'Room.GetBoundingBox → Grid 패턴 / ExPlodProof Tag 부여',
      'KEC 242.2 / KDS 32 10 11 §4.1.2(2)',
      '-',
      '방폭등급 Ex e IIC T4 이상 / 접지저항 10Ω이하 / 산업안전보건기준 제312조 / 금속관 배선 의무'
    ],
    // ── FF-07: CCTV 전용 콘센트 (대합실·승강장) ───────────────────
    [
      'FF-07',
      'CCTV 전용 콘센트',
      'CCTV Power Outlet',
      'M_Power Outlet - CCTV.rfa',
      'CCTV Outlet_IP44',
      '대합실, 승강장',
      '-', '-', '-',
      220,
      'IP44',
      'FALSE',
      '벽면 노출 부착',
      '바닥 0.3~1.5m',
      'CCTV 카메라 설치 위치별 인접 배치',
      '75 × 75 × 45',
      '상용 전열용 간선 / HIV 2.5mm²',
      'HIV 2.5mm²',
      'CD전선관 Ø16',
      '-',
      'N = CCTV 카메라 수',
      'FamilyInstance.ByPoint → CCTV 카메라 위치 기준 -500mm 배치',
      'KDS 31 17 00 / KDS 32 25 10',
      '-',
      'CCTV 전용 분기회로 / 방수형 IP44 / 카메라당 1개'
    ],
    // ── FF-08: UPS 분기 단자함 (역무실) ───────────────────────────
    [
      'FF-08',
      'UPS 분기 단자함',
      'UPS Distribution Terminal Box',
      'M_Electrical Panel - UPS Terminal.rfa',
      'UPS Terminal 300x200',
      '역무실',
      '-', '-', '-',
      220,
      'IP20',
      'FALSE',
      '벽면 매입',
      '바닥 1.2~1.5m',
      '역무실 전산·통신 장비 인접',
      '300 × 200 × 100',
      'UPS 전용간선 / CV 6mm²',
      'CV 6mm²',
      'CD전선관 Ø22',
      '-',
      '역무실 부하 합계 × 수용률 / UPS 용량 산정',
      'Room "역무실" 필터 → FamilyInstance 벽면 배치',
      'KDS 32 20 20 §4.3 / KDS 32 25 10 §1.7.4',
      '-',
      'UPS 이중화 권장 (KDS 32 20 20 §4.3(3)②) / 전압변동 허용범위 준수 / 축전지 충전용량 6~10% 반영'
    ],
    // ── FF-09: 비상콘센트 (공용) ──────────────────────────────────
    [
      'FF-09',
      '비상용 콘센트',
      'Emergency Power Outlet',
      'M_Power Outlet - Emergency.rfa',
      'Emergency Outlet_IP44',
      '대합실, 승강장, 통로',
      '-', '-', '-',
      220,
      'IP44',
      'FALSE',
      '벽면 노출',
      '바닥 0.8~1.5m',
      '소방법 기준 위치 (소방호스 반경 25m)',
      '75 × 75 × 45',
      '비상전용 간선 / FR-8 2.5mm²',
      'FR-8 2.5mm² (내화배선)',
      'HFIX관',
      '-',
      '소방법 기준 산출 (25m 반경)',
      'Space.Area 기반 / 소방법 반경 25m 체크',
      'KDS 32 25 10 §1.7.2',
      '-',
      '비상콘센트 전용회로 / 내화배선 / 표시등 설치'
    ]
  ];

  applyHeader(sh, headers, '#b45309');
  sh.getRange(2, 1, data.length, headers.length).setValues(data);
  applyRowColors(sh, data.length, headers.length, '#fef9c3', '#ffffff');
  sh.autoResizeColumns(1, headers.length);
  Logger.log('✅ fixture_family 완료');
}
