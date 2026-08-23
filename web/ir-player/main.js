import {createSceneFromIR,parseSceneIR} from '../src/ir.js';
const $=id=>document.getElementById(id),canvas=$('canvas'),play=$('play'),slider=$('time'),readout=$('readout'),meta=$('meta');
const source=new URL(location.href).searchParams.get('src')??'./scene.zanim.json';
const ir=parseSceneIR(await (await fetch(source)).text());
const scene=await createSceneFromIR(canvas,ir,{renderer:{unitSize:ir.canvas.unit_size}});
slider.max=String(ir.duration);meta.textContent=`${ir.format} v${ir.version} · ${ir.canvas.width}×${ir.canvas.height} · ${ir.fps} fps · ${ir.objects.length} objects · ${ir.clips.length} clips`;
let running=false,raf=0,start=0;
function show(t){scene.seek(t);slider.value=String(t);readout.textContent=`${t.toFixed(2)} / ${scene.duration.toFixed(2)} s`;}
function tick(now){if(!running)return;let t=(now-start)/1000;if(t>=scene.duration){t=scene.duration;running=false;play.textContent='Play';}show(t);if(running)raf=requestAnimationFrame(tick);}
play.onclick=()=>{if(running){running=false;cancelAnimationFrame(raf);play.textContent='Play';return;}const from=Number(slider.value)>=scene.duration?0:Number(slider.value);start=performance.now()-from*1000;running=true;play.textContent='Pause';raf=requestAnimationFrame(tick);};
slider.oninput=()=>{running=false;cancelAnimationFrame(raf);play.textContent='Play';show(Number(slider.value));};
show(0);
