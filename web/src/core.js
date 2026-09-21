// Zanim Web: deterministic browser runtime backed by the Zig/WASM math kernel.

export const PI = Math.PI;
export const TAU = Math.PI * 2;
export const DEGREES = Math.PI / 180;
export const DEFAULT_STROKE_WIDTH = 4 / 90;
export const LOCAL='local', PARENT='parent', WORLD='world';

const logisticSmoothError = 1 / (1 + Math.exp(5));
export const Easing = Object.freeze({
  LINEAR: t => t,
  SMOOTHSTEP: t => t * t * (3 - 2 * t),
  SMOOTH: t => {
    const u = Math.max(0, Math.min(1, t));
    const value = 1 / (1 + Math.exp(-10 * (u - .5)));
    return Math.max(0, Math.min(1, (value - logisticSmoothError) / (1 - 2 * logisticSmoothError)));
  },
  EASE_IN_OUT: t => t < .5 ? 2*t*t : 1 - Math.pow(-2*t + 2, 2)/2,
});

export class Vec2 {
  constructor(x = 0, y = 0) { this.x = x; this.y = y; }
  add(v) { return new Vec2(this.x + v.x, this.y + v.y); }
  sub(v) { return new Vec2(this.x - v.x, this.y - v.y); }
  mul(k) { return new Vec2(this.x * k, this.y * k); }
  get length() { return Math.hypot(this.x, this.y); }
  static from(v) { return v instanceof Vec2 ? v : new Vec2(v[0], v[1]); }
}


export class Bounds2D {
  constructor(left,bottom,right,top){if(left>right||bottom>top)throw new RangeError('invalid bounds');Object.assign(this,{left,bottom,right,top});}
  get width(){return this.right-this.left;} get height(){return this.top-this.bottom;}
  get center(){return new Vec2((this.left+this.right)/2,(this.bottom+this.top)/2);}
  static union(...items){if(!items.length)throw new Error('Bounds2D.union requires bounds');return new Bounds2D(Math.min(...items.map(b=>b.left)),Math.min(...items.map(b=>b.bottom)),Math.max(...items.map(b=>b.right)),Math.max(...items.map(b=>b.top)));}
}
export class Anchor { constructor(x=0,y=0){if(x< -1||x>1||y< -1||y>1)throw new RangeError('anchor coordinates must be in [-1,1]');this.x=x;this.y=y;} }
export const CENTER=new Anchor(0,0), TOP=new Anchor(0,1), BOTTOM=new Anchor(0,-1), LEFT_CENTER=new Anchor(-1,0), RIGHT_CENTER=new Anchor(1,0), TOP_LEFT=new Anchor(-1,1), TOP_RIGHT=new Anchor(1,1), BOTTOM_LEFT=new Anchor(-1,-1), BOTTOM_RIGHT=new Anchor(1,-1);
function asAnchor(value){if(value instanceof Anchor)return value;const v=Vec2.from(value);return new Anchor(v.x,v.y);}
export class Frame {
  constructor(xMin,yMin,xMax,yMax){if(xMin>xMax||yMin>yMax)throw new RangeError('invalid frame');this.xMin=xMin;this.yMin=yMin;this.xMax=xMax;this.yMax=yMax;}
  static fromRenderer(r){return new Frame(-r.canvas.width/(2*r.unitSize),-r.canvas.height/(2*r.unitSize),r.canvas.width/(2*r.unitSize),r.canvas.height/(2*r.unitSize));}
  get width(){return this.xMax-this.xMin;} get height(){return this.yMax-this.yMin;}
  anchor(anchor){const a=asAnchor(anchor);return new Vec2((this.xMin+this.xMax)/2+a.x*this.width/2,(this.yMin+this.yMax)/2+a.y*this.height/2);}
  get center(){return this.anchor(CENTER);} get top(){return this.anchor(TOP);} get bottom(){return this.anchor(BOTTOM);} get left(){return this.anchor(LEFT_CENTER);} get right(){return this.anchor(RIGHT_CENTER);}
  inset(x,y=x){if(x<0||y<0||2*x>this.width||2*y>this.height)throw new RangeError('invalid frame inset');return new Frame(this.xMin+x,this.yMin+y,this.xMax-x,this.yMax-y);}
  topRegion(height){if(height<0||height>this.height)throw new RangeError('region height must fit');return new Frame(this.xMin,this.yMax-height,this.xMax,this.yMax);}
  below(other,gap=0){const yMax=Math.min(this.yMax,other.yMin-gap);if(yMax<this.yMin)throw new RangeError('no frame remains below');return new Frame(this.xMin,this.yMin,this.xMax,yMax);}
}
function transformBounds(points,m){const q=points.map(p=>m.apply(p[0],p[1]));return new Bounds2D(Math.min(...q.map(p=>p[0])),Math.min(...q.map(p=>p[1])),Math.max(...q.map(p=>p[0])),Math.max(...q.map(p=>p[1])));}
function cubicAxisBounds(p0,p1,p2,p3){
  const values=[p0,p3],a=-p0+3*p1-3*p2+p3,b=2*(p0-2*p1+p2),c=p1-p0;
  const evalAt=t=>{const u=1-t;return u*u*u*p0+3*u*u*t*p1+3*u*t*t*p2+t*t*t*p3;};
  if(Math.abs(a)<1e-14){if(Math.abs(b)>1e-14){const t=-c/b;if(t>0&&t<1)values.push(evalAt(t));}}
  else{const disc=b*b-4*a*c;if(disc>=0){const root=Math.sqrt(disc);for(const t of [(-b-root)/(2*a),(-b+root)/(2*a)])if(t>0&&t<1)values.push(evalAt(t));}}
  return [Math.min(...values),Math.max(...values)];
}
function vectorDocumentBounds(document,m){
  let left=Infinity,bottom=Infinity,right=-Infinity,top=-Infinity;
  for(const path of document.paths)for(const contour of path.contours)for(const seg of contour.segments){
    const q=seg.map(p=>m.apply(p[0],p[1])),xb=cubicAxisBounds(q[0][0],q[1][0],q[2][0],q[3][0]),yb=cubicAxisBounds(q[0][1],q[1][1],q[2][1],q[3][1]);
    left=Math.min(left,xb[0]);right=Math.max(right,xb[1]);bottom=Math.min(bottom,yb[0]);top=Math.max(top,yb[1]);
  }
  if(!Number.isFinite(left)){const p=m.apply(0,0);return new Bounds2D(p[0],p[1],p[0],p[1]);}
  return new Bounds2D(left,bottom,right,top);
}
function boundsOf(object,extra=Transform2D.identity()){
  const m=extra.mul(object.transform);
  if(typeof object._boundsWithTransform==='function')return object._boundsWithTransform(m);
  if(object instanceof Group){if(!object.children.length){const p=m.apply(0,0);return new Bounds2D(p[0],p[1],p[0],p[1]);}return Bounds2D.union(...object.children.map(c=>boundsOf(c,m)));}
  if(object instanceof Ellipse){const c=m.apply(0,0),ex=Math.hypot(object.radiusX*m.xx,object.radiusY*m.xy),ey=Math.hypot(object.radiusX*m.yx,object.radiusY*m.yy);return new Bounds2D(c[0]-ex,c[1]-ey,c[0]+ex,c[1]+ey);}
  if(object instanceof Arc){const c=m.apply(0,0),ex=object.radius*Math.hypot(m.xx,m.xy),ey=object.radius*Math.hypot(m.yx,m.yy);return new Bounds2D(c[0]-ex,c[1]-ey,c[0]+ex,c[1]+ey);}
  if(object instanceof Circle){const c=m.apply(0,0),ex=object.radius*Math.hypot(m.xx,m.xy),ey=object.radius*Math.hypot(m.yx,m.yy);return new Bounds2D(c[0]-ex,c[1]-ey,c[0]+ex,c[1]+ey);}
  if(object instanceof Polyline){return transformBounds(object.points,m);}
  if(object instanceof Line){return transformBounds([object.start,object.end],m);}
  if(object instanceof CircleSet){const pieces=object.items.map(i=>{const c=m.apply(i[0],i[1]),ex=i[2]*Math.hypot(m.xx,m.xy),ey=i[2]*Math.hypot(m.yx,m.yy);return new Bounds2D(c[0]-ex,c[1]-ey,c[0]+ex,c[1]+ey);});return Bounds2D.union(...pieces);}
  if(object instanceof LineSet){return transformBounds(object.items.flatMap(i=>[[i[0],i[1]],[i[2],i[3]]]),m);}
  if(object instanceof RectSet){return Bounds2D.union(...object.items.map(i=>transformBounds([[i[0]-i[2]/2,i[1]-i[3]/2],[i[0]+i[2]/2,i[1]-i[3]/2],[i[0]+i[2]/2,i[1]+i[3]/2],[i[0]-i[2]/2,i[1]+i[3]/2]],m)));}
  if(object instanceof VectorObject2D){return vectorDocumentBounds(object.document,m);}
  if(object instanceof FourierEpicycles){return transformBounds(object._fullTrace,m);}
  if(object instanceof Text){const p=m.apply(0,0),w=String(typeof object.text==='function'?object.text(0,object):object.text).length*object.fontSize*.0062,h=object.fontSize*.011;return new Bounds2D(p[0]-w/2,p[1]-h/2,p[0]+w/2,p[1]+h/2);}
  throw new TypeError(`${object.constructor.name} has no finite bounds`);
}
export class Mat2 {
  constructor(xx = 1, xy = 0, yx = 0, yy = 1) { this.xx=xx; this.xy=xy; this.yx=yx; this.yy=yy; }
  static identity() { return new Mat2(); }
  static rotation(r) { const c=Math.cos(r),s=Math.sin(r); return new Mat2(c,-s,s,c); }
  static scaling(x,y=x) { return new Mat2(x,0,0,y); }
  static shear(x=0,y=0) { return new Mat2(1,x,y,1); }
  static lerp(a,b,t) { return new Mat2(a.xx+(b.xx-a.xx)*t,a.xy+(b.xy-a.xy)*t,a.yx+(b.yx-a.yx)*t,a.yy+(b.yy-a.yy)*t); }
  mul(b) { return new Mat2(this.xx*b.xx+this.xy*b.yx,this.xx*b.xy+this.xy*b.yy,this.yx*b.xx+this.yy*b.yx,this.yx*b.xy+this.yy*b.yy); }
  inverse(){const d=this.determinant;if(Math.abs(d)<1e-15)throw new RangeError('singular Mat2');return new Mat2(this.yy/d,-this.xy/d,-this.yx/d,this.xx/d);}
  apply(x,y) { return [this.xx*x+this.xy*y,this.yx*x+this.yy*y]; }
  get determinant() { return this.xx*this.yy-this.xy*this.yx; }
}

export class Transform2D {
  constructor(xx=1,xy=0,yx=0,yy=1,tx=0,ty=0) { Object.assign(this,{xx,xy,yx,yy,tx,ty}); }
  static identity() { return new Transform2D(); }
  static translation(x,y) { return new Transform2D(1,0,0,1,x,y); }
  static scaling(x,y=x) { return new Transform2D(x,0,0,y,0,0); }
  static rotation(r) { const c=Math.cos(r),s=Math.sin(r); return new Transform2D(c,-s,s,c,0,0); }
  static shear(x=0,y=0) { return new Transform2D(1,x,y,1,0,0); }
  static fromMat2(m) { return new Transform2D(m.xx,m.xy,m.yx,m.yy,0,0); }
  static affine({position=[0,0],rotation=0,scale=1,shear=[0,0]}={}) {
    const [sx,sy] = Array.isArray(scale) ? scale : [scale,scale];
    const [hx,hy] = shear;
    return Transform2D.translation(...position)
      .mul(Transform2D.rotation(rotation))
      .mul(Transform2D.shear(hx,hy))
      .mul(Transform2D.scaling(sx,sy));
  }
  static lerp(a,b,t) { return new Transform2D(a.xx+(b.xx-a.xx)*t,a.xy+(b.xy-a.xy)*t,a.yx+(b.yx-a.yx)*t,a.yy+(b.yy-a.yy)*t,a.tx+(b.tx-a.tx)*t,a.ty+(b.ty-a.ty)*t); }
  mul(b) { return new Transform2D(this.xx*b.xx+this.xy*b.yx,this.xx*b.xy+this.xy*b.yy,this.yx*b.xx+this.yy*b.yx,this.yx*b.xy+this.yy*b.yy,this.xx*b.tx+this.xy*b.ty+this.tx,this.yx*b.tx+this.yy*b.ty+this.ty); }
  inverse(){const d=this.determinant;if(Math.abs(d)<1e-15)throw new RangeError('singular Transform2D');return new Transform2D(this.yy/d,-this.xy/d,-this.yx/d,this.xx/d,(this.xy*this.ty-this.yy*this.tx)/d,(this.yx*this.tx-this.xx*this.ty)/d);}
  apply(x,y) { return [this.xx*x+this.xy*y+this.tx,this.yx*x+this.yy*y+this.ty]; }
  vector(x,y) { return [this.xx*x+this.xy*y,this.yx*x+this.yy*y]; }
  get linear() { return new Mat2(this.xx,this.xy,this.yx,this.yy); }
  get determinant() { return this.xx*this.yy-this.xy*this.yx; }
}
export const affine2d = opts => Transform2D.affine(opts);

function rgbaWithOpacity(color, opacity) {
  // Canvas supports CSS colors; globalAlpha handles object opacity.
  return color;
}

export const Colors = Object.freeze({
  BLUE:'#60a6ff', GREEN:'#52cd96', RED:'#f55c69', YELLOW:'#ffd669', ORANGE:'#ff975c',
  PURPLE:'#b87cff', PINK:'#f55c91', CYAN:'#5fdaff', WHITE:'#ffffff', GRAY:'#919eb8', MUTED:'#919eb8', BLACK:'#000000',
});
export const {WHITE,MUTED,BLUE,GREEN,RED,ORANGE,YELLOW,CYAN,PINK,PURPLE,GRAY,BLACK}=Colors;
export const ORIGIN=Object.freeze([0,0]), RIGHT=Object.freeze([1,0]), LEFT=Object.freeze([-1,0]), UP=Object.freeze([0,1]), DOWN=Object.freeze([0,-1]);

export const DEFAULT_WASM_URL = globalThis.__ZANIM_WASM_URL__ ?? new URL('../dist/zanim_web_core.wasm', import.meta.url);

