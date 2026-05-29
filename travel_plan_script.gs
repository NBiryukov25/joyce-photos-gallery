/**
 * ════════════════════════════════════════════════════════════════════
 *  BACKWARD ASS TRAVEL PLAN — Google Apps Script Template
 * ════════════════════════════════════════════════════════════════════
 *
 *  HOW TO USE:
 *  1. Open a NEW Google Sheets document (sheets.new)
 *  2. Extensions → Apps Script
 *  3. Delete any existing code and paste this entire file
 *  4. Click the ▶ Run button next to "createTravelPlan"
 *  5. Authorize permissions when prompted (needed to modify the sheet)
 *  6. Return to your spreadsheet — everything is built!
 *
 *  THE "BACKWARD" CONCEPT:
 *  Enter your trip date → the plan works backward to tell you exactly
 *  how much you must save every day / week / month to make it happen.
 *
 *  SHEET ORDER (matches priority):
 *    📋 Dashboard        — goal date, countdown, summary
 *    ✈️  1-Necessary       — FIRST priority: must-have travel costs
 *    🏠  2-Living          — SECOND priority: ongoing life expenses
 *    🎉  3-Optional        — THIRD priority: nice-to-haves
 *
 *  TO RESET / REBUILD: run createTravelPlan again (clears & rebuilds).
 * ════════════════════════════════════════════════════════════════════
 */

// ─── PALETTE ─────────────────────────────────────────────────────────────────
var C = {
  // Dashboard
  DASH_BG:      '#1a1a2e',
  DASH_TEXT:    '#ffffff',
  DASH_ACCENT:  '#e94560',
  DASH_INPUT:   '#16213e',
  DASH_LABEL:   '#0f3460',

  // Priority 1 – Necessary Travel (red / urgent)
  P1_HEAD:      '#7b241c',
  P1_SUBHEAD:   '#c0392b',
  P1_ALT:       '#fdedec',
  P1_WHITE:     '#ffffff',

  // Priority 2 – Living Expenses (navy / stable)
  P2_HEAD:      '#154360',
  P2_SUBHEAD:   '#1a5276',
  P2_ALT:       '#eaf4fb',
  P2_WHITE:     '#ffffff',

  // Priority 3 – Optional Travel (green / aspire)
  P3_HEAD:      '#145a32',
  P3_SUBHEAD:   '#1e8449',
  P3_ALT:       '#eafaf1',
  P3_WHITE:     '#ffffff',

  // Shared
  TOTAL_BG:     '#ecf0f1',
  SECTION_BG:   '#d5d8dc',
  SHORT:        '#c0392b',   // negative / still need to save
  OVER:         '#1e8449',   // positive / ahead of target
  INPUT_YEL:    '#fffde7',   // user-entry cells
  HEADER_TEXT:  '#ffffff',
  DARK_TEXT:    '#1a1a1a',
  MID_TEXT:     '#555555',
};

// ─── FONT SIZES ──────────────────────────────────────────────────────────────
var FS = { TITLE: 18, SECTION: 13, ROW: 11, SMALL: 9 };


// ══════════════════════════════════════════════════════════════════════════════
//  ENTRY POINT — run this to build the entire workbook
// ══════════════════════════════════════════════════════════════════════════════
function createTravelPlan() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ss.setSpreadsheetTimeZone(Session.getScriptTimeZone());

  // Remove all existing sheets except one (can't delete all)
  var sheets = ss.getSheets();
  var keeper = sheets[0];
  for (var i = 1; i < sheets.length; i++) ss.deleteSheet(sheets[i]);
  keeper.setName('_tmp');

  // Build sheets in display order
  var dash  = buildDashboard(ss);
  var cat2  = buildNecessaryTravel(ss);
  var cat1  = buildLivingExpenses(ss);
  var cat3  = buildOptionalTravel(ss);
  ss.deleteSheet(keeper);

  // Set tab order
  ss.setActiveSheet(dash);
  ss.moveActiveSheet(1);
  ss.setActiveSheet(cat2);
  ss.moveActiveSheet(2);
  ss.setActiveSheet(cat1);
  ss.moveActiveSheet(3);
  ss.setActiveSheet(cat3);
  ss.moveActiveSheet(4);

  // Back to dashboard
  ss.setActiveSheet(dash);
  SpreadsheetApp.flush();
  SpreadsheetApp.getUi().alert(
    '✅  Backward Ass Travel Plan is ready!\n\n' +
    'Step 1: Enter your Trip Date in cell B3 of the Dashboard.\n' +
    'Step 2: Fill in yellow cells across all sheets.\n' +
    'Step 3: Watch the math work backward to your savings targets.'
  );
}


