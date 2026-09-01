import {createSceneFromIR,validateSceneIR} from '../web/src/ir.js';
import {configureTypstCompiler} from '../web/src/typst.js';

const $=id=>document.getElementById(id);
const canvas=$('canvas'),play=$('play'),reload=$('reload'),slider=$('time'),readout=$('readout'),status=$('status'),errorBox=$('error'),timelineRows=$('timelineRows'),timelineToggle=$('timelineToggle');
let ir=null,scene=null,running=false,raf=0,startClock=0,currentTime=0,selectedEvent=null,expanded=false,eventEls=[];

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const eventStart=e=>Number(e.type==='point'?e.time:e.start);
const eventEnd=e=>e.type==='point'?eventStart(e):eventStart(e)+Number(e.duration);
const eventActive=(e,t)=>e.type==='point'?Math.abs(t-eventStart(e))<=Math.max(.025,(scene?.duration??1)/600):t>=eventStart(e)&&t<eventEnd(e);
const timelineEvents=()=>ir?.debug?.timeline??[];

function overviewEvents(){
  const source=timelineEvents(),groups=new Map();
  for(const event of source){
    const start=eventStart(event),end=eventEnd(event);
    const key=event.type==='point'
      ? `point:${start.toFixed(9)}`
      : `span:${start.toFixed(9)}:${end.toFixed(9)}`;
    if(!groups.has(key))groups.set(key,[]);
    groups.get(key).push(event);
  }
  return [...groups.values()].map(items=>{
    const first=items[0];
    if(first.type==='point'){
      const actions=[...new Set(items.map(x=>String(x.action??'event')))];
      return {...first,_overviewItems:items,label:actions.length===1?`${items.length} ${actions[0]}`:`${items.length} lifecycle`};
    }
    const actions=[...new Set(items.map(x=>String(x.action??'event')))];
    const label=items.length===1?actions[0]:(actions.length===1?`${actions[0]} ×${items.length}`:`parallel ×${items.length}`);
    return {...first,_overviewItems:items,label};
  }).sort((a,b)=>eventStart(a)-eventStart(b)||eventEnd(a)-eventEnd(b));
}

function showError(value){errorBox.textContent=value||'';errorBox.classList.toggle('visible',!!value);}
function stop(){running=false;cancelAnimationFrame(raf);play.textContent='Play';}
function objectDebug(id){return ir?.debug?.objects?.[String(id)]??{};}
function objectLabel(record){
  if(Number(record.id)===0)return 'camera';
  const debug=objectDebug(record.id),name=debug.names?.[0];
  return name??`${debug.type??record.kind}#${record.id}`;
}

function layoutLanes(events,duration){
  const sorted=events.map((event,index)=>({event,index,start:eventStart(event),end:eventEnd(event)})).sort((a,b)=>a.start-b.start||a.end-b.end||a.index-b.index);
  const laneEnds=[],minWidth=Math.max(.025,duration*.006);
  for(const item of sorted){
    // Lifecycle points are markers, not timeline spans. Let them sit on top of
    // an animation that starts at the same instant instead of creating a lane.
    if(item.event.type==='point'){item.lane=0;continue;}
    const visualEnd=Math.max(item.end,item.start+minWidth);
    let lane=laneEnds.findIndex(end=>end<=item.start+1e-12);
    if(lane<0){lane=laneEnds.length;laneEnds.push(visualEnd);}else laneEnds[lane]=visualEnd;
    item.lane=lane;
  }
  return {items:sorted,lanes:Math.max(1,laneEnds.length)};
}

function makeAxis(duration){
  const axis=document.createElement('div');axis.className='track axis';
  const count=8;
  for(let i=0;i<=count;i++){
    const t=duration*i/count,tick=document.createElement('div');tick.className='tick';tick.style.left=`${100*i/count}%`;tick.innerHTML=`<span>${t.toFixed(duration<10?2:1)}s</span>`;axis.appendChild(tick);
  }
  return axis;
}

