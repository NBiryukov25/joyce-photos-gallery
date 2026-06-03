// ============================================================
// Flight Coordinator — Google Apps Script
// Run createFlightCoordinator() to generate the spreadsheet
// ============================================================

function createFlightCoordinator() {
  const ss = SpreadsheetApp.create('✈ Flight Coordinator');
  SpreadsheetApp.setActiveSpreadsheet(ss);

  buildFlightDataSheet(ss);
  buildTimelineSheet(ss);
  buildSummarySheet(ss);

  // Remove default blank sheet
  const blank = ss.getSheetByName('Sheet1');
  if (blank) ss.deleteSheet(blank);

  // Activate the data entry sheet first
  ss.setActiveSheet(ss.getSheetByName('✈ Flight Options'));

  const url = ss.getUrl();
  SpreadsheetApp.getUi().alert('Spreadsheet created!\n\n' + url);
  Logger.log('Spreadsheet URL: ' + url);
}

// ──────────────────────────────────────────────
// SHEET 1 — Flight Options (data entry)
// ──────────────────────────────────────────────
function buildFlightDataSheet(ss) {
  const sh = ss.insertSheet('✈ Flight Options');

  const C = {
    header:      '#1A237E',
    personA:     '#0D47A1',
    personB:     '#B71C1C',
    subHeader:   '#283593',
    altRow:      '#E8EAF6',
    altRowB:     '#FFEBEE',
    accent:      '#FFD600',
    border:      '#9FA8DA',
    white:       '#FFFFFF',
    lightGray:   '#F5F5F5',
    green:       '#E8F5E9',
    overlap:     '#FFF9C4',
  };

  sh.getRange('A1:R1').merge().setValue('✈  ROUND-TRIP FLIGHT COORDINATOR')
    .setBackground(C.header).setFontColor(C.white)
    .setFontSize(18).setFontWeight('bold').setHorizontalAlignment('center')
    .setVerticalAlignment('middle');
  sh.setRowHeight(1, 48);

  sh.getRange('A2:R2').merge()
    .setValue('Enter flight options below. Switch to the "📊 Timeline" tab to visualize overlap and layover coordination.')
    .setBackground('#3949AB').setFontColor('#C5CAE9')
    .setFontSize(11).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(2, 30);

  const colWidths = [30, 120, 140, 90, 110, 110, 70, 90, 70, 30, 120, 140, 90, 110, 110, 70, 90, 70];
  colWidths.forEach((w, i) => sh.setColumnWidth(i + 1, w));

  sh.getRange('A3').setValue('').setBackground(C.lightGray);
  sh.getRange('B3:I3').merge().setValue('👤  PERSON A  —  OUTBOUND FLIGHTS')
    .setBackground(C.personA).setFontColor(C.white)
    .setFontSize(13).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.getRange('J3').setValue('').setBackground(C.lightGray);
  sh.getRange('K3:R3').merge().setValue('👤  PERSON B  —  OUTBOUND FLIGHTS')
    .setBackground(C.personB).setFontColor(C.white)
    .setFontSize(13).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(3, 36);

  const labels = ['Option', 'Airline', 'Route (Origin → Dest)', 'Date', 'Departure', 'Arrival', 'Duration', 'Price (USD)', 'Notes'];
  ['B4:B4','C4','D4','E4','F4','G4','H4','I4'].forEach((r, i) => {
    sh.getRange(r).setValue(labels[i] || '').setBackground('#3949AB').setFontColor(C.white)
      .setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  });
  ['K4','L4','M4','N4','O4','P4','Q4','R4'].forEach((r, i) => {
    sh.getRange(r).setValue(labels[i] || '').setBackground('#C62828').setFontColor(C.white)
      .setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  });
  sh.setRowHeight(4, 30);

  for (let i = 0; i < 6; i++) {
    const row = 5 + i;
    const bg  = i % 2 === 0 ? C.white : C.altRow;
    const bgB = i % 2 === 0 ? C.white : C.altRowB;
    const optLabel = 'Option ' + (i + 1);

    sh.getRange(row, 1).setValue('').setBackground(C.lightGray);
    sh.getRange(row, 2).setValue(optLabel).setBackground(bg).setHorizontalAlignment('center').setFontWeight('bold');
    sh.getRange(row, 3).setValue('').setBackground(bg);
    sh.getRange(row, 4).setValue('').setBackground(bg);
    sh.getRange(row, 5).setValue('').setBackground(bg).setNumberFormat('M/d/yyyy');
    sh.getRange(row, 6).setValue('').setBackground(bg).setNumberFormat('h:mm AM/PM');
    sh.getRange(row, 7).setValue('').setBackground(bg).setNumberFormat('h:mm AM/PM');
    sh.getRange(row, 8).setValue('').setBackground(bg);
    sh.getRange(row, 9).setValue('').setBackground(bg).setNumberFormat('"$"#,##0.00');
    sh.getRange(row, 10).setValue('').setBackground(C.lightGray);

    sh.getRange(row, 11).setValue(optLabel).setBackground(bgB).setHorizontalAlignment('center').setFontWeight('bold');
    sh.getRange(row, 12).setValue('').setBackground(bgB);
    sh.getRange(row, 13).setValue('').setBackground(bgB);
    sh.getRange(row, 14).setValue('').setBackground(bgB).setNumberFormat('M/d/yyyy');
    sh.getRange(row, 15).setValue('').setBackground(bgB).setNumberFormat('h:mm AM/PM');
    sh.getRange(row, 16).setValue('').setBackground(bgB).setNumberFormat('h:mm AM/PM');
    sh.getRange(row, 17).setValue('').setBackground(bgB);
    sh.getRange(row, 18).setValue('').setBackground(bgB).setNumberFormat('"$"#,##0.00');
    sh.setRowHeight(row, 26);
  }

  sh.getRange('A11:R11').merge().setValue('').setBackground(C.lightGray);
  sh.setRowHeight(11, 10);

  sh.getRange('B12:I12').merge().setValue('🔁  PERSON A  —  LAYOVER / CONNECTION (if applicable)')
    .setBackground('#1565C0').setFontColor(C.white)
    .setFontSize(12).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.getRange('K12:R12').merge().setValue('🔁  PERSON B  —  LAYOVER / CONNECTION (if applicable)')
    .setBackground('#C62828').setFontColor(C.white)
    .setFontSize(12).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(12, 32);

  const layLabels = ['Option', 'Airline', 'Connection Airport', 'Date', 'Layover Start', 'Layover End', 'Wait Time', 'Leg 2 Price', 'Notes'];
  ['B13','C13','D13','E13','F13','G13','H13','I13'].forEach((r, i) => {
    sh.getRange(r).setValue(layLabels[i]).setBackground('#3949AB').setFontColor(C.white)
      .setFontWeight('bold').setHorizontalAlignment('center');
  });
  ['K13','L13','M13','N13','O13','P13','Q13','R13'].forEach((r, i) => {
    sh.getRange(r).setValue(layLabels[i]).setBackground('#C62828').setFontColor(C.white)
      .setFontWeight('bold').setHorizontalAlignment('center');
  });
  sh.setRowHeight(13, 28);

  for (let i = 0; i < 6; i++) {
    const row = 14 + i;
    const bg  = i % 2 === 0 ? C.white : C.altRow;
    const bgB = i % 2 === 0 ? C.white : C.altRowB;
    const optLabel = 'Option ' + (i + 1);

    sh.getRange(row, 2).setValue(optLabel).setBackground(bg).setHorizontalAlignment('center').setFontWeight('bold');
    [3,4].forEach(c => sh.getRange(row, c).setBackground(bg));
    sh.getRange(row, 5).setBackground(bg).setNumberFormat('M/d/yyyy');
    sh.getRange(row, 6).setBackground(bg).setNumberFormat('h:mm AM/PM');
    sh.getRange(row, 7).setBackground(bg).setNumberFormat('h:mm AM/PM');
    sh.getRange(row, 8).setBackground(bg);
    sh.getRange(row, 9).setBackground(bg).setNumberFormat('"$"#,##0.00');

    sh.getRange(row, 11).setValue(optLabel).setBackground(bgB).setHorizontalAlignment('center').setFontWeight('bold');
    [12,13].forEach(c => sh.getRange(row, c).setBackground(bgB));
    sh.getRange(row, 14).setBackground(bgB).setNumberFormat('M/d/yyyy');
    sh.getRange(row, 15).setBackground(bgB).setNumberFormat('h:mm AM/PM');
    sh.getRange(row, 16).setBackground(bgB).setNumberFormat('h:mm AM/PM');
    sh.getRange(row, 17).setBackground(bgB);
    sh.getRange(row, 18).setBackground(bgB).setNumberFormat('"$"#,##0.00');
    sh.setRowHeight(row, 24);
  }

  const retStart = 21;
  sh.setRowHeight(retStart - 1, 10);
  sh.getRange(retStart, 2, 1, 8).merge().setValue('✈  PERSON A  —  RETURN FLIGHTS')
    .setBackground(C.personA).setFontColor(C.white)
    .setFontSize(13).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.getRange(retStart, 11, 1, 8).merge().setValue('✈  PERSON B  —  RETURN FLIGHTS')
    .setBackground(C.personB).setFontColor(C.white)
    .setFontSize(13).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(retStart, 36);

  const retLabRow = retStart + 1;
  ['B','C','D','E','F','G','H','I'].forEach((col, i) => {
    sh.getRange(col + retLabRow).setValue(labels[i]).setBackground('#3949AB').setFontColor(C.white)
      .setFontWeight('bold').setHorizontalAlignment('center');
  });
  ['K','L','M','N','O','P','Q','R'].forEach((col, i) => {
    sh.getRange(col + retLabRow).setValue(labels[i]).setBackground('#C62828').setFontColor(C.white)
      .setFontWeight('bold').setHorizontalAlignment('center');
  });
  sh.setRowHeight(retLabRow, 28);

  for (let i = 0; i < 6; i++) {
    const row = retStart + 2 + i;
    const bg  = i % 2 === 0 ? C.white : C.altRow;
    const bgB = i % 2 === 0 ? C.white : C.altRowB;
    const optLabel = 'Option ' + (i + 1);

    sh.getRange(row, 2).setValue(optLabel).setBackground(bg).setHorizontalAlignment('center').setFontWeight('bold');
    sh.getRange(row, 3).setBackground(bg); sh.getRange(row, 4).setBackground(bg);
    sh.getRange(row, 5).setBackground(bg).setNumberFormat('M/d/yyyy');
    sh.getRange(row, 6).setBackground(bg).setNumberFormat('h:mm AM/PM');
    sh.getRange(row, 7).setBackground(bg).setNumberFormat('h:mm AM/PM');
    sh.getRange(row, 8).setBackground(bg);
    sh.getRange(row, 9).setBackground(bg).setNumberFormat('"$"#,##0.00');

    sh.getRange(row, 11).setValue(optLabel).setBackground(bgB).setHorizontalAlignment('center').setFontWeight('bold');
    sh.getRange(row, 12).setBackground(bgB); sh.getRange(row, 13).setBackground(bgB);
    sh.getRange(row, 14).setBackground(bgB).setNumberFormat('M/d/yyyy');
    sh.getRange(row, 15).setBackground(bgB).setNumberFormat('h:mm AM/PM');
    sh.getRange(row, 16).setBackground(bgB).setNumberFormat('h:mm AM/PM');
    sh.getRange(row, 17).setBackground(bgB);
    sh.getRange(row, 18).setBackground(bgB).setNumberFormat('"$"#,##0.00');
    sh.setRowHeight(row, 24);
  }

  const totalRow = retStart + 2 + 6 + 1;
  sh.getRange(totalRow, 2, 1, 7).merge()
    .setValue('TOTAL PRICE — Enter combined round-trip cost per option')
    .setBackground('#FFF176').setFontWeight('bold').setFontSize(11).setHorizontalAlignment('center');
  sh.getRange(totalRow, 9).setValue('$0.00').setBackground('#FFD600')
    .setFontWeight('bold').setHorizontalAlignment('center').setNumberFormat('"$"#,##0.00');
  sh.getRange(totalRow, 11, 1, 7).merge()
    .setValue('TOTAL PRICE — Enter combined round-trip cost per option')
    .setBackground('#FFCDD2').setFontWeight('bold').setFontSize(11).setHorizontalAlignment('center');
  sh.getRange(totalRow, 18).setValue('$0.00').setBackground('#EF9A9A')
    .setFontWeight('bold').setHorizontalAlignment('center').setNumberFormat('"$"#,##0.00');
  sh.setRowHeight(totalRow, 30);

  sh.setFrozenRows(4);
  sh.setFrozenColumns(1);

  sh.getRange('B4:I' + totalRow).setBorder(true, true, true, true, true, true, '#9FA8DA', SpreadsheetApp.BorderStyle.SOLID);
  sh.getRange('K4:R' + totalRow).setBorder(true, true, true, true, true, true, '#FFCDD2', SpreadsheetApp.BorderStyle.SOLID);
}