const sharedWasmLoads=globalThis.__ZANIM_WASM_CACHE__??=(new Map());
let activeZanimWasm=null;
export class ZanimWasm {
  constructor(instance) { this.instance=instance; this.exports=instance.exports; if(this.exports.zanim_web_abi_version()!==1) throw new Error('Zanim Web ABI mismatch'); activeZanimWasm=this; }
  static async load(url) {
    const key=String(url);
    const cached=sharedWasmLoads.get(key);
    if(cached)return cached;
    const pending=(async()=>{
      const response=await fetch(url); let result;
      if(WebAssembly.instantiateStreaming){try{result=await WebAssembly.instantiateStreaming(response.clone(),{});}catch{result=await WebAssembly.instantiate(await response.arrayBuffer(),{});}}
      else result=await WebAssembly.instantiate(await response.arrayBuffer(),{});
      return new ZanimWasm(result.instance);
    })();
    sharedWasmLoads.set(key,pending);
    try{return await pending;}catch(error){sharedWasmLoads.delete(key);throw error;}
  }
  pathBoolean(aContours,bContours,operation,epsilon=1e-9){
    const opId={intersection:0,union:1,difference:2,exclusion:3}[operation];
    if(opId==null)throw new RangeError('invalid boolean operation');
    const flatten=contours=>{
      const points=[],ends=[];let count=0;
      for(const contour of contours){for(const p of contour){points.push(Number(p[0]),Number(p[1]));count++;}ends.push(count);}
      return{points,ends,count};
    };
    const a=flatten(aContours),b=flatten(bContours),e=this.exports;
    const maxPoints=e.zanim_web_boolean_max_input_points(),maxContours=e.zanim_web_boolean_max_input_contours();
    if(a.count>maxPoints||b.count>maxPoints)throw new RangeError('boolean input exceeds WASM point capacity');
    if(a.ends.length>maxContours||b.ends.length>maxContours)throw new RangeError('boolean input exceeds WASM contour capacity');
    const memory=e.memory.buffer;
    new Float64Array(memory,e.zanim_web_boolean_a_points_ptr(),a.count*2).set(a.points);
    new Float64Array(memory,e.zanim_web_boolean_b_points_ptr(),b.count*2).set(b.points);
    new Uint32Array(memory,e.zanim_web_boolean_a_ends_ptr(),a.ends.length).set(a.ends);
    new Uint32Array(memory,e.zanim_web_boolean_b_ends_ptr(),b.ends.length).set(b.ends);
    const encoded=e.zanim_web_path_boolean(a.count,a.ends.length,b.count,b.ends.length,opId,epsilon);
    if(!encoded)throw new Error('Zig vector boolean backend failed');
    const pointCount=encoded-1,contourCount=e.zanim_web_boolean_output_contour_count(),buffer=e.memory.buffer;
    const rawPoints=new Float64Array(buffer,e.zanim_web_boolean_output_points_ptr(),pointCount*2);
    const rawEnds=new Uint32Array(buffer,e.zanim_web_boolean_output_ends_ptr(),contourCount);
    const points=Array.from({length:pointCount},(_,i)=>[rawPoints[i*2],rawPoints[i*2+1]]);
    const contours=[];let start=0;
    for(let i=0;i<contourCount;i++){const end=rawEnds[i];contours.push(points.slice(start,end));start=end;}
    return contours;
  }
  determinant(m){return this.exports.zanim_web_matrix_det(m.xx,m.xy,m.yx,m.yy);}
  resolveGrid(width,height,unitSize,step,m){const count=this.exports.zanim_web_resolve_grid(width,height,unitSize,step,m.xx,m.xy,m.yx,m.yy);const ptr=this.exports.zanim_web_grid_data_ptr();return new Float64Array(this.exports.memory.buffer,ptr,count*4);}
  renderFractal(kind,width,height,centerRe,centerIm,worldPerPixel,maxIter=240,juliaRe=0,juliaIm=0,colorShift=0,colorScale=1,inside=[5,7,14],palette=[105,185,255]){
    const count=this.exports.zanim_web_render_fractal(kind,width,height,centerRe,centerIm,worldPerPixel,maxIter,juliaRe,juliaIm,colorShift,colorScale,...inside.slice(0,3),...palette.slice(0,3));
    if(!count) throw new Error('invalid fractal render parameters');
    const ptr=this.exports.zanim_web_fractal_data_ptr();
    return new Uint8ClampedArray(this.exports.memory.buffer,ptr,count*4);
  }
  renderComplexGrid(kind,width,height,centerRe,centerIm,worldPerPixel,stepX,stepY,progress,strokePx=1.15,params=[]){
    const q=[...params,0,0,0,0,0,0,0,0].slice(0,8);
    const count=this.exports.zanim_web_render_complex_grid(kind,width,height,centerRe,centerIm,worldPerPixel,stepX,stepY,progress,strokePx,...q);
    if(!count) throw new Error('invalid complex-grid render parameters');
    const ptr=this.exports.zanim_web_fractal_data_ptr();
    return new Uint8ClampedArray(this.exports.memory.buffer,ptr,count*4);
  }
  upload3DGeometry(meshes){
    const e=this.exports,memory=e.memory.buffer,maxVertices=e.zanim_web_3d_max_vertices(),maxIndices=e.zanim_web_3d_max_indices(),maxMeshes=e.zanim_web_3d_max_meshes();
    if(meshes.length>maxMeshes)throw new RangeError(`3D layer exceeds ${maxMeshes} meshes`);
    const positions=new Float32Array(memory,e.zanim_web_3d_positions_ptr(),maxVertices*3),normals=new Float32Array(memory,e.zanim_web_3d_normals_ptr(),maxVertices*3),indices=new Uint32Array(memory,e.zanim_web_3d_indices_ptr(),maxIndices),ranges=new Uint32Array(memory,e.zanim_web_3d_ranges_ptr(),maxMeshes*4);
    let vertexOffset=0,indexOffset=0;
    for(let i=0;i<meshes.length;i++){const mesh=meshes[i];if(vertexOffset+mesh.vertexCount>maxVertices)throw new RangeError(`3D vertices exceed ${maxVertices}`);if(indexOffset+mesh.indexCount>maxIndices)throw new RangeError(`3D indices exceed ${maxIndices}`);positions.set(mesh.positions,vertexOffset*3);normals.set(mesh.normals,vertexOffset*3);indices.set(mesh.indices,indexOffset);ranges.set([vertexOffset,mesh.vertexCount,indexOffset,mesh.indexCount],i*4);vertexOffset+=mesh.vertexCount;indexOffset+=mesh.indexCount;}
    const upload={meshes:[...meshes],meshCount:meshes.length,serial:(this._3dSerial??0)+1};this._3dSerial=upload.serial;this._3dUpload=upload;return upload;
  }
  render3D(width,height,camera,upload,states,lighting=null){
    const e=this.exports;if(!upload||this._3dUpload!==upload)throw new Error('3D geometry upload is no longer active');if(states.length!==upload.meshCount)throw new RangeError('3D state count must match uploaded meshes');
    const maxWidth=e.zanim_web_3d_max_width(),maxHeight=e.zanim_web_3d_max_height();if(width>maxWidth||height>maxHeight)throw new RangeError(`3D render target exceeds ${maxWidth}x${maxHeight}`);
    const memory=e.memory.buffer,models=new Float32Array(memory,e.zanim_web_3d_models_ptr(),upload.meshCount*16),colors=new Uint32Array(memory,e.zanim_web_3d_colors_ptr(),upload.meshCount),opacities=new Float32Array(memory,e.zanim_web_3d_opacities_ptr(),upload.meshCount);
    for(let i=0;i<states.length;i++){const state=states[i];models.set(state.model,i*16);colors[i]=state.colorRGBA>>>0;opacities[i]=state.opacity;}
    const p=camera.position,t=camera.target,u=camera.up,ortho=camera.orthographicHeight;
    const lightVec=(value)=>{
      if(Array.isArray(value))return{x:Number(value[0]),y:Number(value[1]),z:Number(value[2])};
      if(value&&typeof value==='object')return{x:Number(value.x),y:Number(value.y),z:Number(value.z)};
      throw new TypeError('3D light vector must be [x,y,z] or {x,y,z}');
    };
    let lightKind=0,light={x:.35,y:.82,z:.48};
    if(lighting?.position!=null){lightKind=1;light=lightVec(lighting.position);}
    else if(lighting?.direction!=null){light=lightVec(lighting.direction);}
    const ambient=lighting?.ambient==null?.24:Number(lighting.ambient);
    const diffuse=lighting?.diffuse==null?.76:Number(lighting.diffuse);
    const count=e.zanim_web_render_3d(width,height,upload.meshCount,p.x,p.y,p.z,t.x,t.y,t.z,u.x,u.y,u.z,camera.fovYDegrees,camera.near,camera.far,ortho??0,ortho==null?0:1,lightKind,light.x,light.y,light.z,ambient,diffuse);
    if(!count)throw new Error('3D WASM render failed');
    return new Uint8ClampedArray(e.memory.buffer,e.zanim_web_3d_pixels_ptr(),count*4);
  }
}

let nextValueId=1;
export class ScalarValue {
  constructor(value=0){this.id=nextValueId++;this.value=Number(value);this.initial=this.value;}
}
export function sampleValue(value,time=0){return value instanceof ScalarValue?value.value:typeof value==='function'?Number(value(time)):Number(value);}
const scalarAt=sampleValue;

function asScalarExpr(value){if(value instanceof ScalarExpr)return value;if(typeof value==='number'&&Number.isFinite(value))return ScalarExpr.constant(value);throw new TypeError('expected ScalarExpr or finite number');}
export class ScalarExpr {
  constructor(op,args=[]){this.op=op;this.args=[...args];}
  static constant(value){if(!Number.isFinite(Number(value)))throw new TypeError('ScalarExpr constant must be finite');return new ScalarExpr('const',[Number(value)]);}
  static variable(name){if(name!=='x'&&name!=='time')throw new RangeError("ScalarExpr variable must be 'x' or 'time'");return new ScalarExpr('var',[name]);}
  static fromData(value){if(!Array.isArray(value)||!value.length)throw new TypeError('invalid portable scalar expression');const op=String(value[0]);if(op==='const')return ScalarExpr.constant(value[1]);if(op==='var')return ScalarExpr.variable(value[1]);const unary=new Set(['neg','sin','cos','exp','log','abs']),binary=new Set(['add','sub','mul','div','pow']);if(unary.has(op)&&value.length===2)return new ScalarExpr(op,[ScalarExpr.fromData(value[1])]);if(binary.has(op)&&value.length===3)return new ScalarExpr(op,[ScalarExpr.fromData(value[1]),ScalarExpr.fromData(value[2])]);throw new TypeError(`invalid ScalarExpr op ${op}`);}
  toData(){if(this.op==='const'||this.op==='var')return[this.op,this.args[0]];return[this.op,...this.args.map(arg=>asScalarExpr(arg).toData())];}
  evaluate({x=0,time=0}={}){const op=this.op;if(op==='const')return Number(this.args[0]);if(op==='var')return this.args[0]==='x'?Number(x):Number(time);if(op==='neg')return-asScalarExpr(this.args[0]).evaluate({x,time});const a=asScalarExpr(this.args[0]).evaluate({x,time});if(op==='sin')return Math.sin(a);if(op==='cos')return Math.cos(a);if(op==='exp')return Math.exp(a);if(op==='log')return Math.log(a);if(op==='abs')return Math.abs(a);const b=asScalarExpr(this.args[1]).evaluate({x,time});if(op==='add')return a+b;if(op==='sub')return a-b;if(op==='mul')return a*b;if(op==='div')return a/b;if(op==='pow')return a**b;throw new TypeError(`unsupported ScalarExpr op ${op}`);}
  _binary(op,other){return new ScalarExpr(op,[this,asScalarExpr(other)]);}
  add(v){return this._binary('add',v);} sub(v){return this._binary('sub',v);} mul(v){return this._binary('mul',v);} div(v){return this._binary('div',v);} pow(v){return this._binary('pow',v);}
  neg(){return new ScalarExpr('neg',[this]);} sin(){return new ScalarExpr('sin',[this]);} cos(){return new ScalarExpr('cos',[this]);} exp(){return new ScalarExpr('exp',[this]);} log(){return new ScalarExpr('log',[this]);} abs(){return new ScalarExpr('abs',[this]);}
}
export const X=ScalarExpr.variable('x'), TIME=ScalarExpr.variable('time');

let nextObjectId=1;
export class ZObject {
  constructor({transform=Transform2D.identity(),opacity=1,zIndex=0}={}) { this.id=nextObjectId++; this.transform=transform; this.opacity=opacity; this.zIndex=zIndex; this.visible=true; this.birth=0; this.death=Infinity; this._scene=null; this._parent=null; }
  draw(renderer,parent=Transform2D.identity()){}
  world(parent=Transform2D.identity()){return parent.mul(this.transform);}
  bounds(){return boundsOf(this);}
  get center(){return this.bounds().center;}
  anchor(anchor=CENTER){const a=asAnchor(anchor),b=this.bounds();return new Vec2(b.center.x+a.x*b.width/2,b.center.y+a.y*b.height/2);}
  shift(x,y){const v=x instanceof Vec2?x:Array.isArray(x)?Vec2.from(x):new Vec2(x,y);this.transform=Transform2D.translation(v.x,v.y).mul(this.transform);return this;}
  place({anchor=CENTER,at=[0,0]}={}){const q=Vec2.from(at),p=this.anchor(anchor);return this.shift(q.x-p.x,q.y-p.y);}
  nextTo(other,direction=RIGHT,buff=.25){if(buff<0)throw new RangeError('buff must be >= 0');const raw=Vec2.from(direction),len=raw.length;if(len<=1e-12)throw new RangeError('nextTo direction must be non-zero');const d=new Vec2(raw.x/len,raw.y/len),source=this.anchor([-d.x,-d.y]),target=other instanceof ZObject?other.anchor([d.x,d.y]):Vec2.from(other);return this.shift(target.x+d.x*buff-source.x,target.y+d.y*buff-source.y);}
  _bound(){if(!this._scene)throw new Error('object must be added before animation');return this._scene;}
  fadeIn(options={}){this._bound().fadeIn(this,options);return this;}
  fadeOut(options={}){this._bound().fadeOut(this,options);return this;}
  opacityTo(to,options={}){this._bound().animate(this,{...options,opacity:to});return this;}
  styleTo(style,options={}){this._bound().style(this,{...options,to:style});return this;}
  transformFunction(provider,options={}){this._bound().transformFunction(this,provider,options);return this;}
  affine(options={}){this._bound().affine(this,options);return this;}
  move(by,options={}){this._bound().move(this,by,options);return this;}
  moveAlong(path,options={}){this._bound().moveAlong(this,path,options);return this;}
  rotate(by,options={}){this._bound().rotate(this,by,options);return this;}
  scale(by,options={}){this._bound().scale(this,by,options);return this;}
  create(options={}){this._bound().create(this,options);return this;}
  trimTo(to,options={}){this._bound().trim(this,{...options,to});return this;}
  remove(){this._bound().remove(this);return this;}
}

