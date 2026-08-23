import {
  Scene, Transform2D, Mat2, InfiniteGrid, InfiniteLine, Axes, Polygon, Polyline,
  Circle, Square, Rectangle, RegularPolygon, Dot, Line, Arrow, Text, Group,
  CircleSet, LineSet, DynamicPolyline, CustomObject2D, Easing, Row, Column, Grid,
  Image as ZImage, GIF, Video,
  WHITE, MUTED, BLUE, GREEN, RED, ORANGE, YELLOW, CYAN, PINK, PURPLE, GRAY,
  PI, TAU, DEGREES, LOCAL, PARENT, WORLD,
} from '../src/zanim.js';

const smooth = Easing.SMOOTHSTEP;
const clamp01 = x => Math.max(0, Math.min(1, x));
const phase = (t, start, duration) => smooth(clamp01((t - start) / duration));
const rgba = (hex, a=.7) => hex.startsWith('#') ? `${hex}${Math.round(a*255).toString(16).padStart(2,'0')}` : hex;
const rgb=(r,g,b,a=255)=>`rgba(${r},${g},${b},${(a/255).toFixed(6)})`;
const T = (x=0,y=0,rotation=0,scale=1,shear=[0,0]) => Transform2D.affine({position:[x,y],rotation,scale,shear});

function header(scene, title, subtitle='') {
  scene.add(new Text(title,{fontSize:34,transform:T(0,3.18),zIndex:20}));
  if (subtitle) scene.add(new Text(subtitle,{fontSize:19,color:MUTED,transform:T(0,2.72),zIndex:20}));
}
function finalize(scene, duration) { scene.duration=duration; scene.cursor=duration; return scene; }

export function basics(renderer) {
  const scene=new Scene(renderer); header(scene,'Declare → layout → animate','ordinary geometry, groups, text and camera-style motion');
  const square=new Square(1.25,{fill:rgba(BLUE,.78),stroke:WHITE,transform:T(-2.0,.15)});
  const circle=new Circle(.68,{fill:rgba(ORANGE,.78),stroke:WHITE,transform:T(0,.15)});
  const arrow=new Arrow([-0.7,0],[0.7,0],{stroke:GREEN,width:4,transform:T(2.15,.15)});
  const stage=new Group([square,circle,arrow],{transform:T(0,-.35)}); scene.add(stage);
  scene.animate(stage,{transform:T(0,-.15,.20,1.08),duration:1.5,at:.8});
  scene.animate(square,{transform:T(-2.0,.45,.55,1.1),duration:1.3,at:2.5});
  scene.animate(circle,{transform:T(0,-.05,-.35,.8),duration:1.3,at:2.5});
  scene.animate(arrow,{transform:T(2.15,.35,.3,1.15),duration:1.3,at:2.5});
  return finalize(scene,4.3);
}

export function batches(renderer) {
  const scene=new Scene(renderer),N=420;
  const circleState=phase=>Array.from({length:N},(_,i)=>{const u=i/N,angle=TAU*(u*5+phase),radius=.8+3*u,r=.025+.055*(.5+.5*Math.sin(5*TAU*u+phase*2*TAU)),fill=rgb(Math.round(70+170*u),Math.round(145+70*(1-u)),255,220);return[radius*Math.cos(angle),radius*Math.sin(angle),r,fill];});
  const lineState=phase=>Array.from({length:180},(_,i)=>{const u=i/180,a=TAU*u,b=a+phase*PI;return[2*Math.cos(a),2*Math.sin(a),3.5*Math.cos(b),3.5*Math.sin(b),rgb(100,Math.round(140+100*u),255,100),.006];});
  const title=new Text('600 primitives, two batch objects',{fontSize:31,opacity:0,transform:T(-.00086,3.49112)}),dots=new CircleSet(circleState(0),{zIndex:2}),lines=new LineSet(lineState(0),{worldStroke:true,zIndex:0});scene.add(lines,dots,title);scene.fadeIn(title,{duration:.6});scene.parallel(2,api=>{api.batch(dots,{to:circleState(.33)});api.batch(lines,{to:lineState(.55)});});scene.parallel(2,api=>{api.batch(dots,{to:circleState(.68)});api.batch(lines,{to:lineState(1)});});scene.wait(.4);return scene;
}

