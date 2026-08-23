import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {
  Circle, Cube3D, DynamicPolyline, FourierEpicycles, FunctionPlot, LineSet,
  Math as TypstMath, Mat2, Polyline, Scene, Square, TIME, Transform2D,
  Transform3D, Vec3, ZObject, ZanimWasm, resamplePolylineByArcLength,
} from './src/zanim.js';
import { parseSceneIR, sceneFromIR, sceneToIR, stringifySceneIR } from './src/ir.js';

const bytes=await fs.readFile(new URL('./dist/zanim_web_core.wasm',import.meta.url));
const {instance}=await WebAssembly.instantiate(bytes,{});
const wasm=new ZanimWasm(instance);
assert.equal(wasm.determinant(Mat2.identity()),1);
assert.equal(wasm.resolveGrid(1280,720,100,.5,Mat2.identity()).length/4,40);
assert.equal(wasm.resolveGrid(1280,720,100,.5,new Mat2(1,.65,0,0)).length/4,1);
assert.equal(wasm.exports.zanim_web_render_fractal(1,64,36,-.5,0,3.2/64,80,0,0,0,1,5,7,14,105,185,255),64*36);
assert.equal(wasm.exports.zanim_web_render_complex_grid(1,64,36,0,0,5/64,.5,.5,1,.9,0,0,0,0,0,0,0,0),64*36);

const t=Transform2D.affine({position:[2,-3],rotation:.7,scale:[2,.5],shear:[.2,-.1]});
const p=[1.25,-4.5],q=t.inverse().apply(...t.apply(...p));
assert.ok(Math.abs(q[0]-p[0])<1e-10&&Math.abs(q[1]-p[1])<1e-10);
assert.deepEqual(resamplePolylineByArcLength([[0,0],[1,0],[1,2],[4,2]],6),[[0,0],[1,0],[1,1],[1,2],[2,2],[3,2],[4,2]]);

const scene=new Scene({});
const source=scene.add(new Polyline([[0,0],[1,0]],{trim:0}));
scene.create(source,{duration:.4});scene.wait(.2);
const target=new Polyline([[0,0],[.5,1],[1,0]]);const handoff=scene.cursor;
scene.replace(source,target,{duration:.8});
assert.equal(source.death,handoff);assert.equal(target.birth,handoff+.8);

const batchScene=new Scene({});
const lines=batchScene.add(new LineSet([[0,0,1,0,'#60a6ff',.02]],{worldStroke:true}));
batchScene.batch(lines,{to:[[1,2,3,4,'#52cd96',.06]],duration:2});
assert.deepEqual(batchScene.batchAt(lines,1)[0].slice(0,4),[.5,1,2,2]);

const mediaScene=Scene.headless();
const media=new ZObject();media._mediaKind='video';media.duration=2;mediaScene.add(media);
mediaScene.media(media,{duration:4,sourceStart:.25,speed:1.5,loop:true,sourceDuration:2});
assert.ok(Math.abs(mediaScene.mediaTimeAt(media,1)-1.75)<1e-12);

const fakeVector={width:1,height:.5,group_count:0,paths:[]};
const webMath=new TypstMath('x^2',{compiler:async()=>fakeVector});
await webMath.ready;assert.equal(webMath.document.width,1);
const webMathScene=Scene.headless();webMathScene.add(webMath);
assert.throws(()=>sceneToIR(webMathScene),/runtime code|portable/);

const irScene=Scene.headless({width:640,height:360,unitSize:80,fps:60});
const irSquare=irScene.add(new Square(1,{fill:'#60a6ff',stroke:null,trim:0,transform:Transform2D.translation(-1,0)}));
irScene.create(irSquare,{duration:.5});irScene.animate(irSquare,{transform:Transform2D.translation(2,.5),duration:1,at:.5});irScene.wait(.2);
const portable=sceneToIR(irScene),parsed=parseSceneIR(stringifySceneIR(portable));
assert.equal(parsed.duration,2.2);assert.equal(parsed.objects.length,2);assert.equal(parsed.clips.length,2);

const semantic=Scene.headless({width:640,height:360,unitSize:80,fps:60});
semantic.add(new FunctionPlot(TIME.sin(),{samples:41}));
semantic.add(new FourierEpicycles([[0,.2,-.1],[1,1.1,.25]],{drawDuration:1.4}));semantic.wait(2);
const semanticIR=sceneToIR(semantic);
assert.equal(semanticIR.objects.filter(o=>o.kind==='function_plot').length,1);
assert.equal(semanticIR.objects.filter(o=>o.kind==='fourier_epicycles').length,1);

const dynamic=Scene.headless({width:320,height:180,unitSize:40,fps:20});
dynamic.add(new DynamicPolyline(time=>[[0,0],[1+time,time]],{stroke:'#5fdaff'}));dynamic.wait(1);
assert.throws(()=>sceneToIR(dynamic),/sampleDynamicProviders/);
assert.equal(sceneToIR(dynamic,{sampleDynamicProviders:true}).meta.sampled_dynamic_objects,1);

const callback=Scene.headless({width:320,height:180,unitSize:40,fps:60});
const callbackSquare=callback.add(new Square(1));
callback.transformFunction(callbackSquare,a=>Transform2D.translation(a,0).mul(Transform2D.rotation(.75*a)),{duration:1});
assert.throws(()=>sceneToIR(callback),/sampleTransformFunctions/);
assert.equal(sceneToIR(callback,{sampleTransformFunctions:true}).clips.find(c=>c.kind==='sampled_transform').samples.length,61);

const fakeCtx={save(){},restore(){},setTransform(){},stroke(){},fill(){},beginPath(){},moveTo(){},lineTo(){},rect(){},arc(){},ellipse(){},translate(){},transform(){},fillText(){},setLineDash(){},globalAlpha:1};
globalThis.Path2D??=class{moveTo(){}lineTo(){}rect(){}arc(){}closePath(){}bezierCurveTo(){}};
const fakeRenderer={canvas:{width:640,height:360},ctx:fakeCtx,baseUnitSize:80,unitSize:80,dpr:1,resize(){},clear(){},time:0,toDevice(x,y){return[x,y]}};
const roundtrip=sceneFromIR(parsed,fakeRenderer),roundtripSquare=roundtrip.objects.find(o=>o instanceof Square);
assert.ok(Math.abs(roundtrip.stateAt(roundtripSquare,1.5).transform.tx-.5)<1e-12);

const cube=Cube3D(2,{transform:Transform3D.translation(1,0,0).mul(Transform3D.rotationY(Math.PI/3))});
assert.equal(cube.mesh.vertexCount,24);assert.equal(cube.mesh.indexCount,36);
assert.ok(Math.abs(cube.transform.apply(new Vec3()).x-1)<1e-12);
const upload=wasm.upload3DGeometry([cube.mesh]);
const pixels=wasm.render3D(160,90,{position:new Vec3(4,3,5),target:new Vec3(),up:new Vec3(0,1,0),fovYDegrees:45,near:.05,far:100,orthographicHeight:null},upload,[cube.stateAt(0)]);
assert.equal(pixels.length,160*90*4);assert.ok(pixels.some((v,i)=>i%4===3&&v>0));

console.log('zanim-web smoke test: ok');