// ──────────────────────────────────────────────
// SHEET 2 — Timeline (visual Gantt)
// ──────────────────────────────────────────────
function buildTimelineSheet(ss) {
  const sh = ss.insertSheet('📊 Timeline');

  sh.getRange('A1:AV1').merge().setValue('📊  FLIGHT TIMELINE — Overlap & Layover Coordination View')
    .setBackground('#1A237E').setFontColor('#FFFFFF')
    .setFontSize(16).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(1, 46);

  sh.getRange('A2:AV2').merge()
    .setValue('Each column = 30 minutes. Fill departure and arrival columns based on your entries in "✈ Flight Options". Shared travel periods are highlighted automatically.')
    .setBackground('#283593').setFontColor('#C5CAE9')
    .setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(2, 28);

  const startHour = 6;
  const blocks = 36;

  sh.getRange('A3').setValue('Party / Option').setBackground('#37474F').setFontColor('#FFFFFF')
    .setFontWeight('bold').setHorizontalAlignment('center');
  sh.setColumnWidth(1, 160);

  sh.getRange('B3').setValue('Leg').setBackground('#37474F').setFontColor('#FFFFFF')
    .setFontWeight('bold').setHorizontalAlignment('center');
  sh.setColumnWidth(2, 60);

  for (let b = 0; b < blocks; b++) {
    const col = b + 3;
    const totalMin = startHour * 60 + b * 30;
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    const ampm = h < 12 ? 'AM' : 'PM';
    const displayH = h === 0 ? 12 : h > 12 ? h - 12 : h;
    const label = displayH + (m === 0 ? ':00' : ':30') + ampm;

    sh.getRange(3, col).setValue(label)
      .setBackground(b % 2 === 0 ? '#455A64' : '#546E7A')
      .setFontColor('#ECEFF1').setFontSize(8)
      .setHorizontalAlignment('center').setVerticalAlignment('middle');
    sh.setColumnWidth(col, 52);
  }
  sh.setRowHeight(3, 28);

  const legRow = 4;
  sh.getRange('A' + legRow).setValue('LEGEND →').setFontWeight('bold').setBackground('#ECEFF1');
  sh.getRange('B' + legRow + ':E' + legRow).merge().setValue('✈  In Air (Person A)')
    .setBackground('#1565C0').setFontColor('#FFFFFF').setHorizontalAlignment('center').setFontWeight('bold');
  sh.getRange('F' + legRow + ':I' + legRow).merge().setValue('✈  In Air (Person B)')
    .setBackground('#B71C1C').setFontColor('#FFFFFF').setHorizontalAlignment('center').setFontWeight('bold');
  sh.getRange('J' + legRow + ':M' + legRow).merge().setValue('🟡  BOTH In Air (Overlap)')
    .setBackground('#F9A825').setFontColor('#000000').setHorizontalAlignment('center').setFontWeight('bold');
  sh.getRange('N' + legRow + ':Q' + legRow).merge().setValue('⏳  Layover (A)')
    .setBackground('#42A5F5').setFontColor('#000000').setHorizontalAlignment('center');
  sh.getRange('R' + legRow + ':U' + legRow).merge().setValue('⏳  Layover (B)')
    .setBackground('#EF9A9A').setFontColor('#000000').setHorizontalAlignment('center');
  sh.getRange('V' + legRow + ':Y' + legRow).merge().setValue('🟢  Layover synced with other\'s flight')
    .setBackground('#2E7D32').setFontColor('#FFFFFF').setHorizontalAlignment('center');
  sh.setRowHeight(legRow, 28);

  sh.getRange('A5:AV5').merge()
    .setValue('HOW TO USE: After entering your flights in "✈ Flight Options", color cells covering each in-air window. Use the Legend above as your color guide. Fill the Overlap Analysis table at the bottom once all options are entered.')
    .setBackground('#E3F2FD').setFontSize(10).setWrap(true);
  sh.setRowHeight(5, 40);

  sh.getRange('A6:AV6').merge().setValue('📝  TIMELINE ROWS — Color cells to match each flight window (see Legend)')
    .setBackground('#37474F').setFontColor('#ECEFF1').setFontWeight('bold').setHorizontalAlignment('center');
  sh.setRowHeight(6, 28);

  const persons  = ['A', 'B'];
  const bgPerson = { A: '#0D47A1', B: '#B71C1C' };
  const layColor = { A: '#90CAF9', B: '#FFCDD2' };

  let r = 7;
  for (let opt = 1; opt <= 6; opt++) {
    sh.getRange(r, 1, 1, blocks + 2).merge()
      .setValue('  OPTION ' + opt)
      .setBackground('#263238').setFontColor('#ECEFF1')
      .setFontWeight('bold').setFontSize(11);
    sh.setRowHeight(r, 24);
    r++;

    for (const p of persons) {
      sh.getRange(r, 1).setValue('Person ' + p + ' — Outbound')
        .setBackground(bgPerson[p]).setFontColor('#FFFFFF').setFontWeight('bold');
      sh.getRange(r, 2).setValue('Leg 1').setBackground(bgPerson[p]).setFontColor('#FFFFFF').setHorizontalAlignment('center');
      for (let b = 0; b < blocks; b++) {
        sh.getRange(r, b + 3).setValue('').setBackground('#ECEFF1');
      }
      sh.setRowHeight(r, 26);
      r++;

      sh.getRange(r, 1).setValue('Person ' + p + ' — Layover')
        .setBackground(layColor[p]).setFontColor('#000000');
      sh.getRange(r, 2).setValue('⏳').setBackground(layColor[p]).setHorizontalAlignment('center');
      for (let b = 0; b < blocks; b++) {
        sh.getRange(r, b + 3).setValue('').setBackground('#FAFAFA');
      }
      sh.setRowHeight(r, 22);
      r++;

      sh.getRange(r, 1).setValue('Person ' + p + ' — Return')
        .setBackground(bgPerson[p]).setFontColor('#FFFFFF').setFontWeight('bold');
      sh.getRange(r, 2).setValue('Leg 2').setBackground(bgPerson[p]).setFontColor('#FFFFFF').setHorizontalAlignment('center');
      for (let b = 0; b < blocks; b++) {
        sh.getRange(r, b + 3).setValue('').setBackground('#ECEFF1');
      }
      sh.setRowHeight(r, 26);
      r++;
    }

    sh.getRange(r, 1, 1, blocks + 2).merge().setValue('').setBackground('#CFD8DC');
    sh.setRowHeight(r, 6);
    r++;
  }

  sh.getRange(r, 1, 1, blocks + 2).merge()
    .setValue('🔍  OVERLAP & COORDINATION ANALYSIS')
    .setBackground('#1A237E').setFontColor('#FFFFFF').setFontSize(13).setFontWeight('bold').setHorizontalAlignment('center');
  sh.setRowHeight(r, 32);
  r++;

  const analysisLabels = [
    '✅ Simultaneous in-air (both flying same window)',
    '❌ Non-overlapping (one lands before other departs)',
    '⏳ Person A layover matches Person B in-air window',
    '⏳ Person B layover matches Person A in-air window',
    '🟢 Layovers coincide (both waiting at airport together)',
    '💰 Combined price — this option',
    '⭐ Best overlap fit? (manual)',
  ];

  analysisLabels.forEach((lbl, i) => {
    const row = r + i;
    sh.getRange(row, 1).setValue(lbl).setBackground(i % 2 === 0 ? '#E8EAF6' : '#FFFFFF')
      .setFontSize(10).setWrap(true);
    for (let opt = 0; opt < 6; opt++) {
      sh.getRange(row, opt + 2).setValue('—').setHorizontalAlignment('center')
        .setBackground(i % 2 === 0 ? '#E8EAF6' : '#FFFFFF');
    }
    sh.setRowHeight(row, 28);
  });

  sh.setFrozenRows(3);
  sh.setFrozenColumns(2);
}