export function compositing(renderer) {
  const scene=new Scene(renderer); header(scene,'A Scene can become raster data for another Scene','content + alpha mask → composited result');
  const obj=new CustomObject2D(({ctx,renderer:r,time})=>{
    const p=phase(time,.25,4),ang=.8*PI*p,maskX=-1.35+2.7*p,maskY=.28*Math.sin(TAU*p),maskR=.72+.38*Math.sin(PI*p);
    const panels=[-4.25,0,4.25];
    for(const x of panels){const d=r.toDevice(x,-.45);ctx.fillStyle='rgba(255,255,255,.035)';ctx.fillRect(d[0]-1.75*r.unitSize,d[1]-1.25*r.unitSize,3.5*r.unitSize,2.5*r.unitSize);}
    const content=(offset,clip=false)=>{ctx.save();if(clip){const c=r.toDevice(offset+maskX,-.45+maskY);ctx.beginPath();ctx.arc(c[0],c[1],maskR*r.unitSize,0,TAU);ctx.clip();}drawWorldRect(ctx,r,offset-1.0,-.05,1.25,1.25,rgba(BLUE,.88),ang);drawWorldCircle(ctx,r,offset+1.0,-.75,.72,rgba(ORANGE,.88),WHITE);drawWorldRect(ctx,r,offset,-1.45,3.1,.28,rgba(GREEN,.82),-.12);ctx.restore();};
    content(-4.25,false); drawWorldCircle(ctx,r,maskX,-.45+maskY,maskR,'rgba(255,255,255,.85)'); content(4.25,true);
    for(const [x,label] of [[-4.25,'content'],[0,'mask alpha'],[4.25,'result']]){const d=r.toDevice(x,1.25);ctx.fillStyle=MUTED;ctx.font=`${18*r.dpr}px system-ui`;ctx.textAlign='center';ctx.fillText(label,d[0],d[1]);}
  });scene.add(obj);return finalize(scene,4.7);
}

export function infinite_space(renderer) {
  const scene=new Scene(renderer),title=new Text('Linear algebra on an infinite plane',{fontSize:32,color:WHITE,zIndex:20,transform:T(.00567,3.204)}),subtitle=new Text('the infinite grid and the finite reference shape receive the same 2×2 matrix',{fontSize:19,color:MUTED,zIndex:20,transform:T(-.00112,2.78612)}),grid=new InfiniteGrid({step:.5,stroke:rgb(94,108,136,115),strokeWidth:.014,zIndex:-4}),xAxis=new InfiniteLine([0,0],[1,0],{stroke:rgba(RED,220/255),strokeWidth:.035,zIndex:-2}),yAxis=new InfiniteLine([0,0],[0,1],{stroke:rgba(GREEN,220/255),strokeWidth:.035,zIndex:-2}),reference=new Polygon([[.45,.35],[2.05,.35],[2.05,.85],[1.2,.85],[1.2,1.75],[.45,1.75]],{fill:rgba(BLUE,145/255),stroke:CYAN,strokeWidth:.045,zIndex:4}),origin=new Dot([0,0],{radius:.055,color:YELLOW,zIndex:8}),note=new Text('same A',{fontSize:17,color:CYAN,zIndex:20,transform:T(1.27498,2.02118)});scene.add(grid,xAxis,yAxis,reference,origin,title,subtitle,note);const objects=[grid,xAxis,yAxis,reference];scene.wait(.55);
  const apply=(provider,duration)=>scene.parallel(duration,api=>{for(const o of objects)api.transformFunction(o,provider);});
  const stage=(name,matrix,provider,{duration=1.65,hold=.42}={})=>{let label=scene.add(new Text(name,{fontSize:24,color:WHITE,opacity:0,zIndex:20,transform:T(0,-2.72)})),formula=scene.add(new Text(matrix,{fontSize:19,color:MUTED,opacity:0,zIndex:20,transform:T(0,-3.05)}));scene.parallel(.28,api=>{api.fadeIn(label);api.fadeIn(formula);});apply(provider,duration);scene.wait(hold);apply(a=>provider(1-a),.95);scene.parallel(.24,api=>{api.fadeOut(label);api.fadeOut(formula);});label.remove();formula.remove();scene.wait(.08);};
  stage('Rotation','R(θ),  θ: 0 → 55°   ·   det A = 1',a=>Transform2D.rotation(a*55*PI/180));stage('Anisotropic scaling','A = diag(1.8, 0.55)',a=>Transform2D.scaling(1+.8*a,1-.45*a));stage('Shear','A = [[1, 1.15], [0, 1]]   ·   area preserved',a=>Transform2D.shear(1.15*a,0));stage('Singular projection','A → [[1, 0.65], [0, 0]]   ·   rank 2 → rank 1',a=>new Transform2D(1,.65*a,0,1-a,0,0),{duration:1.9,hold:.62});stage('General invertible map','A = [[1.15, 0.75], [-0.45, 1.05]]',a=>new Transform2D(1+.15*a,.75*a,-.45*a,1+.05*a,0,0),{duration:1.9});scene.wait(.45);return scene;
}