export class Camera2D extends ZObject {
  constructor(scene){super();this._scene=scene;}
  affine({position=[0,0],rotation=0,scale=1,shear=[0,0],...options}={}){this._scene.animate(this,{...options,transform:Transform2D.affine({position,rotation,scale,shear})});return this;}
  pan(by,options={}){const current=this._scene.authoredState(this).transform,v=Vec2.from(by);return this.transformFunction(a=>current.mul(Transform2D.translation(-v.x*a,-v.y*a)),options);}
}

export class CustomObject2D extends ZObject {
  constructor(drawFn, opts={}) { super(opts); this.drawFn=drawFn; }
  draw(renderer,parent=Transform2D.identity()) { withObjectContext(renderer,this,ctx=>this.drawFn({renderer,ctx,time:renderer.time??0,transform:this.world(parent),object:this})); }
}

export class SceneViewport extends ZObject {
  constructor({sourceCenter=[0,0],sourceSize=[1,1],width=4,height=3,...rest}={}) {
    super(rest);
    this.sourceCenter=sourceCenter;
    this.sourceSize=sourceSize;
    this.width=Number(width);
    this.height=Number(height);
    if(!(this.width>0&&this.height>0))throw new RangeError('SceneViewport width/height must be positive');
  }
  _value(value,time){return typeof value==='function'?value(time,this):value;}
  _boundsWithTransform(m){
    return transformBounds([
      [-this.width/2,-this.height/2],
      [ this.width/2,-this.height/2],
      [ this.width/2, this.height/2],
      [-this.width/2, this.height/2],
    ],m);
  }
  bounds(){return this._boundsWithTransform(this.transform);}
  draw(r,parent=Transform2D.identity()){
    const center=Vec2.from(this._value(this.sourceCenter,r.time??0));
    const size=Vec2.from(this._value(this.sourceSize,r.time??0));
    if(!(size.x>0&&size.y>0))return;

    const sourceCenter=r.toDevice(center.x,center.y);
    const sx=sourceCenter[0]-size.x*r.unitSize/2;
    const sy=sourceCenter[1]-size.y*r.unitSize/2;
    const sw=size.x*r.unitSize;
    const sh=size.y*r.unitSize;

    const buffer=document.createElement('canvas');
    buffer.width=Math.max(1,Math.round(sw));
    buffer.height=Math.max(1,Math.round(sh));
    buffer.getContext('2d').drawImage(
      r.canvas,sx,sy,sw,sh,0,0,buffer.width,buffer.height,
    );

    const m=this.world(parent),ctx=r.ctx;
    ctx.save();
    ctx.globalAlpha*=clamp01(this.opacity);
    const p=r.toDevice(...m.apply(0,0));
    const ex=m.vector(this.width,0),ey=m.vector(0,this.height);
    const dw=Math.hypot(ex[0],ex[1])*r.unitSize;
    const dh=Math.hypot(ey[0],ey[1])*r.unitSize;
    const angle=Math.atan2(ex[1],ex[0]);
    ctx.translate(p[0],p[1]);
    ctx.rotate(-angle);
    ctx.drawImage(buffer,-dw/2,-dh/2,dw,dh);
    ctx.restore();
  }
}

function withObjectContext(renderer,obj,fn){const ctx=renderer.ctx;ctx.save();ctx.globalAlpha*=Math.max(0,Math.min(1,obj.opacity));fn(ctx);ctx.restore();}
function applyPoint(m,p){return m.apply(p[0],p[1]);}

function clamp01(value){return Math.max(0,Math.min(1,value));}
export function lerpNumber(a,b,t){return a+(b-a)*t;}
function lerpPoint(a,b,t){return [lerpNumber(a[0],b[0],t),lerpNumber(a[1],b[1],t)];}
function cloneTransform(m){return new Transform2D(m.xx,m.xy,m.yx,m.yy,m.tx,m.ty);}

// Match src/interpolation.zig's Polyline->Polyline normalization: both paths
// are sampled at uniform arc-length positions using the denser endpoint's
// segment count. Keeping this rule identical is what makes Web replace() move
// like the native renderer instead of merely cross-fading or changing order.
export function resamplePolylineByArcLength(points, segmentCount){
  if(segmentCount<1||points.length<2)throw new RangeError('polyline interpolation requires at least two points');
  const lengths=[];let total=0;
  for(let i=0;i<points.length-1;i++){const a=points[i],b=points[i+1],d=Math.hypot(b[0]-a[0],b[1]-a[1]);lengths.push(d);total+=d;}
  if(total<=1e-14)return Array.from({length:segmentCount+1},()=>[points[0][0],points[0][1]]);
  const out=[[points[0][0],points[0][1]]];let edgeIndex=0,walked=0,edgeStart=points[0],edgeEnd=points[1],edgeLength=lengths[0];
  for(let i=0;i<segmentCount;i++){
    const target=total*(i+1)/segmentCount;
    while(edgeIndex+1<lengths.length && walked+edgeLength<target-1e-14){walked+=edgeLength;edgeIndex++;edgeStart=points[edgeIndex];edgeEnd=points[edgeIndex+1];edgeLength=lengths[edgeIndex];}
    const local=edgeLength<=1e-14?0:(target-walked)/edgeLength;
    out.push([lerpNumber(edgeStart[0],edgeEnd[0],clamp01(local)),lerpNumber(edgeStart[1],edgeEnd[1],clamp01(local))]);
  }
  return out;
}


export function pointAtArcLength(points,proportion){
  if(!Array.isArray(points)||points.length<2)throw new RangeError('path sampling requires at least two points');
  const alpha=clamp01(Number(proportion)),lengths=[];let total=0;
  for(let i=0;i<points.length-1;i++){const a=points[i],b=points[i+1],d=Math.hypot(b[0]-a[0],b[1]-a[1]);lengths.push(d);total+=d;}
  if(total<=1e-14)return Vec2.from(points[0]);
  const target=total*alpha;let walked=0;
  for(let i=0;i<lengths.length;i++){
    const length=lengths[i],a=points[i],b=points[i+1];
    if(walked+length<target-1e-14){walked+=length;continue;}
    const local=length<=1e-14?0:(target-walked)/length;
    return new Vec2(lerpNumber(a[0],b[0],clamp01(local)),lerpNumber(a[1],b[1],clamp01(local)));
  }
  return Vec2.from(points.at(-1));
}

export function motionPathPoints(object,{samples=256,tolerance=1e-3}={}){
  if(!(samples>=2))throw new RangeError('samples must be >= 2');
  if(!(tolerance>0))throw new RangeError('tolerance must be positive');

  if(object instanceof Line)return [[object.start[0],object.start[1]],[object.end[0],object.end[1]]];

  if(object instanceof Polyline){
    const points=object.points.map(p=>[p[0],p[1]]);
    if(object.closed&&points.length){
      const a=points[0],b=points.at(-1);
      if(Math.hypot(a[0]-b[0],a[1]-b[1])>1e-14)points.push([a[0],a[1]]);
    }
    return points;
  }

  if(object instanceof Circle){
    return Array.from({length:samples+1},(_,i)=>{
      const a=TAU*i/samples;return[object.radius*Math.cos(a),object.radius*Math.sin(a)];
    });
  }

  if(object instanceof Ellipse){
    return Array.from({length:samples+1},(_,i)=>{
      const a=TAU*i/samples;return[object.radiusX*Math.cos(a),object.radiusY*Math.sin(a)];
    });
  }

  if(object instanceof Arc){
    const count=Math.max(2,Math.ceil(samples*Math.abs(object.sweepAngle)/TAU)+1);
    return Array.from({length:count},(_,i)=>{
      const a=object.startAngle+object.sweepAngle*i/(count-1);
      return[object.radius*Math.cos(a),object.radius*Math.sin(a)];
    });
  }

  if(object instanceof VectorObject2D){
    const contours=object.document.paths.flatMap(path=>path.contours);
    if(contours.length!==1)throw new RangeError('moveAlong() requires exactly one vector contour');
    const contour=contours[0],points=[];
    for(const seg of contour.segments){
      const flat=booleanFlattenCubic(seg,tolerance);
      if(points.length)points.push(...flat.slice(1));else points.push(...flat);
    }
    if(contour.closed&&points.length){
      const a=points[0],b=points.at(-1);
      if(Math.hypot(a[0]-b[0],a[1]-b[1])>1e-14)points.push([a[0],a[1]]);
    }
    return points;
  }

  throw new TypeError('moveAlong() path must be Line, Polyline/Polygon, Circle/Ellipse/Arc, or single-contour VectorObject2D');
}

export function parseWebColor(value){
  if(value==null)return null;
  if(typeof value!=='string')throw new TypeError('interpolated colors must be CSS strings');
  const v=value.trim();
  if(v[0]==='#'){
    let h=v.slice(1);if(h.length===3||h.length===4)h=[...h].map(c=>c+c).join('');
    if(h.length===6)h+='ff';if(h.length!==8)throw new TypeError(`unsupported color ${value}`);
    return [0,2,4,6].map(i=>parseInt(h.slice(i,i+2),16));
  }
  const m=v.match(/^rgba?\(([^)]+)\)$/i);
  if(m){const q=m[1].split(',').map(x=>x.trim());const a=q.length>3?Math.round(Number(q[3])*255):255;return [Number(q[0]),Number(q[1]),Number(q[2]),a];}
  throw new TypeError(`unsupported interpolated color ${value}`);
}
function rgbaString(c){return `rgba(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])},${(Math.round(c[3])/255).toFixed(5)})`;}
function transparentColor(c){return [c[0],c[1],c[2],0];}
export function lerpColorValue(a,b,t){
  const ca=parseWebColor(a),cb=parseWebColor(b);if(!ca&&!cb)return null;
  const x=ca??transparentColor(cb),y=cb??transparentColor(ca);
  return rgbaString(x.map((v,i)=>lerpNumber(v,y[i],t)));
}
function snapshotPolyline(object){
  if(!(object instanceof Polyline)||object.closed)throw new TypeError('Web interpolation currently supports open Polyline endpoints only');
  return {points:object.points.map(p=>[p[0],p[1]]),transform:cloneTransform(object.transform),stroke:object.stroke,fill:object.fill,width:object.width,worldStroke:object.worldStroke,opacity:object.opacity};
}

export class PolylineInterpolation extends ZObject {
  constructor(source,target,start,end,easing){
    super({zIndex:Math.max(source.zIndex,target.zIndex)});this.source=snapshotPolyline(source);this.target=snapshotPolyline(target);this.start=start;this.end=end;this.easing=easing;
    const segments=Math.max(this.source.points.length-1,this.target.points.length-1);this.a=resamplePolylineByArcLength(this.source.points,segments);this.b=resamplePolylineByArcLength(this.target.points,segments);
  }
  draw(r,parent=Transform2D.identity()){
    const raw=this.end<=this.start?1:(r.time-this.start)/(this.end-this.start),t=this.easing(clamp01(raw)),pts=this.a.map((p,i)=>[lerpNumber(p[0],this.b[i][0],t),lerpNumber(p[1],this.b[i][1],t)]),path=new Path2D();
    path.moveTo(pts[0][0],pts[0][1]);for(let i=1;i<pts.length;i++)path.lineTo(pts[i][0],pts[i][1]);
    const transform=Transform2D.lerp(this.source.transform,this.target.transform,t),ctx=r.ctx,stroke=lerpColorValue(this.source.stroke,this.target.stroke,t),fill=lerpColorValue(this.source.fill,this.target.fill,t),width=lerpNumber(this.source.width,this.target.width,t),opacity=lerpNumber(this.source.opacity,this.target.opacity,t);
    ctx.save();ctx.globalAlpha*=clamp01(opacity);setWorldCanvasTransform(r,ctx,parent.mul(transform));ctx.lineJoin='round';ctx.lineCap='round';if(fill){ctx.fillStyle=fill;ctx.fill(path);}if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=(this.source.worldStroke&&this.target.worldStroke)?width:width*r.dpr/r.unitSize;ctx.stroke(path);}ctx.restore();
  }
}

export class Line extends ZObject {
  constructor(start=[-1,0],end=[1,0],{stroke=WHITE,width=null,strokeWidth=null,...rest}={}){super(rest);this.start=start;this.end=end;this.stroke=stroke;const useWorld=strokeWidth!=null||width==null;this.width=strokeWidth??width??DEFAULT_STROKE_WIDTH;this.worldStroke=useWorld;}
  draw(r,parent){const m=this.world(parent);withObjectContext(r,this,ctx=>{const a=r.toDevice(...applyPoint(m,this.start)),b=r.toDevice(...applyPoint(m,this.end));ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.strokeStyle=this.stroke;ctx.lineWidth=this.worldStroke?this.width*r.unitSize:this.width*r.dpr;ctx.stroke();});}
}
export class Polyline extends ZObject {
  constructor(points,{stroke=WHITE,width=null,strokeWidth=null,closed=false,fill=null,lineJoin='round',lineCap='round',miterLimit=10,reveal=undefined,trim=undefined,...rest}={}){super(rest);this._points=points;this.stroke=stroke;const useWorld=strokeWidth!=null||width==null;this.width=strokeWidth??width??DEFAULT_STROKE_WIDTH;this.worldStroke=useWorld;this.closed=closed;this.fill=fill;this.lineJoin=lineJoin;this.lineCap=lineCap;this.miterLimit=miterLimit;this.reveal=trim??reveal??1;this._path=null;this._totalLength=0;}
  get trim(){return this.reveal;} set trim(value){this.reveal=value;}
  create(options={}){if(!this._scene)throw new Error('object must be added before create()');this._scene.create(this,options);return this;}
  trimTo(to,options={}){if(!this._scene)throw new Error('object must be added before trimTo()');this._scene.trim(this,{...options,to});return this;}
  get points(){return this._points;}
  set points(value){this._points=value;this._path=null;}
  invalidate(){this._path=null;return this;}
  _buildPath(){const path=new Path2D();let total=0;if(this.points.length){path.moveTo(this.points[0][0],this.points[0][1]);for(let i=1;i<this.points.length;i++){const a=this.points[i-1],b=this.points[i];total+=Math.hypot(b[0]-a[0],b[1]-a[1]);path.lineTo(b[0],b[1]);}if(this.closed){const a=this.points[this.points.length-1],b=this.points[0];total+=Math.hypot(b[0]-a[0],b[1]-a[1]);path.closePath();}}this._totalLength=total;return this._path=path;}
  draw(r,parent){if(!this.points.length)return;const path=this._path??this._buildPath(),m=this.world(parent),ctx=r.ctx,reveal=Math.max(0,Math.min(1,scalarAt(this.reveal,r.time)));
    ctx.save();ctx.globalAlpha*=Math.max(0,Math.min(1,this.opacity));setWorldCanvasTransform(r,ctx,m);ctx.lineJoin=this.lineJoin;ctx.lineCap=this.lineCap;ctx.miterLimit=this.miterLimit;
    if(this.fill&&reveal>=.999999){ctx.fillStyle=this.fill;ctx.fill(path);}
    const trimStroke=this.stroke??(reveal<.999999?this.fill:null),trimWidth=this.stroke?this.width:.035,trimWorld=this.stroke?this.worldStroke:true;
    if(trimStroke&&reveal>0){ctx.strokeStyle=trimStroke;ctx.lineWidth=trimWorld?trimWidth:trimWidth*r.dpr/r.unitSize;if(reveal<.999999&&this._totalLength>0){ctx.setLineDash([this._totalLength,this._totalLength]);ctx.lineDashOffset=this._totalLength*(1-reveal);}ctx.stroke(path);}
    ctx.restore();}
}

