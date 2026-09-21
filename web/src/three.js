import { BLUE, ZObject, parseWebColor, sampleValue } from './core.js';

export class Vec3 {
  constructor(x=0,y=0,z=0){this.x=Number(x);this.y=Number(y);this.z=Number(z);}
  static from(value){if(value instanceof Vec3)return value;if(Array.isArray(value)&&value.length===3)return new Vec3(...value);throw new TypeError('expected Vec3 or [x,y,z]');}
  add(v){v=Vec3.from(v);return new Vec3(this.x+v.x,this.y+v.y,this.z+v.z);}
  sub(v){v=Vec3.from(v);return new Vec3(this.x-v.x,this.y-v.y,this.z-v.z);}
  mul(s){return new Vec3(this.x*s,this.y*s,this.z*s);}
  dot(v){v=Vec3.from(v);return this.x*v.x+this.y*v.y+this.z*v.z;}
  cross(v){v=Vec3.from(v);return new Vec3(this.y*v.z-this.z*v.y,this.z*v.x-this.x*v.z,this.x*v.y-this.y*v.x);}
  get length(){return Math.hypot(this.x,this.y,this.z);}
  normalized(){const n=this.length;if(n<=1e-15)throw new RangeError('cannot normalize zero Vec3');return this.mul(1/n);}
}

export class Transform3D {
  constructor(
    m00=1,m01=0,m02=0,m03=0,
    m10=0,m11=1,m12=0,m13=0,
    m20=0,m21=0,m22=1,m23=0,
    m30=0,m31=0,m32=0,m33=1,
  ){Object.assign(this,{m00,m01,m02,m03,m10,m11,m12,m13,m20,m21,m22,m23,m30,m31,m32,m33});}
  static identity(){return new Transform3D();}
  static translation(x,y,z){return new Transform3D(1,0,0,x,0,1,0,y,0,0,1,z,0,0,0,1);}
  static scaling(x,y=x,z=x){return new Transform3D(x,0,0,0,0,y,0,0,0,0,z,0,0,0,0,1);}
  static rotationAxis(axis,radians){
    const a=Vec3.from(axis).normalized(),{x,y,z}=a,c=Math.cos(radians),s=Math.sin(radians),q=1-c;
    return new Transform3D(
      c+x*x*q,x*y*q-z*s,x*z*q+y*s,0,
      y*x*q+z*s,c+y*y*q,y*z*q-x*s,0,
      z*x*q-y*s,z*y*q+x*s,c+z*z*q,0,
      0,0,0,1,
    );
  }
  static rotationX(r){return Transform3D.rotationAxis(new Vec3(1,0,0),r);}
  static rotationY(r){return Transform3D.rotationAxis(new Vec3(0,1,0),r);}
  static rotationZ(r){return Transform3D.rotationAxis(new Vec3(0,0,1),r);}
  mul(b){
    if(!(b instanceof Transform3D))throw new TypeError('Transform3D.mul requires Transform3D');
    const a=this,A=a.asArray(),B=b.asArray(),out=new Array(16).fill(0);
    for(let r=0;r<4;r++)for(let c=0;c<4;c++)for(let k=0;k<4;k++)out[r*4+c]+=A[r*4+k]*B[k*4+c];
    return new Transform3D(...out);
  }
  translate(x,y,z){return this.mul(Transform3D.translation(x,y,z));}
  scale(x,y=x,z=x){return this.mul(Transform3D.scaling(x,y,z));}
  rotateX(r){return this.mul(Transform3D.rotationX(r));}
  rotateY(r){return this.mul(Transform3D.rotationY(r));}
  rotateZ(r){return this.mul(Transform3D.rotationZ(r));}
  apply(point){
    const p=Vec3.from(point),x=this.m00*p.x+this.m01*p.y+this.m02*p.z+this.m03,y=this.m10*p.x+this.m11*p.y+this.m12*p.z+this.m13,z=this.m20*p.x+this.m21*p.y+this.m22*p.z+this.m23,w=this.m30*p.x+this.m31*p.y+this.m32*p.z+this.m33;
    if(Math.abs(w)<=1e-15)throw new RangeError('Transform3D produced a point at infinity');return new Vec3(x/w,y/w,z/w);
  }
  asArray(){return [this.m00,this.m01,this.m02,this.m03,this.m10,this.m11,this.m12,this.m13,this.m20,this.m21,this.m22,this.m23,this.m30,this.m31,this.m32,this.m33];}
}