export function kinematics(renderer) {
  const scene=new Scene(renderer),link=(length,color)=>new Line([0,0],[length,0],{stroke:color,strokeWidth:.07}),l1=2.2,l2=1.7,l3=1.15,link1=link(l1,BLUE),link2=link(l2,GREEN),link3=link(l3,ORANGE),j1Mark=new Dot([0,0],{radius:.11,color:WHITE,zIndex:4}),j2Mark=new Dot([0,0],{radius:.11,color:WHITE,zIndex:4}),slider=new Dot([0,0],{radius:.11,color:ORANGE,zIndex:4}),ee=new Dot([l3,0],{radius:.13,color:rgb(255,224,105),zIndex:5}),joint3=new Group([slider,link3,ee],{transform:T(l2,0)}),joint2=new Group([j2Mark,link2,joint3],{transform:T(l1,0)}),joint1=new Group([j1Mark,link1,joint2],{transform:T(-3.135,-.55)}),title=new Text('Open-chain FK = ordinary frame composition',{fontSize:32,transform:T(-.005278,3.399043)}),formula=new Text('T₀ₑ = T₀₁(q₁) · T₁₂(q₂) · T₂₃(q₃)',{fontSize:25,color:MUTED,transform:T(.007118,2.857224)});scene.add(title,formula,joint1);scene.wait(.6);const h1=joint1.transform,h2=joint2.transform,h3=joint3.transform;scene.parallel(6,api=>{api.transformFunction(joint1,a=>h1.mul(Transform2D.rotation(.75*Math.sin(TAU*a))));api.transformFunction(joint2,a=>h2.mul(Transform2D.rotation(-.9*Math.sin(TAU*a+.8))));api.transformFunction(joint3,a=>h3.mul(Transform2D.translation(.65*(.5-.5*Math.cos(TAU*a)),0)));});scene.wait(.5);return scene;
}

export function layout(renderer) {
  const scene=new Scene(renderer),title=new Text('Declare → layout → animate',{fontSize:34,transform:T(.006021,3.54575)}),note=new Text('layout is an explicit target, not a persistent constraint',{fontSize:21,color:MUTED,transform:T(-.00051,3.033208)}),tile=rgb(225,235,255),square=new Square(1,{fill:rgba(BLUE,185/255),stroke:tile}),circle=new Circle(.55,{fill:rgba(ORANGE,185/255),stroke:tile}),triangle=new RegularPolygon(3,.68,{fill:rgba(GREEN,185/255),stroke:tile}),card=new Rectangle(1.35,.82,{fill:rgba(PURPLE,185/255),stroke:tile}),group=new Group([square,circle,triangle,card]);
  const header=scene.frame.topRegion(1.25),content=scene.frame.inset(.7).below(header,.25),center=[content.center.x,content.center.y];new Row({gap:.75,at:center}).place(...group.children);scene.add(title,note,group);scene.wait(.7);
  scene.parallel(1.2,api=>{api.move(square,[-1.5,1],{frame:WORLD});api.rotate(circle,.9,{about:[circle.center.x,circle.center.y]});api.scale(triangle,1.45,{about:[triangle.center.x,triangle.center.y]});api.move(card,[1.3,-.9],{frame:WORLD});});scene.wait(.35);
  scene.layout(group,{to:new Row({gap:.75,at:center}),duration:1});scene.wait(.3);scene.layout(group,{to:new Grid({rows:2,cols:2,gap:[.9,.65],at:center}),duration:1.1});scene.wait(.3);scene.layout(group,{to:new Column({gap:.38,at:center}),duration:1.1});scene.wait(.3);scene.layout(group,{to:new Row({gap:.75,at:center}),duration:1});scene.wait(.4);return scene;
}

