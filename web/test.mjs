import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {
  Circle, Cube3D, DynamicLineSet, DynamicPolyline, DynamicVectorObject2D, FourierEpicycles, FunctionPlot, LineSet,
  Math as TypstMath, Mat2, PARENT, Polyline, ScalarValue, Scene, Square, TIME, Transform2D,
  Transform3D, Vec3, ZObject, ZanimWasm, prepareVectorMorph, resamplePolylineByArcLength,
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

const ownership=Scene.headless();
const owned=ownership.add(new Square(1));
const rawOwned=owned.transform;
owned.move([2,1],{frame:PARENT,duration:1});
assert.equal(owned.transform,rawOwned);
assert.equal(ownership.authoredState(owned).transform.tx,2);
assert.equal(ownership.authoredState(owned).transform.ty,1);
const ownedValue=ownership.addValue(new ScalarValue(1));
ownership.animateValue(ownedValue,{to:5,duration:1});
assert.equal(ownedValue.value,1);
assert.equal(ownership.authoredValue(ownedValue),5);

const batchScene=new Scene({});
const lines=batchScene.add(new LineSet([[0,0,1,0,'#60a6ff',.02]],{worldStroke:true}));
batchScene.batch(lines,{to:[[1,2,3,4,'#52cd96',.06]],duration:2});
assert.deepEqual(batchScene.batchAt(lines,1)[0].slice(0,4),[.5,1,2,2]);

const mediaScene=Scene.headless();
const media=new ZObject();media._mediaKind='video';media.duration=2;mediaScene.add(media);
mediaScene.media(media,{duration:4,sourceStart:.25,speed:1.5,loop:true,sourceDuration:2});
assert.ok(Math.abs(mediaScene.mediaTimeAt(media,1)-1.75)<1e-12);

// Bitmap media must compensate the world-space Y-up transform explicitly.
// Negative drawImage destination heights do not mirror image pixels.
const {MediaObject2D}=await import('./src/media.js');
const mediaCalls=[];
const mediaCtx={
  globalAlpha:1, save(){}, restore(){},
  setTransform(...args){mediaCalls.push(['setTransform',...args]);},
  scale(...args){mediaCalls.push(['scale',...args]);},
  drawImage(...args){mediaCalls.push(['drawImage',...args]);},
};
const mediaRenderer={canvas:{width:640,height:360},ctx:mediaCtx,unitSize:80};
const bitmap=new MediaObject2D('test.png',{width:2,height:1});
const element={tag:'bitmap'};
bitmap._drawElement(mediaRenderer,Transform2D.identity(),element);
assert.deepEqual(mediaCalls.find(call=>call[0]==='scale'),['scale',1,-1]);
assert.deepEqual(mediaCalls.find(call=>call[0]==='drawImage'),['drawImage',element,-1,-.5,2,1]);

// A child Scene remains a live full-resolution surface when embedded.
const {SceneRasterObject2D}=await import('./src/compositing.js');
const childCanvas={width:1600,height:900};
const sampledTimes=[];
const childScene={renderer:{canvas:childCanvas},duration:2,stats:{frames:1},seek(time){sampledTimes.push(time);this.time=time;return this;},destroy(){this.destroyed=true;}};
const nested=new SceneRasterObject2D(childScene,{width:8,sourceTime:1.25});
const nestedCalls=[];
const nestedCtx={globalAlpha:1,save(){},restore(){},setTransform(){},scale(...args){nestedCalls.push(['scale',...args]);},drawImage(...args){nestedCalls.push(['drawImage',...args]);}};
const nestedRenderer={canvas:{width:640,height:360},ctx:nestedCtx,unitSize:40,dpr:1,time:.5};
nested.draw(nestedRenderer,Transform2D.identity());
assert.deepEqual(sampledTimes,[1.25]);
assert.equal(nested.height,4.5);
assert.deepEqual(nestedCalls.find(call=>call[0]==='scale'),['scale',1,-1]);
assert.deepEqual(nestedCalls.find(call=>call[0]==='drawImage'),['drawImage',childCanvas,-4,-2.25,8,4.5]);

const morphDocA={width:1,height:1,group_count:1,paths:[{group:0,fill:'#ffffff',stroke:null,contours:[{closed:true,segments:[[[0,0],[0,0],[1,0],[1,0]],[[1,0],[1,0],[1,1],[1,1]],[[1,1],[1,1],[0,1],[0,1]],[[0,1],[0,1],[0,0],[0,0]]]}]}]};
const morphDocB={width:2,height:1,group_count:2,paths:[{group:0,fill:'#58b9f2',stroke:null,contours:[{closed:true,segments:[[[1,0],[1,0],[2,0],[2,0]],[[2,0],[2,0],[2,1],[2,1]],[[2,1],[2,1],[1,1],[1,1]],[[1,1],[1,1],[1,0],[1,0]]]}]},{group:1,fill:'#ffd166',stroke:null,contours:[{closed:true,segments:[[[3,0],[3,0],[4,0],[4,0]],[[4,0],[4,0],[4,1],[4,1]],[[4,1],[4,1],[3,1],[3,1]],[[3,1],[3,1],[3,0],[3,0]]]}]}]};
const morphPlan=prepareVectorMorph(morphDocA,morphDocB),morphMid=morphPlan.sample(.5);
assert.equal(morphPlan.matched.length,1);assert.equal(morphPlan.targetOnly.length,1);assert.equal(morphMid.group_count,2);assert.ok(Math.abs(morphMid.width-1.5)<1e-12);
const dynamicVector=new DynamicVectorObject2D(time=>morphPlan.sample(time));assert.equal(dynamicVector.document,morphDocA);

const fakeVector={width:1,height:.5,group_count:0,paths:[]};
const webMath=new TypstMath('x^2',{compiler:async()=>fakeVector,tint:'#123456'});
await webMath.ready;assert.equal(webMath.document.width,1);assert.equal(webMath.tint,'#123456');
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
let pathBuildCount=0;
globalThis.Path2D??=class{constructor(){pathBuildCount++;}moveTo(){}lineTo(){}rect(){}arc(){}closePath(){}bezierCurveTo(){}};
const fakeRenderer={canvas:{width:640,height:360},ctx:fakeCtx,baseUnitSize:80,unitSize:80,dpr:1,resize(){},clear(){},time:0,toDevice(x,y){return[x,y]}};
const roundtrip=sceneFromIR(parsed,fakeRenderer),roundtripSquare=roundtrip.objects.find(o=>o instanceof Square);
assert.ok(Math.abs(roundtrip.stateAt(roundtripSquare,1.5).transform.tx-.5)<1e-12);
const retainedBatchScene=new Scene(fakeRenderer);
const retainedLines=retainedBatchScene.add(new LineSet([[0,0,1,0,'#60a6ff',1]]));
retainedBatchScene.render();
const retainedBuilds=pathBuildCount;
retainedBatchScene.render();
assert.equal(pathBuildCount,retainedBuilds,'retained LineSet cache should survive repeated renders');

const stableDynamicItems=[[0,0,1,0,'#60a6ff',1]];
const stableDynamicScene=new Scene(fakeRenderer);
const stableDynamic=stableDynamicScene.add(new DynamicLineSet(()=>stableDynamicItems));
stableDynamicScene.render();
const dynamicBuilds=pathBuildCount;
stableDynamicScene.render();
assert.equal(pathBuildCount,dynamicBuilds,'DynamicLineSet should reuse cache when provider returns the same array');

const renderOwnership=new Scene(fakeRenderer);
const renderOwned=renderOwnership.add(new Square(1));
const renderRaw=renderOwned.transform;
renderOwned.move([2,0],{frame:PARENT,duration:1});
renderOwnership.seek(.5);
assert.equal(renderOwned.transform,renderRaw);
assert.ok(Math.abs(renderOwnership.stateAt(renderOwned,.5).transform.tx-1)<1e-12);

const cube=Cube3D(2,{transform:Transform3D.translation(1,0,0).mul(Transform3D.rotationY(Math.PI/3))});
assert.equal(cube.mesh.vertexCount,24);assert.equal(cube.mesh.indexCount,36);
assert.ok(Math.abs(cube.transform.apply(new Vec3()).x-1)<1e-12);
const upload=wasm.upload3DGeometry([cube.mesh]);
const pixels=wasm.render3D(160,90,{position:new Vec3(4,3,5),target:new Vec3(),up:new Vec3(0,1,0),fovYDegrees:45,near:.05,far:100,orthographicHeight:null},upload,[cube.stateAt(0)]);
assert.equal(pixels.length,160*90*4);assert.ok(pixels.some((v,i)=>i%4===3&&v>0));

console.log('zanim-web smoke test: ok');