function flattenVec3(values,name){
  if(values instanceof Float32Array){if(values.length%3)throw new RangeError(`${name} must contain xyz triples`);return values;}
  const out=[];for(const value of values){const v=Vec3.from(value);out.push(v.x,v.y,v.z);}return new Float32Array(out);
}

export class TriangleMesh {
  constructor(vertices,normals,indices){
    this.positions=flattenVec3(vertices,'vertices');this.normals=flattenVec3(normals,'normals');this.indices=indices instanceof Uint32Array?indices:new Uint32Array(indices);
    this.vertexCount=this.positions.length/3;this.indexCount=this.indices.length;
    if(this.vertexCount<3)throw new RangeError('TriangleMesh requires at least 3 vertices');
    if(this.normals.length!==this.positions.length)throw new RangeError('TriangleMesh normals must match vertices');
    if(!this.indexCount||this.indexCount%3)throw new RangeError('TriangleMesh indices must contain triangles');
    for(const index of this.indices)if(index>=this.vertexCount)throw new RangeError('TriangleMesh index is outside vertex range');
  }
}

function packColorRGBA(color){
  const rgba=parseWebColor(color);if(!rgba)throw new TypeError('3D mesh color is required');
  return (((rgba[0]&255)<<24)|((rgba[1]&255)<<16)|((rgba[2]&255)<<8)|(rgba[3]&255))>>>0;
}

function atTime(value,time,object){return typeof value==='function'?value(time,object):value;}

export class MeshObject3D {
  constructor(mesh,{transform=Transform3D.identity(),geometryTransform=Transform3D.identity(),color=BLUE,opacity=1}={}){
    if(!(mesh instanceof TriangleMesh))throw new TypeError('MeshObject3D requires TriangleMesh');
    this.mesh=mesh;this.transform=transform;this.geometryTransform=geometryTransform;this.color=color;this.opacity=opacity;
  }
  stateAt(time){
    const transform=atTime(this.transform,time,this);if(!(transform instanceof Transform3D))throw new TypeError('3D transform provider must return Transform3D');
    const geometry=atTime(this.geometryTransform,time,this);if(!(geometry instanceof Transform3D))throw new TypeError('3D geometry transform must be Transform3D');
    const opacity=sampleValue(this.opacity,time);if(!(opacity>=0&&opacity<=1))throw new RangeError('3D opacity must be in [0,1]');
    return {model:transform.mul(geometry).asArray(),colorRGBA:packColorRGBA(atTime(this.color,time,this)),opacity};
  }
}

let boxMeshCache=null;
export function unitBoxMesh(){
  if(boxMeshCache)return boxMeshCache;
  const h=.5,faces=[
    [[0,0,1],[[-h,-h,h],[h,-h,h],[h,h,h],[-h,h,h]]],
    [[0,0,-1],[[h,-h,-h],[-h,-h,-h],[-h,h,-h],[h,h,-h]]],
    [[1,0,0],[[h,-h,h],[h,-h,-h],[h,h,-h],[h,h,h]]],
    [[-1,0,0],[[-h,-h,-h],[-h,-h,h],[-h,h,h],[-h,h,-h]]],
    [[0,1,0],[[-h,h,h],[h,h,h],[h,h,-h],[-h,h,-h]]],
    [[0,-1,0],[[-h,-h,-h],[h,-h,-h],[h,-h,h],[-h,-h,h]]],
  ],vertices=[],normals=[],indices=[];
  for(const [normal,corners] of faces){const base=vertices.length;for(const p of corners){vertices.push(p);normals.push(normal);}indices.push(base,base+1,base+2,base,base+2,base+3);}
  return boxMeshCache=new TriangleMesh(vertices,normals,indices);
}