export function math(renderer) {
  const scene=new Scene(renderer); header(scene,'Math can remain live scene data','InfiniteGrid + DynamicPolyline + live Text');
  const progress=time=>phase(time,.4,5),amp=time=>.35+.5*progress(time);
  scene.add(
    new InfiniteGrid({step:.5,stroke:'rgba(115,135,175,.20)',zIndex:-3}),new Axes({width:2,zIndex:-2}),
    new DynamicPolyline(time=>Array.from({length:321},(_,i)=>{const x=-5+10*i/320;return[x,amp(time)*Math.sin(1.25*x)+.08*x*x-.5];}),{stroke:CYAN,width:3}),
    new Text(time=>`a = ${progress(time).toFixed(3)}    f(x) = ${amp(time).toFixed(2)} sin(1.25x) + 0.08x² − 0.5`,{color:YELLOW,fontSize:23,fontFamily:'ui-monospace, monospace',transform:T(0,-2.55)}),
  );return finalize(scene,6.0);
}

export function media(renderer) {
  const scene=new Scene(renderer); header(scene,'Browser-native media shares the scene','Image · GIF · Video are ordinary scene objects');
  const img=new ZImage('../assets/media_demo/image.png',{width:2.6,transform:T(-3.6,-.25)});
  const gif=new GIF('../assets/media_demo/anim.gif',{width:2.35,transform:T(0,-.25)});
  const video=new Video('../assets/media_demo/clip.mp4',{width:2.9,duration:2,muted:true,transform:T(3.6,-.25)});
  const labels=[[-3.6,'IMAGE'],[0,'GIF'],[3.6,'VIDEO']].map(([x,label])=>new Text(label,{fontSize:18,color:MUTED,transform:T(x,-2.0)}));
  scene.add(img,gif,video,...labels);
  scene.parallel(api=>{
    api.transformFunction(img,a=>T(-3.6,-.25,.12*Math.sin(TAU*a)),{duration:5.2,easing:Easing.LINEAR});
    api.transformFunction(gif,a=>T(0,-.25,-.10*Math.sin(.8*TAU*a)),{duration:5.2,easing:Easing.LINEAR});
    api.transformFunction(video,a=>T(3.6,-.25,.08*Math.sin(.7*TAU*a)),{duration:5.2,easing:Easing.LINEAR});
    api.media(video,{duration:5.2,sourceDuration:2,loop:true});
  });
  return scene;
}

