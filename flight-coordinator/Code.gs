// ============================================================
// Flight Coordinator — Auto Overlap Calculator
// Run createFlightCoordinator() to build the spreadsheet
// Then enter times in the INPUT sheet — Timeline updates live
// ============================================================

function createFlightCoordinator() {
  const ss = SpreadsheetApp.create('✈ Flight Coordinator');

  buildInputSheet(ss);
  buildTimelineSheet(ss);

  const blank = ss.getSheetByName('Sheet1');
  if (blank) ss.deleteSheet(blank);

  ss.setActiveSheet(ss.getSheetByName('✈ Enter Flights'));
  Logger.log('Done! Open here: ' + ss.getUrl());
}

// ─────────────────────────────────────────────
// SHEET 1: Input — user fills this in
// ─────────────────────────────────────────────
function buildInputSheet(ss) {
  const sh = ss.insertSheet('✈ Enter Flights');
  sh.setColumnWidth(1, 160);
  sh.setColumnWidth(2, 110); // A Depart
  sh.setColumnWidth(3, 110); // A Arrive
  sh.setColumnWidth(4, 110); // A Layover Start
  sh.setColumnWidth(5, 110); // A Layover End
  sh.setColumnWidth(6, 110); // A Return Depart
  sh.setColumnWidth(7, 110); // A Return Arrive
  sh.setColumnWidth(8, 100); // A Price
  sh.setColumnWidth(9, 20);  // spacer
  sh.setColumnWidth(10, 110); // B Depart
  sh.setColumnWidth(11, 110); // B Arrive
  sh.setColumnWidth(12, 110); // B Layover Start
  sh.setColumnWidth(13, 110); // B Layover End
  sh.setColumnWidth(14, 110); // B Return Depart
  sh.setColumnWidth(15, 110); // B Return Arrive
  sh.setColumnWidth(16, 100); // B Price

  // Title
  sh.getRange('A1:P1').merge()
    .setValue('✈  FLIGHT COORDINATOR — Enter times below, then open the Timeline sheet to see overlap')
    .setBackground('#1A237E').setFontColor('#FFFFFF')
    .setFontSize(13).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(1, 44);

  // Person headers
  sh.getRange('B2:H2').merge().setValue('👤  PERSON A')
    .setBackground('#0D47A1').setFontColor('#FFFFFF').setFontSize(12).setFontWeight('bold').setHorizontalAlignment('center');
  sh.getRange('J2:P2').merge().setValue('👤  PERSON B')
    .setBackground('#B71C1C').setFontColor('#FFFFFF').setFontSize(12).setFontWeight('bold').setHorizontalAlignment('center');
  sh.setRowHeight(2, 32);

  // Column headers
  const aHdrs = ['Outbound\nDepart', 'Outbound\nArrive', 'Layover\nStart', 'Layover\nEnd', 'Return\nDepart', 'Return\nArrive', 'Price'];
  aHdrs.forEach((h, i) => {
    sh.getRange(3, i + 2).setValue(h)
      .setBackground('#1565C0').setFontColor('#FFFFFF').setFontWeight('bold')
      .setHorizontalAlignment('center').setVerticalAlignment('middle').setWrap(true);
  });
  ['Outbound\nDepart','Outbound\nArrive','Layover\nStart','Layover\nEnd','Return\nDepart','Return\nArrive','Price'].forEach((h, i) => {
    sh.getRange(3, i + 10).setValue(h)
      .setBackground('#C62828').setFontColor('#FFFFFF').setFontWeight('bold')
      .setHorizontalAlignment('center').setVerticalAlignment('middle').setWrap(true);
  });
  sh.getRange('A3').setValue('Option').setBackground('#37474F').setFontColor('#FFFFFF').setFontWeight('bold').setHorizontalAlignment('center');
  sh.getRange('I3').setBackground('#ECEFF1');
  sh.setRowHeight(3, 40);

  // Data rows for 6 options
  const timeFmt = 'h:mm AM/PM';
  const priceFmt = '"$"#,##0.00';
  for (let i = 0; i < 6; i++) {
    const row = 4 + i;
    const bg  = i % 2 === 0 ? '#FFFFFF' : '#F5F5F5';
    const bgB = i % 2 === 0 ? '#FFFFFF' : '#FFF5F5';
    sh.getRange(row, 1).setValue('Option ' + (i+1)).setBackground(bg).setFontWeight('bold').setHorizontalAlignment('center');
    for (let c = 2; c <= 7; c++) sh.getRange(row, c).setBackground(bg).setNumberFormat(timeFmt).setHorizontalAlignment('center');
    sh.getRange(row, 8).setBackground(bg).setNumberFormat(priceFmt).setHorizontalAlignment('center');
    sh.getRange(row, 9).setBackground('#ECEFF1');
    for (let c = 10; c <= 15; c++) sh.getRange(row, c).setBackground(bgB).setNumberFormat(timeFmt).setHorizontalAlignment('center');
    sh.getRange(row, 16).setBackground(bgB).setNumberFormat(priceFmt).setHorizontalAlignment('center');
    sh.setRowHeight(row, 28);
  }

  // Helper note
  sh.getRange('A11:P11').merge()
    .setValue('💡 Enter times as h:mm AM/PM (e.g. 8:30 AM). Leave Layover blank if no connection. After filling in, open the "📊 Timeline" sheet.')
    .setBackground('#E3F2FD').setFontSize(10).setWrap(true).setVerticalAlignment('middle');
  sh.setRowHeight(11, 36);

  sh.setFrozenRows(3);
}

