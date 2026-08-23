// Portable Zanim Scene IR v1 bridge.
// This module is deliberately separate from the realtime runtime: authoring can
// stay tiny, while apps that need cross-language serialization opt into IR.

import {
  Scene, CanvasRenderer, ZanimWasm, DEFAULT_WASM_URL,
  Transform2D, Easing, ScalarValue,
  ZObject, Group, Line, Polyline, Polygon, Rectangle, Square, Circle, RegularPolygon,
  Text, CustomObject2D, VectorObject2D,
  LineSet, CircleSet, RectSet, DynamicPolyline, DynamicLineSet, DynamicCircleSet, DynamicRectSet,
  InfiniteLine, InfiniteGrid, FractalField, MandelbrotSet, JuliaSet, ComplexMappedGrid, FourierEpicycles, FunctionPlot, ScalarExpr,
} from './zanim.js';

export const SCENE_IR_FORMAT='zanim.scene';
export const SCENE_IR_VERSION=1;

export class SceneIRUnsupported extends Error {}

const clamp01=x=>Math.max(0,Math.min(1,x));
const T=v=>new Transform2D(...v.map(Number));
const tIR=t=>[t.xx,t.xy,t.yx,t.yy,t.tx,t.ty];
const pIR=p=>[Number(p[0]),Number(p[1])];

function colorArray(value){
  if(value==null)return null;
  if(Array.isArray(value)){if(value.length!==4)throw new TypeError('IR color requires RGBA');return value.map(Number);}
  if(typeof value!=='string')throw new TypeError('portable Web colors must be CSS strings');
  let v=value.trim();
  if(v.startsWith('#')){let h=v.slice(1);if(h.length===3||h.length===4)h=[...h].map(c=>c+c).join('');if(h.length===6)h+='ff';if(h.length!==8)throw new TypeError(`unsupported portable color: ${value}`);return [0,2,4,6].map(i=>parseInt(h.slice(i,i+2),16));}
  const m=v.match(/^rgba?\(([^)]+)\)$/i);if(m){const q=m[1].split(',').map(x=>x.trim()),a=q.length>3?Math.round(Number(q[3])*255):255;return [Number(q[0]),Number(q[1]),Number(q[2]),a];}
  throw new TypeError(`unsupported portable color: ${value}`);
}
function colorCSS(value){if(value==null)return null;const [r,g,b,a]=value;return `#${[r,g,b,a].map(v=>Math.max(0,Math.min(255,Math.round(v))).toString(16).padStart(2,'0')).join('')}`;}
function strokeIR(color,width){return color==null?null:{color:colorArray(color),width:Number(width)};}
function styleIRFromObject(o){
  const fill='fill' in o?o.fill:null,stroke='stroke' in o?o.stroke:null,width='width' in o?o.width:null;
  return {fill:colorArray(fill),stroke:stroke==null?null:{color:colorArray(stroke),width:Number(width??.035)}};
}
function styleWeb(value){const width=value?.stroke?.width??null;return {fill:colorCSS(value?.fill??null),stroke:value?.stroke?colorCSS(value.stroke.color):null,strokeWidth:width,width,worldStroke:true};}
function easingName(fn){if(fn===Easing.LINEAR)return 'linear';if(fn===Easing.SMOOTHSTEP)return 'smoothstep';throw new SceneIRUnsupported('custom easing functions are not portable in Scene IR v1');}
function easingFn(name){if(name==='linear')return Easing.LINEAR;if(name==='smoothstep')return Easing.SMOOTHSTEP;throw new SceneIRUnsupported(`unsupported IR easing: ${name}`);}
function se2Transform(value){const theta=Number(value.theta),[x,y]=value.translation,c=Math.cos(theta),s=Math.sin(theta);return new Transform2D(c,-s,s,c,Number(x),Number(y));}
function interpolateSE2(a,b,t){const d=((Number(b.theta)-Number(a.theta)+Math.PI)%(2*Math.PI)+2*Math.PI)%(2*Math.PI)-Math.PI,theta=Number(a.theta)+d*t,x=Number(a.translation[0])+(Number(b.translation[0])-Number(a.translation[0]))*t,y=Number(a.translation[1])+(Number(b.translation[1])-Number(a.translation[1]))*t,c=Math.cos(theta),s=Math.sin(theta);return new Transform2D(c,-s,s,c,x,y);}