export function state_model(renderer) {
  const scene=new Scene(renderer),title=new Text('Explicit state, explicit time',{fontSize:36,transform:T(.006625,3.488543)}),rule=new Text('add/remove define lifetime; animations only change authored state',{fontSize:23,color:MUTED,transform:T(.000639,2.949168)}),immediate=new Square(1.25,{fill:BLUE,stroke:null,transform:T(-4.005,.35)}),hidden=new Circle(.68,{fill:GREEN,stroke:null,opacity:0,transform:T(0,.35)}),drawn=new Square(1.25,{fill:null,stroke:PURPLE,strokeWidth:.055,trim:0,transform:T(4.005,.35)}),il=new Text('add() = visible now',{fontSize:22,color:MUTED,transform:T(-4.009354,-.810806)}),hl=new Text('opacity=0; fade_in()',{fontSize:22,color:MUTED,transform:T(.000458,-.865806)}),dl=new Text('trim=0; create()',{fontSize:22,color:MUTED,transform:T(4.007903,-.810806)});scene.add(title,rule,immediate,hidden,drawn,il,hl,dl);scene.wait(1.2);scene.parallel(api=>{api.fadeIn(hidden);api.create(drawn);});scene.wait(.8);const late=new Circle(.36,{fill:ORANGE,stroke:null,transform:T(0,-2.453043)}),lateNote=new Text('wait(); add() → lifetime starts here',{fontSize:21,color:ORANGE,transform:T(2.782,-2.430585)});scene.add(late,lateNote);scene.wait(1);immediate.remove();scene.add(new Text('remove() → absent from later snapshots',{fontSize:21,color:RED,transform:T(-.626375,.376833)}));scene.wait(1.2);return scene;
}

function project3(p,ay,ax=0.35){let[x,y,z]=p;const cy=Math.cos(ay),sy=Math.sin(ay);[x,z]=[cy*x+sy*z,-sy*x+cy*z];const cx=Math.cos(ax),sx=Math.sin(ax);[y,z]=[cx*y-sx*z,sx*y+cx*z];const k=1/(1+.11*z);return[x*k,y*k];}
export function three_d(renderer) {
  const scene=new Scene(renderer); header(scene,'2D and 3D share one Scene','software-projected cube + parametric surface in the Web prototype');
  scene.add(new CustomObject2D(({ctx,renderer:r,time})=>{const ay=time*1.15,verts=[];for(const x of [-1,1])for(const y of [-1,1])for(const z of [-1,1])verts.push([x,y,z]);const edges=[];for(let i=0;i<8;i++)for(let j=i+1;j<8;j++){const d=verts[i].reduce((s,v,k)=>s+Math.abs(v-verts[j][k]),0);if(d===2)edges.push([i,j]);}const pv=verts.map(v=>{const q=project3(v,ay);return[q[0]-2.6,q[1]-.2];});ctx.strokeStyle=BLUE;ctx.lineWidth=3*r.dpr;for(const [i,j] of edges){ctx.beginPath();ctx.moveTo(...r.toDevice(...pv[i]));ctx.lineTo(...r.toDevice(...pv[j]));ctx.stroke();}
    ctx.strokeStyle=GREEN;ctx.lineWidth=1*r.dpr;for(let zi=0;zi<18;zi++){ctx.beginPath();for(let xi=0;xi<30;xi++){const x=-2+4*xi/29,z=-2+4*zi/17,rr=Math.hypot(x,z),y=.38*Math.sin(2.3*rr)/(1+.18*rr*rr),q=project3([x*.7,y*1.3,z*.7],-time*.55);const d=r.toDevice(q[0]+2.7,q[1]-.55);xi?ctx.lineTo(...d):ctx.moveTo(...d);}ctx.stroke();}}));return finalize(scene,5.4);
}

export function timeline(renderer) {
  const scene=new Scene(renderer),outlined=color=>({fill:rgba(color,80/255),stroke:color,width:.045,worldStroke:true}),title=new Text('One timeline, independent channels',{fontSize:32,opacity:0,transform:T(.000667,3.375474)}),left=new Circle(.72,{...outlined(BLUE),strokeWidth:.045,transform:T(-3.425,0)}),middle=new Square(1.35,{...outlined(PINK),strokeWidth:.045,transform:T(-1.18,0)}),source=new Circle(.75,{...outlined(GREEN),strokeWidth:.045,transform:T(1.095,0)}),target=new Square(1.45,{...outlined(BLUE),strokeWidth:.045,transform:T(3.42,0)});scene.add(title,left,middle,source,target);scene.fadeIn(title,{duration:.7});const leftOrigin=[-3.425,0];scene.parallel(api=>{api.transformFunction(left,a=>T(leftOrigin[0],leftOrigin[1]+.55*Math.sin(4*PI*a),TAU*a),{duration:3,easing:Easing.LINEAR});api.affine(middle,{position:[-1.18,0],rotation:PI,scale:1.35,duration:1.1,at:.35});api.style(middle,{to:outlined(GREEN),duration:1,at:1.45});api.interpolate(source,target,{duration:2.2,at:.5});});scene.wait(.35);scene.parallel(.7,api=>{api.fadeOut(left);api.fadeOut(middle,{at:.1});api.fadeOut(title,{at:.2});api.fadeOut(source,{at:.2});api.fadeOut(target,{at:.2});});return scene;
}