export function Box3D(size=new Vec3(2,2,2),options={}){const s=Vec3.from(size);if(s.x<=0||s.y<=0||s.z<=0)throw new RangeError('box dimensions must be positive');return new MeshObject3D(unitBoxMesh(),{...options,geometryTransform:Transform3D.scaling(s.x,s.y,s.z)});}
export function Cube3D(side=2,options={}){return Box3D(new Vec3(side,side,side),options);}

export function projectPoint3D(point,cameraState,width,height){
  const p=Vec3.from(point),state=cameraState;
  const forward=state.target.sub(state.position).normalized();
  const right=forward.cross(state.up).normalized();
  const cameraUp=right.cross(forward).normalized();
  const rel=p.sub(state.position);
  const depth=rel.dot(forward);
  if(depth<=state.near)return null;
  let x,y;
  if(state.orthographicHeight!=null){
    const scale=height/state.orthographicHeight;
    x=width/2+rel.dot(right)*scale;
    y=height/2-rel.dot(cameraUp)*scale;
  }else{
    const focal=(height/2)/Math.tan(state.fovYDegrees*Math.PI/360);
    x=width/2+rel.dot(right)*focal/depth;
    y=height/2-rel.dot(cameraUp)*focal/depth;
  }
  return [x,y,depth];
}

function projectedScalarAt(value,renderer,time,object){return Number(typeof value==='function'?value(renderer,time,object):value);}

function resolve3DPoints(value,time,object){
  const raw=typeof value==='function'?value(time,object):value;
  return Array.from(raw,point=>Vec3.from(point));
}

export class ProjectedPolyline3D extends ZObject {
  constructor(points,{camera=new Camera3D(),stroke='#ffffff',strokeWidth=3,closed=false,endTip=false,tipSize=18,...rest}={}){
    super(rest);this.points=points;this.camera=camera;this.stroke=stroke;this.strokeWidth=strokeWidth;this.closed=Boolean(closed);this.endTip=Boolean(endTip);this.tipSize=tipSize;
  }
  draw(renderer){
    const time=renderer.time??0,state=this.camera.stateAt(time),points=resolve3DPoints(this.points,time,this);
    if(points.length<2)return;
    const projected=points.map(p=>projectPoint3D(p,state,renderer.canvas.width,renderer.canvas.height));
    const ctx=renderer.ctx;
    const strokeWidth=projectedScalarAt(this.strokeWidth,renderer,time,this);
    ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha*=Math.max(0,Math.min(1,this.opacity));ctx.strokeStyle=this.stroke;ctx.lineWidth=strokeWidth;ctx.lineCap='round';ctx.lineJoin='round';ctx.beginPath();
    let started=false;
    for(const q of projected){if(!q){started=false;continue;}if(!started){ctx.moveTo(q[0],q[1]);started=true;}else ctx.lineTo(q[0],q[1]);}
    if(this.closed&&started)ctx.closePath();ctx.stroke();
    if(this.endTip){
      let b=null,a=null;
      for(let i=projected.length-1;i>=0;i--){if(!projected[i])continue;if(!b)b=projected[i];else{a=projected[i];break;}}
      if(a&&b){const dx=b[0]-a[0],dy=b[1]-a[1],n=Math.hypot(dx,dy);if(n>1e-6){const ux=dx/n,uy=dy/n,px=-uy,py=ux,L=projectedScalarAt(this.tipSize,renderer,time,this),W=L*.48;ctx.fillStyle=this.stroke;ctx.beginPath();ctx.moveTo(b[0],b[1]);ctx.lineTo(b[0]-ux*L+px*W,b[1]-uy*L+py*W);ctx.lineTo(b[0]-ux*L-px*W,b[1]-uy*L-py*W);ctx.closePath();ctx.fill();}}
    }
    ctx.restore();
  }
}

