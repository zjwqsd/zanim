import {
  Scene, Transform2D, InfiniteGrid, Axes, CustomObject2D, Text, Easing, ScalarValue, LineSet, CircleSet,
  DynamicPolyline, DynamicRectSet, DynamicLineSet, DynamicCircleSet, DynamicTextSet, DynamicNumber, Polyline, Rectangle, RectSet, MandelbrotSet, JuliaSet, ComplexMappedGrid,
  WHITE, MUTED, BLUE, GREEN, RED, ORANGE, YELLOW, CYAN, PINK, PURPLE, GRAY,
  PI, TAU,
} from '../src/zanim.js';
import { SORTING_PARITY_DATA, RB_PARITY_DATA, NEURAL_PARITY_DATA } from './generated/parity_data.js';

const clamp01=x=>Math.max(0,Math.min(1,x));
const smooth=x=>{x=clamp01(x);return x*x*(3-2*x)};
const phase=(t,s,d)=>smooth((t-s)/d);
const rgba=(hex,a=.7)=>hex.startsWith('#')?`${hex}${Math.round(a*255).toString(16).padStart(2,'0')}`:hex;
const rgb=(r,g,b,a=255)=>`rgba(${r},${g},${b},${(a/255).toFixed(6)})`;
const rgbaArray=c=>c?rgb(c[0],c[1],c[2],c[3]):null;
const parityLineItems=items=>items.map(i=>[i[0],i[1],i[2],i[3],rgbaArray(i[4]),i[5]]);
const parityCircleItems=items=>items.map(i=>[i[0],i[1],i[2],rgbaArray(i[3]),rgbaArray(i[4]),i[5]]);
const T=(x=0,y=0)=>Transform2D.translation(x,y);
function header(scene,title,subtitle=''){scene.add(new Text(title,{fontSize:33,transform:T(0,3.16),zIndex:30}));if(subtitle)scene.add(new Text(subtitle,{fontSize:18,color:MUTED,transform:T(0,2.72),zIndex:30}));}
function finalize(scene,d){scene.duration=d;scene.cursor=d;return scene;}
function path(ctx,r,pts,{stroke=WHITE,width=2,close=false,fill=null}={}){if(!pts.length)return;ctx.beginPath();pts.forEach((p,i)=>{const d=r.toDevice(p[0],p[1]);i?ctx.lineTo(...d):ctx.moveTo(...d);});if(close)ctx.closePath();if(fill){ctx.fillStyle=fill;ctx.fill();}if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=width*r.dpr;ctx.lineJoin='round';ctx.lineCap='round';ctx.stroke();}}
function label(ctx,r,x,y,text,color=MUTED,size=16){const d=r.toDevice(x,y);ctx.fillStyle=color;ctx.font=`${size*r.dpr}px system-ui`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(text,d[0],d[1]);}
function lerp(a,b,t){return[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t]}

export function complex_mapping(renderer){
  const scene=new Scene(renderer);
  const title=new Text('Infinite complex-plane mappings',{fontSize:36,color:WHITE,opacity:0,zIndex:10,transform:T(0,4.25)});
  const subtitle=new Text('native inverse mapping · no source window · no sampled polylines',{fontSize:19,color:MUTED,opacity:0,zIndex:10,transform:T(0,3.82)});
  const legendH=new Text('Re(z) = constant',{fontSize:17,color:ORANGE,opacity:0,zIndex:10,transform:T(-4.75,3.33)});
  const legendV=new Text('Im(z) = constant',{fontSize:17,color:CYAN,opacity:0,zIndex:10,transform:T(-4.75,3.01)});
  scene.add(title,subtitle,legendH,legendV);
  scene.parallel(.7,api=>{api.fadeIn(title);api.fadeIn(subtitle);api.fadeIn(legendH);api.fadeIn(legendV);});
  scene.wait(.25);
  const run=(mapping,formula,{step=.5,mapParams=null}={})=>{
    const progress=new ScalarValue(0);scene.addValue(progress);
    const grid=scene.add(new ComplexMappedGrid(mapping,{step,progress,viewport:'canvas',strokePx:2.2,mapParams,opacity:0,zIndex:1,resolution:.18,minWidth:96}));
    const label=scene.add(new Text(formula,{fontSize:22,color:YELLOW,opacity:0,zIndex:10,transform:T(0,-4.18)}));
    scene.parallel(.42,api=>{api.fadeIn(grid);api.fadeIn(label);});
    scene.animateValue(progress,{to:1,duration:2.6,easing:Easing.SMOOTHSTEP});
    scene.wait(.65);
    scene.parallel(.34,api=>{api.fadeOut(grid);api.fadeOut(label);});
    scene.wait(.12);
  };
  run('square','H_a(z)=(1-a)z+a z²');
  run('reciprocal','H_a(z): z → 1/z');
  run('exp','F_a(z)=e^z-1+(1-a)e^(-z)',{step:[.5,TAU/12],mapParams:[1,0]});
  run('mobius','M_a(z): z → (A_a z+B_a)/(C_a z+D_a)',{mapParams:[1.1168,-.1888,.70,-.32,.24,-.16,1,0]});
  scene.wait(.35);return scene;
}