function documentFromIR(raw){return {width:raw.width,height:raw.height,group_count:raw.group_count,paths:raw.paths.map(path=>({group:path.group??0,fill:colorCSS(path.fill),stroke:path.stroke?{color:colorCSS(path.stroke.color),width:Number(path.stroke.width)}:null,contours:path.contours.map(c=>({closed:!!c.closed,segments:c.segments.map(seg=>seg.map(p=>pIR(p)))}))}))};}
function documentToIR(doc){return {width:doc.width,height:doc.height,group_count:doc.group_count??1,paths:doc.paths.map(path=>({group:path.group??0,fill:colorArray(path.fill),stroke:path.stroke?{color:colorArray(path.stroke.color),width:Number(path.stroke.width)}:null,contours:path.contours.map(c=>({closed:!!c.closed,segments:c.segments.map(seg=>seg.map(p=>pIR(p)))}))}))};}

function batchItemsFromIR(raw){
  if(raw.kind==='lines')return raw.starts.map((p,i)=>[p[0],p[1],raw.ends[i][0],raw.ends[i][1],colorCSS(raw.colors[i]),Number(raw.widths[i])]);
  if(raw.kind==='circles')return raw.centers.map((p,i)=>[p[0],p[1],Number(raw.radii[i]),colorCSS(raw.fills[i]),raw.stroke_colors?colorCSS(raw.stroke_colors[i]):null,raw.stroke_widths?Number(raw.stroke_widths[i]):1]);
  if(raw.kind==='rects')return raw.centers.map((p,i)=>[p[0],p[1],raw.sizes[i][0],raw.sizes[i][1],colorCSS(raw.fills[i]),raw.stroke_colors?colorCSS(raw.stroke_colors[i]):null,raw.stroke_widths?Number(raw.stroke_widths[i]):1]);
  throw new SceneIRUnsupported(`unknown batch kind ${raw.kind}`);
}
function batchIRFromItems(object,items){
  if(object instanceof LineSet)return {kind:'lines',starts:items.map(x=>[x[0],x[1]]),ends:items.map(x=>[x[2],x[3]]),colors:items.map(x=>colorArray(x[4]??object.stroke)),widths:items.map(x=>Number(x[5]??object.width))};
  if(object instanceof CircleSet)return {kind:'circles',centers:items.map(x=>[x[0],x[1]]),radii:items.map(x=>Number(x[2])),fills:items.map(x=>colorArray(x[3]??object.fill)),stroke_colors:items.some(x=>(x[4]??object.stroke)!=null)?items.map(x=>colorArray(x[4]??object.stroke)):null,stroke_widths:items.some(x=>(x[4]??object.stroke)!=null)?items.map(x=>Number(x[5]??object.width)):null};
  if(object instanceof RectSet)return {kind:'rects',centers:items.map(x=>[x[0],x[1]]),sizes:items.map(x=>[Number(x[2]),Number(x[3])]),fills:items.map(x=>colorArray(x[4]??object.fill)),stroke_colors:items.some(x=>(x[5]??object.stroke)!=null)?items.map(x=>colorArray(x[5]??object.stroke)):null,stroke_widths:items.some(x=>(x[5]??object.stroke)!=null)?items.map(x=>Number(x[6]??object.width)):null};
  throw new SceneIRUnsupported(`unsupported Web batch ${object.constructor.name}`);
}
function batchObjectFromIR(raw,state,common){
  const items=batchItemsFromIR(raw);
  if(raw.kind==='lines')return new LineSet(items,{worldStroke:true,...common});
  if(raw.kind==='circles')return new CircleSet(items,{worldStroke:true,...common});
  return new RectSet(items,{worldStroke:true,...common});
}

