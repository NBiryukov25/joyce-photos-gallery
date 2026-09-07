import { ANGLES, FRAMINGS, PRESERVATIONS, DEFAULT_PRESERVATION, autoPack, defaultCrop } from './presets.js';
import { ApiClient, uploadForm } from './api-client.js';
import { apiBase } from './config.js';
const template="<link rel=\"stylesheet\" href=\"STYLE_URL\"><section id=\"sign-in\" class=\"panel\"><h2>Connect to ANGLE PACK</h2><p>Use your app password. The image provider credentials stay on the server.</p><form id=\"sign-in-form\"><label>App password<input id=\"password\" type=\"password\" autocomplete=\"current-password\" required minlength=\"12\"></label><button class=\"primary\">Sign in</button></form><button id=\"reconnect\">Reconnect backend</button><p id=\"connection\" role=\"status\"></p></section>\n<header><a class=\"brand\" href=\"#\" aria-label=\"ANGLE PACK home\"><span class=\"brand-icon\">◩</span> ANGLE PACK</a><span class=\"header-note\">ONE SESSION. MORE PERSPECTIVES.</span><span id=\"environment\" class=\"badge\">Loading…</span><button id=\"logout\" hidden>Sign out</button></header>\n<main>\n<div class=\"intro\"><div><p class=\"eyebrow\">THE PHOTO WORKSPACE</p><h1>Explore another angle.</h1><p>Build a consistent set of photographs from the same session.</p></div><div class=\"session-control\"><label for=\"sessions\">Saved sessions</label><select id=\"sessions\"><option value=\"\">New session</option></select></div></div>\n<div id=\"error\" role=\"alert\" hidden></div>\n<div class=\"workspace\">\n<aside>\n<section class=\"panel\"><div class=\"section-heading\"><h2>01 / Reference photos</h2><span id=\"ref-count\">0 / 5</span></div>\n<label class=\"upload\" id=\"drop-zone\"><span class=\"upload-icon\">＋</span><strong>Upload 1–5 photographs</strong><span>Choose files or drop them here</span><small>JPEG, PNG, WebP · up to 15 MB each</small><input id=\"upload\" type=\"file\" accept=\"image/jpeg,image/png,image/webp\" multiple></label>\n<div id=\"references\" class=\"references\"></div><p class=\"hint\">Use the same subject and photo session. Optional view labels help the automatic pack avoid repeated angles.</p></section>\n<section class=\"panel\"><h2>02 / Operation</h2><div id=\"modes\" class=\"modes\">\n<button data-mode=\"CROP_ZOOM\"><strong>Crop Zoom</strong><span>Frame existing pixels · no API cost</span></button>\n<button data-mode=\"OUTPAINT_ZOOM\"><strong>Outpaint Zoom</strong><span>Reconstruct beyond the original edges</span></button>\n<button class=\"selected\" data-mode=\"GENERATIVE_ANGLE\"><strong>Generative Angle</strong><span>Move the virtual camera around the subject</span></button>\n</div><p id=\"mode-note\" class=\"hint\"></p></section>\n<section class=\"panel\"><details><summary>Preservation <span class=\"small-badge\">Consistency controls</span></summary><button id=\"preserve-all\" class=\"secondary compact\">PRESERVE ALL: HIGH</button><div id=\"preservation\" class=\"preservation\"></div></details><label for=\"notes\" class=\"notes-label\">Session instructions <span class=\"muted\">(optional)</span></label><textarea id=\"notes\" maxlength=\"2000\" rows=\"3\" placeholder=\"Details the references should establish together…\"></textarea></section>\n</aside>\n<div class=\"work-area\">\n<section class=\"panel pack-panel\"><div class=\"section-heading\"><div><p class=\"eyebrow\">YOUR SHOT LIST</p><h2>03 / Angle pack</h2></div><button id=\"auto\" class=\"secondary\">✧ AUTO ANGLE PACK</button></div>\n<div class=\"count-row\"><span>Number of outputs</span><div id=\"counts\" class=\"segmented\" aria-label=\"Number of outputs\"></div></div>\n<div id=\"outputs\" class=\"outputs\"></div>\n<div class=\"submission\"><div class=\"execution\"><label for=\"execution\">Generation mode</label><select id=\"execution\"><option value=\"MOCK\">MOCK — no API credits</option><option value=\"LIVE\">LIVE — uses API credits</option></select><p id=\"cost-summary\" class=\"hint\"></p></div><button id=\"generate\" class=\"primary\">GENERATE 1 IMAGE ↗</button></div>\n<p class=\"limitation\">Generative angles are plausible AI reconstructions, not mathematically exact views of the original scene.</p>\n</section>\n<section class=\"panel gallery-panel\"><div class=\"section-heading\"><div><p class=\"eyebrow\">THE CONTACT SHEET</p><h2>04 / Results</h2></div><a id=\"manifest\" hidden>Download manifest ↗</a></div>\n<div id=\"progress-area\" hidden><div class=\"progress-line\"><span id=\"progress-label\" role=\"status\" aria-live=\"polite\"></span><span id=\"progress-count\"></span></div><progress id=\"progress\" max=\"5\" value=\"0\"></progress></div>\n<div id=\"gallery\" class=\"gallery\"><div class=\"empty\"><div class=\"empty-frame\">＋</div><h3>Your next perspective starts here.</h3><p>Add your references, choose a shot list, and generate.</p></div></div><p id=\"save-path\" class=\"hint path\"></p></section>\n</div></div>\n</main><footer>ANGLE PACK <span>Temporary server files · download before restart or redeploy</span></footer>\n<dialog id=\"edit-dialog\"><form id=\"edit-form\"><div class=\"section-heading\"><h2>Edit this output</h2><button type=\"button\" id=\"close-dialog\" aria-label=\"Close\">✕</button></div><p id=\"edit-description\" class=\"hint\"></p><div id=\"edit-controls\"></div><p id=\"edit-cost\" class=\"hint\"></p><button type=\"submit\" class=\"primary\">GENERATE THIS IMAGE</button></form></dialog>\n";
class AnglePackTool extends HTMLElement {
connectedCallback(){if(this.shadowRoot)return;const root=this.attachShadow({mode:'open'});root.innerHTML=template.replace('STYLE_URL',new URL('./style.css',import.meta.url).href);
const $=id=>root.getElementById(id);
const client=new ApiClient(apiBase());
root.querySelector('.brand').onclick=e=>{e.preventDefault();root.querySelector('main').scrollIntoView({behavior:'smooth'});};
const state={refs:[],mode:'GENERATIVE_ANGLE',outputs:[{angle:'LEFT_3Q',framing:'WAIST',custom:'',sourceIndex:0,expansion:1.6}],preservation:{...DEFAULT_PRESERVATION},job:null,busy:false,config:null,edit:null};
let pollTimer;
const el=(tag,attrs={},text)=>{const node=document.createElement(tag);for(const [k,v] of Object.entries(attrs)) {if(k==='class') node.className=v;else node.setAttribute(k,v);}if(text!==undefined)node.textContent=text;return node;};
function message(text='') {$('error').textContent=text;$('error').hidden=!text;}
async function api(url,options={}){try{return await client.request(url,options);}catch(error){if(error.status===401)$('sign-in').hidden=false;throw error;}}
function asset(node,path,attribute='href',download){client.blobUrl(path).then(url=>{node.setAttribute(attribute,url);if(download)node.download=download;}).catch(error=>message(error.message));}
function selectField(label,choices,value,onChange) {
  const field=el('div',{class:'field'}), lab=el('label',{},label), select=el('select',{'aria-label':label});
  for(const [key,name] of Object.entries(choices))select.append(el('option',{value:key},name));
  select.value=String(value);select.addEventListener('change',()=>onChange(select.value));lab.append(select);field.append(lab);return field;
}
function currentExecution(){return $('execution').value;}
function renderReferences() {
  $('references').replaceChildren();$('ref-count').textContent=`${state.refs.length} / 5`;
  state.refs.forEach((ref,i)=>{
    const box=el('div',{class:'reference'}),img=el('img',{src:ref.url,alt:`Reference ${i+1}: ${ref.name}`});
    const remove=el('button',{class:'remove','aria-label':`Remove reference ${i+1}`},'×');remove.disabled=state.busy;
    remove.onclick=()=>{if(ref.file)URL.revokeObjectURL(ref.url);state.refs.splice(i,1);state.outputs.forEach(o=>{o.sourceIndex=o.sourceIndex===i?0:o.sourceIndex>i?o.sourceIndex-1:o.sourceIndex;});renderReferences();renderOutputs();};
    box.append(img,remove,el('p',{},`${i+1}. ${ref.name}`));
    const field=selectField(`Reference ${i+1} angle`,{UNKNOWN:'View: not labeled',...ANGLES},ref.angle,v=>ref.angle=v);
    field.querySelector('select').disabled=state.busy;box.append(field);$('references').append(box);
  });updateSubmission();
}
async function addFiles(files) {
  message();const list=[...files];
  if(state.refs.length+list.length>5)return message('Use a maximum of five reference photos. Remove one before adding more.');
  if(list.some(f=>!['image/png','image/jpeg','image/webp'].includes(f.type)||f.size>15*1024*1024))return message('Use JPEG, PNG or WebP files, each no larger than 15 MB.');
  for(const file of list){const url=URL.createObjectURL(file),img=new Image();img.src=url;try{await img.decode();state.refs.push({file,url,name:file.name,angle:'UNKNOWN'});}catch{URL.revokeObjectURL(url);message(`Could not read ${file.name}.`);}}
  renderReferences();renderOutputs();
}
function renderPreservation() {
  $('preservation').replaceChildren();
  for(const key of PRESERVATIONS){const field=selectField(key.replaceAll('_',' '),{OFF:'OFF',MEDIUM:'MEDIUM',HIGH:'HIGH'},state.preservation[key],v=>state.preservation[key]=v);$('preservation').append(field);}
}
function renderCounts() {
  $('counts').replaceChildren();for(let n=1;n<=5;n++){const b=el('button',{'aria-pressed':String(n===state.outputs.length),class:n===state.outputs.length?'selected':''},String(n));b.disabled=state.busy;b.onclick=()=>{state.outputs=Array.from({length:n},(_,i)=>state.outputs[i]||{angle:'FRONT',framing:'FULL_BODY',sourceIndex:0,custom:'',expansion:1.6});renderCounts();renderOutputs();};$('counts').append(b);}
}
function drawCrop(canvas,ref,crop) {
  if(!ref)return;const img=new Image();img.onload=()=>{canvas.width=img.width;canvas.height=img.height;const ctx=canvas.getContext('2d');ctx.drawImage(img,0,0);ctx.fillStyle='#10231ba8';ctx.fillRect(0,0,img.width,img.height);const x=crop.x*img.width,y=crop.y*img.height,w=crop.w*img.width,h=crop.h*img.height;ctx.drawImage(img,x,y,w,h,x,y,w,h);ctx.strokeStyle='#d8f49b';ctx.lineWidth=Math.max(2,img.width/250);ctx.strokeRect(x,y,w,h);};img.src=ref.url;
}
function outputControls(out,i,mode,refs,refresh) {
  const row=el('div',{class:'output-row'});row.append(el('span',{class:'shot-number'},String(i+1).padStart(2,'0')));
  if(mode==='GENERATIVE_ANGLE')row.append(selectField(`Angle · output ${i+1}`,ANGLES,out.angle,v=>{out.angle=v;refresh();}));
  else row.append(selectField(`Source photo · output ${i+1}`,Object.fromEntries(refs.map((r,i)=>[i,`Reference ${i+1}`])),out.sourceIndex,v=>{out.sourceIndex=Number(v);refresh();}));
  row.append(selectField(`Framing · output ${i+1}`,FRAMINGS,out.framing,v=>{out.framing=v;delete out.crop;refresh();}));
  if(mode==='GENERATIVE_ANGLE' && out.angle==='CUSTOM') {
    const field=el('div',{class:'custom'}),lab=el('label',{},'Custom camera position'),text=el('textarea',{rows:'2',maxlength:'1500',placeholder:'Describe where the photographer moves…',required:''});text.value=out.custom||'';text.oninput=()=>out.custom=text.value;lab.append(text);field.append(lab);row.append(field);
  }
  if(mode==='OUTPAINT_ZOOM') {
    const field=el('div',{class:'full'}),lab=el('label',{},`Expand canvas: ${out.expansion||1.6}×`),range=el('input',{type:'range',min:'1.1',max:'3',step:'.1','aria-label':'Canvas expansion'});range.value=out.expansion||1.6;range.oninput=()=>{out.expansion=Number(range.value);lab.textContent=`Expand canvas: ${range.value}×`;};field.append(lab,range,el('p',{class:'hint'},'Keeps the source camera direction. The model fills new surroundings; prompt-guided extension preserves continuity but does not guarantee exact pixels.'));row.append(field);
  }
  if(mode==='CROP_ZOOM') {
    out.crop ||= defaultCrop(out.framing);const tools=el('div',{class:'crop-tools'}),canvas=el('canvas',{'aria-label':'Crop preview'}),sliders=el('div',{class:'crop-sliders'});
    tools.append(el('p',{class:'hint'},'Adjust the highlighted area. Presets are starting rectangles, not automatic body detection. Full body is possible only if it is already visible.'),canvas,sliders);
    for(const [key,title] of Object.entries({x:'Left',y:'Top',w:'Width',h:'Height'})){
      const lab=el('label',{},title),input=el('input',{type:'range',min:key==='w'||key==='h'?'1':'0',max:'100',step:'1','aria-label':`Crop ${title}`});input.value=Math.round(out.crop[key]*100);
      input.oninput=()=>{out.crop[key]=Number(input.value)/100;if(key==='x'||key==='w')out.crop.x=Math.min(out.crop.x,1-out.crop.w);if(key==='y'||key==='h')out.crop.y=Math.min(out.crop.y,1-out.crop.h);for(const slider of sliders.querySelectorAll('input'))slider.value=Math.round(out.crop[slider.dataset.key]*100);drawCrop(canvas,refs[out.sourceIndex],out.crop);};input.dataset.key=key;lab.append(input);sliders.append(lab);
    }
    row.append(tools);drawCrop(canvas,refs[out.sourceIndex],out.crop);
  }
  return row;
}
function renderOutputs() {
  $('outputs').replaceChildren();state.outputs.forEach((out,i)=>$('outputs').append(outputControls(out,i,state.mode,state.refs,renderOutputs)));
  $('outputs').querySelectorAll('input,select,textarea').forEach(n=>n.disabled=state.busy);updateSubmission();
}
function setMode(mode) {
  state.mode=mode;root.querySelectorAll('[data-mode]').forEach(b=>{b.classList.toggle('selected',b.dataset.mode===mode);b.setAttribute('aria-pressed',String(b.dataset.mode===mode));});
  $('mode-note').textContent={GENERATIVE_ANGLE:'A new camera viewpoint inferred from all references. Left and right refer to the subject’s own sides.',OUTPAINT_ZOOM:'Generatively expands the photograph beyond its edges. Uses all references for continuity.',CROP_ZOOM:'Local crop only. No new pixels or camera angles are generated. All API calls are bypassed.'}[mode];
  $('auto').disabled=state.busy||mode!=='GENERATIVE_ANGLE';renderOutputs();
}
function updateSubmission() {
  const n=state.outputs.length,paid=currentExecution()==='LIVE'&&state.mode!=='CROP_ZOOM';
  $('generate').textContent=state.busy?'GENERATION IN PROGRESS…':`GENERATE ${n} IMAGE${n>1?'S':''} ↗`;
  $('generate').disabled=state.busy||!state.refs.length||!state.config||(paid&&!state.config.liveAvailable);
  $('cost-summary').textContent=state.mode==='CROP_ZOOM'?`${n} local crops · 0 API requests.`:paid?`${n} images · ${n} paid image-edit requests · ${state.config?.quality} · ${state.config?.size}.`:`${n} labeled mock previews · 0 API requests. No new viewpoints in mock mode.`;
}
function setBusy(busy){state.busy=busy;$('upload').disabled=busy;$('execution').disabled=busy;$('sessions').disabled=busy;$('notes').disabled=busy;$('preserve-all').disabled=busy;root.querySelectorAll('[data-mode],#preservation select').forEach(n=>n.disabled=busy);renderCounts();renderOutputs();renderReferences();$('auto').disabled=busy||state.mode!=='GENERATIVE_ANGLE';}
function fileUrl(job,name){return `/api/sessions/${job.id}/file/${encodeURIComponent(name)}`;}
function renderGallery() {
  const job=state.job;if(!job)return;$('gallery').replaceChildren();
  const finished=job.outputs.filter(o=>['complete','failed','interrupted'].includes(o.status)).length;
  $('progress-area').hidden=false;$('progress').max=job.outputs.length;$('progress').value=finished;
  $('progress-label').textContent=state.busy?'Generating sequentially — you can leave this page open.':`Session ${job.status}${job.execution==='MOCK'&&job.mode!=='CROP_ZOOM'?' · MOCK previews only':''}`;
  $('progress-count').textContent=`${finished} / ${job.outputs.length}`;
  $('manifest').hidden=state.busy;if(!state.busy){client.invalidate(fileUrl(job,'manifest.json'));asset($('manifest'),fileUrl(job,'manifest.json'),'href','manifest.json');}
  $('save-path').textContent=`${state.config.hosted?'Temporary server files — download now; files may be lost on restart':'Saved locally'}: ${state.config.dataDir} / ${job.id}`;
  job.outputs.forEach((out,i)=>{
    const card=el('article',{class:'result'});
    if(out.status==='complete') {const link=el('a',{target:'_blank',rel:'noopener'}),img=el('img',{alt:`Output ${i+1}: ${ANGLES[out.angle]}, ${FRAMINGS[out.framing]}`});asset(link,fileUrl(job,out.generatedFilename));asset(img,fileUrl(job,out.generatedFilename),'src');link.append(img);card.append(link);}
    else card.append(el('div',{class:'result-placeholder'},out.status==='running'?(out.providerProgress||'Creating this image…'):out.status));
    const body=el('div',{class:'result-body'});body.append(el('h3',{},`${String(i+1).padStart(2,'0')} / ${job.mode==='GENERATIVE_ANGLE'?ANGLES[out.angle]:'Source view'} · ${FRAMINGS[out.framing]}`),el('p',{},`${out.execution||job.execution} · ${job.mode} · Revision ${out.history.length+1}`));
    if(out.error)body.append(el('p',{class:'error-text'},out.error));
    const actions=el('div',{class:'result-actions'});
    for(const title of ['REGENERATE',...(job.mode==='GENERATIVE_ANGLE'?['CHANGE ANGLE']:[]),'CHANGE ZOOM/FRAMING']){const button=el('button',{},title);button.disabled=state.busy;button.onclick=()=>openEdit(i,title).catch(error=>message(error.message));actions.append(button);}
    if(out.status==='complete'){const link=el('a',{},'Download PNG');asset(link,fileUrl(job,out.generatedFilename),'href',out.generatedFilename);body.append(link);}
    body.append(actions);
    const completeVersions=out.history.filter(o=>o.status==='complete');
    if(completeVersions.length){const versions=el('details');versions.append(el('summary',{},'Previous versions'));for(const prior of completeVersions){const p=el('p'),a=el('a',{},prior.generatedFilename);asset(a,fileUrl(job,prior.generatedFilename),'href',prior.generatedFilename);p.append(a);versions.append(p);}body.append(versions);}
    card.append(body);$('gallery').append(card);
  });
}
async function refreshSessions() {
  const list=await api('/api/sessions');$('sessions').replaceChildren(el('option',{value:''},'New session'));
  for(const job of list)$('sessions').append(el('option',{value:job.id},`${new Date(job.createdAt).toLocaleString()} · ${job.count} · ${job.execution}`));
  $('sessions').value=state.job?.id||'';
}
async function followJob(job) {
  clearTimeout(pollTimer);state.job=job;setBusy(['running','queued'].includes(job.status));renderGallery();
  if(state.busy)pollTimer=setTimeout(async()=>{try{await followJob(await api(`/api/sessions/${job.id}`));}catch(error){if([401,404].includes(error.status)){setBusy(false);message(error.message);return;}message(`Progress connection lost: ${error.message} The server may still be generating. Reconnecting…`);pollTimer=setTimeout(()=>followJob(job),5000);}},1000);
  else await refreshSessions();
}
async function generate() {
  message();if(state.outputs.some(o=>state.mode==='GENERATIVE_ANGLE'&&o.angle==='CUSTOM'&&!o.custom.trim()))return message('Describe each custom camera position before generating.');
  setBusy(true);$('progress-area').hidden=false;$('progress-label').textContent='Uploading reference photos…';
  try {
    const references=await Promise.all(state.refs.map(async ref=>({name:ref.name,file:ref.file||await fetch(ref.url).then(r=>{if(!r.ok)throw new Error('Could not load saved reference');return r.blob();})})));
    const outputs=state.outputs.map(o=>({...o,...(state.mode!=='GENERATIVE_ANGLE'?{angle:'FRONT',custom:''}:{})}));
    const form=uploadForm(references,{mode:state.mode,execution:currentExecution(),outputs,preservation:state.preservation,referenceAngles:state.refs.map(r=>r.angle),notes:$('notes').value});
    await followJob(await api('/api/jobs',{method:'POST',body:form}));
  }catch(error){message(`${error.message} If submission lost its connection, check Saved sessions before submitting again.`);setBusy(false);await refreshSessions().catch(()=>{});}
}
async function openEdit(index,action) {
  const original=state.job.outputs[index];state.edit={index,output:structuredClone(original)};
  $('edit-description').textContent=`${action} · only output ${index+1}. Saved session references and preservation settings will be used. Previous files remain available.`;
  const refs=await Promise.all(state.job.references.map(async(r,i)=>({url:await client.blobUrl(`/api/sessions/${state.job.id}/reference/${i}`),name:r.originalName})));
  const refresh=()=>{$('edit-controls').replaceChildren(outputControls(state.edit.output,index,state.job.mode,refs,refresh));};refresh();
  $('edit-cost').textContent=currentExecution()==='LIVE'&&state.job.mode!=='CROP_ZOOM'?'1 paid image-edit request when you press GENERATE THIS IMAGE.':state.job.mode==='CROP_ZOOM'?'1 local crop · 0 API requests.':'1 MOCK preview · 0 API requests.';
  $('edit-dialog').showModal();
}
async function loadSession(id) {
  message();clearTimeout(pollTimer);
  if(!id){state.job=null;state.refs=[];clearTimeout(pollTimer);$('gallery').replaceChildren();$('manifest').hidden=true;$('progress-area').hidden=true;setBusy(false);return;}
  const job=await api(`/api/sessions/${id}`);
  state.refs.forEach(r=>{if(r.file)URL.revokeObjectURL(r.url);});
  state.refs=await Promise.all(job.references.map(async(r,i)=>({name:r.originalName,url:await client.blobUrl(`/api/sessions/${id}/reference/${i}`),angle:r.angle})));
  state.outputs=job.outputs.map(o=>structuredClone(o));state.preservation={...job.preservation};$('notes').value=job.notes;
  // Opening a saved session never arms live mode.
  $('execution').value='MOCK';renderPreservation();setMode(job.mode);await followJob(job);
}
$('upload').onchange=async event=>{await addFiles(event.target.files);event.target.value='';};
$('drop-zone').ondragover=e=>{e.preventDefault();$('drop-zone').classList.add('dragging');};
$('drop-zone').ondragleave=()=> $('drop-zone').classList.remove('dragging');
$('drop-zone').ondrop=async e=>{e.preventDefault();$('drop-zone').classList.remove('dragging');if(!state.busy)await addFiles(e.dataTransfer.files);};
root.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>setMode(b.dataset.mode));
$('preserve-all').onclick=()=>{state.preservation={...DEFAULT_PRESERVATION};renderPreservation();};
$('auto').onclick=()=>{state.outputs=autoPack(state.outputs.length,state.refs.map(r=>r.angle));renderOutputs();};
$('generate').onclick=generate;$('execution').onchange=updateSubmission;
$('sessions').onchange=e=>loadSession(e.target.value).catch(error=>message(error.message));
$('close-dialog').onclick=()=>$('edit-dialog').close();
$('edit-form').onsubmit=async e=>{e.preventDefault();const edit=state.edit;if(!edit)return;$('edit-dialog').close();message();setBusy(true);try{await followJob(await api(`/api/sessions/${state.job.id}/outputs/${edit.index}/regenerate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({output:edit.output,execution:currentExecution()})}));}catch(error){setBusy(false);message(error.message);renderGallery();}};
$('logout').onclick=async()=>{try{await api('/api/auth/logout',{method:'POST'});client.clear();state.config=null;clearTimeout(pollTimer);$('sign-in').hidden=false;setBusy(false);$('gallery').replaceChildren();}catch(error){message(error.message);}};
async function init(){state.config=await api('/api/config');client.csrf=state.config.token;$('sign-in').hidden=true;$('connection').textContent='Connected';$('logout').hidden=!state.config.authEnabled;$('environment').textContent=state.config.mockOnly?'MOCK / DEVELOPMENT':state.config.hosted?'PRIVATE WORKSPACE':'LOCAL WORKSPACE';$('execution').querySelector('[value="LIVE"]').disabled=!state.config.liveAvailable;renderPreservation();renderCounts();renderReferences();setMode(state.mode);await refreshSessions();}
$('sign-in-form').onsubmit=async e=>{e.preventDefault();const password=$('password').value;$('password').value='';$('connection').textContent='Signing in…';try{await client.login(password);message();await init();}catch(error){$('connection').textContent=error.message;}};
$('reconnect').onclick=()=>init().catch(error=>$('connection').textContent=error.message);
renderPreservation();renderCounts();renderReferences();setMode(state.mode);
init().catch(error=>$('connection').textContent=error.message);
}
}
customElements.define('angle-pack-tool',AnglePackTool);