function sampleCubicSegment(out,p0,p1,p2,p3,count=8,includeStart=false){
  const start=includeStart?0:1;
  for(let i=start;i<=count;i++){
    const t=i/count,u=1-t;
    out.push([
      u*u*u*p0[0]+3*u*u*t*p1[0]+3*u*t*t*p2[0]+t*t*t*p3[0],
      u*u*u*p0[1]+3*u*u*t*p1[1]+3*u*t*t*p2[1]+t*t*t*p3[1],
    ]);
  }
}
function braceProfile(span,depth,samples=8){
  const half=span/2;
  const hookW=Math.min(.22,Math.max(.09,span*.065));
  const notchW=Math.min(.20,Math.max(.10,span*.055));
  const endY=-depth*.52;
  const pts=[];
  const segs=[
    [[-half,endY],[-half,-depth*.18],[-half+hookW*.25,0],[-half+hookW,0]],
    [[-half+hookW,0],[-half+span*.22,0],[-notchW*1.8,0],[-notchW,0]],
    [[-notchW,0],[-notchW*.58,0],[-notchW*.34,depth*.72],[0,depth]],
    [[0,depth],[notchW*.34,depth*.72],[notchW*.58,0],[notchW,0]],
    [[notchW,0],[notchW*1.8,0],[half-span*.22,0],[half-hookW,0]],
    [[half-hookW,0],[half-hookW*.25,0],[half,-depth*.18],[half,endY]],
  ];
  segs.forEach((seg,i)=>sampleCubicSegment(pts,...seg,samples,i===0));
  return pts;
}
export class Brace extends Polyline {
  constructor(target,{direction=[0,-1],buff=.2,depth=.12,color=WHITE,width=null,strokeWidth=null,samples=8,...rest}={}){
    if(!target||typeof target.bounds!=='function')throw new TypeError('Brace target must provide bounds()');
    const b=target.bounds(),d=Vec2.from(direction),len=d.length;
    if(len<=1e-12)throw new RangeError('Brace direction must be non-zero');
    const nx=d.x/len,ny=d.y/len,tx=-ny,ty=nx;
    let supportPoints;
    if(target instanceof Line) supportPoints=[target.start,target.end].map(p=>target.transform.apply(p[0],p[1]));
    else if(target instanceof Polyline) supportPoints=target.points.map(p=>target.transform.apply(p[0],p[1]));
    else supportPoints=[[b.left,b.bottom],[b.left,b.top],[b.right,b.bottom],[b.right,b.top]];
    const us=supportPoints.map(([x,y])=>x*tx+y*ty),vs=supportPoints.map(([x,y])=>x*nx+y*ny);
    const u0=Math.min(...us),u1=Math.max(...us),span=Math.max(1e-6,u1-u0),centerU=(u0+u1)/2,baseV=Math.max(...vs)+buff;
    const world=([x,y])=>[tx*(centerU+x)+nx*(baseV+y),ty*(centerU+x)+ny*(baseV+y)];
    super(braceProfile(span,depth,samples).map(world),{stroke:color,width,strokeWidth,fill:null,lineJoin:'round',lineCap:'round',...rest});
    this.direction=new Vec2(nx,ny);
    this.tangent=new Vec2(tx,ty);
    this._braceCenterU=centerU;
    this._braceBaseV=baseV;
    this.depth=depth;
  }
  labelPoint(buff=.25){
    const u=this._braceCenterU,v=this._braceBaseV+this.depth+buff;
    return new Vec2(this.tangent.x*u+this.direction.x*v,this.tangent.y*u+this.direction.y*v);
  }
}

export class Polygon extends Polyline { constructor(points,opts={}){super(points,{fill:'rgba(82,205,150,.72)',stroke:WHITE,closed:true,lineJoin:'miter',lineCap:'butt',...opts});} }
export class Rectangle extends Polygon { constructor(width=2,height=1,opts={}){const x=width/2,y=height/2;super([[-x,-y],[x,-y],[x,y],[-x,y]],opts);this.rectWidth=width;this.rectHeight=height;} }
export class Square extends Rectangle { constructor(side=1,opts={}){super(side,side,opts);} }
export class RegularPolygon extends Polygon { constructor(sides=6,radius=1,{phase=Math.PI/2,...opts}={}){super(Array.from({length:sides},(_,i)=>{const a=phase+i*TAU/sides;return [radius*Math.cos(a),radius*Math.sin(a)];}),opts);} }
export class Circle extends ZObject {
  constructor(radius=1,{fill='rgba(96,166,255,.72)',stroke=WHITE,width=null,strokeWidth=null,reveal=undefined,trim=undefined,...rest}={}){super(rest);this.radius=radius;this.fill=fill;this.stroke=stroke;const useWorld=strokeWidth!=null||width==null;this.width=strokeWidth??width??DEFAULT_STROKE_WIDTH;this.worldStroke=useWorld;this.reveal=trim??reveal??1;}
  get trim(){return this.reveal;} set trim(value){this.reveal=value;}
  draw(r,parent){const m=this.world(parent),reveal=clamp01(scalarAt(this.reveal,r.time));withObjectContext(r,this,ctx=>{const c=r.toDevice(...m.apply(0,0));const ex=m.vector(this.radius,0),ey=m.vector(0,this.radius);const rx=Math.hypot(...ex)*r.unitSize,ry=Math.hypot(...ey)*r.unitSize;const angle=Math.atan2(ex[1],ex[0]);ctx.beginPath();ctx.ellipse(c[0],c[1],Math.max(.01,rx),Math.max(.01,ry),-angle,0,TAU*reveal);if(this.fill&&reveal>=.999999){ctx.fillStyle=this.fill;ctx.fill();}const trimStroke=this.stroke??(reveal<.999999?this.fill:null),trimWidth=this.stroke?this.width:.035;if(trimStroke&&reveal>0){ctx.strokeStyle=trimStroke;ctx.lineWidth=(this.stroke&& !this.worldStroke)?trimWidth*r.dpr:trimWidth*r.unitSize;ctx.stroke();}});}
}
export class SurroundingRectangle extends Rectangle {
  constructor(target,{buff=.1,color=YELLOW,...options}={}){
    if(!(buff>=0))throw new RangeError('SurroundingRectangle buff must be >= 0');
    if(!target||typeof target.bounds!=='function')throw new TypeError('SurroundingRectangle target must provide bounds()');
    const b=target.bounds();
    super(b.width+2*buff,b.height+2*buff,{fill:null,stroke:color,transform:Transform2D.translation(b.center.x,b.center.y),...options});
  }
}
export class Ellipse extends ZObject {
  constructor(radiusX=1,radiusY=.6,{fill='rgba(96,166,255,.72)',stroke=WHITE,width=null,strokeWidth=null,reveal=undefined,trim=undefined,...rest}={}){super(rest);this.radiusX=radiusX;this.radiusY=radiusY;this.fill=fill;this.stroke=stroke;const useWorld=strokeWidth!=null||width==null;this.width=strokeWidth??width??DEFAULT_STROKE_WIDTH;this.worldStroke=useWorld;this.reveal=trim??reveal??1;}
  get trim(){return this.reveal;} set trim(value){this.reveal=value;}
  draw(r,parent){const m=this.world(parent),reveal=clamp01(scalarAt(this.reveal,r.time)),ctx=r.ctx;ctx.save();ctx.globalAlpha*=clamp01(this.opacity);setWorldCanvasTransform(r,ctx,m);ctx.beginPath();ctx.ellipse(0,0,Math.max(.0001,this.radiusX),Math.max(.0001,this.radiusY),0,0,TAU*reveal);if(this.fill&&reveal>=.999999){ctx.fillStyle=this.fill;ctx.fill();}const trimStroke=this.stroke??(reveal<.999999?this.fill:null),trimWidth=this.stroke?this.width:.035;if(trimStroke&&reveal>0){ctx.strokeStyle=trimStroke;ctx.lineWidth=this.worldStroke?trimWidth:trimWidth*r.dpr/r.unitSize;ctx.stroke();}ctx.restore();}
}
export class Arc extends ZObject {
  constructor(radius=1,startAngle=0,sweepAngle=Math.PI/2,{stroke=WHITE,width=null,strokeWidth=null,reveal=undefined,trim=undefined,...rest}={}){super(rest);this.radius=radius;this.startAngle=startAngle;this.sweepAngle=sweepAngle;this.stroke=stroke;const useWorld=strokeWidth!=null||width==null;this.width=strokeWidth??width??DEFAULT_STROKE_WIDTH;this.worldStroke=useWorld;this.reveal=trim??reveal??1;}
  get trim(){return this.reveal;} set trim(value){this.reveal=value;}
  draw(r,parent){const m=this.world(parent),reveal=clamp01(scalarAt(this.reveal,r.time));if(reveal<=0)return;const ctx=r.ctx;ctx.save();ctx.globalAlpha*=clamp01(this.opacity);setWorldCanvasTransform(r,ctx,m);ctx.beginPath();ctx.arc(0,0,Math.max(.0001,this.radius),this.startAngle,this.startAngle+this.sweepAngle*reveal,this.sweepAngle<0);ctx.strokeStyle=this.stroke;ctx.lineWidth=this.worldStroke?this.width:this.width*r.dpr/r.unitSize;ctx.stroke();ctx.restore();}
}
export class Dot extends Circle { constructor(point=[0,0],{radius=.08,color=WHITE,...opts}={}){super(radius,{fill:color,stroke:null,transform:Transform2D.translation(...point),...opts});} }
export class Arrow extends Line {
  constructor(start=[0,0],end=[1,0],{buff=.25,tipLength=.35,tipWidth=.35,...options}={}){
    super(start,end,options);this.buff=Number(buff);this.tipLength=Number(tipLength);this.tipWidth=Number(tipWidth);
    if(this.buff<0)throw new RangeError('Arrow buff must be >= 0');
  }
  draw(r,parent){
    const m=this.world(parent),rawA=applyPoint(m,this.start),rawB=applyPoint(m,this.end),dx=rawB[0]-rawA[0],dy=rawB[1]-rawA[1],length=Math.hypot(dx,dy);
    if(length<=1e-12)return;
    const ux=dx/length,uy=dy/length,nx=-uy,ny=ux,buff=Math.min(this.buff,length*.49);
    const a=[rawA[0]+ux*buff,rawA[1]+uy*buff],b=[rawB[0]-ux*buff,rawB[1]-uy*buff],renderedLength=Math.max(1e-9,length-2*buff);
    const tl=Math.min(this.tipLength,renderedLength*.25),tw=Math.min(this.tipWidth,tl),base=[b[0]-ux*tl,b[1]-uy*tl],left=[base[0]+nx*tw*.5,base[1]+ny*tw*.5],right=[base[0]-nx*tw*.5,base[1]-ny*tw*.5];
    withObjectContext(r,this,ctx=>{
      ctx.beginPath();ctx.moveTo(...r.toDevice(...a));ctx.lineTo(...r.toDevice(...base));ctx.strokeStyle=this.stroke;ctx.lineWidth=this.worldStroke?this.width*r.unitSize:this.width*r.dpr;ctx.lineCap='round';ctx.stroke();
      ctx.beginPath();ctx.moveTo(...r.toDevice(...b));ctx.lineTo(...r.toDevice(...left));ctx.lineTo(...r.toDevice(...right));ctx.closePath();ctx.fillStyle=this.stroke;ctx.fill();
    });
  }
}

export class Text extends ZObject {
  constructor(text,{fontSize=48,color=WHITE,fontFamily='Inter, ui-sans-serif, system-ui',align='center',weight=400,...rest}={}){super(rest);this.text=text;this.fontSize=fontSize;this.color=color;this.fontFamily=fontFamily;this.align=align;this.weight=weight;}
  draw(r,parent){const m=this.world(parent);withObjectContext(r,this,ctx=>{const p=r.toDevice(...m.apply(0,0));const sx=Math.hypot(m.xx,m.yx),sy=Math.hypot(m.xy,m.yy);ctx.translate(...p);ctx.transform(m.xx/sx,-m.yx/sx,-m.xy/sy,m.yy/sy,0,0);ctx.fillStyle=this.color;ctx.font=`${this.weight} ${this.fontSize*r.unitSize/90}px ${this.fontFamily}`;ctx.textAlign=this.align;ctx.textBaseline='middle';ctx.fillText(String(typeof this.text==='function'?this.text(r.time,this):this.text),0,0);});}
}

