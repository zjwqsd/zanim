import { CanvasRenderer, ZanimWasm } from '../src/zanim.js';
import { sceneFromIR, validateSceneIR } from '../src/ir.js';
import { galleryEntries, galleryCounts } from './registry.js';

const wasm=await ZanimWasm.load('../dist/zanim_web_core.wasm');
const canvas=document.querySelector('#scene');
const renderer=new CanvasRenderer(canvas,wasm,{unitSize:90});
const select=document.querySelector('#demo');
const play=document.querySelector('#play');
const scrub=document.querySelector('#scrub');
const timeLabel=document.querySelector('#time');
const status=document.querySelector('#status');
const modeLabel=document.querySelector('#mode');

const groups={ts:document.createElement('optgroup'),ir:document.createElement('optgroup')};
groups.ts.label=`TypeScript replicas · ${galleryCounts.ts}`;
groups.ir.label=`Python Scene IR replays · ${galleryCounts.ir}`;
for(const [name,entry] of Object.entries(galleryEntries)){
  const o=document.createElement('option');o.value=name;o.textContent=name.replaceAll('_',' ');groups[entry.mode].append(o);
}
select.append(groups.ts,groups.ir);

let scene=null,raf=null,playing=false,start=0,lastFrame=0,loadGeneration=0;
const frameSamples=[],renderSamples=[];
function resetPerf(){frameSamples.length=0;renderSamples.length=0;lastFrame=0;}
function percentile(values,q){if(!values.length)return 0;const a=[...values].sort((x,y)=>x-y);return a[Math.min(a.length-1,Math.floor(a.length*q))];}
function sourceTag(){const meta=galleryEntries[select.value];if(meta.mode==='ir')return 'PYTHON IR';if(meta.status==='parity')return 'TS PARITY';if(meta.status==='prototype')return 'TS PROTOTYPE';return 'TS REPLICA';}
function perfText(){const tag=sourceTag();if(frameSamples.length<12)return `${tag} · ${galleryCounts.ts} TS + ${galleryCounts.ir} IR · ${galleryCounts.total}/29 shown`;const avg=frameSamples.reduce((a,b)=>a+b,0)/frameSamples.length,p95=percentile(frameSamples,.95),render=renderSamples.reduce((a,b)=>a+b,0)/renderSamples.length;return `${tag} · frame ${avg.toFixed(1)}ms · p95 ${p95.toFixed(1)}ms · render ${render.toFixed(1)}ms`;}
function setModeLabel(entry){modeLabel.textContent=entry.mode==='ir'?'Python IR Replay':'TypeScript Replica';modeLabel.dataset.mode=entry.mode;}
async function buildEntry(entry){
  if(entry.mode==='ts')return entry.build(renderer);
  const response=await fetch(entry.url,{cache:'no-cache'});if(!response.ok)throw new Error(`failed to load ${entry.url}: HTTP ${response.status}`);
  return sceneFromIR(validateSceneIR(await response.json()),renderer);
}
async function load(name,{time=0}={}){
  const generation=++loadGeneration;if(raf)cancelAnimationFrame(raf);playing=false;play.textContent='Play';play.disabled=true;resetPerf();
  const entry=galleryEntries[name];if(!entry)return;select.value=name;setModeLabel(entry);status.textContent=`${sourceTag()} · loading…`;
  try{
    const next=await buildEntry(entry);if(generation!==loadGeneration)return;scene?.pause?.();scene=next;scrub.max=scene.duration;scene.seek(Math.min(scene.duration,Math.max(0,time)));history.replaceState(null,'',`?demo=${name}`);play.disabled=false;sync();
  }catch(error){if(generation!==loadGeneration)return;status.textContent=`${sourceTag()} · ${error}`;console.error(error);}
}
function sync(){if(!scene)return;scrub.value=scene.time;timeLabel.textContent=`${scene.time.toFixed(2)} / ${scene.duration.toFixed(2)} s`;status.textContent=perfText();}
function tick(now){if(!playing||!scene)return;if(lastFrame){frameSamples.push(now-lastFrame);if(frameSamples.length>180)frameSamples.shift();}lastFrame=now;const t=(now-start)/1000;if(t>=scene.duration){scene.seek(scene.duration);playing=false;play.textContent='Play';sync();return;}scene.seek(t);renderSamples.push(scene.stats.renderMs);if(renderSamples.length>180)renderSamples.shift();sync();raf=requestAnimationFrame(tick);}
function togglePlay(){if(!scene)return;if(playing){playing=false;play.textContent='Play';if(raf)cancelAnimationFrame(raf);return;}if(scene.time>=scene.duration-.001)scene.seek(0);start=performance.now()-scene.time*1000;lastFrame=0;playing=true;play.textContent='Pause';raf=requestAnimationFrame(tick);}
play.onclick=togglePlay;
scrub.oninput=()=>{if(!scene)return;playing=false;play.textContent='Play';scene.seek(Number(scrub.value));sync();};
select.onchange=()=>load(select.value);
new ResizeObserver(()=>scene?.render()).observe(canvas);
const params=new URLSearchParams(location.search),requested=params.get('demo'),initial=galleryEntries[requested]?requested:'showcase/basics',initialTime=Number(params.get('t')||0);
await load(initial,{time:Number.isFinite(initialTime)?initialTime:0});if(params.get('autoplay')==='1')togglePlay();
