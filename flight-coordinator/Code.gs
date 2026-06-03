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

  const blank = ss.getSheetByName('Sheet1');
  if (blank) ss.deleteSheet(blank);

  ss.setActiveSheet(ss.getSheetByName('✈ Flight Options'));

  const url = ss.getUrl();
  SpreadsheetApp.getUi().alert('Spreadsheet created!\n\n' + url);
  Logger.log('Spreadsheet URL: ' + url);
}

function buildFlightDataSheet(ss) {
  const sh = ss.insertSheet('✈ Flight Options');

  const C = {
    header:    '#1A237E',
    personA:   '#0D47A1',
    personB:   '#B71C1C',
    altRow:    '#E8EAF6',
    altRowB:   '#FFEBEE',
    white:     '#FFFFFF',
    lightGray: '#F5F5F5',
  };

  sh.getRange('A1:R1').merge().setValue('✈  ROUND-TRIP FLIGHT COORDINATOR')
    .setBackground(C.header).setFontColor(C.white)
    .setFontSize(18).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(1, 48);

  sh.getRange('A2:R2').merge()
    .setValue('Enter flight options below. Switch to the "📊 Timeline" tab to visualize overlap and layover coordination.')
    .setBackground('#3949AB').setFontColor('#C5CAE9')
    .setFontSize(11).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(2, 30);

  const colWidths = [30,120,140,90,110,110,70,90,70,30,120,140,90,110,110,70,90,70];
  colWidths.forEach((w,i) => sh.setColumnWidth(i+1, w));

  sh.getRange('A3').setBackground(C.lightGray);
  sh.getRange('B3:I3').merge().setValue('👤  PERSON A  —  OUTBOUND FLIGHTS')
    .setBackground(C.personA).setFontColor(C.white).setFontSize(13).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.getRange('J3').setBackground(C.lightGray);
  sh.getRange('K3:R3').merge().setValue('👤  PERSON B  —  OUTBOUND FLIGHTS')
    .setBackground(C.personB).setFontColor(C.white).setFontSize(13).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(3, 36);

  const labels = ['Option','Airline','Route (Origin → Dest)','Date','Departure','Arrival','Duration','Price (USD)','Notes'];
  ['B4','C4','D4','E4','F4','G4','H4','I4'].forEach((r,i) => sh.getRange(r).setValue(labels[i]).setBackground('#3949AB').setFontColor(C.white).setFontWeight('bold').setHorizontalAlignment('center'));
  ['K4','L4','M4','N4','O4','P4','Q4','R4'].forEach((r,i) => sh.getRange(r).setValue(labels[i]).setBackground('#C62828').setFontColor(C.white).setFontWeight('bold').setHorizontalAlignment('center'));
  sh.setRowHeight(4, 30);

  for (let i=0;i<6;i++) {
    const row=5+i, bg=i%2===0?C.white:C.altRow, bgB=i%2===0?C.white:C.altRowB, opt='Option '+(i+1);
    sh.getRange(row,1).setBackground(C.lightGray);
    sh.getRange(row,2).setValue(opt).setBackground(bg).setHorizontalAlignment('center').setFontWeight('bold');
    [3,4].forEach(c=>sh.getRange(row,c).setBackground(bg));
    sh.getRange(row,5).setBackground(bg).setNumberFormat('M/d/yyyy');
    sh.getRange(row,6).setBackground(bg).setNumberFormat('h:mm AM/PM');
    sh.getRange(row,7).setBackground(bg).setNumberFormat('h:mm AM/PM');
    sh.getRange(row,8).setBackground(bg);
    sh.getRange(row,9).setBackground(bg).setNumberFormat('"$"#,##0.00');
    sh.getRange(row,10).setBackground(C.lightGray);
    sh.getRange(row,11).setValue(opt).setBackground(bgB).setHorizontalAlignment('center').setFontWeight('bold');
    [12,13].forEach(c=>sh.getRange(row,c).setBackground(bgB));
    sh.getRange(row,14).setBackground(bgB).setNumberFormat('M/d/yyyy');
    sh.getRange(row,15).setBackground(bgB).setNumberFormat('h:mm AM/PM');
    sh.getRange(row,16).setBackground(bgB).setNumberFormat('h:mm AM/PM');
    sh.getRange(row,17).setBackground(bgB);
    sh.getRange(row,18).setBackground(bgB).setNumberFormat('"$"#,##0.00');
    sh.setRowHeight(row,26);
  }

  sh.setRowHeight(11,10);
  sh.getRange('B12:I12').merge().setValue('🔁  PERSON A  —  LAYOVER / CONNECTION (if applicable)')
    .setBackground('#1565C0').setFontColor(C.white).setFontSize(12).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.getRange('K12:R12').merge().setValue('🔁  PERSON B  —  LAYOVER / CONNECTION (if applicable)')
    .setBackground('#C62828').setFontColor(C.white).setFontSize(12).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(12,32);

  const layLabels=['Option','Airline','Connection Airport','Date','Layover Start','Layover End','Wait Time','Leg 2 Price','Notes'];
  ['B13','C13','D13','E13','F13','G13','H13','I13'].forEach((r,i)=>sh.getRange(r).setValue(layLabels[i]).setBackground('#3949AB').setFontColor(C.white).setFontWeight('bold').setHorizontalAlignment('center'));
  ['K13','L13','M13','N13','O13','P13','Q13','R13'].forEach((r,i)=>sh.getRange(r).setValue(layLabels[i]).setBackground('#C62828').setFontColor(C.white).setFontWeight('bold').setHorizontalAlignment('center'));
  sh.setRowHeight(13,28);

  for (let i=0;i<6;i++) {
    const row=14+i, bg=i%2===0?C.white:C.altRow, bgB=i%2===0?C.white:C.altRowB, opt='Option '+(i+1);
    sh.getRange(row,2).setValue(opt).setBackground(bg).setHorizontalAlignment('center').setFontWeight('bold');
    [3,4].forEach(c=>sh.getRange(row,c).setBackground(bg));
    sh.getRange(row,5).setBackground(bg).setNumberFormat('M/d/yyyy');
    sh.getRange(row,6).setBackground(bg).setNumberFormat('h:mm AM/PM');
    sh.getRange(row,7).setBackground(bg).setNumberFormat('h:mm AM/PM');
    sh.getRange(row,8).setBackground(bg);
    sh.getRange(row,9).setBackground(bg).setNumberFormat('"$"#,##0.00');
    sh.getRange(row,11).setValue(opt).setBackground(bgB).setHorizontalAlignment('center').setFontWeight('bold');
    [12,13].forEach(c=>sh.getRange(row,c).setBackground(bgB));
    sh.getRange(row,14).setBackground(bgB).setNumberFormat('M/d/yyyy');
    sh.getRange(row,15).setBackground(bgB).setNumberFormat('h:mm AM/PM');
    sh.getRange(row,16).setBackground(bgB).setNumberFormat('h:mm AM/PM');
    sh.getRange(row,17).setBackground(bgB);
    sh.getRange(row,18).setBackground(bgB).setNumberFormat('"$"#,##0.00');
    sh.setRowHeight(row,24);
  }

  const retStart=21;
  sh.setRowHeight(retStart-1,10);
  sh.getRange(retStart,2,1,8).merge().setValue('✈  PERSON A  —  RETURN FLIGHTS').setBackground(C.personA).setFontColor(C.white).setFontSize(13).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.getRange(retStart,11,1,8).merge().setValue('✈  PERSON B  —  RETURN FLIGHTS').setBackground(C.personB).setFontColor(C.white).setFontSize(13).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(retStart,36);

  const retLabRow=retStart+1;
  ['B','C','D','E','F','G','H','I'].forEach((col,i)=>sh.getRange(col+retLabRow).setValue(labels[i]).setBackground('#3949AB').setFontColor(C.white).setFontWeight('bold').setHorizontalAlignment('center'));
  ['K','L','M','N','O','P','Q','R'].forEach((col,i)=>sh.getRange(col+retLabRow).setValue(labels[i]).setBackground('#C62828').setFontColor(C.white).setFontWeight('bold').setHorizontalAlignment('center'));
  sh.setRowHeight(retLabRow,28);

  for (let i=0;i<6;i++) {
    const row=retStart+2+i, bg=i%2===0?C.white:C.altRow, bgB=i%2===0?C.white:C.altRowB, opt='Option '+(i+1);
    sh.getRange(row,2).setValue(opt).setBackground(bg).setHorizontalAlignment('center').setFontWeight('bold');
    sh.getRange(row,3).setBackground(bg); sh.getRange(row,4).setBackground(bg);
    sh.getRange(row,5).setBackground(bg).setNumberFormat('M/d/yyyy');
    sh.getRange(row,6).setBackground(bg).setNumberFormat('h:mm AM/PM');
    sh.getRange(row,7).setBackground(bg).setNumberFormat('h:mm AM/PM');
    sh.getRange(row,8).setBackground(bg);
    sh.getRange(row,9).setBackground(bg).setNumberFormat('"$"#,##0.00');
    sh.getRange(row,11).setValue(opt).setBackground(bgB).setHorizontalAlignment('center').setFontWeight('bold');
    sh.getRange(row,12).setBackground(bgB); sh.getRange(row,13).setBackground(bgB);
    sh.getRange(row,14).setBackground(bgB).setNumberFormat('M/d/yyyy');
    sh.getRange(row,15).setBackground(bgB).setNumberFormat('h:mm AM/PM');
    sh.getRange(row,16).setBackground(bgB).setNumberFormat('h:mm AM/PM');
    sh.getRange(row,17).setBackground(bgB);
    sh.getRange(row,18).setBackground(bgB).setNumberFormat('"$"#,##0.00');
    sh.setRowHeight(row,24);
  }

  const totalRow=retStart+8;
  sh.getRange(totalRow,2,1,7).merge().setValue('TOTAL PRICE — Enter combined round-trip cost per option').setBackground('#FFF176').setFontWeight('bold').setFontSize(11).setHorizontalAlignment('center');
  sh.getRange(totalRow,9).setValue('').setBackground('#FFD600').setFontWeight('bold').setNumberFormat('"$"#,##0.00');
  sh.getRange(totalRow,11,1,7).merge().setValue('TOTAL PRICE — Enter combined round-trip cost per option').setBackground('#FFCDD2').setFontWeight('bold').setFontSize(11).setHorizontalAlignment('center');
  sh.getRange(totalRow,18).setValue('').setBackground('#EF9A9A').setFontWeight('bold').setNumberFormat('"$"#,##0.00');
  sh.setRowHeight(totalRow,30);

  // Freeze top 4 rows only (no column freeze — avoids conflict with merged cells)
  sh.setFrozenRows(4);
  sh.getRange('B4:I'+totalRow).setBorder(true,true,true,true,true,true,'#9FA8DA',SpreadsheetApp.BorderStyle.SOLID);
  sh.getRange('K4:R'+totalRow).setBorder(true,true,true,true,true,true,'#FFCDD2',SpreadsheetApp.BorderStyle.SOLID);
}