function vectorGroupAlpha(reveal,groupCount,group){if(!groupCount)return 1;return clamp01(clamp01(reveal)*groupCount-group);}
export class VectorObject2D extends ZObject {
  constructor(document,{reveal=1,tint=null,...rest}={}){super(rest);this.document=document;this.reveal=reveal;this.tint=tint;this._paths=null;}
  invalidate(){this._paths=null;return this;}
  _build(){
    this._paths=this.document.paths.map(entry=>{
      const path=new Path2D();
      for(const contour of entry.contours){let first=true;for(const seg of contour.segments){const [p0,p1,p2,p3]=seg;if(first){path.moveTo(p0[0],p0[1]);first=false;}path.bezierCurveTo(p1[0],p1[1],p2[0],p2[1],p3[0],p3[1]);}if(contour.closed)path.closePath();}
      return {...entry,path};
    });
    return this._paths;
  }
  draw(r,parent=Transform2D.identity()){
    const paths=this._paths??this._build(),m=this.world(parent),ctx=r.ctx,reveal=clamp01(scalarAt(this.reveal,r.time)),groups=this.document.group_count??1;
    ctx.save();setWorldCanvasTransform(r,ctx,m);
    for(const entry of paths){const alpha=vectorGroupAlpha(reveal,groups,entry.group??0)*clamp01(this.opacity);if(alpha<=0)continue;ctx.save();ctx.globalAlpha*=alpha;if(entry.fill){ctx.fillStyle=this.tint??entry.fill;ctx.fill(entry.path);}if(entry.stroke){ctx.strokeStyle=this.tint??entry.stroke.color;ctx.lineWidth=entry.stroke.width;ctx.stroke(entry.path);}ctx.restore();}
    ctx.restore();
  }
}

export class Group extends ZObject {
  constructor(children=[],opts={}){super(opts);this.children=[...children];for(const child of this.children)child._parent=this;}
  add(...items){for(const item of items)item._parent=this;this.children.push(...items);if(this._scene)for(const item of items)this._scene._track(item,this._scene.cursor);return this;}
  draw(r,parent){const m=this.world(parent),time=r.time??0;for(const child of [...this.children].sort((a,b)=>a.zIndex-b.zIndex))if(child.visible&&time>=child.birth&&time<child.death)child.draw(r,m);}
}


function booleanLinearScaleBound(m){
  const c0=Math.hypot(m.xx,m.yx),c1=Math.hypot(m.xy,m.yy);
  return Math.max(1e-12,Math.hypot(c0,c1));
}
function booleanEllipseSamples(radius,tolerance){
  if(!(radius>0)||tolerance>=radius)return 24;
  const value=Math.max(-1,Math.min(1,1-tolerance/radius)),half=Math.acos(value);
  if(half<=1e-12)return 512;
  return Math.max(24,Math.min(512,Math.ceil(Math.PI/half)));
}
function booleanDedupeClosed(points,epsilon){
  const out=[],eps2=epsilon*epsilon;
  for(const p of points){
    if(out.length){const q=out[out.length-1],dx=p[0]-q[0],dy=p[1]-q[1];if(dx*dx+dy*dy<=eps2)continue;}
    out.push([Number(p[0]),Number(p[1])]);
  }
  if(out.length>=2){const a=out[0],b=out[out.length-1],dx=a[0]-b[0],dy=a[1]-b[1];if(dx*dx+dy*dy<=eps2)out.pop();}
  if(out.length<3)throw new Error('boolean contour requires at least 3 points');
  return out;
}
function booleanPointLineDistance(p,a,b){
  const dx=b[0]-a[0],dy=b[1]-a[1],den=Math.hypot(dx,dy);
  if(den<=1e-15)return Math.hypot(p[0]-a[0],p[1]-a[1]);
  return Math.abs(dy*p[0]-dx*p[1]+b[0]*a[1]-b[1]*a[0])/den;
}
function booleanSplitCubic(seg){
  const p0=seg[0],p1=seg[1],p2=seg[2],p3=seg[3],mid=(a,b)=>[(a[0]+b[0])*.5,(a[1]+b[1])*.5];
  const p01=mid(p0,p1),p12=mid(p1,p2),p23=mid(p2,p3),p012=mid(p01,p12),p123=mid(p12,p23),m=mid(p012,p123);
  return[[p0,p01,p012,m],[m,p123,p23,p3]];
}
function booleanFlattenCubic(seg,tolerance,maxDepth=12){
  const out=[[seg[0][0],seg[0][1]]];
  const visit=(curve,depth)=>{
    const flat=Math.max(booleanPointLineDistance(curve[1],curve[0],curve[3]),booleanPointLineDistance(curve[2],curve[0],curve[3]));
    if(flat<=tolerance||depth>=maxDepth){out.push([curve[3][0],curve[3][1]]);return;}
    const split=booleanSplitCubic(curve);visit(split[0],depth+1);visit(split[1],depth+1);
  };
  visit(seg,0);return out;
}
function booleanCollectContours(object,parent=Transform2D.identity(),tolerance=1/512){
  const transform=parent.mul(object.transform);
  if(object instanceof Group){
    const out=[];for(const child of object.children)out.push(...booleanCollectContours(child,transform,tolerance));
    if(!out.length)throw new Error('boolean Group operand has no closed geometry');
    return out;
  }
  const localTolerance=tolerance/booleanLinearScaleBound(transform);
  let localContours=[];
  if(object instanceof Circle){
    const n=booleanEllipseSamples(object.radius,localTolerance);
    localContours=[Array.from({length:n},(_,i)=>{const a=TAU*i/n;return[object.radius*Math.cos(a),object.radius*Math.sin(a)];})];
  }else if(object instanceof Ellipse){
    const n=booleanEllipseSamples(Math.max(object.radiusX,object.radiusY),localTolerance);
    localContours=[Array.from({length:n},(_,i)=>{const a=TAU*i/n;return[object.radiusX*Math.cos(a),object.radiusY*Math.sin(a)];})];
  }else if(object instanceof Polygon){
    localContours=[object.points.map(p=>[p[0],p[1]])];
  }else if(object instanceof VectorObject2D){
    for(const path of object.document.paths)for(const contour of path.contours){
      if(!contour.closed)continue;
      const points=[];
      for(const seg of contour.segments){const flat=booleanFlattenCubic(seg,localTolerance);if(points.length)points.push(...flat.slice(1));else points.push(...flat);}
      localContours.push(booleanDedupeClosed(points,localTolerance*1e-3));
    }
    if(!localContours.length)throw new Error('boolean VectorObject2D operand has no closed contours');
  }else if(object instanceof Polyline){
    if(!object.closed)throw new TypeError('open Polyline cannot be used as a boolean area');
    localContours=[object.points.map(p=>[p[0],p[1]])];
  }else{
    throw new TypeError('unsupported boolean operand '+object.constructor.name);
  }
  return localContours.map(contour=>booleanDedupeClosed(contour.map(p=>transform.apply(p[0],p[1])),tolerance*1e-3));
}
function booleanCross(a,b){return a[0]*b[1]-a[1]*b[0];}
function booleanSub(a,b){return[a[0]-b[0],a[1]-b[1]];}
function booleanDot(a,b){return a[0]*b[0]+a[1]*b[1];}
function booleanDist2(a,b){const x=a[0]-b[0],y=a[1]-b[1];return x*x+y*y;}
function booleanInside(contours,p,epsilon){
  let winding=0;
  for(const contour of contours){
    for(let i=0;i<contour.length;i++){
      const a=contour[i],b=contour[(i+1)%contour.length],side=booleanCross(booleanSub(b,a),booleanSub(p,a));
      if(a[1]<=p[1]){if(b[1]>p[1]&&side>epsilon)winding++;}
      else if(b[1]<=p[1]&&side<-epsilon)winding--;
    }
  }
  return winding!==0;
}
function booleanResultInside(operation,a,b){
  if(operation==='intersection')return a&&b;
  if(operation==='union')return a||b;
  if(operation==='difference')return a&&!b;
  return a!==b;
}
function booleanAddSplit(list,value,epsilon){
  const v=Math.max(0,Math.min(1,value));if(list.some(x=>Math.abs(x-v)<=epsilon))return;list.push(v);
}
function booleanSegments(contours,epsilon){
  const out=[],eps2=epsilon*epsilon;
  for(const c of contours)for(let i=0;i<c.length;i++){const a=c[i],b=c[(i+1)%c.length];if(booleanDist2(a,b)>eps2)out.push([a,b]);}
  return out;
}
function booleanIntersectSplits(a,b,as,bs,epsilon){
  const r=booleanSub(a[1],a[0]),q=booleanSub(b[0],a[0]),v=booleanSub(b[1],b[0]),rxs=booleanCross(r,v),qxr=booleanCross(q,r);
  if(Math.abs(rxs)>epsilon){
    const t=booleanCross(q,v)/rxs,u=qxr/rxs;
    if(t>=-epsilon&&t<=1+epsilon&&u>=-epsilon&&u<=1+epsilon){booleanAddSplit(as,t,epsilon);booleanAddSplit(bs,u,epsilon);}
    return;
  }
  if(Math.abs(qxr)>epsilon)return;
  const rr=booleanDot(r,r),vv=booleanDot(v,v);if(rr<=epsilon*epsilon||vv<=epsilon*epsilon)return;
  for(const p of b){const t=booleanDot(booleanSub(p,a[0]),r)/rr;if(t>=-epsilon&&t<=1+epsilon)booleanAddSplit(as,t,epsilon);}
  for(const p of a){const u=booleanDot(booleanSub(p,b[0]),v)/vv;if(u>=-epsilon&&u<=1+epsilon)booleanAddSplit(bs,u,epsilon);}
}
function booleanClassifyEdge(edge,aContours,bContours,operation,epsilon){
  const d=booleanSub(edge[1],edge[0]),len=Math.hypot(d[0],d[1]);if(len<=epsilon)return null;
  const m=[(edge[0][0]+edge[1][0])*.5,(edge[0][1]+edge[1][1])*.5],nx=-d[1]/len,ny=d[0]/len,probe=Math.max(epsilon*8,Math.min(len*1e-4,1e-5));
  const l=[m[0]+nx*probe,m[1]+ny*probe],r=[m[0]-nx*probe,m[1]-ny*probe];
  const li=booleanResultInside(operation,booleanInside(aContours,l,epsilon),booleanInside(bContours,l,epsilon)),ri=booleanResultInside(operation,booleanInside(aContours,r,epsilon),booleanInside(bContours,r,epsilon));
  if(li===ri)return null;return li?edge:[edge[1],edge[0]];
}
function booleanFallback(aContours,bContours,operation,epsilon){
  const a=booleanSegments(aContours,epsilon),b=booleanSegments(bContours,epsilon),as=a.map(()=>[0,1]),bs=b.map(()=>[0,1]);
  for(let i=0;i<a.length;i++)for(let j=0;j<b.length;j++)booleanIntersectSplits(a[i],b[j],as[i],bs[j],epsilon);
  const edges=[];
  const emit=(segments,splits)=>{
    for(let i=0;i<segments.length;i++){
      const values=splits[i].sort((x,y)=>x-y),seg=segments[i],mix=t=>[seg[0][0]+(seg[1][0]-seg[0][0])*t,seg[0][1]+(seg[1][1]-seg[0][1])*t];
      for(let j=0;j+1<values.length;j++){
        if(values[j+1]-values[j]<=epsilon)continue;
        const edge=booleanClassifyEdge([mix(values[j]),mix(values[j+1])],aContours,bContours,operation,epsilon);
        if(!edge)continue;
        if(!edges.some(e=>booleanDist2(e[0],edge[0])<epsilon*epsilon*64&&booleanDist2(e[1],edge[1])<epsilon*epsilon*64))edges.push(edge);
      }
    }
  };
  emit(a,as);emit(b,bs);
  const used=new Array(edges.length).fill(false),contours=[],near=(x,y)=>booleanDist2(x,y)<=epsilon*epsilon*144;
  for(let seed=0;seed<edges.length;seed++){
    if(used[seed])continue;
    const contour=[edges[seed][0],edges[seed][1]],start=edges[seed][0];used[seed]=true;let current=edges[seed][1],guard=0;
    while(!near(current,start)){
      if(++guard>edges.length+2)throw new Error('vector boolean fallback produced open contour');
      const previous=contour[contour.length-2],incoming=booleanSub(current,previous),rev=[-incoming[0],-incoming[1]];let found=-1,best=Infinity;
      for(let k=0;k<edges.length;k++){
        if(used[k]||!near(edges[k][0],current))continue;
        const out=booleanSub(edges[k][1],edges[k][0]),signed=Math.atan2(booleanCross(rev,out),booleanDot(rev,out));let cw=-signed;
        while(cw<0)cw+=TAU;while(cw>=TAU)cw-=TAU;
        if(cw<best){best=cw;found=k;}
      }
      if(found<0)throw new Error('vector boolean fallback produced open contour');
      used[found]=true;current=edges[found][1];if(!near(current,start))contour.push(current);
    }
    if(contour.length>=3)contours.push(contour);
  }
  return contours;
}
function booleanLineSegment(a,b){
  return[a,[a[0]+(b[0]-a[0])/3,a[1]+(b[1]-a[1])/3],[a[0]+2*(b[0]-a[0])/3,a[1]+2*(b[1]-a[1])/3],b];
}
function booleanDocument(contours,color,fillOpacity,strokeWidth){
  if(!contours.length)return{width:1e-9,height:1e-9,group_count:0,paths:[]};
  const points=contours.flat(),xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),fill=lerpColorValue(null,color,fillOpacity),stroke=strokeWidth>0?{color,width:strokeWidth}:null;
  return{width:Math.max(1e-9,Math.max(...xs)-Math.min(...xs)),height:Math.max(1e-9,Math.max(...ys)-Math.min(...ys)),group_count:1,paths:[{group:0,fill,stroke,contours:contours.map(points=>({closed:true,segments:points.map((p,i)=>booleanLineSegment(p,points[(i+1)%points.length]))}))}]};
}
export class BooleanShape extends VectorObject2D {
  constructor(first,second,operation,{color=WHITE,fillOpacity=.5,strokeWidth=DEFAULT_STROKE_WIDTH,tolerance=1/512,...rest}={}){
    if(!['intersection','union','difference','exclusion'].includes(operation))throw new RangeError('invalid boolean operation');
    if(!(fillOpacity>=0&&fillOpacity<=1))throw new RangeError('fillOpacity must be in [0,1]');
    if(strokeWidth<0)throw new RangeError('strokeWidth must be >= 0');
    if(!(tolerance>0))throw new RangeError('tolerance must be positive');
    const a=booleanCollectContours(first,Transform2D.identity(),tolerance),b=booleanCollectContours(second,Transform2D.identity(),tolerance),epsilon=Math.max(1e-10,tolerance*1e-5);
    const contours=activeZanimWasm?activeZanimWasm.pathBoolean(a,b,operation,epsilon):booleanFallback(a,b,operation,epsilon);
    super(booleanDocument(contours,color,fillOpacity,strokeWidth),rest);
    Object.assign(this,{first,second,operation,color,fillOpacity,strokeWidth,tolerance,backend:'vector'});
  }
}
export class Intersection extends BooleanShape { constructor(first,second,options={}){super(first,second,'intersection',options);} }
export class Union extends BooleanShape { constructor(first,second,options={}){super(first,second,'union',options);} }
export class Difference extends BooleanShape { constructor(first,second,options={}){super(first,second,'difference',options);} }
export class Exclusion extends BooleanShape { constructor(first,second,options={}){super(first,second,'exclusion',options);} }