// ──────────────────────────────────────────────
// SHEET 3 — Summary & Decision Helper
// ──────────────────────────────────────────────
function buildSummarySheet(ss) {
  const sh = ss.insertSheet('📋 Summary');

  sh.getRange('A1:J1').merge().setValue('📋  FLIGHT DECISION SUMMARY')
    .setBackground('#1A237E').setFontColor('#FFFFFF')
    .setFontSize(18).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(1, 48);

  sh.getRange('A2:J2').merge()
    .setValue('Use this sheet to compare all options at a glance and record your final decision.')
    .setBackground('#283593').setFontColor('#C5CAE9').setFontSize(11)
    .setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(2, 28);

  [200, 140, 140, 100, 100, 120, 120, 120, 120, 160].forEach((w, i) => sh.setColumnWidth(i + 1, w));

  const headers = ['Criteria', 'Option 1', 'Option 2', 'Option 3', 'Option 4', 'Option 5', 'Option 6', '','','Notes'];
  sh.getRange('A3:J3').setValues([headers])
    .setBackground('#37474F').setFontColor('#FFFFFF').setFontWeight('bold').setHorizontalAlignment('center');
  sh.setRowHeight(3, 30);

  const criteria = [
    ['👤 Person A — Outbound Departure'],
    ['👤 Person A — Outbound Arrival'],
    ['👤 Person A — Layover Duration'],
    ['👤 Person A — Return Departure'],
    ['👤 Person A — Return Arrival'],
    ['👤 Person A — Airline(s)'],
    ['💰 Person A — Price'],
    [''],
    ['👤 Person B — Outbound Departure'],
    ['👤 Person B — Outbound Arrival'],
    ['👤 Person B — Layover Duration'],
    ['👤 Person B — Return Departure'],
    ['👤 Person B — Return Arrival'],
    ['👤 Person B — Airline(s)'],
    ['💰 Person B — Price'],
    [''],
    ['✈ Both In-Air Same Time?'],
    ['⏳ A Layover During B Flight?'],
    ['⏳ B Layover During A Flight?'],
    ['🟢 Layovers Coincide?'],
    ['💰 COMBINED TOTAL PRICE'],
    ['⭐ OVERALL SCORE (1–10)'],
  ];

  const altA = '#E8EAF6';
  const altB = '#FFEBEE';

  criteria.forEach((row, i) => {
    const sheetRow = 4 + i;
    const label = row[0];
    const isSection  = label === '';
    const isPersonA  = label.includes('Person A');
    const isPersonB  = label.includes('Person B');
    const isTotal    = label.includes('TOTAL') || label.includes('SCORE');
    const isCombined = label.includes('Both') || label.includes('Layover') || label.includes('Coincide');

    let rowBg = i % 2 === 0 ? '#FFFFFF' : '#F5F5F5';
    if (isSection)   rowBg = '#CFD8DC';
    if (isPersonA)   rowBg = i % 2 === 0 ? '#FFFFFF' : altA;
    if (isPersonB)   rowBg = i % 2 === 0 ? '#FFFFFF' : altB;
    if (isTotal)     rowBg = '#FFF9C4';
    if (isCombined)  rowBg = '#E8F5E9';

    sh.getRange(sheetRow, 1).setValue(label).setBackground(rowBg).setFontWeight(isTotal ? 'bold' : 'normal');
    for (let c = 1; c < 7; c++) {
      sh.getRange(sheetRow, c + 1).setValue('').setBackground(rowBg).setHorizontalAlignment('center');
    }
    sh.getRange(sheetRow, 8, 1, 3).merge().setValue('').setBackground(rowBg);
    sh.setRowHeight(sheetRow, isSection ? 8 : 26);
  });

  const finalRow = 4 + criteria.length + 2;
  sh.getRange(finalRow, 1, 1, 10).merge()
    .setValue('✅  FINAL DECISION')
    .setBackground('#1B5E20').setFontColor('#FFFFFF')
    .setFontSize(14).setFontWeight('bold').setHorizontalAlignment('center');
  sh.setRowHeight(finalRow, 36);

  const decFields = [
    'Person A chose:',
    'Person B chose:',
    'Reason:',
    'Booking confirmation # (A):',
    'Booking confirmation # (B):',
    'Departure airport meetup plan:',
    'Arrival airport meetup plan:',
    'Emergency contact / notes:',
  ];

  decFields.forEach((label, i) => {
    const row = finalRow + 1 + i;
    sh.getRange(row, 1, 1, 2).merge().setValue(label)
      .setBackground('#E8F5E9').setFontWeight('bold');
    sh.getRange(row, 3, 1, 8).merge().setValue('')
      .setBackground('#FFFFFF').setBorder(false, false, true, false, false, false, '#A5D6A7', SpreadsheetApp.BorderStyle.SOLID);
    sh.setRowHeight(row, 28);
  });

  sh.setFrozenRows(3);
  sh.setFrozenColumns(1);
}
