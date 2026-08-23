import { Transform2D } from './core.js';

const TOKEN_RE=/[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g;
const NUMBER_RE=/[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g;
const TRANSFORM_RE=/([A-Za-z]+)\s*\(([^)]*)\)/g;
const lerp=(a,b,t)=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t];
const line=(a,b)=>[a,lerp(a,b,1/3),lerp(a,b,2/3),b];
const quadratic=(a,q,b)=>[a,[a[0]+(q[0]-a[0])*2/3,a[1]+(q[1]-a[1])*2/3],[b[0]+(q[0]-b[0])*2/3,b[1]+(q[1]-b[1])*2/3],b];
const eq=(a,b)=>Math.abs(a[0]-b[0])<1e-12&&Math.abs(a[1]-b[1])<1e-12;

function mapEllipse(cx,cy,rx,ry,phi,p){const c=Math.cos(phi),s=Math.sin(phi);return[cx+rx*p[0]*c-ry*p[1]*s,cy+rx*p[0]*s+ry*p[1]*c];}
function vectorAngle(ux,uy,vx,vy){return Math.atan2(ux*vy-uy*vx,ux*vx+uy*vy);}
function arcToCubics(start,rx,ry,rotationDeg,largeArc,sweep,end){
  rx=Math.abs(rx);ry=Math.abs(ry);if(rx===0||ry===0||eq(start,end))return eq(start,end)?[]:[line(start,end)];
  const phi=(rotationDeg%360)*Math.PI/180,cp=Math.cos(phi),sp=Math.sin(phi),dx=(start[0]-end[0])*.5,dy=(start[1]-end[1])*.5;
  const x1p=cp*dx+sp*dy,y1p=-sp*dx+cp*dy,need=x1p*x1p/(rx*rx)+y1p*y1p/(ry*ry);
  if(need>1){const scale=Math.sqrt(need);rx*=scale;ry*=scale;}
  const numerator=rx*rx*ry*ry-rx*rx*y1p*y1p-ry*ry*x1p*x1p,denominator=rx*rx*y1p*y1p+ry*ry*x1p*x1p;
  let factor=denominator===0?0:Math.sqrt(Math.max(0,numerator/denominator));if(largeArc===sweep)factor=-factor;
  const cxp=factor*(rx*y1p/ry),cyp=factor*(-ry*x1p/rx),cx=cp*cxp-sp*cyp+(start[0]+end[0])*.5,cy=sp*cxp+cp*cyp+(start[1]+end[1])*.5;
  const ux=(x1p-cxp)/rx,uy=(y1p-cyp)/ry,vx=(-x1p-cxp)/rx,vy=(-y1p-cyp)/ry;
  const theta=Math.atan2(uy,ux);let delta=vectorAngle(ux,uy,vx,vy);if(!sweep&&delta>0)delta-=2*Math.PI;else if(sweep&&delta<0)delta+=2*Math.PI;
  const count=Math.max(1,Math.ceil(Math.abs(delta)/(Math.PI/2))),step=delta/count,out=[];let previous=start;
  for(let index=0;index<count;index++){
    const a0=theta+index*step,a1=a0+step,k=4/3*Math.tan(step/4),u0=[Math.cos(a0),Math.sin(a0)],u3=[Math.cos(a1),Math.sin(a1)],u1=[u0[0]-k*u0[1],u0[1]+k*u0[0]],u2=[u3[0]+k*u3[1],u3[1]-k*u3[0]];
    const p1=mapEllipse(cx,cy,rx,ry,phi,u1),p2=mapEllipse(cx,cy,rx,ry,phi,u2),p3=index===count-1?end:mapEllipse(cx,cy,rx,ry,phi,u3);out.push([previous,p1,p2,p3]);previous=p3;
  }
  return out;
}

