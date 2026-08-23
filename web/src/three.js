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

export class Camera3D {
  constructor({position=new Vec3(4.5,3.2,5.5),target=new Vec3(),up=new Vec3(0,1,0),fovYDegrees=45,near=.05,far=100,orthographicHeight=null,layerZIndex=0}={}){
    this.position=Vec3.from(position);this.target=Vec3.from(target);this.up=Vec3.from(up);this.fovYDegrees=Number(fovYDegrees);this.near=Number(near);this.far=Number(far);this.orthographicHeight=orthographicHeight==null?null:Number(orthographicHeight);this.layerZIndex=Number(layerZIndex);
    if(!(this.near>0&&this.far>this.near))throw new RangeError('Camera3D requires 0 < near < far');if(!(this.fovYDegrees>=1&&this.fovYDegrees<179))throw new RangeError('Camera3D fovYDegrees must be in [1,179)');if(this.orthographicHeight!=null&&!(this.orthographicHeight>0))throw new RangeError('Camera3D orthographicHeight must be positive');if(this.target.sub(this.position).length<=1e-12)throw new RangeError('Camera3D position and target must differ');if(this.up.length<=1e-12)throw new RangeError('Camera3D up vector must be non-zero');
  }
}

export class Scene3DLayer extends ZObject {
  constructor(meshes,{camera=new Camera3D(),resolution=1,maxWidth=1280,maxHeight=720,...rest}={}){
    super({zIndex:camera.layerZIndex,...rest});this.meshes=[...meshes];if(this.meshes.some(mesh=>!(mesh instanceof MeshObject3D)))throw new TypeError('Scene3DLayer meshes must be MeshObject3D');this.camera=camera;this.resolution=Number(resolution);this.maxWidth=Math.min(1280,Math.round(maxWidth));this.maxHeight=Math.min(720,Math.round(maxHeight));this._wasm=null;this._upload=null;this._canvas=null;
  }
  draw(renderer){
    if(!this.meshes.length)return;const fullW=renderer.canvas.width,fullH=renderer.canvas.height;if(fullW<=0||fullH<=0)return;
    let width=Math.max(1,Math.min(this.maxWidth,Math.round(fullW*this.resolution))),height=Math.max(1,Math.round(width*fullH/fullW));if(height>this.maxHeight){width=Math.max(1,Math.round(width*this.maxHeight/height));height=this.maxHeight;}
    if(this._wasm!==renderer.wasm||!this._upload||renderer.wasm._3dUpload!==this._upload){this._wasm=renderer.wasm;this._upload=renderer.wasm.upload3DGeometry(this.meshes.map(mesh=>mesh.mesh));}
    const pixels=renderer.wasm.render3D(width,height,this.camera,this._upload,this.meshes.map(mesh=>mesh.stateAt(renderer.time??0)));
    if(!this._canvas)this._canvas=document.createElement('canvas');if(this._canvas.width!==width||this._canvas.height!==height){this._canvas.width=width;this._canvas.height=height;}
    this._canvas.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(pixels),width,height),0,0);
    const ctx=renderer.ctx;ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha*=Math.max(0,Math.min(1,this.opacity));ctx.drawImage(this._canvas,0,0,fullW,fullH);ctx.restore();
  }
}