export class ProjectedLineSet3D extends ZObject {
  constructor(segments,{camera=new Camera3D(),stroke='#ffffff',strokeWidth=3,...rest}={}){
    super(rest);this.segments=segments;this.camera=camera;this.stroke=stroke;this.strokeWidth=strokeWidth;
  }
  draw(renderer){
    const time=renderer.time??0,state=this.camera.stateAt(time),segments=typeof this.segments==='function'?this.segments(time,this):this.segments,ctx=renderer.ctx;
    const strokeWidth=projectedScalarAt(this.strokeWidth,renderer,time,this);
    ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha*=Math.max(0,Math.min(1,this.opacity));ctx.strokeStyle=this.stroke;ctx.lineWidth=strokeWidth;ctx.lineCap='round';ctx.beginPath();
    for(const segment of segments){if(!Array.isArray(segment)||segment.length!==2)continue;const a=projectPoint3D(segment[0],state,renderer.canvas.width,renderer.canvas.height),b=projectPoint3D(segment[1],state,renderer.canvas.width,renderer.canvas.height);if(!a||!b)continue;ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);}
    ctx.stroke();ctx.restore();
  }
}

function cameraValueAt(value,time,camera){return typeof value==='function'?value(time,camera):value;}
function validateCameraState(state){
  if(!(state.near>0&&state.far>state.near))throw new RangeError('Camera3D requires 0 < near < far');
  if(!(state.fovYDegrees>=1&&state.fovYDegrees<179))throw new RangeError('Camera3D fovYDegrees must be in [1,179)');
  if(state.orthographicHeight!=null&&!(state.orthographicHeight>0))throw new RangeError('Camera3D orthographicHeight must be positive');
  if(state.target.sub(state.position).length<=1e-12)throw new RangeError('Camera3D position and target must differ');
  if(state.up.length<=1e-12)throw new RangeError('Camera3D up vector must be non-zero');
  return state;
}
export class Camera3D {
  constructor({position=new Vec3(4.5,3.2,5.5),target=new Vec3(),up=new Vec3(0,1,0),fovYDegrees=45,near=.05,far=100,orthographicHeight=null,layerZIndex=0}={}){
    this.position=position;this.target=target;this.up=up;this.fovYDegrees=fovYDegrees;this.near=near;this.far=far;this.orthographicHeight=orthographicHeight;this.layerZIndex=layerZIndex;
    this._viewOverride={yaw:0,pitch:0,distanceScale:1};
    this.stateAt(0);
  }
  get viewOverride(){return{...this._viewOverride};}
  setViewOverride({yaw=this._viewOverride.yaw,pitch=this._viewOverride.pitch,distanceScale=this._viewOverride.distanceScale}={}){
    yaw=Number(yaw);pitch=Number(pitch);distanceScale=Number(distanceScale);
    if(!Number.isFinite(yaw)||!Number.isFinite(pitch))throw new TypeError('Camera3D view override angles must be finite');
    if(!(distanceScale>0)&&Number.isFinite(distanceScale))throw new RangeError('Camera3D view override distanceScale must be positive');
    if(!Number.isFinite(distanceScale)||distanceScale<=0)throw new RangeError('Camera3D view override distanceScale must be finite and positive');
    this._viewOverride={yaw,pitch:Math.max(-Math.PI*.48,Math.min(Math.PI*.48,pitch)),distanceScale:Math.max(.12,Math.min(8,distanceScale))};
    return this;
  }
  orbitBy(yaw=0,pitch=0){return this.setViewOverride({yaw:this._viewOverride.yaw+Number(yaw),pitch:this._viewOverride.pitch+Number(pitch)});}
  zoomBy(factor=1){factor=Number(factor);if(!(factor>0)||!Number.isFinite(factor))throw new RangeError('Camera3D zoom factor must be finite and positive');return this.setViewOverride({distanceScale:this._viewOverride.distanceScale*factor});}
  resetViewOverride(){this._viewOverride={yaw:0,pitch:0,distanceScale:1};return this;}
  stateAt(time=0){
    let position=Vec3.from(cameraValueAt(this.position,time,this));
    const target=Vec3.from(cameraValueAt(this.target,time,this));
    const up=Vec3.from(cameraValueAt(this.up,time,this));
    const override=this._viewOverride;
    if(override&&(Math.abs(override.yaw)>1e-12||Math.abs(override.pitch)>1e-12||Math.abs(override.distanceScale-1)>1e-12)){
      const rel=position.sub(target),baseRadius=rel.length;
      if(baseRadius>1e-12){
        const theta=Math.atan2(rel.y,rel.x)+override.yaw;
        const basePhi=Math.acos(Math.max(-1,Math.min(1,rel.z/baseRadius)));
        const phi=Math.max(.02,Math.min(Math.PI-.02,basePhi+override.pitch));
        const radius=baseRadius*override.distanceScale,sinPhi=Math.sin(phi);
        position=new Vec3(
          target.x+radius*sinPhi*Math.cos(theta),
          target.y+radius*sinPhi*Math.sin(theta),
          target.z+radius*Math.cos(phi),
        );
      }
    }
    const fovYDegrees=Number(cameraValueAt(this.fovYDegrees,time,this));
    const near=Number(cameraValueAt(this.near,time,this));
    const far=Number(cameraValueAt(this.far,time,this));
    const rawOrtho=cameraValueAt(this.orthographicHeight,time,this);
    const orthographicHeight=rawOrtho==null?null:Number(rawOrtho);
    const layerZIndex=Number(cameraValueAt(this.layerZIndex,time,this));
    return validateCameraState({position,target,up,fovYDegrees,near,far,orthographicHeight,layerZIndex});
  }
}