function clipInfiniteLine(width,height,unitSize,p,d){const hx=width/(2*unitSize),hy=height/(2*unitSize);let t0=-Infinity,t1=Infinity;for(const [pv,dv,lo,hi] of [[p[0],d[0],-hx,hx],[p[1],d[1],-hy,hy]]){if(Math.abs(dv)<1e-12){if(pv<lo||pv>hi)return null;continue;}let a=(lo-pv)/dv,b=(hi-pv)/dv;if(a>b)[a,b]=[b,a];t0=Math.max(t0,a);t1=Math.min(t1,b);if(t0>t1)return null;}return [[p[0]+d[0]*t0,p[1]+d[1]*t0],[p[0]+d[0]*t1,p[1]+d[1]*t1]];}
export class InfiniteLine extends ZObject {
  constructor(point=[0,0],direction=[1,0],{stroke=WHITE,width=null,strokeWidth=null,...rest}={}){super(rest);this.point=point;this.direction=direction;this.stroke=stroke;const useWorld=strokeWidth!=null||width==null;this.width=strokeWidth??width??DEFAULT_STROKE_WIDTH;this.worldStroke=useWorld;}
  draw(r,parent){const m=this.world(parent),p=m.apply(...this.point),d=m.vector(...this.direction),seg=clipInfiniteLine(r.canvas.width,r.canvas.height,r.unitSize,p,d);if(!seg)return;withObjectContext(r,this,ctx=>{ctx.beginPath();ctx.moveTo(...r.toDevice(...seg[0]));ctx.lineTo(...r.toDevice(...seg[1]));ctx.strokeStyle=this.stroke;ctx.lineWidth=this.worldStroke?this.width*r.unitSize:this.width*r.dpr;ctx.stroke();});}
}
export class InfiniteGrid extends ZObject {
  constructor({step=.5,stroke='rgba(115,135,175,.42)',width=null,strokeWidth=null,...rest}={}){super(rest);this.step=step;this.stroke=stroke;const useWorld=strokeWidth!=null||width==null;this.width=strokeWidth??width??(2/90);this.worldStroke=useWorld;}
  draw(r,parent){const t=this.world(parent),segments=r.wasm.resolveGrid(r.canvas.width,r.canvas.height,r.unitSize,this.step,t.linear);withObjectContext(r,this,ctx=>{ctx.beginPath();for(let i=0;i<segments.length;i+=4){const a=r.toDevice(segments[i]+t.tx,segments[i+1]+t.ty),b=r.toDevice(segments[i+2]+t.tx,segments[i+3]+t.ty);ctx.moveTo(...a);ctx.lineTo(...b);}ctx.strokeStyle=this.stroke;ctx.lineWidth=this.worldStroke?this.width*r.unitSize:this.width*r.dpr;ctx.stroke();});}
}
export class NumberPlane extends ZObject {
  constructor({step=1,fadedLineRatio=4,backgroundColor='#236B8E',axisColor=WHITE,backgroundStrokeWidth=2/90,fadedStrokeWidth=1/90,axisStrokeWidth=2/90,...rest}={}){
    super(rest);Object.assign(this,{step,fadedLineRatio,backgroundColor,axisColor,backgroundStrokeWidth,fadedStrokeWidth,axisStrokeWidth});
  }
  draw(r,parent){
    const t=this.world(parent);
    if(this.fadedLineRatio>0)new InfiniteGrid({step:this.step/(this.fadedLineRatio+1),stroke:this.backgroundColor+'40',strokeWidth:this.fadedStrokeWidth,transform:t}).draw(r);
    new InfiniteGrid({step:this.step,stroke:this.backgroundColor,strokeWidth:this.backgroundStrokeWidth,transform:t}).draw(r);
    new InfiniteLine([0,0],[1,0],{stroke:this.axisColor,strokeWidth:this.axisStrokeWidth,transform:t}).draw(r);
    new InfiniteLine([0,0],[0,1],{stroke:this.axisColor,strokeWidth:this.axisStrokeWidth,transform:t}).draw(r);
  }
}
export class Axes extends ZObject {
  constructor({xColor=RED,yColor=GREEN,width=2.5,...rest}={}){super(rest);this.xColor=xColor;this.yColor=yColor;this.width=width;}
  draw(r,parent){const t=this.world(parent);new InfiniteLine([0,0],[1,0],{stroke:this.xColor,width:this.width,transform:t}).draw(r);new InfiniteLine([0,0],[0,1],{stroke:this.yColor,width:this.width,transform:t}).draw(r);}
}

export function setWorldCanvasTransform(renderer, ctx, m) {
  const u=renderer.unitSize,ox=renderer.canvas.width*.5,oy=renderer.canvas.height*.5;
  ctx.setTransform(u*m.xx,-u*m.yx,u*m.xy,-u*m.yy,ox+u*m.tx,oy-u*m.ty);
}

export class CachedBatch2D extends ZObject {
  constructor(items=[],opts={}){super(opts);this._items=items;this._cache=null;}
  batchTo(to,options={}){this._bound().batch(this,{...options,to});return this;}
  get items(){return this._items;}
  set items(value){this._items=value;this._cache=null;}
  invalidate(){this._cache=null;return this;}
}

// Batch objects are retained render primitives. Their local Path2D geometry is
// compiled once and reused under a changing affine CTM, so animation cost is
// proportional to style groups/draw calls rather than primitive count in JS.
export class CircleSet extends CachedBatch2D {
  constructor(items=[],{fill=BLUE,stroke=null,width=1,worldStroke=false,...rest}={}){super(items,rest);this.fill=fill;this.stroke=stroke;this.width=width;this.worldStroke=worldStroke;}
  _build(){
    const fills=new Map(),strokes=new Map();
    for(const item of this.items){const [x,y,rad]=item,fill=item[3]??this.fill,stroke=item[4]??this.stroke,width=item[5]??this.width;if(fill){let path=fills.get(fill);if(!path)fills.set(fill,path=new Path2D());path.moveTo(x+rad,y);path.arc(x,y,rad,0,TAU);}if(stroke){const key=`${stroke}\u0000${width}`;let group=strokes.get(key);if(!group)strokes.set(key,group={color:stroke,width,path:new Path2D()});group.path.moveTo(x+rad,y);group.path.arc(x,y,rad,0,TAU);}}
    return this._cache={fills,strokes:[...strokes.values()]};
  }
  draw(r,parent){
    const cache=this._cache??this._build(),m=this.world(parent),ctx=r.ctx;
    ctx.save();ctx.globalAlpha*=Math.max(0,Math.min(1,this.opacity));setWorldCanvasTransform(r,ctx,m);
    for(const [color,path] of cache.fills){ctx.fillStyle=color;ctx.fill(path);}for(const group of cache.strokes){ctx.strokeStyle=group.color;ctx.lineWidth=this.worldStroke?group.width:group.width*r.dpr/r.unitSize;ctx.stroke(group.path);}
    ctx.restore();
  }
}
export class LineSet extends CachedBatch2D {
  constructor(items=[],{stroke=WHITE,width=1,worldStroke=false,...rest}={}){super(items,rest);this.stroke=stroke;this.width=width;this.worldStroke=worldStroke;}
  _build(){
    const groups=new Map();
    for(const item of this.items){const [x0,y0,x1,y1]=item,color=item[4]??this.stroke,w=item[5]??this.width,key=`${color}\u0000${w}`;let group=groups.get(key);if(!group)groups.set(key,group={color,width:w,path:new Path2D()});group.path.moveTo(x0,y0);group.path.lineTo(x1,y1);}
    return this._cache=[...groups.values()];
  }
  draw(r,parent){
    const groups=this._cache??this._build(),m=this.world(parent),ctx=r.ctx;
    ctx.save();ctx.globalAlpha*=Math.max(0,Math.min(1,this.opacity));setWorldCanvasTransform(r,ctx,m);
    for(const group of groups){ctx.strokeStyle=group.color;ctx.lineWidth=this.worldStroke?group.width:group.width*r.dpr/r.unitSize;ctx.stroke(group.path);}
    ctx.restore();
  }
}
export class RectSet extends CachedBatch2D {
  constructor(items=[],{fill=BLUE,stroke=null,width=1,worldStroke=false,...rest}={}){super(items,rest);this.fill=fill;this.stroke=stroke;this.width=width;this.worldStroke=worldStroke;}
  _build(){
    const fills=new Map(),strokes=new Map();
    for(const item of this.items){const [x,y,w,h]=item,fill=item[4]??this.fill,stroke=item[5]??this.stroke,width=item[6]??this.width;if(fill){let path=fills.get(fill);if(!path)fills.set(fill,path=new Path2D());path.rect(x-w*.5,y-h*.5,w,h);}if(stroke){const key=`${stroke}\u0000${width}`;let group=strokes.get(key);if(!group)strokes.set(key,group={color:stroke,width,path:new Path2D()});group.path.rect(x-w*.5,y-h*.5,w,h);}}
    return this._cache={fills,strokes:[...strokes.values()]};
  }
  draw(r,parent){
    const cache=this._cache??this._build(),m=this.world(parent),ctx=r.ctx;
    ctx.save();ctx.globalAlpha*=Math.max(0,Math.min(1,this.opacity));setWorldCanvasTransform(r,ctx,m);
    for(const [color,path] of cache.fills){ctx.fillStyle=color;ctx.fill(path);}for(const group of cache.strokes){ctx.strokeStyle=group.color;ctx.lineWidth=this.worldStroke?group.width:group.width*r.dpr/r.unitSize;ctx.stroke(group.path);}
    ctx.restore();
  }
}

function vectorGroups(document){
  const count=Math.max(0,Number(document?.group_count??0));
  const groups=Array.from({length:count},()=>[]);
  for(const path of document?.paths??[]){const group=Math.max(0,Math.min(count-1,Number(path.group??0)));if(count)groups[group].push(path);}
  return groups;
}
function vectorPathBounds(paths){
  if(!paths.length)return[0,0,0,0];let left=Infinity,bottom=Infinity,right=-Infinity,top=-Infinity;
  for(const path of paths)for(const contour of path.contours??[])for(const segment of contour.segments??[])for(const point of segment){left=Math.min(left,point[0]);bottom=Math.min(bottom,point[1]);right=Math.max(right,point[0]);top=Math.max(top,point[1]);}
  return[left,bottom,right,top];
}
function vectorTopology(paths){return JSON.stringify(paths.map(path=>(path.contours??[]).map(contour=>[!!contour.closed,(contour.segments??[]).length])));}
function vectorVisualSignature(paths){
  const[left,bottom,right,top]=vectorPathBounds(paths),width=Math.max(right-left,1e-12),height=Math.max(top-bottom,1e-12),scale=Math.max(width,height);
  const point=p=>[Math.round((p[0]-left)/scale*10000),Math.round((p[1]-bottom)/scale*10000)];
  return JSON.stringify([Math.round(width/scale*10000),Math.round(height/scale*10000),paths.map(path=>(path.contours??[]).map(contour=>[!!contour.closed,(contour.segments??[]).map(segment=>segment.map(point))]))]);
}
function vectorLcsPairs(a,b){
  const rows=a.length+1,cols=b.length+1,dp=Array.from({length:rows},()=>new Uint16Array(cols));
  for(let i=a.length-1;i>=0;i--)for(let j=b.length-1;j>=0;j--)dp[i][j]=a[i]===b[j]?dp[i+1][j+1]+1:Math.max(dp[i+1][j],dp[i][j+1]);
  const pairs=[];let i=0,j=0;while(i<a.length&&j<b.length){if(a[i]===b[j]){pairs.push([i,j]);i++;j++;}else if(dp[i+1][j]>=dp[i][j+1])i++;else j++;}return pairs;
}
function vectorStrokeLerp(a,b,t){
  if(!a&&!b)return null;const x=a??{color:null,width:b.width},y=b??{color:null,width:a.width};
  return{color:lerpColorValue(a?.color??null,b?.color??null,t),width:lerpNumber(Number(x.width??0),Number(y.width??0),t)};
}
function vectorRelabel(paths,group){return paths.map(path=>({...path,group}));}
function vectorLerpPaths(source,target,t,group){
  if(vectorTopology(source)!==vectorTopology(target))throw new Error('vector groups must share topology for direct interpolation');
  return source.map((aPath,pathIndex)=>{const bPath=target[pathIndex];return{group,fill:lerpColorValue(aPath.fill??null,bPath.fill??null,t),stroke:vectorStrokeLerp(aPath.stroke??null,bPath.stroke??null,t),contours:aPath.contours.map((aContour,contourIndex)=>{const bContour=bPath.contours[contourIndex];return{closed:!!aContour.closed&&!!bContour.closed,segments:aContour.segments.map((aSeg,segmentIndex)=>{const bSeg=bContour.segments[segmentIndex];return aSeg.map((p,pointIndex)=>lerpPoint(p,bSeg[pointIndex],t));})};})};});
}
function vectorColorOpacity(color,opacity){return color==null?null:lerpColorValue(null,color,clamp01(opacity));}
function vectorScalePaths(paths,scale,opacity,group){
  const[left,bottom,right,top]=vectorPathBounds(paths),cx=(left+right)*.5,cy=(bottom+top)*.5,point=p=>[cx+(p[0]-cx)*scale,cy+(p[1]-cy)*scale];
  return paths.map(path=>({group,fill:vectorColorOpacity(path.fill??null,opacity),stroke:path.stroke?{color:vectorColorOpacity(path.stroke.color,opacity),width:path.stroke.width}:null,contours:path.contours.map(contour=>({closed:!!contour.closed,segments:contour.segments.map(segment=>segment.map(point))}))}));
}
export function prepareVectorMorph(source,target){
  if(!source||!target)throw new TypeError('prepareVectorMorph requires source and target VectorDocuments');
  const sourceGroups=vectorGroups(source),targetGroups=vectorGroups(target),sourceKeys=sourceGroups.map(vectorVisualSignature),targetKeys=targetGroups.map(vectorVisualSignature),matched=vectorLcsPairs(sourceKeys,targetKeys),sourceMatched=new Set(matched.map(pair=>pair[0])),targetMatched=new Set(matched.map(pair=>pair[1]));
  const sourceOnly=sourceGroups.map((_,i)=>i).filter(i=>!sourceMatched.has(i)),targetOnly=targetGroups.map((_,i)=>i).filter(i=>!targetMatched.has(i));
  return{source,target,matched,sourceOnly,targetOnly,sample(alpha){const t=clamp01(alpha);if(t<=0)return source;if(t>=1)return target;const paths=[];let group=0;for(const[sourceIndex,targetIndex]of matched){const a=sourceGroups[sourceIndex],b=targetGroups[targetIndex];if(vectorTopology(a)===vectorTopology(b))paths.push(...vectorLerpPaths(a,b,t,group));else{paths.push(...vectorScalePaths(a,1-.35*t,1-t,group++));paths.push(...vectorScalePaths(b,.65+.35*t,t,group));}group++;}for(const i of sourceOnly)paths.push(...vectorScalePaths(sourceGroups[i],1-.45*t,1-t,group++));for(const i of targetOnly)paths.push(...vectorScalePaths(targetGroups[i],.55+.45*t,t,group++));return{paths,width:lerpNumber(Number(source.width),Number(target.width),t),height:lerpNumber(Number(source.height),Number(target.height),t),group_count:group};}};
}
export class DynamicVectorObject2D extends VectorObject2D {
  constructor(provider,options={}){if(typeof provider!=='function')throw new TypeError('DynamicVectorObject2D provider must be a function');const initial=provider(0,null);if(!initial?.paths)throw new TypeError('DynamicVectorObject2D provider must return a VectorDocument');super(initial,options);this.provider=provider;this._webRuntimeOnly='dynamic-vector';}
  draw(renderer,parent=Transform2D.identity()){const document=this.provider(renderer.time??0,this);if(!document?.paths)throw new TypeError('DynamicVectorObject2D provider returned an invalid VectorDocument');if(document!==this.document){this.document=document;this.invalidate();}super.draw(renderer,parent);}
}