export function de_casteljau(renderer){
  const scene=new Scene(renderer),tValue=new ScalarValue(0);scene.addValue(tValue);
  const P=[[-4.4,-2.2],[-2.2,3.0],[2.0,-3.0],[4.4,2.0]];
  const lp=(a,b,t)=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t];
  const levels=t=>{const first=[lp(P[0],P[1],t),lp(P[1],P[2],t),lp(P[2],P[3],t)],second=[lp(first[0],first[1],t),lp(first[1],first[2],t)],final=lp(second[0],second[1],t);return{first,second,final};};
  const bezier=t=>{const u=1-t,w=[u**3,3*u*u*t,3*u*t*t,t**3];return[w.reduce((q,x,i)=>q+x*P[i][0],0),w.reduce((q,x,i)=>q+x*P[i][1],0)];};
  const controlLines=new LineSet(P.slice(0,-1).map((a,i)=>[...a,...P[i+1],rgb(118,130,154,115),.018]),{worldStroke:true,opacity:0,zIndex:0});
  const controlDots=new CircleSet(P.map(q=>[...q,.095,rgb(154,166,191,175),WHITE,.014]),{worldStroke:true,opacity:0,zIndex:4});
  const trace=new DynamicLineSet(()=>{const t=tValue.value,pts=Array.from({length:221},(_,i)=>bezier(t*i/220));return pts.slice(0,-1).map((a,i)=>[...a,...pts[i+1],GREEN,.045]);},{worldStroke:true,opacity:0,zIndex:1});
  const construction=new DynamicLineSet(()=>{const {first,second}=levels(tValue.value);return[[...first[0],...first[1],CYAN,.026],[...first[1],...first[2],CYAN,.026],[...second[0],...second[1],ORANGE,.032]];},{worldStroke:true,opacity:0,zIndex:2});
  const moving=new DynamicCircleSet(()=>{const {first,second,final}=levels(tValue.value),centers=[...first,...second,final],fills=[CYAN,CYAN,CYAN,ORANGE,ORANGE,YELLOW],r=[.078,.078,.078,.085,.085,.115];return centers.map((q,i)=>[...q,r[i],fills[i],WHITE,.012]);},{worldStroke:true,opacity:0,zIndex:5});
  const title=new Text('Bézier curve · De Casteljau',{fontSize:36,color:WHITE,opacity:0,zIndex:10,transform:T(0,4.25)}),subtitle=new Text('repeat linear interpolation: 4 points → 3 → 2 → 1',{fontSize:19,color:MUTED,opacity:0,zIndex:10,transform:T(0,3.8)}),l1=new Text('level 1',{fontSize:17,color:CYAN,opacity:0,zIndex:10,transform:T(-4.75,3.35)}),l2=new Text('level 2',{fontSize:17,color:ORANGE,opacity:0,zIndex:10,transform:T(-4.75,2.98)}),curveLabel=new Text('B(t)',{fontSize:18,color:GREEN,opacity:0,zIndex:10,transform:T(-4.75,2.61)}),tLabel=new Text('t =',{fontSize:25,color:YELLOW,opacity:0,zIndex:10,transform:T(-.42,-4.2)}),tNumber=new DynamicNumber(tValue,{digits:2,color:YELLOW,fontSize:27,opacity:0,zIndex:10,transform:T(.38,-4.2)});
  scene.add(controlLines,trace,construction,controlDots,moving,title,subtitle,l1,l2,curveLabel,tLabel,tNumber);
  scene.parallel(.75,api=>{for(const o of [controlLines,trace,construction,controlDots,moving,title,subtitle,l1,l2,curveLabel,tLabel,tNumber])api.fadeIn(o);});
  scene.wait(.35);scene.animateValue(tValue,{to:1,duration:7,easing:Easing.LINEAR});scene.wait(.75);return scene;
}

function heartSamples(n=160){const a=[];for(let i=0;i<n;i++){const t=TAU*i/n;a.push([1.6*Math.sin(t)**3,(13*Math.cos(t)-5*Math.cos(2*t)-2*Math.cos(3*t)-Math.cos(4*t))/10]);}return a;}
function dft(points){const N=points.length,out=[];for(let k=0;k<N;k++){let re=0,im=0;for(let n=0;n<N;n++){const [x,y]=points[n],ang=-TAU*k*n/N,c=Math.cos(ang),s=Math.sin(ang);re+=x*c-y*s;im+=x*s+y*c;}re/=N;im/=N;let freq=k;if(k>N/2)freq=k-N;out.push({freq,re,im,amp:Math.hypot(re,im)});}return out.sort((a,b)=>b.amp-a.amp);}
const fourierCoeffs=dft(heartSamples(96)).slice(0,42);
function fourierPoint(t,terms=fourierCoeffs){let x=0,y=0;for(const c of terms){const a=c.freq*t,co=Math.cos(a),si=Math.sin(a);x+=c.re*co-c.im*si;y+=c.re*si+c.im*co;}return[x,y]}
export function fourier_draw(renderer){
  const scene=new Scene(renderer);header(scene,'Fourier drawing','public dynamic batches reconstruct a closed contour');
  const state=time=>{const t=((time*.42)%1)*TAU,circles=[],lines=[];let x=-1.9,y=0;for(let i=0;i<fourierCoeffs.length;i++){const c=fourierCoeffs[i],px=x,py=y,a=c.freq*t,co=Math.cos(a),si=Math.sin(a);x+=c.re*co-c.im*si;y+=c.re*si+c.im*co;if(i<14){circles.push([px,py,c.amp,'rgba(0,0,0,0)']);lines.push([px,py,x,y,rgba(CYAN,.65),1]);}}return{t,circles,lines};};
  scene.add(
    new DynamicCircleSet(time=>state(time).circles,{fill:'rgba(0,0,0,0)',stroke:'rgba(135,146,168,.28)',width:1}),
    new DynamicLineSet(time=>state(time).lines),
    new DynamicPolyline(time=>{const t=state(time).t,out=[];for(let i=0;i<=260;i++){const q=fourierPoint(t*i/260);out.push([q[0]-1.9,q[1]]);}return out;},{stroke:PINK,width:3}),
    new Polyline(heartSamples(180).map(q=>[q[0]+2.75,q[1]]),{stroke:rgba(WHITE,.38),width:2}),
    new Text('source contour',{fontSize:16,color:MUTED,transform:T(2.75,-2.35)}),new Text('Fourier reconstruction',{fontSize:16,color:MUTED,transform:T(-1.9,-2.35)}),
  );return finalize(scene,8);
}