function geometryObjectFromIR(g,state){
  const st=styleWeb(state.style),common={transform:T(state.transform),opacity:Number(state.opacity),zIndex:Number(state.z_index),fill:st.fill,stroke:st.stroke};
  if(st.strokeWidth!=null)common.strokeWidth=Number(st.strokeWidth);
  const trim=Number(state.trim??1);let o;
  if(g.kind==='line')o=new Line(g.start,g.end,common);
  else if(g.kind==='polyline')o=new Polyline(g.points,{...common,trim});
  else if(g.kind==='polygon')o=new Polygon(g.points,{...common,trim});
  else if(g.kind==='rectangle')o=new Rectangle(Number(g.width),Number(g.height),{...common,trim});
  else if(g.kind==='square')o=new Square(Number(g.side),{...common,trim});
  else if(g.kind==='circle')o=new Circle(Number(g.radius),{...common,trim});
  else if(g.kind==='regular_polygon')o=new RegularPolygon(Number(g.sides),Number(g.radius),{...common,phase:Number(g.phase),trim});
  else throw new SceneIRUnsupported(`Web IR player does not yet implement geometry ${g.kind}`);
  return o;
}
function snapshotObjectFromIR(raw){return geometryObjectFromIR(raw.geometry,raw);}
function geometryIRFromObject(o){
  if(o instanceof Square)return {kind:'square',side:o.rectWidth};
  if(o instanceof Rectangle)return {kind:'rectangle',width:o.rectWidth,height:o.rectHeight};
  if(o instanceof RegularPolygon)return {kind:'polygon',points:o.points.map(pIR)};
  if(o instanceof Polygon)return {kind:'polygon',points:o.points.map(pIR)};
  if(o instanceof Polyline)return {kind:'polyline',points:o.points.map(pIR)};
  if(o instanceof Line)return {kind:'line',start:pIR(o.start),end:pIR(o.end)};
  if(o instanceof Circle)return {kind:'circle',radius:o.radius};
  throw new SceneIRUnsupported(`unsupported Web geometry ${o.constructor.name}`);
}
function objectSnapshotToIR(o,state){return {geometry:geometryIRFromObject(o),transform:tIR(state.transform),style:styleIRFromObjectState(o,state.style),opacity:Number(state.opacity),z_index:Number(o.zIndex),trim:Number(state.reveal??('reveal' in o?o.reveal:1)??1)};}
function styleIRFromObjectState(o,state){const s=state??null;if(s&&('fill' in s||'stroke' in s))return {fill:colorArray(s.fill??null),stroke:s.stroke==null?null:{color:colorArray(s.stroke),width:Number(s.width??.035)}};return styleIRFromObject(o);}

function commonState(record){const s=record.state;return {transform:T(s.transform),opacity:Number(s.opacity??1),zIndex:Number(s.z_index??0)};}

function sampledIndex(state,time){
  const offsets=state.sample_offsets??[],local=Number(time)-Number(state.sample_start??0);
  if(!offsets.length)return 0;let lo=0,hi=offsets.length;while(lo<hi){const mid=(lo+hi)>>1;if(Number(offsets[mid])<=local+1e-12)lo=mid+1;else hi=mid;}return Math.max(0,Math.min(offsets.length-1,lo-1));
}
function sampledValue(state,time){return state.samples[sampledIndex(state,time)];}

class SampledGeometryIRObject extends ZObject {
  constructor(state){
    const style=styleWeb(state.style);super({transform:T(state.transform),opacity:Number(state.opacity??1),zIndex:Number(state.z_index??0)});
    this.track=state;this.fill=style.fill;this.stroke=style.stroke;this.width=style.strokeWidth??.035;this.worldStroke=true;this.reveal=Number(state.trim??1);
  }
  draw(r,parent=Transform2D.identity()){
    const geometry=sampledValue(this.track,r.time),style={fill:colorArray(this.fill),stroke:this.stroke==null?null:{color:colorArray(this.stroke),width:Number(this.width)}};
    const child=geometryObjectFromIR(geometry,{geometry,transform:[1,0,0,1,0,0],style,opacity:1,z_index:0,trim:this.reveal});
    child.draw(r,parent.mul(this.transform));
  }
}
class SampledVectorIRObject extends VectorObject2D {
  constructor(state,resources){
    const docs=state.samples.map(id=>{const resource=resources.get(Number(id));if(!resource||resource.kind!=='vector_document')throw new SceneIRUnsupported('sampled_vector2d references missing vector_document resource');return documentFromIR(resource.data);});
    super(docs[0],{transform:T(state.transform),reveal:Number(state.reveal??1),opacity:Number(state.opacity??1),zIndex:Number(state.z_index??0)});this.track=state;this.documents=docs;this._sampleIndex=-1;
  }
  draw(r,parent=Transform2D.identity()){const index=sampledIndex(this.track,r.time);if(index!==this._sampleIndex){this._sampleIndex=index;this.document=this.documents[index];this.invalidate();}super.draw(r,parent);}
}
function sampledBatchObjectFromIR(state,common){
  const first=state.samples[0],provider=time=>batchItemsFromIR(sampledValue(state,time));
  if(first.kind==='lines')return new DynamicLineSet(provider,{worldStroke:true,...common});
  if(first.kind==='circles')return new DynamicCircleSet(provider,{worldStroke:true,...common});
  if(first.kind==='rects')return new DynamicRectSet(provider,{worldStroke:true,...common});
  throw new SceneIRUnsupported(`unknown sampled batch kind ${first.kind}`);
}