// ══════════════════════════════════════════════════════════════════════════════
//  SHEET 1 — DASHBOARD
// ══════════════════════════════════════════════════════════════════════════════
function buildDashboard(ss) {
  var sh = ss.insertSheet('📋 Dashboard');
  sh.setTabColor('#e94560');
  sh.setFrozenRows(1);

  // Column widths
  sh.setColumnWidth(1, 280);  // A – labels
  sh.setColumnWidth(2, 180);  // B – values
  sh.setColumnWidth(3, 30);   // C – spacer
  sh.setColumnWidth(4, 220);  // D – summary labels
  sh.setColumnWidth(5, 160);  // E – summary values

  // ── Row 1: Big Title ──────────────────────────────────────────────
  sh.getRange('A1:E1').merge()
    .setValue('BACKWARD ASS TRAVEL PLAN')
    .setBackground(C.DASH_BG).setFontColor(C.DASH_TEXT)
    .setFontSize(22).setFontWeight('bold')
    .setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(1, 52);

  // ── Section: Goal & Countdown ─────────────────────────────────────
  var goalSection = [
    ['', 'A', 'B'],
    ['TRIP GOAL & COUNTDOWN', null, null],
    ['🎯  Trip / Goal Date',             '',       null],  // B3 = user input
    ['📅  Today',                        '=TODAY()', null],
    ['⏳  Days Until Trip',              '=IF(B3="","—",MAX(0,B3-B4))', null],
    ['📆  Weeks Until Trip',             '=IF(B5="—","—",ROUND(B5/7,1))', null],
    ['🗓️  Months Until Trip',            '=IF(B5="—","—",ROUND(B5/30.44,1))', null],
  ];

  // Row 2 – subsection header
  sh.getRange('A2:B2').merge()
    .setValue('GOAL & COUNTDOWN')
    .setBackground(C.DASH_LABEL).setFontColor(C.DASH_TEXT)
    .setFontSize(FS.SECTION).setFontWeight('bold')
    .setHorizontalAlignment('left');
  sh.setRowHeight(2, 28);

  // Rows 3-7: countdown data
  var cdata = [
    ['🎯  Trip / Goal Date',   '',          '=IF(B3="","",TEXT(B3,"MMMM D, YYYY"))'],
    ['📅  Today',              '=TODAY()',   '=TEXT(B4,"MMMM D, YYYY")'],
    ['⏳  Days Until Trip',    '=IF(B3="","—",MAX(0,B3-B4))', '=IF(B5="—","enter date above →","days to go")'],
    ['📆  Weeks Until Trip',   '=IF(B5="—","—",ROUND(B5/7,1))', ''],
    ['🗓️  Months Until Trip',  '=IF(B5="—","—",ROUND(B5/30.44,1))', ''],
  ];
  for (var r = 0; r < cdata.length; r++) {
    var row = r + 3;
    sh.getRange(row, 1).setValue(cdata[r][0])
      .setBackground(C.DASH_INPUT).setFontColor(C.DASH_TEXT)
      .setFontSize(FS.ROW).setFontWeight('bold')
      .setHorizontalAlignment('left');
    sh.getRange(row, 2).setValue(cdata[r][1])
      .setBackground(r === 0 ? C.INPUT_YEL : C.DASH_INPUT)
      .setFontColor(r === 0 ? C.DARK_TEXT : C.DASH_ACCENT)
      .setFontSize(r === 0 ? 13 : FS.ROW).setFontWeight('bold')
      .setHorizontalAlignment('center');
    if (cdata[r][2]) {
      sh.getRange(row, 3).setValue(cdata[r][2])
        .setFontColor(C.MID_TEXT).setFontSize(FS.SMALL)
        .setBackground(C.DASH_BG);
    }
    sh.setRowHeight(row, 26);
  }
  // Format B3 as date
  sh.getRange('B3').setNumberFormat('MM/DD/YYYY');
  sh.getRange('B5').setNumberFormat('0');
  sh.getRange('B6:B7').setNumberFormat('0.0');

  // ── Row 8: spacer ────────────────────────────────────────────────
  sh.getRange('A8:E8').setBackground(C.DASH_BG);
  sh.setRowHeight(8, 10);

  // ── Row 9: Priority Guide header ─────────────────────────────────
  sh.getRange('A9:E9').merge()
    .setValue('PRIORITY ORDER  —  Fill sheets in this sequence')
    .setBackground(C.DASH_LABEL).setFontColor(C.DASH_TEXT)
    .setFontSize(FS.SECTION).setFontWeight('bold')
    .setHorizontalAlignment('center');
  sh.setRowHeight(9, 28);

  // Rows 10-12: priority cards
  var priorities = [
    ['#1 — FIRST PRIORITY',    '✈️  Necessary Travel',  'Must-have trip costs. Fund these first.',   C.P1_SUBHEAD],
    ['#2 — SECOND PRIORITY',   '🏠  Living Expenses',   'Keep the lights on. Cover before extras.',  C.P2_SUBHEAD],
    ['#3 — THIRD PRIORITY',    '🎉  Optional Travel',   'Nice-to-haves once #1 & #2 are covered.',  C.P3_SUBHEAD],
  ];
  for (var p = 0; p < priorities.length; p++) {
    var pr = priorities[p];
    var row = p + 10;
    sh.getRange(row, 1).setValue(pr[0])
      .setBackground(pr[3]).setFontColor('#ffffff')
      .setFontSize(12).setFontWeight('bold').setHorizontalAlignment('center');
    sh.getRange(row, 2).setValue(pr[1])
      .setBackground(pr[3]).setFontColor('#ffffff')
      .setFontSize(FS.ROW).setFontWeight('bold').setHorizontalAlignment('center');
    sh.getRange(row, 3).setValue(pr[2])
      .setBackground(pr[3]).setFontColor('#ffffffcc')
      .setFontSize(FS.SMALL).setHorizontalAlignment('left');
    sh.setRowHeight(row, 32);
  }

  // ── Row 13: spacer ───────────────────────────────────────────────
  sh.setRowHeight(13, 10);

  // ── Rows 14+: Summary totals ──────────────────────────────────────
  sh.getRange('A14:E14').merge()
    .setValue('MASTER SUMMARY')
    .setBackground(C.DASH_LABEL).setFontColor(C.DASH_TEXT)
    .setFontSize(FS.SECTION).setFontWeight('bold')
    .setHorizontalAlignment('center');
  sh.setRowHeight(14, 28);

  // Summary rows referencing other sheets
  var sumRows = [
    // label, sheet ref formula, note
    ['✈️  Necessary Travel — Total Needed',
     "='1-Necessary Travel'!C20",
     "='1-Necessary Travel'!D20",
     C.P1_SUBHEAD],
    ['✈️  Necessary Travel — Total Saved',
     "='1-Necessary Travel'!B20",
     '',
     C.P1_SUBHEAD],
    ['✈️  Necessary Travel — Still Short / Over',
     "='1-Necessary Travel'!D20",
     '',
     C.P1_SUBHEAD],
    ['✈️  Daily Savings Needed (Necessary)',
     "='1-Necessary Travel'!E20",
     '',
     C.P1_SUBHEAD],
    ['', '', '', '#cccccc'],
    ['🏠  Living — Total Monthly',
     "='2-Living Expenses'!B35",
     '',
     C.P2_SUBHEAD],
    ['🏠  Living — Total Weekly',
     "='2-Living Expenses'!C35",
     '',
     C.P2_SUBHEAD],
    ['🏠  Living — Total Daily',
     "='2-Living Expenses'!D35",
     '',
     C.P2_SUBHEAD],
    ['', '', '', '#cccccc'],
    ['🎉  Optional Travel — Total Needed',
     "='3-Optional Travel'!C14",
     '',
     C.P3_SUBHEAD],
    ['🎉  Optional Travel — Still Short / Over',
     "='3-Optional Travel'!D14",
     '',
     C.P3_SUBHEAD],
  ];

  for (var s = 0; s < sumRows.length; s++) {
    var sr = sumRows[s];
    var row = s + 15;
    if (sr[0] === '') {
      sh.getRange(row, 1, 1, 5).setBackground('#2c2c4a');
      sh.setRowHeight(row, 8);
      continue;
    }
    sh.getRange(row, 1).setValue(sr[0])
      .setBackground(C.DASH_INPUT).setFontColor('#ffffff')
      .setFontSize(FS.ROW).setFontWeight('bold');
    sh.getRange(row, 2).setValue(sr[1])
      .setBackground(sr[3]).setFontColor('#ffffff')
      .setFontSize(FS.ROW).setFontWeight('bold')
      .setHorizontalAlignment('center')
      .setNumberFormat('$#,##0.00');
    sh.setRowHeight(row, 26);
  }

  // Conditional formatting on summary: red if negative, green if positive
  var shortRange = sh.getRange('B15:B26');
  var rulesArr = sh.getConditionalFormatRules();
  var negRule = SpreadsheetApp.newConditionalFormatRule()
    .whenNumberLessThan(0).setFontColor(C.SHORT)
    .setRanges([shortRange]).build();
  var posRule = SpreadsheetApp.newConditionalFormatRule()
    .whenNumberGreaterThan(0).setFontColor(C.OVER)
    .setRanges([shortRange]).build();
  rulesArr.push(negRule, posRule);
  sh.setConditionalFormatRules(rulesArr);

  // Hide grid lines for dashboard aesthetic
  sh.setHiddenGridlines(true);

  return sh;
}


