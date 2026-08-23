import { CanvasRenderer, ZanimWasm } from '../src/zanim.js';
import { allDemos, demoMeta } from './registry.js';

const wasm=await ZanimWasm.load('../dist/zanim_web_core.wasm');
const canvas=document.querySelector('#scene');
const renderer=new CanvasRenderer(canvas,wasm,{unitSize:90});
const select=document.querySelector('#demo');
const play=document.querySelector('#play');
const scrub=document.querySelector('#scrub');
const timeLabel=document.querySelector('#time');
const status=document.querySelector('#status');
for(const name of Object.keys(allDemos)){const o=document.createElement('option');o.value=name;o.textContent=name.replaceAll('_',' ');select.append(o);}
let scene=null,raf=null,playing=false,start=0,lastFrame=0;
const frameSamples=[],renderSamples=[];
function resetPerf(){frameSamples.length=0;renderSamples.length=0;lastFrame=0;}
function percentile(values,q){if(!values.length)return 0;const a=[...values].sort((x,y)=>x-y);return a[Math.min(a.length-1,Math.floor(a.length*q))];}
function perfText(){const status=demoMeta[select.value]?.status,tag=status==='parity'?'PARITY':status==='native'?'NATIVE':'PROTOTYPE';if(frameSamples.length<12)return `${tag} · ${Object.keys(allDemos).length} gallery demos`;const avg=frameSamples.reduce((a,b)=>a+b,0)/frameSamples.length,p95=percentile(frameSamples,.95),render=renderSamples.reduce((a,b)=>a+b,0)/renderSamples.length;return `${tag} · frame ${avg.toFixed(1)}ms · p95 ${p95.toFixed(1)}ms · render ${render.toFixed(1)}ms`;}
function load(name){if(raf)cancelAnimationFrame(raf);playing=false;play.textContent='Play';resetPerf();scene=allDemos[name](renderer);scrub.max=scene.duration;scene.seek(0);status.textContent=perfText();history.replaceState(null,'',`?demo=${name}`);sync();}
function sync(){scrub.value=scene.time;timeLabel.textContent=`${scene.time.toFixed(2)} / ${scene.duration.toFixed(2)} s`;status.textContent=perfText();}
function tick(now){if(!playing)return;if(lastFrame){frameSamples.push(now-lastFrame);if(frameSamples.length>180)frameSamples.shift();}lastFrame=now;const t=(now-start)/1000;if(t>=scene.duration){scene.seek(scene.duration);playing=false;play.textContent='Play';sync();return;}scene.seek(t);renderSamples.push(scene.stats.renderMs);if(renderSamples.length>180)renderSamples.shift();sync();raf=requestAnimationFrame(tick);}
function togglePlay(){if(playing){playing=false;play.textContent='Play';if(raf)cancelAnimationFrame(raf);return;}if(scene.time>=scene.duration-.001)scene.seek(0);start=performance.now()-scene.time*1000;lastFrame=0;playing=true;play.textContent='Pause';raf=requestAnimationFrame(tick);}
play.onclick=togglePlay;
scrub.oninput=()=>{playing=false;play.textContent='Play';scene.seek(Number(scrub.value));sync();};
select.onchange=()=>load(select.value);
new ResizeObserver(()=>scene?.render()).observe(canvas);
const params=new URLSearchParams(location.search),initial=params.get('demo'),initialTime=Number(params.get('t')||0);select.value=allDemos[initial]?initial:'showcase/basics';load(select.value);if(Number.isFinite(initialTime)&&initialTime>0){scene.seek(Math.min(scene.duration,initialTime));sync();}if(params.get('autoplay')==='1')togglePlay();