export class Scene3DLayer extends ZObject {
  constructor(meshes,{camera=new Camera3D(),lightPosition=null,lightDirection=null,ambientLight=.24,diffuseLight=.76,resolution=1,maxWidth=1280,maxHeight=720,...rest}={}){
    super({zIndex:camera.layerZIndex,...rest});
    if(lightPosition!=null&&lightDirection!=null)throw new TypeError('Scene3DLayer accepts either lightPosition or lightDirection, not both');
    this.meshes=[...meshes];if(this.meshes.some(mesh=>!(mesh instanceof MeshObject3D)))throw new TypeError('Scene3DLayer meshes must be MeshObject3D');
    this.camera=camera;this.lightPosition=lightPosition;this.lightDirection=lightDirection;this.ambientLight=Number(ambientLight);this.diffuseLight=Number(diffuseLight);if(!(this.ambientLight>=0)||!(this.diffuseLight>=0))throw new RangeError('Scene3DLayer lighting strengths must be non-negative');this.resolution=Number(resolution);this.maxWidth=Math.min(1280,Math.round(maxWidth));this.maxHeight=Math.min(720,Math.round(maxHeight));this._wasm=null;this._upload=null;this._canvas=null;
  }
  draw(renderer){
    if(!this.meshes.length)return;const fullW=renderer.canvas.width,fullH=renderer.canvas.height;if(fullW<=0||fullH<=0)return;
    let width=Math.max(1,Math.min(this.maxWidth,Math.round(fullW*this.resolution))),height=Math.max(1,Math.round(width*fullH/fullW));if(height>this.maxHeight){width=Math.max(1,Math.round(width*this.maxHeight/height));height=this.maxHeight;}
    if(this._wasm!==renderer.wasm||!this._upload||renderer.wasm._3dUpload!==this._upload){this._wasm=renderer.wasm;this._upload=renderer.wasm.upload3DGeometry(this.meshes.map(mesh=>mesh.mesh));}
    const time=renderer.time??0,camera=typeof this.camera.stateAt==='function'?this.camera.stateAt(time):this.camera;
    const lighting=this.lightPosition!=null
      ?{position:Vec3.from(atTime(this.lightPosition,time,this)),ambient:this.ambientLight,diffuse:this.diffuseLight}
      :this.lightDirection!=null
        ?{direction:Vec3.from(atTime(this.lightDirection,time,this)),ambient:this.ambientLight,diffuse:this.diffuseLight}
        :{ambient:this.ambientLight,diffuse:this.diffuseLight};
    const pixels=renderer.wasm.render3D(width,height,camera,this._upload,this.meshes.map(mesh=>mesh.stateAt(time)),lighting);
    if(!this._canvas)this._canvas=document.createElement('canvas');if(this._canvas.width!==width||this._canvas.height!==height){this._canvas.width=width;this._canvas.height=height;}
    this._canvas.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(pixels),width,height),0,0);
    const ctx=renderer.ctx;ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha*=Math.max(0,Math.min(1,this.opacity));ctx.drawImage(this._canvas,0,0,fullW,fullH);ctx.restore();
  }
}