export function parseSvgPathData(data){
  const tokens=String(data).replaceAll(',',' ').match(TOKEN_RE)??[];let i=0,command=null,current=[0,0],start=[0,0],segments=[],contours=[],prevC=null,prevQ=null;
  const number=()=>{if(i>=tokens.length||/^[A-Za-z]$/.test(tokens[i]))throw new Error(`invalid SVG path near token ${i}`);return Number(tokens[i++]);};
  const point=relative=>{const x=number(),y=number();return relative?[current[0]+x,current[1]+y]:[x,y];};
  const finish=closed=>{if(segments.length){contours.push({closed,segments});segments=[];}};
  while(i<tokens.length){if(/^[A-Za-z]$/.test(tokens[i]))command=tokens[i++];if(!command)throw new Error('SVG path does not start with a command');const relative=command===command.toLowerCase(),op=command.toUpperCase();
    if(op==='Z'){if(!eq(current,start))segments.push(line(current,start));current=start;finish(true);prevC=prevQ=null;command=null;continue;}
    if(op==='M'){const p=point(relative);if(segments.length)finish(false);current=start=p;prevC=prevQ=null;command=relative?'l':'L';continue;}
    if(op==='L'){const p=point(relative);segments.push(line(current,p));current=p;prevC=prevQ=null;}
    else if(op==='H'){const x=number()+(relative?current[0]:0),p=[x,current[1]];segments.push(line(current,p));current=p;prevC=prevQ=null;}
    else if(op==='V'){const y=number()+(relative?current[1]:0),p=[current[0],y];segments.push(line(current,p));current=p;prevC=prevQ=null;}
    else if(op==='C'){const c1=point(relative),c2=point(relative),p=point(relative);segments.push([current,c1,c2,p]);current=p;prevC=c2;prevQ=null;}
    else if(op==='S'){const c1=prevC?[2*current[0]-prevC[0],2*current[1]-prevC[1]]:current,c2=point(relative),p=point(relative);segments.push([current,c1,c2,p]);current=p;prevC=c2;prevQ=null;}
    else if(op==='Q'){const q=point(relative),p=point(relative);segments.push(quadratic(current,q,p));current=p;prevQ=q;prevC=null;}
    else if(op==='T'){const q=prevQ?[2*current[0]-prevQ[0],2*current[1]-prevQ[1]]:current,p=point(relative);segments.push(quadratic(current,q,p));current=p;prevQ=q;prevC=null;}
    else if(op==='A'){const rx=number(),ry=number(),rotation=number(),large=!!Number(number()),sweep=!!Number(number()),p=point(relative);segments.push(...arcToCubics(current,rx,ry,rotation,large,sweep,p));current=p;prevC=prevQ=null;}
    else throw new Error(`unsupported SVG path command ${command}`);
  }
  if(segments.length)finish(false);return contours;
}