function makeTrack(events,duration,{overview=false}={}){
  const track=document.createElement('div');track.className=`track event-track${overview?' overview':''}`;
  const layout=layoutLanes(events,duration),laneH=overview?26:27;
  track.style.height=`${Math.max(overview?29:30,layout.lanes*laneH+3)}px`;
  for(const item of layout.items){
    const event=item.event,el=document.createElement('button'),start=item.start;
    el.type='button';
    el.className=`timeline-event ${event.type} action-${String(event.action??'event').replace(/[^a-z0-9_-]/gi,'-')}`;
    el.style.top=`${item.lane*laneH+(overview?3:4)}px`;
    el.style.left=`${100*start/duration}%`;
    if(event.type==='span')el.style.width=`max(${100*Math.max(0,Number(event.duration))/duration}%, 5px)`;

    const fullLabel=String(event.label??event.action??'event');
    const displayLabel=overview?String(event.label??event.action??'event'):String(event.action??fullLabel);
    if(event.type==='span')el.textContent=displayLabel;

    const when=event.type==='point'?`${start.toFixed(3)}s`:`${start.toFixed(3)}–${item.end.toFixed(3)}s`;
    const details=event._overviewItems?.map(x=>x.label).join('\n');
    el.title=`${details||fullLabel}\n${when}`;
    const globalIndex=event._overviewItems?.length===1?timelineEvents().indexOf(event._overviewItems[0]):timelineEvents().indexOf(event);
    el.onclick=e=>{e.stopPropagation();selectedEvent=globalIndex;stop();show(start);updateTimelineState();};
    eventEls.push({el,event,index:globalIndex});track.appendChild(el);
  }
  const head=document.createElement('div');head.className='playhead';track.appendChild(head);
  return track;
}

function recordsTree(){
  const records=[...(ir?.objects??[]),...(ir?.values??[])];
  const byId=new Map(records.map(record=>[Number(record.id),record]));
  const eventTargets=new Set(timelineEvents().flatMap(event=>(event.targets??[]).map(Number)));
  if(eventTargets.has(0)&&!byId.has(0))byId.set(0,{id:0,parent:null,kind:'camera2d'});
  const children=new Map();
  for(const record of byId.values()){
    const parent=record.parent==null?null:Number(record.parent);
    if(!children.has(parent))children.set(parent,[]);
    children.get(parent).push(record);
  }
  for(const list of children.values())list.sort((a,b)=>Number(a.id)-Number(b.id));
  return {byId,children};
}

function appendObjectRows(parentId,depth,tree,duration){
  for(const record of tree.children.get(parentId)??[]){
    if(Number(record.id)===0&&!(timelineEvents().some(e=>(e.targets??[]).map(Number).includes(0))))continue;
    const row=document.createElement('div');row.className='timeline-row object-row';
    const label=document.createElement('div');label.className='track-label object-label';label.style.paddingLeft=`${12+depth*18}px`;
    const hasChildren=(tree.children.get(Number(record.id))??[]).length>0;
    if(hasChildren){const branch=document.createElement('span');branch.className='branch';branch.textContent='↳';label.appendChild(branch);}
    const name=document.createElement('span');name.className='object-name';name.textContent=objectLabel(record);label.appendChild(name);
    const id=Number(record.id),events=timelineEvents().filter(event=>(event.targets??[]).map(Number).includes(id));
    row.append(label,makeTrack(events,duration));timelineRows.appendChild(row);
    appendObjectRows(id,depth+1,tree,duration);
  }
}

function renderTimeline(){
  timelineRows.textContent='';eventEls=[];selectedEvent=null;
  const duration=Math.max(Number(ir?.duration??0),1e-9),events=timelineEvents();

  const axisRow=document.createElement('div');axisRow.className='timeline-row axis-row';
  const axisLabel=document.createElement('div');axisLabel.className='track-label axis-label';axisLabel.textContent='';axisRow.append(axisLabel,makeAxis(duration));timelineRows.appendChild(axisRow);

  const totalRow=document.createElement('div');totalRow.className='timeline-row total-row';
  const totalLabel=document.createElement('button');totalLabel.type='button';totalLabel.className='track-label total-label';totalLabel.innerHTML=`<span class="caret">${expanded?'▾':'▸'}</span><strong>Scene</strong>`;
  totalLabel.onclick=e=>{e.stopPropagation();expanded=!expanded;renderTimeline();updateTimelineState();};
  totalRow.append(totalLabel,makeTrack(overviewEvents(),duration,{overview:true}));timelineRows.appendChild(totalRow);

  if(expanded){const tree=recordsTree();appendObjectRows(null,0,tree,duration);}
  timelineToggle.textContent=expanded?'Collapse':'Expand';
  updateTimelineState();
}