export function sceneFromIR(ir,renderer,{proceduralQuality={resolution:.22,minWidth:96,maxWidth:720,maxHeight:405}}={}){
  validateSceneIR(ir);
  const scene=new Scene(renderer,{fps:Number(ir.fps)}),records=new Map(ir.objects.map(x=>[Number(x.id),x])),resources=new Map((ir.resources??[]).map(x=>[Number(x.id),x])),values=new Map(),objects=new Map([[0,scene.camera]]);
  for(const v of ir.values??[])values.set(Number(v.id),new ScalarValue(Number(v.initial)));
  // Build all objects before hierarchy/value references.
  for(const record of [...records.values()].sort((a,b)=>a.id-b.id)){
    const id=Number(record.id),kind=record.kind,s=record.state;if(kind==='camera2d')continue;const common=commonState(record);let o;
    if(kind==='group')o=new Group([],common);
    else if(kind==='object2d')o=geometryObjectFromIR(s.geometry,s);
    else if(kind==='sampled_object2d')o=new SampledGeometryIRObject(s);
    else if(kind==='function_plot'){const st=styleWeb(s.style),a=s.axes;o=new FunctionPlot(ScalarExpr.fromData(s.expression),{...common,xRange:s.x_range.map(Number),axesXRange:a.x_range.map(Number),axesYRange:a.y_range.map(Number),width:Number(a.width),height:Number(a.height),center:a.center.map(Number),samples:Number(s.samples),stroke:st.stroke,strokeWidth:Number(st.strokeWidth??.035),trim:Number(s.trim??1)});}
    else if(kind==='batch2d')o=batchObjectFromIR(s.batch,s,common);
    else if(kind==='sampled_batch2d')o=sampledBatchObjectFromIR(s,common);
    else if(kind==='vector2d'){const resource=resources.get(Number(s.resource));if(!resource||resource.kind!=='vector_document')throw new SceneIRUnsupported('vector2d references missing vector_document resource');o=new VectorObject2D(documentFromIR(resource.data),{...common,reveal:Number(s.reveal??1)});}
    else if(kind==='sampled_vector2d')o=new SampledVectorIRObject(s,resources);
    else if(kind==='fourier_epicycles'){const circle=styleWeb(s.circle_style),arrow=styleWeb(s.arrow_style),trace=styleWeb(s.trace_style),tip=styleWeb(s.tip_style);o=new FourierEpicycles(s.terms,{...common,startTime:Number(s.start_time),drawDuration:Number(s.draw_duration),circleSamples:Number(s.circle_samples),traceSamples:Number(s.trace_samples),visualIndices:s.visual_indices.map(Number),circleColor:circle.stroke,circleWidth:Number(circle.strokeWidth??.012),arrowColor:arrow.fill,traceColor:trace.stroke,traceWidth:Number(trace.strokeWidth??.045),tipColor:tip.fill,tipRadius:Number(s.tip_radius),tipSides:Number(s.tip_sides)});}
    else if(kind==='infinite_line')o=new InfiniteLine(s.point,s.direction,{...common,stroke:colorCSS(s.color),strokeWidth:Number(s.stroke_width)});
    else if(kind==='infinite_grid'){
      if(Math.abs(Number(s.origin?.[0]??0))>1e-12||Math.abs(Number(s.origin?.[1]??0))>1e-12||Math.abs(Number(s.step[0])-Number(s.step[1]))>1e-12)throw new SceneIRUnsupported('Web InfiniteGrid IR v1 currently requires origin=0 and equal x/y step');
      o=new InfiniteGrid({step:Number(s.step[0]),stroke:colorCSS(s.color),strokeWidth:Number(s.stroke_width),...common});
    }else if(kind==='fractal'){
      const opts={...common,...proceduralQuality,viewport:'transform',maxIter:Number(s.max_iter),juliaC:s.julia_c,colorShift:Number(s.color_shift),colorScale:Number(s.color_scale),insideColor:colorCSS(s.inside_color),paletteColor:colorCSS(s.palette_color)};
      o=Number(s.fractal_kind)===1?new MandelbrotSet(opts):new JuliaSet(s.julia_c,opts);
    }else if(kind==='complex_grid'){
      const map={1:'square',2:'exp',3:'reciprocal',4:'mobius'}[Number(s.map_kind)],progress=s.progress;
      o=new ComplexMappedGrid(map,{...common,...proceduralQuality,viewport:'canvas',step:s.step,mapParams:s.map_params,progress:typeof progress==='object'?0:Number(progress)});
    }else throw new SceneIRUnsupported(`Web IR player does not support object ${kind}`);
    objects.set(id,o);
  }
  // Resolve scalar references and hierarchy.
  for(const record of records.values()){
    if(record.kind==='complex_grid'&&typeof record.state.progress==='object'){const o=objects.get(Number(record.id)),ref=Number(record.state.progress.value_ref);if(!values.has(ref))throw new Error(`missing ScalarValue ${ref}`);o.progress=values.get(ref);}
    const parent=record.parent;if(parent!=null&&record.kind!=='camera2d'){const p=objects.get(Number(parent)),o=objects.get(Number(record.id));if(!(p instanceof Group))throw new Error('IR parent must be Group');p.children.push(o);o._parent=p;}
  }
  const cameraRecord=[...records.values()].find(r=>r.kind==='camera2d');if(cameraRecord){const s=cameraRecord.state;scene.camera.transform=T(s.transform);scene.camera.opacity=Number(s.opacity??1);scene.camera.zIndex=Number(s.z_index??0);scene.initial.set(scene.camera.id,{transform:scene.camera.transform,opacity:scene.camera.opacity,reveal:null,style:null});}
  // Register roots without changing authored time.
  for(const record of [...records.values()].sort((a,b)=>a.id-b.id)){if(record.kind==='camera2d'||record.parent!=null)continue;const o=objects.get(Number(record.id));scene.objects.push(o);scene._track(o,Number(record.birth??0));}
  for(const [id,v] of values){scene.addValue(v);v._irId=id;}
  for(const record of records.values()){if(record.kind==='camera2d')continue;const o=objects.get(Number(record.id));o.birth=Number(record.birth??0);o.death=record.death==null?Infinity:Number(record.death);o._irId=Number(record.id);}
  scene.camera._irId=0;
  const valueObject=id=>{const v=values.get(Number(id));if(!v)throw new Error(`unknown IR value ${id}`);return v;},object=id=>{const o=Number(id)===0?scene.camera:objects.get(Number(id));if(!o)throw new Error(`unknown IR object ${id}`);return o;};
  const clips=[...(ir.clips??[])].map((x,i)=>({...x,_order:i})).sort((a,b)=>Number(a.start)-Number(b.start)||a._order-b._order);
  for(const raw of clips){const start=Number(raw.start),duration=Number(raw.duration),e=easingFn(raw.easing??'smoothstep');
    if(raw.kind==='transform')scene.animate(object(raw.target),{transform:T(raw.after),duration,easing:e,at:start});
    else if(raw.kind==='se2_transform'){
      const target=object(raw.target),before=raw.before,after=raw.after;
      scene.transformFunction(target,a=>interpolateSE2(before,after,a),{duration,easing:e,at:start});
      scene.clips.at(-1)._irSE2={before,after};
    }
    else if(raw.kind==='sampled_transform'){
      const samples=raw.samples.map(T),offsets=(raw.sample_offsets??raw.samples.map((_,i)=>duration*i/Math.max(1,raw.samples.length-1))).map(Number),provider=a=>{if(samples.length===1)return samples[0];const local=clamp01(a)*duration;let i=0;while(i+1<offsets.length&&offsets[i+1]<=local+1e-12)i++;if(Math.abs(local-offsets[i])<=1e-10||i===samples.length-1)return samples[i];const j=i+1,width=offsets[j]-offsets[i],u=width<=1e-15?0:(local-offsets[i])/width;return Transform2D.lerp(samples[i],samples[j],clamp01(u));};scene.transformFunction(object(raw.target),provider,{duration,easing:Easing.LINEAR,at:start});const clip=scene.clips.at(-1);clip._irSampled={sample_rate:raw.sample_rate,sample_offsets:raw.sample_offsets,samples:raw.samples};
    }else if(raw.kind==='opacity')scene.animate(object(raw.target),{opacity:Number(raw.after),duration,easing:e,at:start});
    else if(raw.kind==='style')scene.animate(object(raw.target),{style:styleWeb(raw.after),duration,easing:e,at:start});
    else if(raw.kind==='trim'||raw.kind==='reveal')scene.animate(object(raw.target),{reveal:Number(raw.after),duration,easing:e,at:start});
    else if(raw.kind==='batch')scene.batch(object(raw.target),{to:batchItemsFromIR(raw.after),duration,easing:e,at:start});
    else if(raw.kind==='value')scene.animateValue(valueObject(raw.target),{to:Number(raw.after),duration,easing:e,at:start});
    else if(raw.kind==='interpolation')scene.interpolate(snapshotObjectFromIR(raw.source),snapshotObjectFromIR(raw.target),{duration,easing:e,at:start});
    else throw new SceneIRUnsupported(`Web IR player does not support clip ${raw.kind}`);
  }
  scene.cursor=Number(ir.duration??0);scene.duration=Number(ir.duration??0);scene.seek(0);return scene;
}