function buildTimelineSheet(ss) {
  const sh = ss.insertSheet('📊 Timeline');
  sh.getRange('A1:AV1').merge().setValue('📊  FLIGHT TIMELINE — Overlap & Layover Coordination View')
    .setBackground('#1A237E').setFontColor('#FFFFFF').setFontSize(16).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(1,46);
  sh.getRange('A2:AV2').merge().setValue('Each column = 30 minutes (6 AM → midnight). Color cells to show who is in-air or on layover. See Legend row for colors.')
    .setBackground('#283593').setFontColor('#C5CAE9').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(2,28);

  sh.getRange('A3').setValue('Party / Option').setBackground('#37474F').setFontColor('#FFFFFF').setFontWeight('bold').setHorizontalAlignment('center');
  sh.setColumnWidth(1,160);
  sh.getRange('B3').setValue('Leg').setBackground('#37474F').setFontColor('#FFFFFF').setFontWeight('bold').setHorizontalAlignment('center');
  sh.setColumnWidth(2,60);

  for (let b=0;b<36;b++) {
    const col=b+3, totalMin=6*60+b*30, h=Math.floor(totalMin/60), m=totalMin%60;
    const ampm=h<12?'AM':'PM', dh=h===0?12:h>12?h-12:h;
    sh.getRange(3,col).setValue(dh+(m===0?':00':':30')+ampm)
      .setBackground(b%2===0?'#455A64':'#546E7A').setFontColor('#ECEFF1').setFontSize(8).setHorizontalAlignment('center');
    sh.setColumnWidth(col,52);
  }
  sh.setRowHeight(3,28);

  sh.getRange('A4').setValue('LEGEND →').setFontWeight('bold').setBackground('#ECEFF1');
  sh.getRange('B4:E4').merge().setValue('✈ In Air (A)').setBackground('#1565C0').setFontColor('#FFFFFF').setHorizontalAlignment('center').setFontWeight('bold');
  sh.getRange('F4:I4').merge().setValue('✈ In Air (B)').setBackground('#B71C1C').setFontColor('#FFFFFF').setHorizontalAlignment('center').setFontWeight('bold');
  sh.getRange('J4:M4').merge().setValue('🟡 BOTH In Air').setBackground('#F9A825').setFontColor('#000000').setHorizontalAlignment('center').setFontWeight('bold');
  sh.getRange('N4:Q4').merge().setValue('⏳ Layover (A)').setBackground('#42A5F5').setFontColor('#000000').setHorizontalAlignment('center');
  sh.getRange('R4:U4').merge().setValue('⏳ Layover (B)').setBackground('#EF9A9A').setFontColor('#000000').setHorizontalAlignment('center');
  sh.getRange('V4:Y4').merge().setValue('🟢 Layovers Coincide').setBackground('#2E7D32').setFontColor('#FFFFFF').setHorizontalAlignment('center');
  sh.setRowHeight(4,28);

  sh.getRange('A5:AV5').merge().setValue('Color cells in each row to match the in-air or layover window. Use the Legend above as your guide.')
    .setBackground('#E3F2FD').setFontSize(10).setWrap(true);
  sh.setRowHeight(5,36);

  const bgP={A:'#0D47A1',B:'#B71C1C'}, layC={A:'#90CAF9',B:'#FFCDD2'};
  let r=6;
  for (let opt=1;opt<=6;opt++) {
    sh.getRange(r,1,1,38).merge().setValue('  OPTION '+opt).setBackground('#263238').setFontColor('#ECEFF1').setFontWeight('bold').setFontSize(11);
    sh.setRowHeight(r,24); r++;
    for (const p of ['A','B']) {
      sh.getRange(r,1).setValue('Person '+p+' — Outbound').setBackground(bgP[p]).setFontColor('#FFFFFF').setFontWeight('bold');
      sh.getRange(r,2).setValue('Leg 1').setBackground(bgP[p]).setFontColor('#FFFFFF').setHorizontalAlignment('center');
      for (let b=0;b<36;b++) sh.getRange(r,b+3).setBackground('#ECEFF1');
      sh.setRowHeight(r,26); r++;
      sh.getRange(r,1).setValue('Person '+p+' — Layover').setBackground(layC[p]).setFontColor('#000000');
      sh.getRange(r,2).setValue('⏳').setBackground(layC[p]).setHorizontalAlignment('center');
      for (let b=0;b<36;b++) sh.getRange(r,b+3).setBackground('#FAFAFA');
      sh.setRowHeight(r,22); r++;
      sh.getRange(r,1).setValue('Person '+p+' — Return').setBackground(bgP[p]).setFontColor('#FFFFFF').setFontWeight('bold');
      sh.getRange(r,2).setValue('Leg 2').setBackground(bgP[p]).setFontColor('#FFFFFF').setHorizontalAlignment('center');
      for (let b=0;b<36;b++) sh.getRange(r,b+3).setBackground('#ECEFF1');
      sh.setRowHeight(r,26); r++;
    }
    sh.getRange(r,1,1,38).merge().setBackground('#CFD8DC'); sh.setRowHeight(r,6); r++;
  }

  sh.getRange(r,1,1,38).merge().setValue('🔍  OVERLAP & COORDINATION ANALYSIS')
    .setBackground('#1A237E').setFontColor('#FFFFFF').setFontSize(13).setFontWeight('bold').setHorizontalAlignment('center');
  sh.setRowHeight(r,32); r++;

  ['✅ Simultaneous in-air (both flying same window)','❌ Non-overlapping (one lands before other departs)',
   '⏳ Person A layover matches Person B in-air window','⏳ Person B layover matches Person A in-air window',
   '🟢 Layovers coincide (both waiting at airport)','💰 Combined price — this option','⭐ Best overlap fit? (your rating)'
  ].forEach((lbl,i)=>{
    sh.getRange(r,1).setValue(lbl).setBackground(i%2===0?'#E8EAF6':'#FFFFFF').setFontSize(10).setWrap(true);
    for (let o=0;o<6;o++) sh.getRange(r,o+2).setValue('—').setHorizontalAlignment('center').setBackground(i%2===0?'#E8EAF6':'#FFFFFF');
    sh.setRowHeight(r,28); r++;
  });

  sh.setFrozenRows(3);
  sh.setFrozenColumns(2);
}

