import {ZanimWasm,CanvasRenderer,Scene,LineSet,CircleSet,RectSet,Transform2D,TAU} from '../src/zanim.js';
const wasm=await ZanimWasm.load('../dist/zanim_web_core.wasm');
const canvas=document.querySelector('#scene'),renderer=new CanvasRenderer(canvas,wasm,{unitSize:72}),scene=new Scene(renderer);
const lines=[];for(let i=0;i<5000;i++){const a=i*.013;lines.push([-6*Math.cos(a),-3*Math.sin(a),6*Math.cos(a+.7),3*Math.sin(a+.7),'rgba(96,166,255,.20)',.7]);}
const circles=[];for(let i=0;i<1200;i++){const a=TAU*i/1200,r=.35+4.8*((i%53)/52);circles.push([r*Math.cos(a),.52*r*Math.sin(a),.025+(i%5)*.004,'rgba(82,205,150,.55)']);}
const rects=[];for(let i=0;i<600;i++){const x=-6+(i%60)*.2,y=-2.8+Math.floor(i/60)*.18;rects.push([x,y,.13,.10,'rgba(255,166,92,.45)']);}
const lineSet=new LineSet(lines),circleSet=new CircleSet(circles),rectSet=new RectSet(rects);scene.add(lineSet,circleSet,rectSet);
const frames=[],renders=[];let prev=performance.now(),start=prev,count=0;
function p95(a){const s=[...a].sort((x,y)=>x-y);return s[Math.min(s.length-1,Math.floor(s.length*.95))]??0;}
function tick(now){const dt=now-prev;prev=now;if(now-start>800){frames.push(dt);if(frames.length>240)frames.shift();}
 const t=(now-start)/1000;lineSet.transform=Transform2D.rotation(t*.18);circleSet.transform=Transform2D.rotation(-t*.23);rectSet.transform=Transform2D.rotation(t*.08);scene.time=t;scene.render();renders.push(scene.stats.renderMs);if(renders.length>240)renders.shift();count++;
 if(frames.length>60){const avg=frames.reduce((a,b)=>a+b,0)/frames.length,rav=renders.reduce((a,b)=>a+b,0)/renders.length,over=frames.filter(x=>x>18).length/frames.length*100;document.querySelector('#hud').textContent=`frames=${count}\nframe avg=${avg.toFixed(2)} ms p95=${p95(frames).toFixed(2)}\nrender avg=${rav.toFixed(2)} ms p95=${p95(renders).toFixed(2)}\n>18ms=${over.toFixed(1)}%\nlines=5000 circles=1200 rects=600`;}
 requestAnimationFrame(tick);}requestAnimationFrame(tick);