export async function createSceneFromIR(canvas,ir,{wasmURL=DEFAULT_WASM_URL,wasm=null,renderer={},observeResize=true,...options}={}){
  const target=typeof canvas==='string'?document.querySelector(canvas):canvas;if(!target||typeof target.getContext!=='function')throw new TypeError('createSceneFromIR requires a canvas element or selector');
  const engine=wasm??await ZanimWasm.load(wasmURL),scene=sceneFromIR(ir,new CanvasRenderer(target,engine,{unitSize:Number(ir.canvas?.unit_size??renderer.unitSize??90),...renderer}),options);
  if(observeResize&&typeof ResizeObserver!=='undefined'){scene._resizeObserver=new ResizeObserver(()=>scene.render());scene._resizeObserver.observe(target);}scene.render();return scene;
}

function portableScalar(value,idMap){if(value instanceof ScalarValue)return {value_ref:idMap.get(value)};if(typeof value==='number')return value;if(typeof value==='function')throw new SceneIRUnsupported('runtime scalar callback is not portable in Scene IR v1');return Number(value);}
function initialOf(scene,o){return scene.initial.get(o.id)??{transform:o.transform,opacity:o.opacity,reveal:'reveal' in o?o.reveal:null,style:null};}
function frameSampleTimes(start,end,rate){start=Number(start);end=Math.max(start,Number(end));const times=[start];if(end<=start+1e-15)return times;const first=Math.ceil(start*rate-1e-12),last=Math.floor(end*rate+1e-12);for(let frame=first;frame<=last;frame++){const time=frame/rate;if(time>start+1e-12&&time<end-1e-12)times.push(time);}if(end-times.at(-1)>1e-12)times.push(end);else times[times.length-1]=end;return times;}
function sampledState(times,samples,rate){const start=times[0];return{sample_rate:rate,sample_start:start,sample_offsets:times.map(time=>time-start),samples};}