export class TextSet extends ZObject {
  constructor(items=[],{color=WHITE,fontSize=16,fontFamily='Inter, ui-sans-serif, system-ui',weight=500,align='center',...rest}={}){super(rest);this.items=items;this.color=color;this.fontSize=fontSize;this.fontFamily=fontFamily;this.weight=weight;this.align=align;}
  draw(r,parent){const m=this.world(parent),ctx=r.ctx;withObjectContext(r,this,()=>{ctx.textBaseline='middle';for(const item of this.items){const x=item[0],y=item[1],text=item[2],color=item[3]??this.color,size=item[4]??this.fontSize,weight=item[5]??this.weight,p=m.apply(x,y),d=r.toDevice(...p);ctx.fillStyle=color;ctx.font=`${weight} ${size*r.unitSize/90}px ${this.fontFamily}`;ctx.textAlign=this.align;ctx.fillText(String(text),d[0],d[1]);}});}
}
export class DynamicTextSet extends TextSet {
  constructor(provider,opts={}){super([],opts);this.provider=provider;}
  draw(r,parent){this.items=this.provider(r.time,this);super.draw(r,parent);}
}

export class DynamicNumber extends Text {
  constructor(value,{digits=2,prefix='',suffix='',format=null,...opts}={}){
    const formatter=(time)=>format?format(sampleValue(value,time),time):`${prefix}${sampleValue(value,time).toFixed(digits)}${suffix}`;
    super(formatter,opts);this.value=value;this.format=format;
  }
}
export class DynamicPolyline extends Polyline {
  constructor(provider,opts={}){super([],{...opts});this.provider=provider;this._providerTime=NaN;}
  draw(r,parent){const points=this.provider(r.time,this);if(points!==this._points){this._points=points;this._path=null;}else this._path=null;super.draw(r,parent);}
}
export class FunctionPlot extends Polyline {
  constructor(expression,{xRange=[-5,5],axesXRange=xRange,axesYRange=[-3,3],width=10,height=6,center=[0,0],samples=240,...opts}={}){
    const expr=asScalarExpr(expression),n=Math.round(samples);if(n<2)throw new RangeError('FunctionPlot requires at least two samples');if(!(xRange[0]<xRange[1])||!(axesXRange[0]<axesXRange[1])||!(axesYRange[0]<axesYRange[1]))throw new RangeError('FunctionPlot ranges must be increasing');
    super([],{strokeWidth:DEFAULT_STROKE_WIDTH,...opts});this.expression=expr;this.xRange=xRange.map(Number);this.axesXRange=axesXRange.map(Number);this.axesYRange=axesYRange.map(Number);this.plotWidth=Number(width);this.plotHeight=Number(height);this.plotCenter=center.map(Number);this.samples=n;this._points=this.pointsAt(0);
  }
  pointsAt(time){const[a,b]=this.xRange,[ax0,ax1]=this.axesXRange,[ay0,ay1]=this.axesYRange,[cx,cy]=this.plotCenter,mx=(ax0+ax1)/2,my=(ay0+ay1)/2,sx=this.plotWidth/(ax1-ax0),sy=this.plotHeight/(ay1-ay0),out=[];for(let i=0;i<this.samples;i++){const x=a+(b-a)*i/(this.samples-1),y=this.expression.evaluate({x,time});out.push([cx+(x-mx)*sx,cy+(y-my)*sy]);}return out;}
  draw(r,parent){this._points=this.pointsAt(r.time);this._path=null;super.draw(r,parent);}
}
// Dynamic batch providers use array identity as an explicit cache hint: return
// the same array when geometry is unchanged, and a new array when it changes.
// This keeps absolute-time semantics while allowing static timeline regions to
// reuse the retained Path2D cache.
function sampleDynamicBatch(object,time){
  const items=object.provider(time,object);
  if(!Array.isArray(items))throw new TypeError('dynamic batch provider must return an item array');
  if(items!==object._items){object._items=items;object._cache=null;}
}
export class DynamicLineSet extends LineSet {
  constructor(provider,opts={}){super([],{width:DEFAULT_STROKE_WIDTH,worldStroke:true,...opts});this.provider=provider;}
  draw(r,parent){sampleDynamicBatch(this,r.time);super.draw(r,parent);}
}
export class DynamicCircleSet extends CircleSet {
  constructor(provider,opts={}){super([],opts);this.provider=provider;}
  draw(r,parent){sampleDynamicBatch(this,r.time);super.draw(r,parent);}
}
export class DynamicRectSet extends RectSet {
  constructor(provider,opts={}){super([],opts);this.provider=provider;}
  draw(r,parent){sampleDynamicBatch(this,r.time);super.draw(r,parent);}
}

function normalizeFourierTerms(terms){return terms.map(term=>{if(Array.isArray(term))return{frequency:Number(term[0]),re:Number(term[1]),im:Number(term[2])};const c=term.coefficient??[term.re??0,term.im??0];return{frequency:Number(term.frequency),re:Number(Array.isArray(c)?c[0]:c.re??0),im:Number(Array.isArray(c)?c[1]:c.im??0)};});}
function roundHalfEven(value){const x=Number(value),floor=Math.floor(x),fraction=x-floor;if(Math.abs(fraction-.5)<=1e-12)return floor%2===0?floor:floor+1;return Math.round(x);}
function fourierChain(terms,phase){let x=0,y=0;const out=[[0,0]],t=((Number(phase)%1)+1)%1;for(const term of terms){const a=TAU*term.frequency*t,c=Math.cos(a),q=Math.sin(a);x+=term.re*c-term.im*q;y+=term.re*q+term.im*c;out.push([x,y]);}return out;}
function fourierArrow(start,end){const dx=end[0]-start[0],dy=end[1]-start[1],length=Math.hypot(dx,dy);if(length<=1e-8)return[start,[start[0]+1e-5,start[1]],[start[0],start[1]+1e-5]];const ux=dx/length,uy=dy/length,nx=-uy,ny=ux,shaft=Math.min(.018,length*.08),tipLength=Math.min(.15,length*.32),tipHalf=Math.min(.065,Math.max(shaft*2.4,length*.10)),bx=end[0]-ux*tipLength,by=end[1]-uy*tipLength;return[[start[0]+nx*shaft,start[1]+ny*shaft],[bx+nx*shaft,by+ny*shaft],[bx+nx*tipHalf,by+ny*tipHalf],end,[bx-nx*tipHalf,by-ny*tipHalf],[bx-nx*shaft,by-ny*shaft],[start[0]-nx*shaft,start[1]-ny*shaft]];}
export class FourierEpicycles extends ZObject {
  constructor(terms,{startTime=0,drawDuration=1,circleSamples=28,traceSamples=1000,visualIndices=null,circleColor='rgba(132,157,198,.322)',circleWidth=.012,arrowColor='rgba(205,220,245,.745)',traceColor='#ff6c8b',traceWidth=.045,tipColor='#ffccd6',tipRadius=.055,tipSides=14,...rest}={}){
    super(rest);this.terms=normalizeFourierTerms(terms);if(!this.terms.length)throw new RangeError('FourierEpicycles requires terms');if(!(drawDuration>0))throw new RangeError('drawDuration must be positive');this.startTime=Number(startTime);this.drawDuration=Number(drawDuration);this.circleSamples=Math.max(3,Math.round(circleSamples));this.traceSamples=Math.max(2,Math.round(traceSamples));this.visualIndices=visualIndices?[...visualIndices]:this.terms.map((term,i)=>term.frequency!==0&&Math.hypot(term.re,term.im)>2e-4?i:-1).filter(i=>i>=0);this.circleColor=circleColor;this.circleWidth=Number(circleWidth);this.arrowColor=arrowColor;this.traceColor=traceColor;this.traceWidth=Number(traceWidth);this.tipColor=tipColor;this.tipRadius=Number(tipRadius);this.tipSides=Math.max(3,Math.round(tipSides));this._fullTrace=Array.from({length:this.traceSamples},(_,i)=>fourierChain(this.terms,i/(this.traceSamples-1)).at(-1));
  }
  phaseAt(time){return clamp01((Number(time)-this.startTime)/this.drawDuration);}
  draw(r,parent=Transform2D.identity()){const phase=this.phaseAt(r.time),chain=fourierChain(this.terms,phase),ctx=r.ctx,m=this.world(parent);ctx.save();ctx.globalAlpha*=clamp01(this.opacity);setWorldCanvasTransform(r,ctx,m);ctx.lineJoin='round';ctx.lineCap='round';
    ctx.beginPath();for(const index of this.visualIndices){const center=chain[index],radius=Math.hypot(this.terms[index].re,this.terms[index].im);for(let i=0;i<=this.circleSamples;i++){const a=TAU*i/this.circleSamples,x=center[0]+radius*Math.cos(a),y=center[1]+radius*Math.sin(a);i?ctx.lineTo(x,y):ctx.moveTo(x,y);}}ctx.strokeStyle=this.circleColor;ctx.lineWidth=this.circleWidth;ctx.stroke();
    ctx.beginPath();for(const index of this.visualIndices){const pts=fourierArrow(chain[index],chain[index+1]);ctx.moveTo(...pts[0]);for(let i=1;i<pts.length;i++)ctx.lineTo(...pts[i]);ctx.closePath();}ctx.fillStyle=this.arrowColor;ctx.fill();
    const end=Math.max(1,Math.min(this.traceSamples-1,roundHalfEven(phase*(this.traceSamples-1))));ctx.beginPath();ctx.moveTo(...this._fullTrace[0]);for(let i=1;i<=end;i++)ctx.lineTo(...this._fullTrace[i]);ctx.strokeStyle=this.traceColor;ctx.lineWidth=this.traceWidth;ctx.stroke();
    const tip=chain.at(-1);ctx.beginPath();for(let i=0;i<this.tipSides;i++){const a=TAU*i/this.tipSides,x=tip[0]+this.tipRadius*Math.cos(a),y=tip[1]+this.tipRadius*Math.sin(a);i?ctx.lineTo(x,y):ctx.moveTo(x,y);}ctx.closePath();ctx.fillStyle=this.tipColor;ctx.fill();ctx.restore();}
}

export class FractalField extends ZObject {
  constructor(kind,{center=[-0.5,0],zoom=1,maxIter=240,juliaC=[0,0],colorShift=0,colorScale=1,insideColor='#05070e',paletteColor='#69b9ff',viewport='parameters',resolution=.72,minWidth=160,maxWidth=960,maxHeight=540,...rest}={}){
    super(rest);this.kind=kind;this.viewportCenter=[...center];this.zoom=zoom;this.maxIter=maxIter;this.juliaC=[...juliaC];this.colorShift=colorShift;this.colorScale=colorScale;this.insideColor=insideColor;this.paletteColor=paletteColor;this.viewport=viewport;this.resolution=resolution;this.minWidth=minWidth;this.maxWidth=maxWidth;this.maxHeight=maxHeight;this._canvas=null;
  }
  draw(r,parent=Transform2D.identity()){
    const cssW=Math.max(1,r.canvas.width/r.dpr),cssH=Math.max(1,r.canvas.height/r.dpr);
    let w=Math.max(this.minWidth,Math.round(cssW*this.resolution));let h=Math.round(w*cssH/cssW);
    if(w>this.maxWidth){h=Math.round(h*this.maxWidth/w);w=this.maxWidth;}if(h>this.maxHeight){w=Math.round(w*this.maxHeight/h);h=this.maxHeight;}
    const maxIter=Math.max(1,Math.round(scalarAt(this.maxIter,r.time))),jr=scalarAt(this.juliaC[0],r.time),ji=scalarAt(this.juliaC[1],r.time),shift=scalarAt(this.colorShift,r.time),scale=scalarAt(this.colorScale,r.time);let cr,ci,worldPerPixel;
    if(this.viewport==='transform'){
      const m=parent.mul(this.transform),inv=m.inverse(),center=inv.apply(0,0),sx=Math.hypot(m.xx,m.yx),sy=Math.hypot(m.xy,m.yy),uniform=(sx+sy)*.5;cr=center[0];ci=center[1];worldPerPixel=r.canvas.width/(w*r.unitSize*Math.max(1e-12,uniform));
    }else{const zoom=scalarAt(this.zoom,r.time);cr=scalarAt(this.viewportCenter[0],r.time);ci=scalarAt(this.viewportCenter[1],r.time);worldPerPixel=(3.2/Math.max(1e-12,zoom))/w;}
    const inside=parseWebColor(this.insideColor).slice(0,3),palette=parseWebColor(this.paletteColor).slice(0,3),bytes=r.wasm.renderFractal(this.kind,w,h,cr,ci,worldPerPixel,maxIter,jr,ji,shift,scale,inside,palette);
    const copy=new Uint8ClampedArray(bytes);if(!this._canvas)this._canvas=document.createElement('canvas');this._canvas.width=w;this._canvas.height=h;this._canvas.getContext('2d').putImageData(new ImageData(copy,w,h),0,0);
    withObjectContext(r,this,ctx=>ctx.drawImage(this._canvas,0,0,r.canvas.width,r.canvas.height));
  }
}
export class MandelbrotSet extends FractalField { constructor(options={}){super(1,{center:[-0.5,0],...options});} }
export class JuliaSet extends FractalField { constructor(c=[-0.8,.156],options={}){super(2,{center:[0,0],juliaC:c,...options});} }