// ─────────────────────────────────────────────
// SHEET 2: Timeline — auto-colored + overlap
// ─────────────────────────────────────────────
function buildTimelineSheet(ss) {
  const sh = ss.insertSheet('📊 Timeline');

  // Title
  sh.getRange('A1:AV1').merge()
    .setValue('📊  FLIGHT TIMELINE — Runs 5 AM to Midnight in 30-min blocks. Blue = Person A in air. Red = Person B. Yellow = Both in air. Green = Layovers overlap.')
    .setBackground('#1A237E').setFontColor('#FFFFFF')
    .setFontSize(11).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle').setWrap(true);
  sh.setRowHeight(1, 52);

  // Time axis: 5AM to midnight = 38 blocks of 30min
  const START_HOUR = 5;
  const BLOCKS = 38;
  const TIME_COL_START = 3; // column C

  sh.getRange('A2').setValue('Option').setBackground('#37474F').setFontColor('#FFFFFF').setFontWeight('bold').setHorizontalAlignment('center');
  sh.setColumnWidth(1, 120);
  sh.getRange('B2').setValue('Who').setBackground('#37474F').setFontColor('#FFFFFF').setFontWeight('bold').setHorizontalAlignment('center');
  sh.setColumnWidth(2, 90);

  for (let b = 0; b < BLOCKS; b++) {
    const col = TIME_COL_START + b;
    const mins = START_HOUR * 60 + b * 30;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    const ampm = h < 12 ? 'AM' : 'PM';
    const dh = h === 0 ? 12 : h > 12 ? h - 12 : h;
    sh.getRange(2, col).setValue(dh + (m === 0 ? ':00' : ':30') + ampm)
      .setBackground(b % 2 === 0 ? '#455A64' : '#546E7A')
      .setFontColor('#ECEFF1').setFontSize(8).setHorizontalAlignment('center');
    sh.setColumnWidth(col, 48);
  }
  sh.setRowHeight(2, 26);

  // Legend
  sh.getRange('A3:B3').merge().setValue('LEGEND →').setBackground('#ECEFF1').setFontWeight('bold').setHorizontalAlignment('center');
  sh.getRange('C3:F3').merge().setValue('✈ Person A — In Air').setBackground('#1565C0').setFontColor('#FFFFFF').setHorizontalAlignment('center').setFontWeight('bold');
  sh.getRange('G3:J3').merge().setValue('✈ Person B — In Air').setBackground('#C62828').setFontColor('#FFFFFF').setHorizontalAlignment('center').setFontWeight('bold');
  sh.getRange('K3:N3').merge().setValue('🟡 BOTH in air').setBackground('#F9A825').setFontColor('#000').setHorizontalAlignment('center').setFontWeight('bold');
  sh.getRange('O3:R3').merge().setValue('⏳ Layover A').setBackground('#90CAF9').setFontColor('#000').setHorizontalAlignment('center');
  sh.getRange('S3:V3').merge().setValue('⏳ Layover B').setBackground('#FFCDD2').setFontColor('#000').setHorizontalAlignment('center');
  sh.getRange('W3:Z3').merge().setValue('🟢 Layovers overlap').setBackground('#2E7D32').setFontColor('#FFFFFF').setHorizontalAlignment('center');
  sh.setRowHeight(3, 26);

  // Build one group of rows per option
  // Rows per option: outbound, layover, return, overlap summary, spacer
  const inputSheet = '✈ Enter Flights';
  let row = 4;

  for (let opt = 1; opt <= 6; opt++) {
    const inputRow = opt + 3; // data starts at row 4 in input sheet

    // Option header
    sh.getRange(row, 1, 1, BLOCKS + 2).merge()
      .setValue('OPTION ' + opt)
      .setBackground('#263238').setFontColor('#ECEFF1').setFontWeight('bold').setFontSize(11);
    sh.setRowHeight(row, 22);
    row++;

    // ── Outbound row (A and B combined on two rows) ──
    const outboundRows = [
      { label: 'Person A\nOutbound', leg: 'outbound', person: 'A',
        dCol: 2,  aCol: 3,  color: '#1565C0', layS: 4, layE: 5 },
      { label: 'Person B\nOutbound', leg: 'outbound', person: 'B',
        dCol: 10, aCol: 11, color: '#C62828', layS: 12, layE: 13 },
    ];

    for (const cfg of outboundRows) {
      sh.getRange(row, 1).setValue(cfg.label)
        .setBackground(cfg.color).setFontColor('#FFFFFF').setFontWeight('bold')
        .setWrap(true).setVerticalAlignment('middle');
      sh.getRange(row, 2).setValue('Outbound')
        .setBackground(cfg.color).setFontColor('#FFFFFF').setHorizontalAlignment('center').setVerticalAlignment('middle');

      // Outbound in-air formula
      for (let b = 0; b < BLOCKS; b++) {
        const col = TIME_COL_START + b;
        const slotFrac = (START_HOUR * 60 + b * 30) / 1440;
        const slotEndFrac = (START_HOUR * 60 + b * 30 + 30) / 1440;
        // depart cell and arrive cell from input sheet
        const dRef = "'" + inputSheet + "'!" + columnLetter(cfg.dCol) + inputRow;
        const aRef = "'" + inputSheet + "'!" + columnLetter(cfg.aCol) + inputRow;
        // cell is in-air if slot overlaps [depart, arrive]
        const formula = '=IF(AND(' + dRef + '<>"",ISNUMBER(' + dRef + '),'
          + dRef + '<' + slotEndFrac + ',' + aRef + '>' + slotFrac + '),"✈","")';
        sh.getRange(row, col).setFormula(formula)
          .setHorizontalAlignment('center').setVerticalAlignment('middle').setFontSize(9);
      }
      sh.setRowHeight(row, 28);
      row++;

      // Layover row
      const layColor = cfg.person === 'A' ? '#90CAF9' : '#FFCDD2';
      sh.getRange(row, 1).setValue(cfg.person === 'A' ? 'Person A\nLayover' : 'Person B\nLayover')
        .setBackground(layColor).setFontColor('#000').setWrap(true).setVerticalAlignment('middle');
      sh.getRange(row, 2).setValue('Layover')
        .setBackground(layColor).setFontColor('#000').setHorizontalAlignment('center').setVerticalAlignment('middle');

      for (let b = 0; b < BLOCKS; b++) {
        const col = TIME_COL_START + b;
        const slotFrac = (START_HOUR * 60 + b * 30) / 1440;
        const slotEndFrac = (START_HOUR * 60 + b * 30 + 30) / 1440;
        const lsRef = "'" + inputSheet + "'!" + columnLetter(cfg.layS) + inputRow;
        const leRef = "'" + inputSheet + "'!" + columnLetter(cfg.layE) + inputRow;
        const formula = '=IF(AND(' + lsRef + '<>"",ISNUMBER(' + lsRef + '),'
          + lsRef + '<' + slotEndFrac + ',' + leRef + '>' + slotFrac + '),"⏳","")';
        sh.getRange(row, col).setFormula(formula)
          .setHorizontalAlignment('center').setVerticalAlignment('middle').setFontSize(9);
      }
      sh.setRowHeight(row, 24);
      row++;
    }

    // ── Return row ──
    const returnRows = [
      { label: 'Person A\nReturn', person: 'A', dCol: 6, aCol: 7, color: '#0D47A1' },
      { label: 'Person B\nReturn', person: 'B', dCol: 14, aCol: 15, color: '#B71C1C' },
    ];
    for (const cfg of returnRows) {
      sh.getRange(row, 1).setValue(cfg.label)
        .setBackground(cfg.color).setFontColor('#FFFFFF').setFontWeight('bold')
        .setWrap(true).setVerticalAlignment('middle');
      sh.getRange(row, 2).setValue('Return')
        .setBackground(cfg.color).setFontColor('#FFFFFF').setHorizontalAlignment('center').setVerticalAlignment('middle');

      for (let b = 0; b < BLOCKS; b++) {
        const col = TIME_COL_START + b;
        const slotFrac = (START_HOUR * 60 + b * 30) / 1440;
        const slotEndFrac = (START_HOUR * 60 + b * 30 + 30) / 1440;
        const dRef = "'" + inputSheet + "'!" + columnLetter(cfg.dCol) + inputRow;
        const aRef = "'" + inputSheet + "'!" + columnLetter(cfg.aCol) + inputRow;
        const formula = '=IF(AND(' + dRef + '<>"",ISNUMBER(' + dRef + '),'
          + dRef + '<' + slotEndFrac + ',' + aRef + '>' + slotFrac + '),"✈","")';
        sh.getRange(row, col).setFormula(formula)
          .setHorizontalAlignment('center').setVerticalAlignment('middle').setFontSize(9);
      }
      sh.setRowHeight(row, 28);
      row++;
    }

    // ── Overlap summary row ──
    sh.getRange(row, 1).setValue('⚡ Overlap\nSummary')
      .setBackground('#F9A825').setFontColor('#000').setFontWeight('bold')
      .setWrap(true).setVerticalAlignment('middle');
    sh.getRange(row, 2).setValue('Analysis')
      .setBackground('#F9A825').setFontColor('#000').setHorizontalAlignment('center').setVerticalAlignment('middle');

    // For each slot, show overlap type
    // A outbound row = row - 6 (A out), A layover = row-5, B out = row-4, B layover = row-3, A ret = row-2, B ret = row-1
    const aOutRow  = row - 6;
    const aLayRow  = row - 5;
    const bOutRow  = row - 4;
    const bLayRow  = row - 3;
    const aRetRow  = row - 2;
    const bRetRow  = row - 1;

    for (let b = 0; b < BLOCKS; b++) {
      const col = TIME_COL_START + b;
      const aOutCell  = columnLetter(col) + aOutRow;
      const aLayCell  = columnLetter(col) + aLayRow;
      const bOutCell  = columnLetter(col) + bOutRow;
      const bLayCell  = columnLetter(col) + bLayRow;
      const aRetCell  = columnLetter(col) + aRetRow;
      const bRetCell  = columnLetter(col) + bRetRow;

      // Both in air outbound = yellow, A layover + B flying = green, B layover + A flying = green, both layover = teal
      const formula =
        '=IF(AND(' + aOutCell + '<>"","' + bOutCell + '<>""),"BOTH FLY",' +
        'IF(AND(' + aLayCell + '<>"",' + bOutCell + '<>""),"A WAIT/B FLY",' +
        'IF(AND(' + bLayCell + '<>"",' + aOutCell + '<>""),"B WAIT/A FLY",' +
        'IF(AND(' + aLayCell + '<>"",' + bLayCell + '<>""),"BOTH WAIT",""))))';

      sh.getRange(row, col).setFormula(formula)
        .setHorizontalAlignment('center').setVerticalAlignment('middle').setFontSize(7).setWrap(true);
    }
    sh.setRowHeight(row, 36);
    row++;

    // ── Price + combined summary ──
    const aPrice = "'" + inputSheet + "'!H" + inputRow;
    const bPrice = "'" + inputSheet + "'!P" + inputRow;
    sh.getRange(row, 1, 1, BLOCKS + 2).merge()
      .setFormula('=IF(' + aPrice + '<>"","💰 Option ' + opt + ' Combined Price: $"&TEXT(' + aPrice + '+' + bPrice + ',"#,##0.00"),"(enter prices in the Enter Flights sheet)")')
      .setBackground('#FFF9C4').setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
    sh.setRowHeight(row, 24);
    row++;

    // Spacer
    sh.getRange(row, 1, 1, BLOCKS + 2).merge().setBackground('#CFD8DC');
    sh.setRowHeight(row, 6);
    row++;
  }

  // Conditional formatting for overlap summary rows — color by text value
  // (Google Sheets conditional formatting is better done manually, but we set background via onEdit trigger below)

  sh.setFrozenRows(3);
}