const FRACTAL_SIDE=7.0;
const FRACTAL_CREATE=.65, FRACTAL_TRANSITION=.78, FRACTAL_ORDER_HOLD=.16, FRACTAL_SECTION_HOLD=.38, FRACTAL_FADE=.32;

function fitPoints(points,side=FRACTAL_SIDE){
  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys),extent=Math.max(x1-x0,y1-y0);
  if(extent<=1e-12)throw new Error('cannot fit zero-size path');const scale=side/extent,cx=(x0+x1)/2,cy=(y0+y1)/2;return points.map(([x,y])=>[(x-cx)*scale,(y-cy)*scale]);
}
function orientEndpointChord(points,angle=0){
  const a=points[0],b=points.at(-1),dx=b[0]-a[0],dy=b[1]-a[1];if(Math.hypot(dx,dy)<=1e-12)throw new Error('path endpoints must differ');const rot=angle-Math.atan2(dy,dx),c=Math.cos(rot),q=Math.sin(rot);return points.map(([x,y])=>[c*x-q*y,q*x+c*y]);
}
function kochSnowflakePoints(order){
  const h=Math.sqrt(3)/2,turn=-TAU/6,c=Math.cos(turn),q=Math.sin(turn);let points=[[-.5,-h/3],[.5,-h/3],[0,2*h/3],[-.5,-h/3]];
  for(let k=0;k<order;k++){const refined=[];for(let i=0;i<points.length-1;i++){const a=points[i],b=points[i+1],dx=(b[0]-a[0])/3,dy=(b[1]-a[1])/3,p1=[a[0]+dx,a[1]+dy],rd=[c*dx-q*dy,q*dx+c*dy],p2=[p1[0]+rd[0],p1[1]+rd[1]],p3=[a[0]+2*dx,a[1]+2*dy];refined.push(a,p1,p2,p3);}refined.push(points.at(-1));points=refined;}return fitPoints(points);
}
function sierpinskiArrowheadPoints(order){
  let word='A';for(let k=0;k<order;k++)word=[...word].map(ch=>ch==='A'?'B-A-B':ch==='B'?'A+B+A':ch).join('');let angle=0,x=0,y=0;const turn=TAU/6,points=[[0,0]];
  for(const token of word){if(token==='A'||token==='B'){x+=Math.cos(angle);y+=Math.sin(angle);points.push([x,y]);}else if(token==='+')angle+=turn;else if(token==='-')angle-=turn;}return fitPoints(orientEndpointChord(points));
}
function dragonCurvePoints(order){
  let points=[[0,0],[1,0]];for(let k=0;k<order;k++){const pivot=points.at(-1),extra=[];for(let i=points.length-2;i>=0;i--){const dx=points[i][0]-pivot[0],dy=points[i][1]-pivot[1];extra.push([pivot[0]-dy,pivot[1]+dx]);}points=points.concat(extra);}return fitPoints(orientEndpointChord(points));
}
function levyCPoints(order){
  let points=[[-.5,0],[.5,0]];for(let k=0;k<order;k++){const refined=[];for(let i=0;i<points.length-1;i++){const a=points[i],b=points[i+1],dx=b[0]-a[0],dy=b[1]-a[1],apex=[(a[0]+b[0])/2-dy/2,(a[1]+b[1])/2+dx/2];refined.push(a,apex);}refined.push(points.at(-1));points=refined;}return fitPoints(points);
}
const FRACTAL_SPECS=[
  ['Koch snowflake','each edge becomes four self-similar edges',kochSnowflakePoints,0,5,CYAN],
  ['Sierpiński arrowhead','one continuous curve approaches the Sierpiński triangle',sierpinskiArrowheadPoints,1,7,GREEN],
  ['Heighway dragon','fold, rotate 90°, and repeat',dragonCurvePoints,1,12,PINK],
  ['Lévy C curve','every segment becomes two 45° branches',levyCPoints,0,11,ORANGE],
];
function fractalCurve(spec,order,{trim=1}={}){const [, ,generator,first,,color]=spec;return new Polyline(generator(order),{stroke:color,strokeWidth:Math.max(.018,.052-.003*Math.max(0,order-first)),trim,zIndex:1});}
function fractalHeading(spec){return [new Text(spec[0],{fontSize:35,color:WHITE,opacity:0,zIndex:10,transform:T(0,4.25)}),new Text(spec[1],{fontSize:19,color:MUTED,opacity:0,zIndex:10,transform:T(0,3.78)})];}
function fractalOrderLabel(order,count){return new Text(`order ${order}   ·   ${(count-1).toLocaleString('en-US')} segments`,{fontSize:20,color:YELLOW,opacity:0,zIndex:10,transform:T(0,-4.28)});}
function animateFractal(scene,spec){
  const firstOrder=spec[3],lastOrder=spec[4],firstPoints=spec[2](firstOrder);let curve=fractalCurve(spec,firstOrder,{trim:0}),[title,subtitle]=fractalHeading(spec),label=fractalOrderLabel(firstOrder,firstPoints.length);scene.add(curve,title,subtitle,label);
  scene.parallel(FRACTAL_CREATE,api=>{api.create(curve,{duration:FRACTAL_CREATE});api.fadeIn(title,{duration:.42});api.fadeIn(subtitle,{duration:.48,at:.08});api.fadeIn(label,{duration:.42,at:.08});});scene.wait(FRACTAL_SECTION_HOLD);
  for(let order=firstOrder+1;order<=lastOrder;order++){
    const next=fractalCurve(spec,order),points=spec[2](order);curve=scene.replace(curve,next,{duration:FRACTAL_TRANSITION});const nextLabel=scene.add(fractalOrderLabel(order,points.length));scene.parallel(.16,api=>{api.fadeOut(label,{duration:.16});api.fadeIn(nextLabel,{duration:.16});});label.remove();label=nextLabel;scene.wait(FRACTAL_ORDER_HOLD);
  }
  scene.wait(FRACTAL_SECTION_HOLD);scene.parallel(FRACTAL_FADE,api=>{api.fadeOut(curve,{duration:FRACTAL_FADE});api.fadeOut(title,{duration:FRACTAL_FADE});api.fadeOut(subtitle,{duration:FRACTAL_FADE});api.fadeOut(label,{duration:FRACTAL_FADE});});curve.remove();title.remove();subtitle.remove();label.remove();
}
export function fractals(renderer){const scene=new Scene(renderer);for(const spec of FRACTAL_SPECS)animateFractal(scene,spec);scene.wait(.35);return scene;}