const COMPLEX_MAP_KIND=Object.freeze({square:1,exp:2,reciprocal:3,mobius:4});
export class ComplexMappedGrid extends ZObject {
  constructor(mapping,{step=.5,progress=1,center=[0,0],span=5,strokePx=1.15,mapParams=null,viewport='parameters',resolution=.72,minWidth=120,maxWidth=960,maxHeight=540,frame=null,...rest}={}){
    super(rest);if(!(mapping in COMPLEX_MAP_KIND))throw new Error(`unsupported complex mapping: ${mapping}`);this.mapping=mapping;this.mapKind=COMPLEX_MAP_KIND[mapping];this.step=Array.isArray(step)?step:[step,step];this.progress=progress;this.viewportCenter=[...center];this.span=span;this.strokePx=strokePx;this.viewport=viewport;this.resolution=resolution;this.minWidth=minWidth;this.maxWidth=maxWidth;this.maxHeight=maxHeight;this.frame=frame;
    if(mapParams)this.mapParams=[...mapParams];else if(mapping==='exp')this.mapParams=[1,0];else if(mapping==='mobius')this.mapParams=[1,.18,.55,-.25,.18,-.12,1,0];else this.mapParams=[];
  }
  draw(r,parent=Transform2D.identity()){
    const fullCssW=Math.max(1,r.canvas.width/r.dpr),fullCssH=Math.max(1,r.canvas.height/r.dpr),frame=this.frame;
    const cssW=frame?Math.max(1,frame.size[0]*r.unitSize/r.dpr):fullCssW,cssH=frame?Math.max(1,frame.size[1]*r.unitSize/r.dpr):fullCssH;
    let w=Math.max(this.minWidth,Math.round(cssW*this.resolution)),h=Math.round(w*cssH/cssW);if(w>this.maxWidth){h=Math.round(h*this.maxWidth/w);w=this.maxWidth;}if(h>this.maxHeight){w=Math.round(w*this.maxHeight/h);h=this.maxHeight;}
    const span=this.viewport==='canvas'?r.canvas.width/r.unitSize:scalarAt(this.span,r.time),p=scalarAt(this.progress,r.time),cr=scalarAt(this.viewportCenter[0],r.time),ci=scalarAt(this.viewportCenter[1],r.time),bytes=r.wasm.renderComplexGrid(this.mapKind,w,h,cr,ci,span/w,this.step[0],this.step[1],p,this.strokePx,this.mapParams),copy=new Uint8ClampedArray(bytes);
    if(!this._canvas)this._canvas=document.createElement('canvas');this._canvas.width=w;this._canvas.height=h;this._canvas.getContext('2d').putImageData(new ImageData(copy,w,h),0,0);
    withObjectContext(r,this,ctx=>{if(frame){const d=r.toDevice(frame.center[0],frame.center[1]),dw=frame.size[0]*r.unitSize,dh=frame.size[1]*r.unitSize;ctx.drawImage(this._canvas,d[0]-dw/2,d[1]-dh/2,dw,dh);}else ctx.drawImage(this._canvas,0,0,r.canvas.width,r.canvas.height);});
  }
}

export class CanvasRenderer {
  constructor(canvas,wasm,{unitSize=90,background='#080b12'}={}){this.canvas=canvas;this.ctx=canvas.getContext('2d');this.wasm=wasm;this.baseUnitSize=unitSize;this.unitSize=unitSize;this.background=background;this.dpr=1;}
  resize(){const dpr=Math.min(globalThis.devicePixelRatio||1,2),rect=this.canvas.getBoundingClientRect();const w=Math.max(1,Math.round(rect.width*dpr)),h=Math.max(1,Math.round(rect.height*dpr));this.dpr=dpr;this.unitSize=this.baseUnitSize*dpr;if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=w;this.canvas.height=h;}}
  toDevice(x,y){return[this.canvas.width/2+x*this.unitSize,this.canvas.height/2-y*this.unitSize];}
  clear(){const c=this.ctx;c.save();c.setTransform(1,0,0,1,0,0);c.globalAlpha=1;c.fillStyle=this.background;c.fillRect(0,0,this.canvas.width,this.canvas.height);c.restore();}
}


function cubicLine(a,b){return{p0:a,p1:[lerpNumber(a[0],b[0],1/3),lerpNumber(a[1],b[1],1/3)],p2:[lerpNumber(a[0],b[0],2/3),lerpNumber(a[1],b[1],2/3)],p3:b};}
function ellipse8(radius){const out=[],delta=PI/4,k=(4/3)*Math.tan(delta/4);for(let i=0;i<8;i++){const a0=i*delta,a1=a0+delta,p0=[radius*Math.cos(a0),radius*Math.sin(a0)],p3=[radius*Math.cos(a1),radius*Math.sin(a1)],t0=[-radius*Math.sin(a0),radius*Math.cos(a0)],t1=[-radius*Math.sin(a1),radius*Math.cos(a1)];out.push({p0,p1:[p0[0]+k*t0[0],p0[1]+k*t0[1]],p2:[p3[0]-k*t1[0],p3[1]-k*t1[1]],p3});}return out;}
function rectangle8(width,height){const hx=width/2,hy=height/2,a=[[hx,0],[hx,hy],[0,hy],[-hx,hy],[-hx,0],[-hx,-hy],[0,-hy],[hx,-hy]];return a.map((p,i)=>cubicLine(p,a[(i+1)%8]));}
function splitLine8(a,b){return Array.from({length:8},(_,i)=>cubicLine([lerpNumber(a[0],b[0],i/8),lerpNumber(a[1],b[1],i/8)],[lerpNumber(a[0],b[0],(i+1)/8),lerpNumber(a[1],b[1],(i+1)/8)]));}
function resampleClosed(points,count){const source=[...points,points[0]],lengths=[],cum=[0];for(let i=0;i<source.length-1;i++){const d=Math.hypot(source[i+1][0]-source[i][0],source[i+1][1]-source[i][1]);lengths.push(d);cum.push(cum.at(-1)+d);}const total=cum.at(-1);if(total<=1e-14)return Array.from({length:count},()=>[points[0][0],points[0][1]]);const out=[];let seg=0;for(let i=0;i<count;i++){const target=total*i/count;while(seg+1<cum.length-1&&cum[seg+1]<target)seg++;const local=lengths[seg]<=1e-14?0:(target-cum[seg])/lengths[seg];out.push([lerpNumber(source[seg][0],source[seg+1][0],local),lerpNumber(source[seg][1],source[seg+1][1],local)]);}return out;}
function normalizeGeometry(object,count=8){
  if(object instanceof Circle)return{segments:ellipse8(object.radius),closed:true};
  if(object instanceof Rectangle)return{segments:rectangle8(object.rectWidth,object.rectHeight),closed:true};
  if(object instanceof Line)return{segments:splitLine8(object.start,object.end),closed:false};
  if(object instanceof Polyline){if(object.closed){const q=resampleClosed(object.points,count);return{segments:q.map((p,i)=>cubicLine(p,q[(i+1)%q.length])),closed:true};}const q=resamplePolylineByArcLength(object.points,count);return{segments:q.slice(0,-1).map((p,i)=>cubicLine(p,q[i+1])),closed:false};}
  throw new TypeError(`unsupported interpolation geometry: ${object.constructor.name}`);
}
export class PrimitiveInterpolation extends ZObject {
  constructor(source,target,start,end,easing){super({zIndex:Math.max(source.zIndex,target.zIndex)});this.source={geometry:normalizeGeometry(source,8),transform:cloneTransform(source.transform),style:snapshotStyle(source),opacity:source.opacity};this.target={geometry:normalizeGeometry(target,8),transform:cloneTransform(target.transform),style:snapshotStyle(target),opacity:target.opacity};if(this.source.geometry.closed!==this.target.geometry.closed)throw new Error('interpolation topology mismatch');this.start=start;this.end=end;this.easing=easing;}
  draw(r,parent=Transform2D.identity()){const raw=this.end<=this.start?1:(r.time-this.start)/(this.end-this.start),t=this.easing(clamp01(raw)),a=this.source.geometry.segments,b=this.target.geometry.segments,path=new Path2D();for(let i=0;i<a.length;i++){const seg={p0:lerpPoint(a[i].p0,b[i].p0,t),p1:lerpPoint(a[i].p1,b[i].p1,t),p2:lerpPoint(a[i].p2,b[i].p2,t),p3:lerpPoint(a[i].p3,b[i].p3,t)};if(i===0)path.moveTo(...seg.p0);path.bezierCurveTo(...seg.p1,...seg.p2,...seg.p3);}if(this.source.geometry.closed)path.closePath();const transform=Transform2D.lerp(this.source.transform,this.target.transform,t),style=lerpStyleState(this.source.style,this.target.style,t),opacity=lerpNumber(this.source.opacity,this.target.opacity,t),ctx=r.ctx;ctx.save();ctx.globalAlpha*=clamp01(opacity);setWorldCanvasTransform(r,ctx,parent.mul(transform));if(style?.fill){ctx.fillStyle=style.fill;ctx.fill(path);}if(style?.stroke){ctx.strokeStyle=style.stroke;ctx.lineWidth=style.worldStroke?style.width:style.width*r.dpr/r.unitSize;ctx.stroke(path);}ctx.restore();}
}
export function snapshotStyle(o){
  if(!('fill' in o)&&!('stroke' in o)&&!('width' in o))return null;
  return {fill:'fill' in o?o.fill:null,stroke:'stroke' in o?o.stroke:null,width:'width' in o?o.width:null,worldStroke:'worldStroke' in o?!!o.worldStroke:false};
}
export function applyStyle(o,style){if(!style)return;if('fill' in o)o.fill=style.fill;if('stroke' in o)o.stroke=style.stroke;if('width' in o&&style.width!=null)o.width=style.width;if('worldStroke' in o)o.worldStroke=!!style.worldStroke;}
export function lerpStyleState(a,b,t){
  if(!a&&!b)return null;const x=a??b,y=b??a;
  return {fill:lerpColorValue(a?.fill??null,b?.fill??null,t),stroke:lerpColorValue(a?.stroke??null,b?.stroke??null,t),width:lerpNumber(x.width??0,y.width??0,t),worldStroke:t<1?!!x.worldStroke:!!y.worldStroke};
}
export function cloneState(o){return{transform:o.transform,opacity:o.opacity,reveal:'reveal' in o?Number(o.reveal):null,style:snapshotStyle(o)};}
export function assignState(o,s){if(s.transform)o.transform=s.transform;if(s.opacity!=null)o.opacity=s.opacity;if(s.reveal!=null&&'reveal' in o)o.reveal=s.reveal;if(s.style!==undefined)applyStyle(o,s.style);}
export function appendOrdered(map,key,clip){
  let list=map.get(key);if(!list)map.set(key,list=[]);
  if(!list.length||list[list.length-1].start<=clip.start)list.push(clip);
  else{let i=list.length;while(i>0&&list[i-1].start>clip.start)i--;list.splice(i,0,clip);}
  return clip;
}

class LayoutBase {
  targets(...objects){const centers=this.centers(objects);return objects.map((o,i)=>{const b=o.bounds(),delta=new Vec2(centers[i].x-b.center.x,centers[i].y-b.center.y);return Transform2D.translation(delta.x,delta.y).mul(o.transform);});}
  place(...objects){const targets=this.targets(...objects);objects.forEach((o,i)=>o.transform=targets[i]);return objects;}
  placeBlock(objects,centers){const bounds=Bounds2D.union(...objects.map((o,i)=>{const b=o.bounds(),hw=b.width/2,hh=b.height/2,c=centers[i];return new Bounds2D(c.x-hw,c.y-hh,c.x+hw,c.y+hh);})),a=asAnchor(this.anchor),block=new Vec2(bounds.center.x+a.x*bounds.width/2,bounds.center.y+a.y*bounds.height/2),at=Vec2.from(this.at),d=at.sub(block);return centers.map(c=>c.add(d));}
}
export class Row extends LayoutBase {
  constructor({gap=.25,anchor=CENTER,at=[0,0],align=CENTER}={}){super();Object.assign(this,{gap,anchor,at,align});}
  centers(objects){const cross=asAnchor(this.align).y,widths=objects.map(o=>o.bounds().width),total=widths.reduce((a,b)=>a+b,0)+this.gap*(objects.length-1);let cursor=-total/2;const centers=objects.map((o,i)=>{const c=new Vec2(cursor+widths[i]/2,-cross*o.bounds().height/2);cursor+=widths[i]+this.gap;return c;});return this.placeBlock(objects,centers);}
}
export class Column extends LayoutBase {
  constructor({gap=.25,anchor=CENTER,at=[0,0],align=CENTER}={}){super();Object.assign(this,{gap,anchor,at,align});}
  centers(objects){const cross=asAnchor(this.align).x,heights=objects.map(o=>o.bounds().height),total=heights.reduce((a,b)=>a+b,0)+this.gap*(objects.length-1);let cursor=total/2;const centers=objects.map((o,i)=>{const c=new Vec2(-cross*o.bounds().width/2,cursor-heights[i]/2);cursor-=heights[i]+this.gap;return c;});return this.placeBlock(objects,centers);}
}
export class Grid extends LayoutBase {
  constructor({rows=null,cols=null,gap=.25,anchor=CENTER,at=[0,0]}={}){super();Object.assign(this,{rows,cols,gap,anchor,at});}
  centers(objects){let rows=this.rows,cols=this.cols,count=objects.length;if(rows==null&&cols==null)cols=Math.ceil(Math.sqrt(count));if(cols==null)cols=Math.ceil(count/rows);if(rows==null)rows=Math.ceil(count/cols);const gap=Array.isArray(this.gap)||this.gap instanceof Vec2?Vec2.from(this.gap):new Vec2(this.gap,this.gap),cw=Math.max(...objects.map(o=>o.bounds().width)),ch=Math.max(...objects.map(o=>o.bounds().height)),tw=cols*cw+(cols-1)*gap.x,th=rows*ch+(rows-1)*gap.y,centers=objects.map((o,i)=>{const row=Math.floor(i/cols),col=i%cols;return new Vec2(-tw/2+cw/2+col*(cw+gap.x),th/2-ch/2-row*(ch+gap.y));});return this.placeBlock(objects,centers);}
}