function updateTimelineState(){
  for(const item of eventEls){
    item.el.classList.toggle('active',eventActive(item.event,currentTime));
    item.el.classList.toggle('selected',selectedEvent===item.index);
    item.el.classList.toggle('passed',item.event.type==='point'&&currentTime>=eventStart(item.event));
  }
  const duration=Math.max(Number(scene?.duration??0),1e-9),left=`${100*clamp(currentTime/duration,0,1)}%`;
  for(const head of timelineRows.querySelectorAll('.playhead'))head.style.left=left;
}

function show(t){
  if(!scene)return;currentTime=clamp(Number(t),0,scene.duration);scene.seek(currentTime);slider.value=String(currentTime);readout.textContent=`${currentTime.toFixed(2)} / ${scene.duration.toFixed(2)} s`;updateTimelineState();
}
function tick(now){if(!running)return;let t=(now-startClock)/1000;if(t>=scene.duration){t=scene.duration;stop();}show(t);if(running)raf=requestAnimationFrame(tick);}

async function fetchJSON(url,options){const r=await fetch(url,{cache:'no-store',...options});const text=await r.text();let value;try{value=JSON.parse(text);}catch{value={error:text||`${r.status} ${r.statusText}`};}if(!r.ok)throw new Error(value.traceback||value.error||`${r.status} ${r.statusText}`);return value;}
configureTypstCompiler(async payload=>(await fetchJSON('/api/typst',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})).document);

async function loadScene(preserveTime=0){
  stop();showError('');status.textContent='Loading Scene IR…';
  try{
    const payload=await fetchJSON('/api/ir');ir=validateSceneIR(payload);canvas.style.aspectRatio=`${ir.canvas.width}/${ir.canvas.height}`;scene?.destroy?.();scene=await createSceneFromIR(canvas,ir,{renderer:{unitSize:Number(ir.canvas.unit_size)}});
    slider.max=String(ir.duration);renderTimeline();
    const rev=ir.meta?.preview_revision??'?',events=timelineEvents().length;status.textContent=`Web IR Preview · revision ${rev} · ${ir.canvas.width}×${ir.canvas.height} · ${ir.fps} fps · ${events} timeline events`;
    const meta=await fetchJSON('/api/meta');reload.disabled=!meta.reload_available;show(Math.min(Number(preserveTime)||0,scene.duration));
  }catch(err){showError(String(err.stack||err));status.textContent='Scene IR unavailable';reload.disabled=false;}
}

play.onclick=()=>{if(!scene)return;if(running){stop();return;}const from=currentTime>=scene.duration?0:currentTime;startClock=performance.now()-from*1000;running=true;play.textContent='Pause';raf=requestAnimationFrame(tick);};
slider.oninput=()=>{stop();show(Number(slider.value));};
reload.onclick=async()=>{stop();reload.disabled=true;showError('');try{const result=await fetchJSON(`/api/reload?t=${encodeURIComponent(currentTime)}`,{method:'POST'});await loadScene(result.time);}catch(err){showError(String(err.stack||err));reload.disabled=false;}};
timelineToggle.onclick=e=>{e.stopPropagation();expanded=!expanded;renderTimeline();};
timelineRows.onclick=e=>{if(!scene||e.target.closest('button'))return;const track=e.target.closest('.track');if(!track)return;const rect=track.getBoundingClientRect();selectedEvent=null;stop();show((e.clientX-rect.left)/rect.width*scene.duration);};
window.addEventListener('keydown',e=>{if(e.key===' '&&e.target===document.body){e.preventDefault();play.click();}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='r'){e.preventDefault();reload.click();}});
await loadScene(0);