function hilbertD2xy(n,d){let rx,ry,s,t=d,x=0,y=0;for(s=1;s<n;s*=2){rx=1&(t>>1);ry=1&(t^rx);if(ry===0){if(rx===1){x=s-1-x;y=s-1-y;}[x,y]=[y,x];}x+=s*rx;y+=s*ry;t>>=2;}return[x,y]}
function hilbertPoints(order,side=7){const n=1<<order,N=n*n,den=n-1,half=side/2,pts=[];for(let d=0;d<N;d++){const [x,y]=hilbertD2xy(n,d);pts.push([side*x/den-half,side*y/den-half]);}return pts;}
const HILBERT_PALETTE=[BLUE,CYAN,GREEN,YELLOW,ORANGE,PINK];
function hilbertCurve(order,{trim=1}={}){return new Polyline(hilbertPoints(order),{stroke:HILBERT_PALETTE[Math.min(order-1,HILBERT_PALETTE.length-1)],strokeWidth:Math.max(.018,.052-.006*(order-1)),trim,zIndex:1});}
function hilbertLabel(order){return new Text(`order ${order}   ·   ${(4**order).toLocaleString('en-US')} vertices`,{fontSize:21,color:MUTED,opacity:0,zIndex:10,transform:T(0,-4.25)});}
export function hilbert_curve(renderer){
  const scene=new Scene(renderer),title=new Text('Hilbert curve',{fontSize:36,color:WHITE,opacity:0,zIndex:10,transform:T(0,4.25)});let label=hilbertLabel(1),curve=hilbertCurve(1,{trim:0});scene.add(curve,title,label);
  scene.parallel(1.0,api=>{api.create(curve,{duration:1});api.fadeIn(title,{duration:.55});api.fadeIn(label,{duration:.55});});scene.wait(.42);
  for(let order=2;order<=6;order++){curve=scene.replace(curve,hilbertCurve(order),{duration:1.15});const next=scene.add(hilbertLabel(order));scene.parallel(.18,api=>{api.fadeOut(label,{duration:.18});api.fadeIn(next,{duration:.18});});label.remove();label=next;scene.wait(.42);}scene.wait(.5);return scene;
}