function parseTransform(value){
  let out=Transform2D.identity();if(!value)return out;TRANSFORM_RE.lastIndex=0;let match;
  while((match=TRANSFORM_RE.exec(value))){const name=match[1],args=(match[2].match(NUMBER_RE)??[]).map(Number);let local;
    if(name==='matrix'&&args.length===6){const[a,b,c,d,e,f]=args;local=new Transform2D(a,c,b,d,e,f);}
    else if(name==='translate'&&args.length>=1&&args.length<=2)local=Transform2D.translation(args[0],args[1]??0);
    else if(name==='scale'&&args.length>=1&&args.length<=2)local=Transform2D.scaling(args[0],args[1]??args[0]);
    else if(name==='rotate'&&(args.length===1||args.length===3)){const r=Transform2D.rotation(args[0]*Math.PI/180);local=args.length===3?Transform2D.translation(args[1],args[2]).mul(r).mul(Transform2D.translation(-args[1],-args[2])):r;}
    else if(name==='skewX'&&args.length===1)local=new Transform2D(1,Math.tan(args[0]*Math.PI/180),0,1,0,0);
    else if(name==='skewY'&&args.length===1)local=new Transform2D(1,0,Math.tan(args[0]*Math.PI/180),1,0,0);
    else throw new Error(`unsupported SVG transform ${name}(${match[2]})`);
    out=out.mul(local);
  }
  return out;
}
function applyTransform(contours,t){return contours.map(c=>({closed:c.closed,segments:c.segments.map(seg=>seg.map(([x,y])=>t.apply(x,y)))}));}
function lengthValue(v){const m=String(v??'').match(NUMBER_RE);return m?Number(m[0]):null;}
function styleMap(el){const out={};for(const part of String(el.getAttribute('style')??'').split(';'))if(part.includes(':')){const i=part.indexOf(':');out[part.slice(0,i).trim()]=part.slice(i+1).trim();}for(const key of ['fill','fill-opacity','stroke','stroke-opacity','stroke-width','opacity'])if(el.hasAttribute(key))out[key]=el.getAttribute(key);return out;}
function parseColor(value,def){if(value==null)return def;const v=String(value).trim();if(v==='none')return null;if(v.startsWith('#'))return v;if(/^rgba?\(/i.test(v))return v;if(v==='black')return '#000000';if(v==='white')return '#ffffff';if(v==='red')return '#ff0000';if(v==='blue')return '#0000ff';if(v.startsWith('var('))return def;throw new Error(`unsupported SVG color ${v}`);}
function colorWithOpacity(color,opacity){if(color==null||opacity>=.999999)return color;if(color.startsWith('#')){let h=color.slice(1);if(h.length===3)h=[...h].map(x=>x+x).join('');if(h.length===6){const a=Math.max(0,Math.min(255,Math.round(opacity*255))).toString(16).padStart(2,'0');return `#${h}${a}`;}}return color;}

export function vectorDocumentFromSvg(source,{unitScale=1/72}={}){
  if(typeof DOMParser==='undefined')throw new Error('SVG import requires a browser DOMParser');
  const parsed=new DOMParser().parseFromString(String(source),'image/svg+xml');
  let root=parsed.documentElement;
  let rootTag=root.tagName?.split(':').pop()?.toLowerCase();
  if(rootTag==='parsererror')throw new Error('invalid SVG');
  if(rootTag!=='svg'){
    const nested=parsed.querySelector('svg');
    if(nested){root=nested;rootTag='svg';}
  }
  if(rootTag!=='svg')throw new Error(`SVG document root must contain <svg>, got <${root.tagName}>`);
  const vb=root.getAttribute('viewBox')||root.getAttribute('viewbox');let x0=0,y0=0,width,height;
  if(vb){const values=(vb.match(NUMBER_RE)??[]).slice(0,4).map(Number);if(values.length===4)[x0,y0,width,height]=values;}
  if(!(width>0&&height>0)){width=lengthValue(root.getAttribute('width')||root.getAttribute('data-width'));height=lengthValue(root.getAttribute('height')||root.getAttribute('data-height'));}
  if(!(width>0&&height>0))throw new Error(`SVG requires viewBox or width/height; root=${root.outerHTML.slice(0,180)}`);
  const idMap=new Map([...root.querySelectorAll('[id]')].map(el=>[el.id,el])),paths=[];let nextGroup=0;
  function render(el,parent,inheritFill,inheritStroke,inheritOpacity,groupOverride=null,fromUse=false){const tag=el.tagName?.split(':').pop()?.toLowerCase();if(tag==='defs'&&!fromUse)return;const transform=parent.mul(parseTransform(el.getAttribute?.('transform'))),styles=styleMap(el),opacity=inheritOpacity*Number(styles.opacity||1);let fill=parseColor(styles.fill,inheritFill);fill=colorWithOpacity(fill,opacity*Number(styles['fill-opacity']||1));let strokeColor=parseColor(styles.stroke,inheritStroke?.color??null),stroke=null;if(strokeColor!=null){strokeColor=colorWithOpacity(strokeColor,opacity*Number(styles['stroke-opacity']||1));stroke={color:strokeColor,width:Number(styles['stroke-width']??inheritStroke?.width??1)*unitScale};}
    if(tag==='use'){const href=el.getAttribute('href')||el.getAttribute('xlink:href');if(!href?.startsWith('#')||!idMap.has(href.slice(1)))return;const x=lengthValue(el.getAttribute('x'))||0,y=lengthValue(el.getAttribute('y'))||0,group=groupOverride??nextGroup++;render(idMap.get(href.slice(1)),transform.mul(Transform2D.translation(x,y)),fill,stroke,opacity,group,true);return;}
    if(tag==='path'&&el.getAttribute('d')){const contours=parseSvgPathData(el.getAttribute('d'));if(contours.length){const group=groupOverride??nextGroup++;paths.push({group,fill,stroke,contours:applyTransform(contours,transform)});}return;}
    if(['svg','g','symbol'].includes(tag)||fromUse)for(const child of el.children)render(child,transform,fill,stroke,opacity,groupOverride,fromUse);
  }
  render(root,Transform2D.identity(),'#000000',null,1);
  const final=Transform2D.scaling(unitScale,-unitScale).mul(Transform2D.translation(-(x0+width/2),-(y0+height/2)));
  return {width:width*unitScale,height:height*unitScale,group_count:paths.length?nextGroup:0,paths:paths.map(p=>({...p,contours:applyTransform(p.contours,final)}))};
}
