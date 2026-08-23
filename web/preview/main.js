import {createSceneFromIR,validateSceneIR} from '../web/src/ir.js';

const $=id=>document.getElementById(id);
const canvas=$('canvas'),play=$('play'),reload=$('reload'),slider=$('time'),readout=$('readout'),status=$('status'),errorBox=$('error'),objectsEl=$('objects'),sourceCode=$('sourceCode'),sourceHead=$('sourceHead');
let ir=null,scene=null,running=false,raf=0,startClock=0,currentTime=0,selectedId=null,selectedClip=null,sourceLines=[];

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const active=(span,t)=>t>=Number(span.start)&&t<Number(span.start)+Number(span.duration);
const objectDebug=id=>ir?.debug?.objects?.[String(id)]??{};
const objectLabel=record=>{const d=objectDebug(record.id),names=d.names??[];return names[0]??d.type??`${record.kind} #${record.id}`;};

function showError(value){errorBox.textContent=value||'';errorBox.classList.toggle('visible',!!value);}
function stop(){running=false;cancelAnimationFrame(raf);play.textContent='Play';}

function renderSource(){
  const src=ir?.debug?.source;
  sourceCode.textContent='';sourceLines=[];
  if(!src?.text){sourceHead.textContent='Source unavailable';sourceCode.innerHTML='<span class="empty">No source metadata in this Scene IR.</span>';return;}
  sourceHead.textContent=src.path;
  for(const line of src.text.split('\n')){const el=document.createElement('span');el.className='src-line';el.textContent=line||' ';sourceCode.appendChild(el);sourceLines.push(el);}
}
function sourceSpanForClip(clip){return clip?.debug?.source??null;}
function highlightSource(t){
  for(const el of sourceLines)el.classList.remove('active','selected');
  const spans=[];
  if(selectedClip!=null){const span=sourceSpanForClip(ir.clips[selectedClip]);if(span)spans.push([span,'selected']);}
  if(!spans.length)for(const clip of ir?.clips??[]){if(active(clip,t)){const span=sourceSpanForClip(clip);if(span)spans.push([span,'active']);}}
  for(const [span,cls] of spans)for(let line=Number(span.start_line);line<=Number(span.end_line);line++)sourceLines[line-1]?.classList.add(cls);
  if(selectedClip!=null&&spans[0])sourceLines[Math.max(0,Number(spans[0][0].start_line)-1)]?.scrollIntoView({block:'center'});
}

function clipsFor(record){return (ir?.clips??[]).map((clip,index)=>({clip,index})).filter(({clip})=>Number(clip.target)===Number(record.id));}
function renderInspector(t){
  if(!ir){objectsEl.innerHTML='';return;}
  const records=[...ir.objects,...(ir.values??[])].sort((a,b)=>Number(a.id)-Number(b.id));objectsEl.textContent='';
  for(const record of records){
    const birth=Number(record.birth??0),death=record.death==null?Infinity:Number(record.death),alive=t>=birth&&t<death;
    const row=document.createElement('div');row.className=`object${alive?'':' inactive'}${selectedId!==null&&Number(selectedId)===Number(record.id)?' selected':''}`;row.onclick=()=>{selectedId=record.id;selectedClip=null;renderInspector(currentTime);highlightSource(currentTime);};
    const title=document.createElement('div');title.className='object-title';title.innerHTML=`<span class="name">${objectLabel(record)}</span><span class="badge">${record.kind}</span>`;row.appendChild(title);
    if(selectedId!==null&&Number(selectedId)===Number(record.id)){
      const list=document.createElement('div');list.className='clips';
      const entries=clipsFor(record);
      if(!entries.length){const empty=document.createElement('div');empty.className='empty';empty.textContent=`lifetime [${birth.toFixed(2)}, ${Number.isFinite(death)?death.toFixed(2):'∞'})`;list.appendChild(empty);}
      for(const {clip,index} of entries){const el=document.createElement('div'),isActive=active(clip,t);el.className=`clip${isActive?' active':''}${selectedClip===index?' selected':''}`;el.textContent=`${clip.kind}  ${Number(clip.start).toFixed(2)}–${(Number(clip.start)+Number(clip.duration)).toFixed(2)}s`;el.onclick=e=>{e.stopPropagation();selectedClip=index;highlightSource(currentTime);renderInspector(currentTime);};list.appendChild(el);}
      row.appendChild(list);
    }
    objectsEl.appendChild(row);
  }
}

function show(t){
  if(!scene)return;currentTime=clamp(Number(t),0,scene.duration);scene.seek(currentTime);slider.value=String(currentTime);readout.textContent=`${currentTime.toFixed(2)} / ${scene.duration.toFixed(2)} s`;renderInspector(currentTime);highlightSource(currentTime);
}
function tick(now){if(!running)return;let t=(now-startClock)/1000;if(t>=scene.duration){t=scene.duration;stop();}show(t);if(running)raf=requestAnimationFrame(tick);}

async function fetchJSON(url,options){const r=await fetch(url,{cache:'no-store',...options});const text=await r.text();let value;try{value=JSON.parse(text);}catch{value={error:text||`${r.status} ${r.statusText}`};}if(!r.ok)throw new Error(value.traceback||value.error||`${r.status} ${r.statusText}`);return value;}
async function loadScene(preserveTime=0){
  stop();showError('');status.textContent='Loading Scene IR…';
  try{
    const payload=await fetchJSON('/api/ir');ir=validateSceneIR(payload);canvas.style.aspectRatio=`${ir.canvas.width}/${ir.canvas.height}`;scene?.destroy?.();scene=await createSceneFromIR(canvas,ir,{renderer:{unitSize:Number(ir.canvas.unit_size)}});
    slider.max=String(ir.duration);selectedClip=null;if(selectedId!=null&&!ir.objects.some(x=>Number(x.id)===Number(selectedId)))selectedId=null;renderSource();
    const rev=ir.meta?.preview_revision??'?';status.textContent=`Web IR Preview · revision ${rev} · ${ir.canvas.width}×${ir.canvas.height} · ${ir.fps} fps · ${ir.objects.length} objects · ${ir.clips.length} clips`;
    const meta=await fetchJSON('/api/meta');reload.disabled=!meta.reload_available;show(Math.min(Number(preserveTime)||0,scene.duration));
  }catch(err){showError(String(err.stack||err));status.textContent='Scene IR unavailable';reload.disabled=false;}
}

play.onclick=()=>{if(!scene)return;if(running){stop();return;}const from=currentTime>=scene.duration?0:currentTime;startClock=performance.now()-from*1000;running=true;play.textContent='Pause';raf=requestAnimationFrame(tick);};
slider.oninput=()=>{stop();show(Number(slider.value));};
reload.onclick=async()=>{stop();reload.disabled=true;showError('');try{const result=await fetchJSON(`/api/reload?t=${encodeURIComponent(currentTime)}`,{method:'POST'});await loadScene(result.time);}catch(err){showError(String(err.stack||err));reload.disabled=false;}};
window.addEventListener('keydown',e=>{if(e.key===' '&&e.target===document.body){e.preventDefault();play.click();}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='r'){e.preventDefault();reload.click();}});
await loadScene(0);