export function mandelbrot_julia(renderer){
  const scene=new Scene(renderer),centered=(re,im,scale)=>Transform2D.translation(-scale*re,-scale*im).mul(Transform2D.scaling(scale));
  const title=new Text('Infinite fractals',{fontSize:35,color:WHITE,opacity:0,zIndex:20,transform:T(0,1.94)}),subtitle=new Text('viewport-resolved in Zig · every zoom recomputes the complex plane',{fontSize:18,color:MUTED,opacity:0,zIndex:20,transform:T(0,1.62)}),mLabel=new Text('Mandelbrot  ·  z ← z² + c',{fontSize:22,color:WHITE,opacity:0,zIndex:20,transform:T(-2.70,-1.88)}),jLabel=new Text('Julia  ·  c = -0.8 + 0.156i',{fontSize:22,color:WHITE,opacity:0,zIndex:20,transform:T(-2.82,-1.88)});
  const mandel=new MandelbrotSet({viewport:'transform',maxIter:360,insideColor:rgb(4,6,13),paletteColor:rgb(105,185,255),colorShift:.06,colorScale:1,transform:centered(-.55,0,1.18),zIndex:-10,resolution:.18,minWidth:96});
  const julia=new JuliaSet([-.8,.156],{viewport:'transform',maxIter:320,insideColor:rgb(5,5,13),paletteColor:rgb(255,155,105),colorShift:.40,colorScale:1.08,opacity:0,transform:centered(0,0,1.28),zIndex:-9,resolution:.18,minWidth:96});
  scene.add(mandel,julia,title,subtitle,mLabel,jLabel);scene.parallel(.65,api=>{api.fadeIn(title);api.fadeIn(subtitle);api.fadeIn(mLabel);});scene.wait(.30);
  scene.affine(mandel,{position:[-180*(-.743643887037151),-180*.13182590420533],scale:180,duration:4.2});scene.wait(.55);
  scene.parallel(.70,api=>{api.fadeOut(mandel);api.fadeOut(mLabel);api.fadeIn(julia);api.fadeIn(jLabel);});scene.wait(.25);
  scene.affine(julia,{position:[-30*(-.5966666666666667),-30*(-.15)],scale:30,duration:4});scene.wait(.65);
  scene.parallel(.45,api=>{api.fadeOut(julia);api.fadeOut(jLabel);api.fadeOut(title);api.fadeOut(subtitle);});return scene;
}

const midiNotes=Array.from({length:72},(_,i)=>({key:(i*7+i*i*3)%24,start:i*.085,dur:.35+(i%5)*.07,color:[BLUE,CYAN,PINK,PURPLE,YELLOW][i%5]}));
export function midi_piano(renderer){
  const scene=new Scene(renderer);header(scene,'MIDI piano roll','public RectSet / DynamicRectSet on one absolute timeline');const x0=-5.1,w=10.2/24,keyY=-2.05;
  const keys=Array.from({length:24},(_,k)=>[x0+(k+.5)*w,keyY-.5,w,1,k%2?'#d8deea':'#f7f8fb']);
  scene.add(
    new RectSet(keys,{stroke:'#333b4b',width:1}),
    new DynamicRectSet(time=>{const out=[];for(const n of midiNotes){const dt=n.start-time;if(dt<-.25||dt>4)continue;const h=n.dur*1.15;out.push([x0+(n.key+.5)*w,keyY+.35+dt*1.15+h/2,w*.76,h,rgba(n.color,.88)]);}return out;}),
    new Text('visual timing driven from parsed note events',{fontSize:16,color:MUTED,transform:T(0,2.15)}),
  );return finalize(scene,6.4);
}

function drawNetwork(ctx,r,time,{centerY=-.1,scale=1}={}){const layers=[6,9,9,4],xs=[-4.2,-1.4,1.4,4.2];const pos=layers.map((n,L)=>Array.from({length:n},(_,i)=>[xs[L]*scale,centerY+(i-(n-1)/2)*.45*scale]));for(let l=0;l<layers.length-1;l++)for(let i=0;i<pos[l].length;i++)for(let j=0;j<pos[l+1].length;j++){const a=pos[l][i],b=pos[l+1][j],w=Math.sin(i*13+j*7+l*5+time*.8);path(ctx,r,[a,b],{stroke:w>0?rgba(BLUE,.12+.14*Math.abs(w)):rgba(RED,.12+.14*Math.abs(w)),width:.5+1.2*Math.abs(w)});}for(let l=0;l<pos.length;l++)for(let i=0;i<pos[l].length;i++){const a=.5+.5*Math.sin(time*1.3+i*.6+l),d=r.toDevice(...pos[l][i]);ctx.beginPath();ctx.arc(d[0],d[1],(.055+.04*a)*r.unitSize,0,TAU);ctx.fillStyle=`rgba(${Math.round(70+130*a)},${Math.round(120+90*a)},245,.95)`;ctx.fill();}return pos;}
function networkPositions({centerY=-.1,scale=1}={}){const layers=[6,9,9,4],xs=[-4.2,-1.4,1.4,4.2];return layers.map((n,L)=>Array.from({length:n},(_,i)=>[xs[L]*scale,centerY+(i-(n-1)/2)*.45*scale]));}
export function neural_network(renderer){
  const scene=new Scene(renderer),data=NEURAL_PARITY_DATA;
  const edges=data.edges.map(e=>new LineSet(parityLineItems(e.idle),{worldStroke:true,zIndex:0}));
  const nodes=data.nodes.map(n=>new CircleSet(parityCircleItems(n.idle),{worldStroke:true,zIndex:2}));
  const title=new Text('Signals flow; geometry stays batched',{fontSize:31,opacity:0,zIndex:10,transform:T(0,3.55)});
  scene.add(...edges,...nodes,title);scene.fadeIn(title,{duration:.6});
  for(let i=0;i<edges.length;i++)scene.parallel(api=>{
    api.batch(nodes[i],{to:parityCircleItems(data.nodes[i].active),duration:.55});
    api.batch(edges[i],{to:parityLineItems(data.edges[i].active),duration:.75,at:.25});
    api.batch(nodes[i+1],{to:parityCircleItems(data.nodes[i+1].active),duration:.55,at:.65});
  }),scene.wait(.12);
  scene.batch(nodes.at(-1),{to:parityCircleItems(data.final),duration:.55});scene.wait(.65);return scene;
}