function parityAxis(color,end){return new Line([0,0],end,{stroke:color,strokeWidth:.035});}
function parityPanel(centerX){const parentX=parityAxis(RED,[1.5,0]),parentY=parityAxis(GREEN,[0,1.15]),origin=new Dot([0,0],{radius:.07,color:WHITE}),body=new Square(.72,{fill:rgba(BLUE,190/255),stroke:WHITE,strokeWidth:.035}),childX=parityAxis(RED,[.78,0]),childY=parityAxis(GREEN,[0,.78]),tool=new Group([body,childX,childY],{transform:T(-.55,-.1,-33*DEGREES)}),panel=new Group([parentX,parentY,origin,tool],{transform:T(centerX,-.45,20*DEGREES)});return[panel,tool];}
export function transforms(renderer) {
  const scene=new Scene(renderer),title=new Text('One vector, three coordinate frames',{fontSize:35,transform:T(.000729,3.540625)}),subtitle=new Text('move(by=(1.5, 0), frame=...) changes which basis interprets the vector',{fontSize:21,color:MUTED,transform:T(-.001094,3.059458)}),[localPanel,localTool]=parityPanel(-4.1),[parentPanel,parentTool]=parityPanel(0),[worldPanel,worldTool]=parityPanel(4.1),labels=[new Text('LOCAL',{fontSize:24,color:YELLOW,transform:T(-4.1,2.05)}),new Text('PARENT',{fontSize:24,color:YELLOW,transform:T(0,2.05)}),new Text('WORLD',{fontSize:24,color:YELLOW,transform:T(4.1,2.05)})];scene.add(title,subtitle,localPanel,parentPanel,worldPanel,...labels);scene.wait(.6);scene.parallel(2.2,api=>{api.move(localTool,[1.5,0],{frame:LOCAL});api.move(parentTool,[1.5,0],{frame:PARENT});api.move(worldTool,[1.5,0],{frame:WORLD});});scene.wait(.45);scene.camera.affine({position:[.65,-.15],scale:1.12,duration:1});scene.camera.affine({position:[0,0],scale:1,duration:.9});scene.wait(.35);return scene;
}

function heartPoints(n=420){const out=[];for(let i=0;i<n;i++){const t=TAU*i/(n-1),x=16*Math.sin(t)**3/10,y=(13*Math.cos(t)-5*Math.cos(2*t)-2*Math.cos(3*t)-Math.cos(4*t))/10;out.push([x,y]);}return out;}
export function vectors(renderer) {
  const scene=new Scene(renderer); header(scene,'SVG becomes ordinary reusable vector data','two Polyline objects share one immutable point resource');
  const pts=heartPoints(),left=new Polyline(pts,{stroke:PINK,width:3,reveal:time=>phase(time,.35,1.8),transform:T(-2.6,-.45,0,.72)}),right=new Polyline(pts,{stroke:CYAN,width:3,reveal:time=>phase(time,.70,1.8),opacity:.72,transform:T(2.6,-.45,-.22,.72)});
  scene.add(left,right);
  scene.animate(left,{transform:T(-2.25,-.2,.18,.82),duration:1.25,at:2.55});
  scene.animate(right,{transform:T(2.25,-.2,-.38,.82),opacity:1,duration:1.25,at:2.55});
  return finalize(scene,4.35);
}

export const showcaseDemos = {
  basics, batches, compositing, infinite_space, kinematics, layout, math, media,
  state_model, three_d, timeline, transforms, vectors,
};