// ══════════════════════════════════════════════════════════════════════════════
//  SHEET 2 — CATEGORY 2: NECESSARY TRAVEL (First Priority)
// ══════════════════════════════════════════════════════════════════════════════
function buildNecessaryTravel(ss) {
  var sh = ss.insertSheet('1-Necessary Travel');
  sh.setTabColor(C.P1_SUBHEAD);
  sh.setFrozenRows(4);

  // Column widths
  sh.setColumnWidth(1, 260);  // A – Item
  sh.setColumnWidth(2, 140);  // B – Amount Paid/Saved
  sh.setColumnWidth(3, 150);  // C – Amount Necessary
  sh.setColumnWidth(4, 160);  // D – Short(-) / Over(+)
  sh.setColumnWidth(5, 130);  // E – Daily Save Needed
  sh.setColumnWidth(6, 130);  // F – Weekly Save Needed
  sh.setColumnWidth(7, 130);  // G – Monthly Save Needed
  sh.setColumnWidth(8, 200);  // H – Notes

  // ── Row 1: Title ─────────────────────────────────────────────────
  sh.getRange('A1:H1').merge()
    .setValue('✈️  CATEGORY 2 — NECESSARY TRAVEL  (FIRST PRIORITY)')
    .setBackground(C.P1_HEAD).setFontColor('#ffffff')
    .setFontSize(FS.TITLE).setFontWeight('bold')
    .setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(1, 44);

  // ── Row 2: Countdown reference ───────────────────────────────────
  sh.getRange('A2').setValue('Days Until Trip →')
    .setBackground(C.P1_SUBHEAD).setFontColor('#ffffff')
    .setFontWeight('bold').setFontSize(FS.ROW);
  sh.getRange('B2').setValue("='📋 Dashboard'!B5")
    .setBackground(C.INPUT_YEL).setFontColor(C.DARK_TEXT)
    .setFontWeight('bold').setFontSize(13).setHorizontalAlignment('center')
    .setNumberFormat('0');
  sh.getRange('C2').setValue('Weeks →')
    .setBackground(C.P1_SUBHEAD).setFontColor('#ffffff')
    .setFontWeight('bold').setFontSize(FS.ROW).setHorizontalAlignment('right');
  sh.getRange('D2').setValue("='📋 Dashboard'!B6")
    .setBackground(C.INPUT_YEL).setFontColor(C.DARK_TEXT)
    .setFontWeight('bold').setFontSize(13).setHorizontalAlignment('center')
    .setNumberFormat('0.0');
  sh.getRange('E2').setValue('Months →')
    .setBackground(C.P1_SUBHEAD).setFontColor('#ffffff')
    .setFontWeight('bold').setFontSize(FS.ROW).setHorizontalAlignment('right');
  sh.getRange('F2').setValue("='📋 Dashboard'!B7")
    .setBackground(C.INPUT_YEL).setFontColor(C.DARK_TEXT)
    .setFontWeight('bold').setFontSize(13).setHorizontalAlignment('center')
    .setNumberFormat('0.0');
  sh.getRange('G2:H2').setBackground(C.P1_HEAD);
  sh.setRowHeight(2, 28);

  // ── Row 3: How-to note ───────────────────────────────────────────
  sh.getRange('A3:H3').merge()
    .setValue('💡  Enter amounts in YELLOW cells. "Short" = you still need to save that much. "Over" = you\'re ahead of target.')
    .setBackground('#fff3cd').setFontColor('#856404')
    .setFontSize(FS.SMALL).setFontStyle('italic')
    .setHorizontalAlignment('left');
  sh.setRowHeight(3, 22);

  // ── Row 4: Column headers ─────────────────────────────────────────
  var headers4 = ['TRAVEL EXPENSE', 'PAID / SAVED', 'NEEDED (TOTAL)', 'SHORT(−) / OVER(+)', 'SAVE / DAY', 'SAVE / WEEK', 'SAVE / MONTH', 'NOTES'];
  var hdr = sh.getRange(4, 1, 1, 8);
  hdr.setValues([headers4])
    .setBackground(C.P1_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold')
    .setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(4, 30);

  // ── Data rows (5–19): travel line items ───────────────────────────
  var items = [
    'Airfare',
    'Lodging — Hotel',
    'Lodging — Airbnb',
    'Lodging — Food',
    'Airport Food',
    'Transportation — Car Rental',
    'Transportation — Fuel',
    'Transportation — Tolls & Parking',
    '',   // blank spacer
    '',
    '',
    '',
    '',
    '',
    '',   // 15 data rows total (rows 5-19)
  ];

  for (var i = 0; i < 15; i++) {
    var row = i + 5;
    var bg  = (i % 2 === 0) ? C.P1_WHITE : C.P1_ALT;

    // A – item label
    sh.getRange(row, 1).setValue(items[i] || '')
      .setBackground(bg).setFontColor(C.DARK_TEXT)
      .setFontSize(FS.ROW);

    // B – Amount Paid/Saved (user enters)
    sh.getRange(row, 2)
      .setBackground(C.INPUT_YEL).setNumberFormat('$#,##0.00');

    // C – Amount Necessary (user enters)
    sh.getRange(row, 3)
      .setBackground(C.INPUT_YEL).setNumberFormat('$#,##0.00');

    // D – Short / Over = C - B  (negative = short, positive = over)
    sh.getRange(row, 4)
      .setValue('=IF(OR(C' + row + '="",C' + row + '=0),"",C' + row + '-B' + row + ')')
      .setBackground(bg).setNumberFormat('$#,##0.00')
      .setFontWeight('bold');

    // E – Daily save needed (only when short)
    sh.getRange(row, 5)
      .setValue('=IF(OR(D' + row + '="",D' + row + '>=0,$B$2="—",$B$2=0),"",ABS(D' + row + ')/$B$2)')
      .setBackground(bg).setNumberFormat('$#,##0.00');

    // F – Weekly save needed
    sh.getRange(row, 6)
      .setValue('=IF(E' + row + '="","",E' + row + '*7)')
      .setBackground(bg).setNumberFormat('$#,##0.00');

    // G – Monthly save needed
    sh.getRange(row, 7)
      .setValue('=IF(E' + row + '="","",E' + row + '*30.44)')
      .setBackground(bg).setNumberFormat('$#,##0.00');

    // H – Notes (user enters)
    sh.getRange(row, 8)
      .setBackground(bg).setFontColor(C.MID_TEXT)
      .setFontSize(FS.SMALL).setFontStyle('italic');

    sh.setRowHeight(row, 24);
  }

  // ── Row 20: TOTALS ────────────────────────────────────────────────
  var totRow = 20;
  sh.getRange(totRow, 1).setValue('TOTAL')
    .setBackground(C.P1_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold');
  sh.getRange(totRow, 2)  // total saved
    .setValue('=SUM(B5:B19)')
    .setBackground(C.P1_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(totRow, 3)  // total needed
    .setValue('=SUM(C5:C19)')
    .setBackground(C.P1_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(totRow, 4)  // total short/over
    .setValue('=SUM(D5:D19)')
    .setBackground(C.P1_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(totRow, 5)  // total daily save needed
    .setValue('=IFERROR(IF($B$2="—",0,ABS(MIN(D5:D19,0))*COUNTIF(D5:D19,"<0")/$B$2),"")')
    .setBackground(C.P1_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(totRow, 5)
    .setValue('=IFERROR(IF(OR($B$2="—",$B$2=0),"",ABS(SUM(IF(D5:D19<0,D5:D19,0)))/$B$2),"")')
    .setBackground(C.P1_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  // Fix E20 with proper array-safe formula
  sh.getRange(totRow, 5)
    .setValue('=IFERROR(SUMIF(D5:D19,"<0",D5:D19)*-1/IF(OR($B$2="—",$B$2=0),1,$B$2),"")')
    .setBackground(C.P1_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(totRow, 6)
    .setValue('=IF(E' + totRow + '="","",E' + totRow + '*7)')
    .setBackground(C.P1_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(totRow, 7)
    .setValue('=IF(E' + totRow + '="","",E' + totRow + '*30.44)')
    .setBackground(C.P1_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(totRow, 8).setBackground(C.P1_SUBHEAD);
  sh.setRowHeight(totRow, 30);

  // ── Conditional formatting: D column Short=red, Over=green ───────
  var dRange = sh.getRange('D5:D19');
  var rules = [];
  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberLessThan(0).setFontColor(C.SHORT).setBackground('#fdecea')
      .setRanges([dRange]).build()
  );
  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberGreaterThan(0).setFontColor(C.OVER).setBackground('#eafaf1')
      .setRanges([dRange]).build()
  );
  sh.setConditionalFormatRules(rules);

  return sh;
}


// ══════════════════════════════════════════════════════════════════════════════
//  SHEET 3 — CATEGORY 1: LIVING EXPENSES (Second Priority)
// ══════════════════════════════════════════════════════════════════════════════
function buildLivingExpenses(ss) {
  var sh = ss.insertSheet('2-Living Expenses');
  sh.setTabColor(C.P2_SUBHEAD);
  sh.setFrozenRows(4);

  // Column widths
  sh.setColumnWidth(1, 260);  // A – Category / Item
  sh.setColumnWidth(2, 150);  // B – Monthly
  sh.setColumnWidth(3, 130);  // C – Weekly  (calculated)
  sh.setColumnWidth(4, 120);  // D – Daily   (calculated)
  sh.setColumnWidth(5, 200);  // E – Notes

  // ── Row 1: Title ─────────────────────────────────────────────────
  sh.getRange('A1:E1').merge()
    .setValue('🏠  CATEGORY 1 — LIVING EXPENSES  (SECOND PRIORITY)')
    .setBackground(C.P2_HEAD).setFontColor('#ffffff')
    .setFontSize(FS.TITLE).setFontWeight('bold')
    .setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(1, 44);

  // ── Row 2: How-to note ───────────────────────────────────────────
  sh.getRange('A2:E2').merge()
    .setValue('💡  Enter your MONTHLY amount in the yellow column. Weekly and Daily are calculated automatically.')
    .setBackground('#fff3cd').setFontColor('#856404')
    .setFontSize(FS.SMALL).setFontStyle('italic');
  sh.setRowHeight(2, 22);

  // ── Row 3: Conversion note ───────────────────────────────────────
  sh.getRange('A3:E3').merge()
    .setValue('Weekly = Monthly × (12/52)  |  Daily = Monthly ÷ 30.44  |  These show the true daily cost of your lifestyle.')
    .setBackground('#eaf4fb').setFontColor('#1a5276')
    .setFontSize(FS.SMALL).setFontStyle('italic');
  sh.setRowHeight(3, 20);

  // ── Row 4: Column headers ─────────────────────────────────────────
  var hdrs = ['EXPENSE CATEGORY', 'MONTHLY  (enter here)', 'WEEKLY  (auto)', 'DAILY  (auto)', 'NOTES'];
  sh.getRange(4, 1, 1, 5).setValues([hdrs])
    .setBackground(C.P2_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold')
    .setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(4, 30);

  // ── Helper: write a section header ───────────────────────────────
  function sectionHeader(row, label) {
    sh.getRange(row, 1, 1, 5).merge()
      .setValue(label)
      .setBackground(C.P2_HEAD).setFontColor('#ffffff')
      .setFontSize(FS.SECTION).setFontWeight('bold')
      .setHorizontalAlignment('left');
    sh.setRowHeight(row, 26);
    return row;
  }

  // ── Helper: write a data row ──────────────────────────────────────
  function dataRow(row, label, alt) {
    var bg = alt ? C.P2_ALT : C.P2_WHITE;
    sh.getRange(row, 1).setValue(label)
      .setBackground(bg).setFontColor(C.DARK_TEXT).setFontSize(FS.ROW);
    sh.getRange(row, 2)  // Monthly – user enters
      .setBackground(C.INPUT_YEL).setNumberFormat('$#,##0.00');
    sh.getRange(row, 3)  // Weekly
      .setValue('=IF(B' + row + '="","",B' + row + '*(12/52))')
      .setBackground(bg).setFontColor(C.MID_TEXT)
      .setNumberFormat('$#,##0.00').setFontStyle('italic');
    sh.getRange(row, 4)  // Daily
      .setValue('=IF(B' + row + '="","",B' + row + '/30.44)')
      .setBackground(bg).setFontColor(C.MID_TEXT)
      .setNumberFormat('$#,##0.00').setFontStyle('italic');
    sh.getRange(row, 5)  // Notes
      .setBackground(bg).setFontColor(C.MID_TEXT)
      .setFontSize(FS.SMALL).setFontStyle('italic');
    sh.setRowHeight(row, 24);
    return row;
  }

  // ── Helper: subtotal row ──────────────────────────────────────────
  function subtotalRow(row, startRow, endRow, label) {
    var lbl = label || 'SUBTOTAL';
    sh.getRange(row, 1).setValue(lbl)
      .setBackground(C.SECTION_BG).setFontColor(C.DARK_TEXT)
      .setFontSize(FS.ROW).setFontWeight('bold');
    sh.getRange(row, 2)
      .setValue('=SUM(B' + startRow + ':B' + endRow + ')')
      .setBackground(C.SECTION_BG).setFontColor(C.DARK_TEXT)
      .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00');
    sh.getRange(row, 3)
      .setValue('=SUM(C' + startRow + ':C' + endRow + ')')
      .setBackground(C.SECTION_BG).setFontColor(C.DARK_TEXT)
      .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00');
    sh.getRange(row, 4)
      .setValue('=SUM(D' + startRow + ':D' + endRow + ')')
      .setBackground(C.SECTION_BG).setFontColor(C.DARK_TEXT)
      .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00');
    sh.getRange(row, 5).setBackground(C.SECTION_BG);
    sh.setRowHeight(row, 26);
    return row;
  }

  // ── SUBSCRIPTIONS SECTION (rows 5-15) ────────────────────────────
  sectionHeader(5, '📱  SUBSCRIPTIONS  (list each service below)');
  var subItems = [
    'Subscription 1',
    'Subscription 2',
    'Subscription 3',
    'Subscription 4',
    'Subscription 5',
    'Subscription 6',
    'Subscription 7',
    'Subscription 8',
  ];
  for (var s = 0; s < subItems.length; s++) {
    dataRow(s + 6, subItems[s], s % 2 === 0);
  }
  subtotalRow(14, 6, 13, 'Subscriptions Subtotal');

  // ── HOUSING & TRANSPORTATION (rows 15-22) ────────────────────────
  sectionHeader(15, '🏠  HOUSING & TRANSPORTATION');
  var htItems = ['Rent', 'Renters Insurance', 'Car Payment', 'Car Insurance', 'Phone'];
  for (var h = 0; h < htItems.length; h++) {
    dataRow(h + 16, htItems[h], h % 2 === 0);
  }
  subtotalRow(21, 16, 20, 'Housing & Transportation Subtotal');

  // ── HEALTH (rows 22-26) ──────────────────────────────────────────
  sectionHeader(22, '💊  HEALTH & MEDICAL');
  var healthItems = ['Prescription Medication', 'Doctor Bills'];
  for (var m = 0; m < healthItems.length; m++) {
    dataRow(m + 23, healthItems[m], m % 2 === 0);
  }
  subtotalRow(25, 23, 24, 'Health Subtotal');

  // ── OBLIGATIONS (rows 26-31) ─────────────────────────────────────
  sectionHeader(26, '⚖️  FINANCIAL OBLIGATIONS');
  var obligItems = ['Child Support', 'State Taxes Owed', 'Gifts'];
  for (var o = 0; o < obligItems.length; o++) {
    dataRow(o + 27, obligItems[o], o % 2 === 0);
  }
  subtotalRow(30, 27, 29, 'Obligations Subtotal');

  // ── EXTRA ROWS (31-34) ───────────────────────────────────────────
  sectionHeader(31, '➕  OTHER LIVING EXPENSES');
  dataRow(32, 'Other 1', false);
  dataRow(33, 'Other 2', true);
  dataRow(34, 'Other 3', false);

  // ── Row 35: GRAND TOTAL ──────────────────────────────────────────
  sh.getRange(35, 1).setValue('💰  GRAND TOTAL — ALL LIVING EXPENSES')
    .setBackground(C.P2_HEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold');
  var totalRefs = [14, 21, 25, 30];  // subtotal rows to sum
  var bTotalFormula = '=' + totalRefs.map(function(r){ return 'B'+r; }).join('+') + '+SUM(B32:B34)';
  var cTotalFormula = '=' + totalRefs.map(function(r){ return 'C'+r; }).join('+') + '+SUM(C32:C34)';
  var dTotalFormula = '=' + totalRefs.map(function(r){ return 'D'+r; }).join('+') + '+SUM(D32:D34)';
  sh.getRange(35, 2).setValue(bTotalFormula)
    .setBackground(C.P2_HEAD).setFontColor('#ffffff')
    .setFontSize(13).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(35, 3).setValue(cTotalFormula)
    .setBackground(C.P2_HEAD).setFontColor('#ffffff')
    .setFontSize(13).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(35, 4).setValue(dTotalFormula)
    .setBackground(C.P2_HEAD).setFontColor('#ffffff')
    .setFontSize(13).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(35, 5).setBackground(C.P2_HEAD);
  sh.setRowHeight(35, 34);

  return sh;
}


// ══════════════════════════════════════════════════════════════════════════════
//  SHEET 4 — CATEGORY 3: OPTIONAL TRAVEL (Third Priority)
// ══════════════════════════════════════════════════════════════════════════════
function buildOptionalTravel(ss) {
  var sh = ss.insertSheet('3-Optional Travel');
  sh.setTabColor(C.P3_SUBHEAD);
  sh.setFrozenRows(4);

  // Column widths
  sh.setColumnWidth(1, 260);
  sh.setColumnWidth(2, 140);
  sh.setColumnWidth(3, 150);
  sh.setColumnWidth(4, 160);
  sh.setColumnWidth(5, 130);
  sh.setColumnWidth(6, 130);
  sh.setColumnWidth(7, 130);
  sh.setColumnWidth(8, 200);

  // ── Row 1: Title ─────────────────────────────────────────────────
  sh.getRange('A1:H1').merge()
    .setValue('🎉  CATEGORY 3 — OPTIONAL TRAVEL  (THIRD PRIORITY)')
    .setBackground(C.P3_HEAD).setFontColor('#ffffff')
    .setFontSize(FS.TITLE).setFontWeight('bold')
    .setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(1, 44);

  // ── Row 2: Countdown reference ───────────────────────────────────
  sh.getRange('A2').setValue('Days Until Trip →')
    .setBackground(C.P3_SUBHEAD).setFontColor('#ffffff')
    .setFontWeight('bold').setFontSize(FS.ROW);
  sh.getRange('B2').setValue("='📋 Dashboard'!B5")
    .setBackground(C.INPUT_YEL).setFontColor(C.DARK_TEXT)
    .setFontWeight('bold').setFontSize(13).setHorizontalAlignment('center')
    .setNumberFormat('0');
  sh.getRange('C2').setValue('Weeks →')
    .setBackground(C.P3_SUBHEAD).setFontColor('#ffffff').setHorizontalAlignment('right');
  sh.getRange('D2').setValue("='📋 Dashboard'!B6")
    .setBackground(C.INPUT_YEL).setFontColor(C.DARK_TEXT)
    .setFontWeight('bold').setFontSize(13).setHorizontalAlignment('center')
    .setNumberFormat('0.0');
  sh.getRange('E2:H2').setBackground(C.P3_HEAD);
  sh.setRowHeight(2, 28);

  // ── Row 3: How-to note ───────────────────────────────────────────
  sh.getRange('A3:H3').merge()
    .setValue('💡  Fund these ONLY after Category 2 (Necessary Travel) and Category 1 (Living) are fully covered.')
    .setBackground('#d5f5e3').setFontColor('#145a32')
    .setFontSize(FS.SMALL).setFontStyle('italic');
  sh.setRowHeight(3, 22);

  // ── Row 4: Column headers ─────────────────────────────────────────
  var headers4 = ['OPTIONAL EXPENSE', 'PAID / SAVED', 'WOULD LIKE TO SPEND', 'SHORT(−) / OVER(+)', 'SAVE / DAY', 'SAVE / WEEK', 'SAVE / MONTH', 'NOTES'];
  sh.getRange(4, 1, 1, 8).setValues([headers4])
    .setBackground(C.P3_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold')
    .setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(4, 30);

  // ── Data rows 5-13 ────────────────────────────────────────────────
  var items = [
    'Restaurants & Dining Out',
    'Airport Food',
    'Transportation — Fuel',
    'Transportation — Tolls & Parking',
    'Sightseeing & Attractions',
    'Miscellaneous / Souvenirs',
    '',
    '',
    '',
  ];

  for (var i = 0; i < items.length; i++) {
    var row = i + 5;
    var bg  = (i % 2 === 0) ? C.P3_WHITE : C.P3_ALT;

    sh.getRange(row, 1).setValue(items[i] || '')
      .setBackground(bg).setFontColor(C.DARK_TEXT).setFontSize(FS.ROW);
    sh.getRange(row, 2).setBackground(C.INPUT_YEL).setNumberFormat('$#,##0.00');
    sh.getRange(row, 3).setBackground(C.INPUT_YEL).setNumberFormat('$#,##0.00');
    sh.getRange(row, 4)
      .setValue('=IF(OR(C' + row + '="",C' + row + '=0),"",C' + row + '-B' + row + ')')
      .setBackground(bg).setNumberFormat('$#,##0.00').setFontWeight('bold');
    sh.getRange(row, 5)
      .setValue('=IF(OR(D' + row + '="",D' + row + '>=0,$B$2="—",$B$2=0),"",ABS(D' + row + ')/$B$2)')
      .setBackground(bg).setNumberFormat('$#,##0.00');
    sh.getRange(row, 6)
      .setValue('=IF(E' + row + '="","",E' + row + '*7)')
      .setBackground(bg).setNumberFormat('$#,##0.00');
    sh.getRange(row, 7)
      .setValue('=IF(E' + row + '="","",E' + row + '*30.44)')
      .setBackground(bg).setNumberFormat('$#,##0.00');
    sh.getRange(row, 8).setBackground(bg).setFontSize(FS.SMALL).setFontStyle('italic');
    sh.setRowHeight(row, 24);
  }

  // ── Row 14: TOTALS ────────────────────────────────────────────────
  var totRow = 14;
  sh.getRange(totRow, 1).setValue('TOTAL')
    .setBackground(C.P3_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold');
  sh.getRange(totRow, 2).setValue('=SUM(B5:B13)')
    .setBackground(C.P3_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(totRow, 3).setValue('=SUM(C5:C13)')
    .setBackground(C.P3_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(totRow, 4).setValue('=SUM(D5:D13)')
    .setBackground(C.P3_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(totRow, 5)
    .setValue('=IFERROR(SUMIF(D5:D13,"<0",D5:D13)*-1/IF(OR($B$2="—",$B$2=0),1,$B$2),"")')
    .setBackground(C.P3_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(totRow, 6)
    .setValue('=IF(E' + totRow + '="","",E' + totRow + '*7)')
    .setBackground(C.P3_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(totRow, 7)
    .setValue('=IF(E' + totRow + '="","",E' + totRow + '*30.44)')
    .setBackground(C.P3_SUBHEAD).setFontColor('#ffffff')
    .setFontSize(FS.ROW).setFontWeight('bold').setNumberFormat('$#,##0.00').setHorizontalAlignment('center');
  sh.getRange(totRow, 8).setBackground(C.P3_SUBHEAD);
  sh.setRowHeight(totRow, 30);

  // ── Conditional formatting on D column ───────────────────────────
  var dRange = sh.getRange('D5:D13');
  var rules = [];
  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberLessThan(0).setFontColor(C.SHORT).setBackground('#fdecea')
      .setRanges([dRange]).build()
  );
  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberGreaterThan(0).setFontColor(C.OVER).setBackground('#eafaf1')
      .setRanges([dRange]).build()
  );
  sh.setConditionalFormatRules(rules);

  return sh;
}


// ══════════════════════════════════════════════════════════════════════════════
//  MACRO: Quick-update a single expense from a prompt
// ══════════════════════════════════════════════════════════════════════════════
function updateExpense() {
  var ui = SpreadsheetApp.getUi();
  var sheet = SpreadsheetApp.getActiveSheet();
  var cell  = sheet.getActiveCell();
  if (!cell) {
    ui.alert('Select a yellow (input) cell first, then run this macro.');
    return;
  }
  var current = cell.getValue();
  var resp = ui.prompt(
    'Update Expense',
    'Cell: ' + cell.getA1Notation() + '   Current: ' + (current || '(empty)') + '\n\nEnter new amount (numbers only):',
    ui.ButtonSet.OK_CANCEL
  );
  if (resp.getSelectedButton() !== ui.Button.OK) return;
  var val = parseFloat(resp.getResponseText().replace(/[$,]/g, ''));
  if (isNaN(val)) { ui.alert('Invalid number. No change made.'); return; }
  cell.setValue(val);
  SpreadsheetApp.flush();
  ui.alert('✅  Updated to $' + val.toFixed(2));
}


// ══════════════════════════════════════════════════════════════════════════════
//  MACRO: Set / update the trip goal date
// ══════════════════════════════════════════════════════════════════════════════
function setGoalDate() {
  var ui = SpreadsheetApp.getUi();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var dash;
  try { dash = ss.getSheetByName('📋 Dashboard'); }
  catch(e) { dash = null; }
  if (!dash) { ui.alert('Dashboard sheet not found. Run createTravelPlan first.'); return; }

  var current = dash.getRange('B3').getValue();
  var currentStr = current ? Utilities.formatDate(new Date(current), Session.getScriptTimeZone(), 'MM/dd/yyyy') : '(not set)';

  var resp = ui.prompt(
    'Set Trip Goal Date',
    'Current date: ' + currentStr + '\n\nEnter your trip date (MM/DD/YYYY):',
    ui.ButtonSet.OK_CANCEL
  );
  if (resp.getSelectedButton() !== ui.Button.OK) return;

  var raw = resp.getResponseText().trim();
  var parsed = new Date(raw);
  if (isNaN(parsed.getTime())) {
    ui.alert('Could not parse "' + raw + '" as a date. Use MM/DD/YYYY format.');
    return;
  }
  dash.getRange('B3').setValue(parsed);
  SpreadsheetApp.flush();

  var days = Math.max(0, Math.floor((parsed - new Date()) / 86400000));
  ui.alert('✅  Goal date set to ' + Utilities.formatDate(parsed, Session.getScriptTimeZone(), 'MMMM d, yyyy') +
           '\n' + days + ' days to go!');
}


// ══════════════════════════════════════════════════════════════════════════════
//  MACRO: Highlight all input cells (yellow) — helps users find where to type
// ══════════════════════════════════════════════════════════════════════════════
function highlightInputCells() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ui = SpreadsheetApp.getUi();
  var sheetNames = ['1-Necessary Travel', '2-Living Expenses', '3-Optional Travel'];
  var count = 0;
  sheetNames.forEach(function(name) {
    var sh = ss.getSheetByName(name);
    if (!sh) return;
    var range = sh.getDataRange();
    var bgs   = range.getBackgrounds();
    var vals  = range.getValues();
    for (var r = 0; r < bgs.length; r++) {
      for (var c = 0; c < bgs[r].length; c++) {
        if (bgs[r][c].toLowerCase() === '#fffde7' && (vals[r][c] === '' || vals[r][c] === 0)) {
          count++;
        }
      }
    }
  });
  ui.alert('📝  There are ' + count + ' empty input cells remaining across all travel/living sheets.\n\nYellow cells = your input. All others are auto-calculated.');
}


// ══════════════════════════════════════════════════════════════════════════════
//  MACRO: Print summary to a new tab (snapshot)
// ══════════════════════════════════════════════════════════════════════════════
function snapshotSummary() {
  var ss  = SpreadsheetApp.getActiveSpreadsheet();
  var ui  = SpreadsheetApp.getUi();
  var now = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm');
  var snapName = 'Snapshot ' + now;

  // Copy dashboard sheet
  var dash = ss.getSheetByName('📋 Dashboard');
  if (!dash) { ui.alert('Run createTravelPlan first.'); return; }

  var copy = dash.copyTo(ss);
  copy.setName(snapName);
  copy.setTabColor('#888888');

  // Add a header noting it's a snapshot
  copy.getRange('A1').setValue('SNAPSHOT — ' + now + '  |  Backward Ass Travel Plan')
    .setBackground('#555555').setFontColor('#ffffff')
    .setFontSize(12).setFontWeight('bold');

  ui.alert('✅  Snapshot saved as tab: "' + snapName + '"');
}


// ══════════════════════════════════════════════════════════════════════════════
//  MENU — adds "Travel Plan" menu to Google Sheets UI
// ══════════════════════════════════════════════════════════════════════════════
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('✈️  Travel Plan')
    .addItem('🔨  Build / Rebuild Sheet', 'createTravelPlan')
    .addSeparator()
    .addItem('📅  Set Goal Date', 'setGoalDate')
    .addItem('💰  Update Selected Expense', 'updateExpense')
    .addSeparator()
    .addItem('📝  Count Empty Input Cells', 'highlightInputCells')
    .addItem('📸  Snapshot Current Summary', 'snapshotSummary')
    .addToUi();
}