export function mnist_training(renderer){
  const scene=new Scene(renderer);header(scene,'MNIST training','public dynamic batches + graph + number readouts');const pos=networkPositions({centerY:.5,scale:.72}),pAt=time=>smooth(time/8),lossAt=time=>2.2*Math.exp(-4.2*pAt(time))+.08,accAt=time=>.1+.89*(1-Math.exp(-4.5*pAt(time)));
  const sample=[];for(let yy=0;yy<7;yy++)for(let xx=0;xx<7;xx++){const on=((xx-3)**2+(yy-3)**2<7)&&(xx>2||yy<3);sample.push([2.0+xx*.18,-2.0+yy*.18,.15,.15,on?WHITE:'#222a38']);}
  scene.add(
    new DynamicLineSet(time=>{const items=[];for(let l=0;l<pos.length-1;l++)for(let i=0;i<pos[l].length;i++)for(let j=0;j<pos[l+1].length;j++){const a=pos[l][i],b=pos[l+1][j],w=Math.sin(i*13+j*7+l*5+time*.8);items.push([a[0],a[1],b[0],b[1],w>0?rgba(BLUE,.16):rgba(RED,.16),.6+Math.abs(w)]);}return items;}),
    new DynamicCircleSet(time=>{const items=[];for(let l=0;l<pos.length;l++)for(let i=0;i<pos[l].length;i++){const a=.5+.5*Math.sin(time*1.3+i*.6+l),q=pos[l][i];items.push([q[0],q[1],.045+.035*a,rgba(BLUE,.55+.4*a)]);}return items;}),
    new DynamicPolyline(time=>{const p=pAt(time),out=[];for(let i=0;i<=100;i++){const q=i/100;if(q>p)break;out.push([-4.9+4.2*q,-2.3+1.25*(1-(2.2*Math.exp(-4.2*q)+.08)/2.4)]);}return out;},{stroke:ORANGE,width:2.5}),
    new RectSet(sample),
    new Text(time=>`epoch ${Math.floor(1+pAt(time)*19)}   loss ${lossAt(time).toFixed(3)}`,{fontSize:16,color:ORANGE,transform:T(-2.8,-2.62)}),
    new Text(time=>`validation accuracy ${(accAt(time)*100).toFixed(1)}%`,{fontSize:17,color:GREEN,transform:T(2.75,-2.62)}),
    new Text('prediction: 8',{fontSize:20,transform:T(3.4,-1.45)}),
  );return finalize(scene,8.5);
}

export function modular_multiplication(renderer){
  const scene=new Scene(renderer),n=240,radius=3.35,multiplier=new ScalarValue(0);scene.addValue(multiplier);
  const point=i=>[radius*Math.cos(TAU*i/n),radius*Math.sin(TAU*i/n)];
  const outlinePts=Array.from({length:256},(_,i)=>[radius*Math.cos(TAU*i/256),radius*Math.sin(TAU*i/256)]);
  const outline=new LineSet(outlinePts.map((a,i)=>[...a,...outlinePts[(i+1)%256],rgb(135,148,174,110),.014]),{worldStroke:true,opacity:0,zIndex:0});
  const lines=new DynamicLineSet(()=>Array.from({length:n},(_,i)=>{const u=i/n,a=point(i),b=point(multiplier.value*i),rr=Math.round(105+70*(.5+.5*Math.sin(TAU*u))),g=Math.round(150+70*(.5+.5*Math.sin(TAU*u+2.094))),bb=Math.min(255,Math.round(205+45*(.5+.5*Math.sin(TAU*u+4.189))));return[...a,...b,rgb(rr,g,bb,145),.012];}),{worldStroke:true,opacity:0,zIndex:1});
  const dots=new CircleSet(Array.from({length:n},(_,i)=>[...point(i),.018,rgb(190,205,230,175)]),{opacity:0,zIndex:2});
  const title=new Text('Modular multiplication circle',{fontSize:36,color:WHITE,opacity:0,zIndex:10,transform:T(0,4.25)}),subtitle=new Text('connect i → k·i mod n   ·   the multiplier changes continuously',{fontSize:19,color:MUTED,opacity:0,zIndex:10,transform:T(0,3.8)}),kLabel=new Text('k =',{fontSize:26,color:YELLOW,opacity:0,zIndex:10,transform:T(-.48,-4.18)}),kValue=new DynamicNumber(multiplier,{digits:2,color:CYAN,fontSize:28,opacity:0,zIndex:10,transform:T(.34,-4.18)}),nLabel=new Text(`n = ${n}`,{fontSize:18,color:MUTED,opacity:0,zIndex:10,transform:T(4.6,-4.18)});
  scene.add(outline,lines,dots,title,subtitle,kLabel,kValue,nLabel);scene.parallel(.75,api=>{for(const o of [outline,lines,dots,title,subtitle,kLabel,kValue,nLabel])api.fadeIn(o);});scene.wait(.35);scene.animateValue(multiplier,{to:12,duration:18,easing:Easing.LINEAR});scene.wait(.65);return scene;
}