// Converts a column number to a letter (1=A, 2=B, etc.)
function columnLetter(col) {
  let letter = '';
  while (col > 0) {
    const rem = (col - 1) % 26;
    letter = String.fromCharCode(65 + rem) + letter;
    col = Math.floor((col - 1) / 26);
  }
  return letter;
}

// ─────────────────────────────────────────────
// onEdit trigger: color overlap summary cells
// Install via: Triggers > onEdit
// ─────────────────────────────────────────────
function onEdit(e) {
  colorOverlapCells();
}

function colorOverlapCells() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName('📊 Timeline');
  if (!sh) return;

  const lastRow = sh.getLastRow();
  const lastCol = sh.getLastColumn();
  const data = sh.getRange(1, 1, lastRow, lastCol).getValues();

  for (let r = 0; r < lastRow; r++) {
    if (data[r][1] === 'Analysis') {
      for (let c = 2; c < lastCol; c++) {
        const val = data[r][c];
        const cell = sh.getRange(r + 1, c + 1);
        if (val === 'BOTH FLY')       cell.setBackground('#F9A825').setFontColor('#000');
        else if (val === 'A WAIT/B FLY') cell.setBackground('#FFCDD2').setFontColor('#000');
        else if (val === 'B WAIT/A FLY') cell.setBackground('#BBDEFB').setFontColor('#000');
        else if (val === 'BOTH WAIT')    cell.setBackground('#C8E6C9').setFontColor('#000');
        else                             cell.setBackground('#FFFFFF').setFontColor('#000');
      }
    }
  }
}