function buildSummarySheet(ss) {
  const sh=ss.insertSheet('📋 Summary');
  sh.getRange('A1:J1').merge().setValue('📋  FLIGHT DECISION SUMMARY')
    .setBackground('#1A237E').setFontColor('#FFFFFF').setFontSize(18).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(1,48);
  sh.getRange('A2:J2').merge().setValue('Compare all options and record your final decision.')
    .setBackground('#283593').setFontColor('#C5CAE9').setFontSize(11).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sh.setRowHeight(2,28);
  [200,140,140,100,100,120,120,120,120,160].forEach((w,i)=>sh.setColumnWidth(i+1,w));
  sh.getRange('A3:J3').setValues([['Criteria','Option 1','Option 2','Option 3','Option 4','Option 5','Option 6','','','Notes']])
    .setBackground('#37474F').setFontColor('#FFFFFF').setFontWeight('bold').setHorizontalAlignment('center');
  sh.setRowHeight(3,30);

  const rows=[
    ['👤 Person A — Outbound Departure','A'],['👤 Person A — Outbound Arrival','A'],
    ['👤 Person A — Layover Duration','A'],['👤 Person A — Return Departure','A'],
    ['👤 Person A — Return Arrival','A'],['👤 Person A — Airline(s)','A'],['💰 Person A — Price','A'],
    ['','sep'],
    ['👤 Person B — Outbound Departure','B'],['👤 Person B — Outbound Arrival','B'],
    ['👤 Person B — Layover Duration','B'],['👤 Person B — Return Departure','B'],
    ['👤 Person B — Return Arrival','B'],['👤 Person B — Airline(s)','B'],['💰 Person B — Price','B'],
    ['','sep'],
    ['✈ Both In-Air Same Time?','coord'],['⏳ A Layover During B Flight?','coord'],
    ['⏳ B Layover During A Flight?','coord'],['🟢 Layovers Coincide?','coord'],
    ['💰 COMBINED TOTAL PRICE','total'],['⭐ OVERALL SCORE (1–10)','total'],
  ];

  rows.forEach(([label,type],i)=>{
    const sr=4+i;
    const bg=type==='sep'?'#CFD8DC':type==='A'?(i%2===0?'#FFFFFF':'#E8EAF6'):
             type==='B'?(i%2===0?'#FFFFFF':'#FFEBEE'):type==='coord'?'#E8F5E9':'#FFF9C4';
    sh.getRange(sr,1).setValue(label).setBackground(bg).setFontWeight(type==='total'?'bold':'normal');
    for (let c=1;c<7;c++) sh.getRange(sr,c+1).setValue('').setBackground(bg).setHorizontalAlignment('center');
    sh.getRange(sr,8,1,3).merge().setValue('').setBackground(bg);
    sh.setRowHeight(sr,type==='sep'?8:26);
  });

  const fr=4+rows.length+2;
  sh.getRange(fr,1,1,10).merge().setValue('✅  FINAL DECISION')
    .setBackground('#1B5E20').setFontColor('#FFFFFF').setFontSize(14).setFontWeight('bold').setHorizontalAlignment('center');
  sh.setRowHeight(fr,36);

  ['Person A chose:','Person B chose:','Reason:','Booking # (A):','Booking # (B):',
   'Departure airport meetup:','Arrival airport meetup:','Notes:'].forEach((lbl,i)=>{
    const row=fr+1+i;
    sh.getRange(row,1,1,2).merge().setValue(lbl).setBackground('#E8F5E9').setFontWeight('bold');
    sh.getRange(row,3,1,8).merge().setValue('').setBackground('#FFFFFF')
      .setBorder(false,false,true,false,false,false,'#A5D6A7',SpreadsheetApp.BorderStyle.SOLID);
    sh.setRowHeight(row,28);
  });

  sh.setFrozenRows(3);
  sh.setFrozenColumns(1);
}