class RBNode{constructor(v){this.v=v;this.red=true;this.l=null;this.r=null;this.p=null}}
function rbInsert(root,v){let z=new RBNode(v),y=null,x=root;while(x){y=x;x=v<x.v?x.l:x.r;}z.p=y;if(!y)root=z;else if(v<y.v)y.l=z;else y.r=z;while(z!==root&&z.p?.red){if(z.p===z.p.p.l){let u=z.p.p.r;if(u?.red){z.p.red=false;u.red=false;z.p.p.red=true;z=z.p.p;}else{if(z===z.p.r){z=z.p;let q=z.r;z.r=q.l;if(q.l)q.l.p=z;q.p=z.p;if(!z.p)root=q;else if(z===z.p.l)z.p.l=q;else z.p.r=q;q.l=z;z.p=q;}z.p.red=false;z.p.p.red=true;let g=z.p.p,q=g.l;g.l=q.r;if(q.r)q.r.p=g;q.p=g.p;if(!g.p)root=q;else if(g===g.p.l)g.p.l=q;else g.p.r=q;q.r=g;g.p=q;}}else{let u=z.p.p.l;if(u?.red){z.p.red=false;u.red=false;z.p.p.red=true;z=z.p.p;}else{if(z===z.p.l){z=z.p;let q=z.l;z.l=q.r;if(q.r)q.r.p=z;q.p=z.p;if(!z.p)root=q;else if(z===z.p.l)z.p.l=q;else z.p.r=q;q.r=z;z.p=q;}z.p.red=false;z.p.p.red=true;let g=z.p.p,q=g.r;g.r=q.l;if(q.l)q.l.p=g;q.p=g.p;if(!g.p)root=q;else if(g===g.p.l)g.p.l=q;else g.p.r=q;q.l=g;g.p=q;}}}root.red=false;return root}
const rbValues=[41,18,67,9,25,52,81,4,13,21,31,48,59,73,92,2,7,11,15];
function rbState(count){let root=null;for(const v of rbValues.slice(0,count))root=rbInsert(root,v);return root}
function treeLayout(root){const out=[];let ix=0;function walk(n,d){if(!n)return;walk(n.l,d+1);n._x=ix++;n._d=d;out.push(n);walk(n.r,d+1);}walk(root,0);const mid=(ix-1)/2;for(const n of out)n._x=(n._x-mid)*.65;return out}
function rbFrame(count){const root=rbState(count),nodes=treeLayout(root),map=new Map();for(const n of nodes)map.set(n.v,{v:n.v,x:n._x,y:1.85-n._d*.58,red:n.red,parent:n.p?.v??null});return map;}
const rbFrames=Array.from({length:rbValues.length},(_,i)=>rbFrame(i+1));
function rbVisual(time){const f=Math.min(rbFrames.length-1,Math.max(0,time/.42)),i0=Math.floor(f),i1=Math.min(rbFrames.length-1,i0+1),u=smooth(f-i0),a=rbFrames[i0],b=rbFrames[i1],nodes=[];for(const [v,n1] of b){const n0=a.get(v)??(n1.parent!=null?a.get(n1.parent):null)??n1;nodes.push({v,x:n0.x+(n1.x-n0.x)*u,y:n0.y+(n1.y-n0.y)*u,red:n1.red,parent:n1.parent,newNode:!a.has(v),u});}const byValue=new Map(nodes.map(n=>[n.v,n]));return{nodes,byValue,index:i1};}
function rbPositionMap(step,values){const sorted=[...values].sort((a,b)=>a-b),rank=new Map(sorted.map((v,i)=>[v,i])),den=Math.max(1,values.length-1),states=new Map(step.nodes.map(n=>[n.value,n])),out=new Map();for(const v of values)out.set(v,[-5.1+10.2*rank.get(v)/den,states.has(v)?2.55-states.get(v).depth*1.18:-4.15]);return out;}
function rbNodeBatch(step,values){const positions=rbPositionMap(step??{nodes:[]},values),states=new Map((step?.nodes??[]).map(n=>[n.value,n])),active=new Set(step?.active??[]);return[...values].sort((a,b)=>a-b).map(v=>{const p=positions.get(v),st=states.get(v),fill=!st?rgb(22,26,34,0):st.red?RED:rgb(22,26,34),stroke=!st?rgb(188,198,220,0):active.has(v)?YELLOW:rgb(188,198,220,210),w=active.has(v)?.055:.030;return[...p,.34,fill,stroke,w];});}
function rbEdgeBatch(step,values){const states=new Map((step?.nodes??[]).map(n=>[n.value,n])),pos=rbPositionMap(step??{nodes:[]},values);return[...values].sort((a,b)=>a-b).map(v=>{const st=states.get(v),child=pos.get(v);if(!st||st.parent==null)return[...child,...child,rgb(135,148,174,0),.025];const parent=pos.get(st.parent),dx=child[0]-parent[0],dy=child[1]-parent[1],L=Math.hypot(dx,dy),ux=L?dx/L:0,uy=L?dy/L:0;return[parent[0]+ux*.34,parent[1]+uy*.34,child[0]-ux*.34,child[1]-uy*.34,rgb(135,148,174,190),.025];});}
function rbStatusColor(kind){return kind==='insert'?WHITE:kind==='recolor'?YELLOW:kind.startsWith('rotate')?rgb(110,205,255):kind==='root_black'?GRAY:MUTED;}
export function red_black_tree(renderer){
  const scene=new Scene(renderer),data=RB_PARITY_DATA,values=data.values,empty={kind:'empty',message:'',nodes:[],active:[]};
  const title=new Text('Random red-black tree insertion',{fontSize:34,color:WHITE,transform:T(0,4.35)}),sequence=new Text('sequence  '+values.join('  '),{fontSize:18,color:MUTED,transform:T(0,3.90)}),nodes=new CircleSet(rbNodeBatch(null,values),{worldStroke:true,zIndex:2}),edges=new LineSet(rbEdgeBatch(null,values),{worldStroke:true,zIndex:0});scene.add(edges,nodes,title,sequence);
  const initial=rbPositionMap(empty,values),labels=new Map();for(const v of values){const p=initial.get(v),label=new Text(String(v),{fontSize:18,color:WHITE,opacity:0,zIndex:4,transform:T(...p)});labels.set(v,label);scene.add(label);}
  let status=scene.add(new Text(`seed ${data.seed} · ${data.count} unique keys`,{fontSize:20,color:MUTED,opacity:0,zIndex:10,transform:T(0,3.43)}));scene.fadeIn(status,{duration:.25});scene.wait(.22);let visible=new Set();
  for(const step of data.trace){const next=scene.add(new Text(step.message,{fontSize:20,color:rbStatusColor(step.kind),opacity:0,zIndex:10,transform:T(0,3.43)}));scene.parallel(.12,api=>{api.fadeOut(status);api.fadeIn(next);});status.remove();status=next;const duration=step.kind==='insert'?.58:step.kind.startsWith('rotate')?.72:.48,positions=rbPositionMap(step,values),stepValues=new Set(step.nodes.map(n=>n.value)),newly=[...stepValues].filter(v=>!visible.has(v));scene.parallel(duration,api=>{api.batch(nodes,{to:rbNodeBatch(step,values)});api.batch(edges,{to:rbEdgeBatch(step,values)});for(const v of stepValues)api.animate(labels.get(v),{transform:T(...positions.get(v))});for(const v of newly)api.fadeIn(labels.get(v));});visible=stepValues;scene.wait(step.kind==='insert'?.20:.12);}
  const final=scene.add(new Text('all invariants restored · root black · equal black height',{fontSize:20,color:rgb(120,220,165),opacity:0,zIndex:10,transform:T(0,3.43)}));scene.parallel(.24,api=>{api.fadeOut(status);api.fadeIn(final);});status.remove();scene.wait(.85);return scene;
}