export function sceneToIR(scene,{sampleTransformFunctions=false,sampleDynamicProviders=false,sampleFps=scene?.fps??60}={}){
  if(!(scene instanceof Scene))throw new TypeError('sceneToIR requires Scene');
  const idMap=new Map([[scene.camera,0]]),portableObjects=[...scene._trackedObjects.values()].filter(o=>o!==scene.camera&&!o._transientInterpolation),values=[...scene.values];let next=1;for(const o of portableObjects)idMap.set(o,next++);for(const v of values)idMap.set(v,next++);
  const resources=[],resourceIds=new Map();const vectorResource=doc=>{if(resourceIds.has(doc))return resourceIds.get(doc);const id=resources.length+1;resourceIds.set(doc,id);resources.push({id,kind:'vector_document',data:documentToIR(doc)});return id;};
  const objects=[{id:0,parent:null,birth:0,death:null,kind:'camera2d',state:{transform:tIR(initialOf(scene,scene.camera).transform),opacity:initialOf(scene,scene.camera).opacity,z_index:scene.camera.zIndex}}];
  let sampledDynamicObjects=0;
  for(const o of portableObjects){const isDynamicGeometry=o instanceof DynamicPolyline,isDynamicBatch=o instanceof DynamicLineSet||o instanceof DynamicCircleSet||o instanceof DynamicRectSet,hasProvider='provider' in o&&typeof o.provider==='function';if(o instanceof CustomObject2D||o instanceof Text||(hasProvider&&!isDynamicGeometry&&!isDynamicBatch))throw new SceneIRUnsupported(`${o.constructor.name} contains browser/runtime code and is not portable in Scene IR v1`);if((isDynamicGeometry||isDynamicBatch)&&!sampleDynamicProviders)throw new SceneIRUnsupported(`${o.constructor.name} contains browser/runtime code; pass {sampleDynamicProviders:true} to bake it`);const init=initialOf(scene,o),base={id:idMap.get(o),parent:o._parent?idMap.get(o._parent):null,birth:o.birth,death:Number.isFinite(o.death)?o.death:null};let record;
    if(o instanceof Group)record={...base,kind:'group',state:{transform:tIR(init.transform),opacity:init.opacity,z_index:o.zIndex}};
    else if(o instanceof VectorObject2D)record={...base,kind:'vector2d',state:{resource:vectorResource(o.document),transform:tIR(init.transform),reveal:Number(init.reveal??1),opacity:init.opacity,z_index:o.zIndex}};
    else if(isDynamicGeometry){const rate=Math.max(1,Math.round(Number(sampleFps))),end=Math.min(Number.isFinite(o.death)?o.death:scene.duration,scene.duration),times=frameSampleTimes(o.birth,Math.max(o.birth,end),rate),samples=times.map(time=>({kind:'polyline',points:o.provider(time,o).map(pIR)}));record={...base,kind:'sampled_object2d',state:{...sampledState(times,samples,rate),transform:tIR(init.transform),style:styleIRFromObject(o),opacity:init.opacity,z_index:o.zIndex,trim:Number(init.reveal??o.reveal??1)}};sampledDynamicObjects++;}
    else if(isDynamicBatch){const rate=Math.max(1,Math.round(Number(sampleFps))),end=Math.min(Number.isFinite(o.death)?o.death:scene.duration,scene.duration),times=frameSampleTimes(o.birth,Math.max(o.birth,end),rate),samples=times.map(time=>batchIRFromItems(o,o.provider(time,o)));record={...base,kind:'sampled_batch2d',state:{...sampledState(times,samples,rate),transform:tIR(init.transform),opacity:init.opacity,z_index:o.zIndex}};sampledDynamicObjects++;}
    else if(o instanceof LineSet||o instanceof CircleSet||o instanceof RectSet)record={...base,kind:'batch2d',state:{batch:batchIRFromItems(o,scene._batchInitial.get(o.id)??o.items),transform:tIR(init.transform),opacity:init.opacity,z_index:o.zIndex}};
    else if(o instanceof FunctionPlot)record={...base,kind:'function_plot',state:{expression:o.expression.toData(),axes:{x_range:[...o.axesXRange],y_range:[...o.axesYRange],width:o.plotWidth,height:o.plotHeight,center:[...o.plotCenter]},x_range:[...o.xRange],samples:o.samples,transform:tIR(init.transform),style:styleIRFromObject(o),opacity:init.opacity,z_index:o.zIndex,trim:Number(init.reveal??o.reveal??1)}};
    else if(o instanceof FourierEpicycles)record={...base,kind:'fourier_epicycles',state:{terms:o.terms.map(term=>[term.frequency,term.re,term.im]),start_time:o.startTime,draw_duration:o.drawDuration,circle_samples:o.circleSamples,trace_samples:o.traceSamples,visual_indices:[...o.visualIndices],circle_style:{fill:null,stroke:{color:colorArray(o.circleColor),width:o.circleWidth}},arrow_style:{fill:colorArray(o.arrowColor),stroke:null},trace_style:{fill:null,stroke:{color:colorArray(o.traceColor),width:o.traceWidth}},tip_style:{fill:colorArray(o.tipColor),stroke:null},tip_radius:o.tipRadius,tip_sides:o.tipSides,transform:tIR(init.transform),opacity:init.opacity,z_index:o.zIndex}};
    else if(o instanceof InfiniteLine)record={...base,kind:'infinite_line',state:{point:pIR(o.point),direction:pIR(o.direction),transform:tIR(init.transform),color:colorArray(o.stroke),stroke_width:Number(o.width),opacity:init.opacity,z_index:o.zIndex}};
    else if(o instanceof InfiniteGrid)record={...base,kind:'infinite_grid',state:{origin:[0,0],step:[Number(o.step),Number(o.step)],transform:tIR(init.transform),color:colorArray(o.stroke),stroke_width:Number(o.width),opacity:init.opacity,z_index:o.zIndex}};
    else if(o instanceof FractalField){if([o.maxIter,o.colorShift,o.colorScale,...o.juliaC,...o.viewportCenter,o.zoom].some(x=>typeof x==='function'||x instanceof ScalarValue))throw new SceneIRUnsupported('dynamic FractalField parameter callbacks are not portable; animate its transform instead');record={...base,kind:'fractal',state:{fractal_kind:o.kind,max_iter:Number(o.maxIter),escape_radius:2,julia_c:o.juliaC.map(Number),inside_color:colorArray(o.insideColor),palette_color:colorArray(o.paletteColor),color_shift:Number(o.colorShift),color_scale:Number(o.colorScale),transform:tIR(init.transform),opacity:init.opacity,z_index:o.zIndex}};}
    else if(o instanceof ComplexMappedGrid)record={...base,kind:'complex_grid',state:{map_kind:o.mapKind,origin:[0,0],step:o.step.map(Number),progress:portableScalar(o.progress,idMap),map_params:[...o.mapParams],x_color:[255,151,92,210],y_color:[95,218,255,210],stroke_width:Number(o.strokePx)/90,transform:tIR(init.transform),opacity:init.opacity,z_index:o.zIndex}};
    else if(o instanceof ZObject)record={...base,kind:'object2d',state:objectSnapshotToIR(o,init)};
    else throw new SceneIRUnsupported(`unsupported Web object ${o.constructor.name}`);objects.push(record);
  }
  const valueRecords=values.map(v=>({id:idMap.get(v),parent:null,birth:0,death:null,kind:'scalar',initial:v.initial})),clips=[];
  for(const clip of scene.clips){if(clip.kind==='batch'){clips.push({kind:'batch',target:idMap.get(clip.object),start:clip.start,duration:clip.end-clip.start,easing:easingName(clip.easing),before:batchIRFromItems(clip.object,clip.before),after:batchIRFromItems(clip.object,clip.after)});continue;}if(clip.kind==='transformFunction'){
      if(clip._irSE2){clips.push({kind:'se2_transform',target:idMap.get(clip.object),start:clip.start,duration:clip.end-clip.start,easing:easingName(clip.easing),before:clip._irSE2.before,after:clip._irSE2.after});continue;}
      if(clip._irSampled){clips.push({kind:'sampled_transform',target:idMap.get(clip.object),start:clip.start,duration:clip.end-clip.start,sample_rate:clip._irSampled.sample_rate,sample_offsets:clip._irSampled.sample_offsets,samples:clip._irSampled.samples});continue;}
      if(!sampleTransformFunctions)throw new SceneIRUnsupported('transformFunction callback is not portable; pass {sampleTransformFunctions:true} to bake it');
      const rate=Math.max(1,Math.round(Number(sampleFps))),duration=clip.end-clip.start,times=[clip.start];
      const first=Math.ceil(clip.start*rate-1e-12),last=Math.floor(clip.end*rate+1e-12);
      for(let frame=first;frame<=last;frame++){const time=frame/rate;if(time>clip.start+1e-12&&time<clip.end-1e-12)times.push(time);}
      if(clip.end-times.at(-1)>1e-12)times.push(clip.end);else times[times.length-1]=clip.end;
      const samples=times.map(time=>{const alpha=duration<=0?1:(time-clip.start)/duration,value=clip.provider(clip.easing(clamp01(alpha)));if(!(value instanceof Transform2D))throw new SceneIRUnsupported('transformFunction provider must return Transform2D');return tIR(value);});
      clips.push({kind:'sampled_transform',target:idMap.get(clip.object),start:clip.start,duration,sample_rate:rate,sample_offsets:times.map(time=>time-clip.start),samples});continue;
    }if(clip.kind!=='state')continue;for(const [key,change] of Object.entries(clip.changes)){const common={target:idMap.get(clip.object),start:clip.start,duration:clip.end-clip.start,easing:easingName(clip.easing)};if(key==='transform')clips.push({kind:'transform',...common,before:tIR(change.before),after:tIR(change.after)});else if(key==='opacity')clips.push({kind:'opacity',...common,before:change.before,after:change.after});else if(key==='reveal')clips.push({kind:'trim',...common,before:change.before,after:change.after});else if(key==='style')clips.push({kind:'style',...common,before:styleIRFromObjectState(clip.object,change.before),after:styleIRFromObjectState(clip.object,change.after)});}}
  for(const clip of scene.valueClips)clips.push({kind:'value',target:idMap.get(clip.value),start:clip.start,duration:clip.end-clip.start,easing:easingName(clip.easing),before:clip.before,after:clip.after});
  for(const x of scene.interpolations){clips.push({kind:'interpolation',start:x.start,duration:x.end-x.start,easing:easingName(x.easing),source:objectSnapshotToIR(x.source,{transform:x.source.transform,opacity:x.source.opacity,reveal:'reveal' in x.source?x.source.reveal:1,style:styleIRFromObject(x.source)}),target:objectSnapshotToIR(x.target,{transform:x.target.transform,opacity:x.target.opacity,reveal:'reveal' in x.target?x.target.reveal:1,style:styleIRFromObject(x.target)})});}
  clips.sort((a,b)=>a.start-b.start);
  return {format:SCENE_IR_FORMAT,version:SCENE_IR_VERSION,canvas:{width:scene.renderer?.canvas?.width??1280,height:scene.renderer?.canvas?.height??720,unit_size:scene.renderer?.baseUnitSize??90},fps:scene.fps,duration:scene.duration,objects,values:valueRecords,resources,clips,meta:{portable:true,sampled_dynamic_objects:sampledDynamicObjects}};
}

export function validateSceneIR(ir){if(!ir||ir.format!==SCENE_IR_FORMAT||Number(ir.version)!==SCENE_IR_VERSION)throw new TypeError(`unsupported Zanim Scene IR ${ir?.format??'<missing>'} v${ir?.version??'?'}`);if(!ir.canvas||!Array.isArray(ir.objects)||!Array.isArray(ir.resources)||!Array.isArray(ir.clips))throw new TypeError('invalid Zanim Scene IR structure');return ir;}
export const stringifySceneIR=(ir,space=0)=>JSON.stringify(validateSceneIR(ir),null,space);
export const parseSceneIR=text=>validateSceneIR(JSON.parse(text));