function sortingLineState(step,n){
  const pos=new Map(step.values.map((v,i)=>[v,i])),spacing=10.2/Math.max(1,n-1),heightScale=5.65/n,x0=-5.1,active=new Set(step.active),settled=new Set(step.settled);return Array.from({length:n},(_,k)=>{const value=k+1,x=x0+pos.get(value)*spacing,color=value===step.pivot?PINK:active.has(value)?(step.kind==='move'?ORANGE:YELLOW):settled.has(value)?GREEN:BLUE;return[x,-3.05,x,-3.05+value*heightScale,color,.11];});
}
export function sorting_algorithms(renderer){
  const scene=new Scene(renderer),data=SORTING_PARITY_DATA,n=data.n,initial={kind:'initial',values:data.initial,active:[],pivot:null,settled:[]};
  for(const trace of data.traces){
    const title=new Text(trace.name,{fontSize:35,color:WHITE,opacity:0,zIndex:10,transform:T(0,4.2)}),subtitle=new Text(trace.subtitle,{fontSize:18,color:MUTED,opacity:0,zIndex:10,transform:T(0,3.76)}),legend=new Text('yellow compare   ·   orange move   ·   pink pivot   ·   green settled',{fontSize:17,color:MUTED,opacity:0,zIndex:10,transform:T(0,-4.25)}),bars=new LineSet(sortingLineState(initial,n),{worldStroke:true,opacity:0,zIndex:1}),baseline=new LineSet([[-5.4,-3.05,5.4,-3.05,rgb(103,114,138,105),.018]],{worldStroke:true,opacity:0,zIndex:0});
    scene.add(bars,baseline,title,subtitle,legend);scene.parallel(.2,api=>{for(const o of [bars,baseline,title,subtitle,legend])api.fadeIn(o);});scene.wait(.09);
    for(const step of trace.steps)scene.batch(bars,{to:sortingLineState(step,n),duration:step.kind==='move'?.06:.065});
    scene.wait(.175);scene.parallel(.14,api=>{for(const o of [bars,baseline,title,subtitle,legend])api.fadeOut(o);});for(const o of [bars,baseline,title,subtitle,legend])o.remove();
  }
  scene.wait(.125);return scene;
}



export const extraDemos={complex_mapping,de_casteljau,fourier_draw,fractals,hilbert_curve,mandelbrot_julia,midi_piano,mnist_training,modular_multiplication,neural_network,red_black_tree,sorting_algorithms};
