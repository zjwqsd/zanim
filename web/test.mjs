import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { Circle, DynamicPolyline, FourierEpicycles, FunctionPlot, LineSet, Math as TypstMath, Mat2, Polyline, Scene, Square, TIME, Transform2D, X, ZObject, ZanimWasm, resamplePolylineByArcLength } from './src/zanim.js';
import { allDemos, galleryEntries, galleryCounts, irReplayDemos, parityDemos, prototypeDemos } from './gallery/registry.js';
import { parseSceneIR, sceneFromIR, sceneToIR, stringifySceneIR } from './src/ir.js';

const bytes = await fs.readFile(new URL('./dist/zanim_web_core.wasm', import.meta.url));
const { instance } = await WebAssembly.instantiate(bytes, {});
const wasm = new ZanimWasm(instance);
assert.equal(wasm.determinant(Mat2.identity()), 1);
assert.equal(wasm.resolveGrid(1280, 720, 100, 0.5, Mat2.identity()).length / 4, 40);
assert.equal(wasm.resolveGrid(1280, 720, 100, 0.5, new Mat2(1, 0.65, 0, 0)).length / 4, 1);
assert.ok(wasm.resolveGrid(1280, 720, 100, 0.5, Mat2.shear(1.15)).length > 40);
const t = Transform2D.affine({position:[2,-3],rotation:.7,scale:[2,.5],shear:[.2,-.1]});
const p0=[1.25,-4.5],p1=t.apply(...p0),p2=t.inverse().apply(...p1);
assert.ok(Math.abs(p2[0]-p0[0])<1e-10 && Math.abs(p2[1]-p0[1])<1e-10, 'Transform2D inverse round-trip');
const fractalCount = wasm.exports.zanim_web_render_fractal(1, 64, 36, -0.5, 0, 3.2/64, 80, 0, 0, 0, 1, 5, 7, 14, 105, 185, 255);
assert.equal(fractalCount, 64*36);

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const expected=[];
for (const category of ['showcase','extras','janim_api']) {
  for (const file of await fs.readdir(path.join(root,'examples',category))) {
    if (file.endsWith('.py') && file !== '__init__.py') expected.push(`${category}/${file.slice(0,-3)}`);
  }
}
expected.sort();
assert.deepEqual(Object.keys(galleryEntries).sort(), expected, 'Web gallery must track every Python demo');
assert.equal(expected.length, 29);
assert.equal(galleryCounts.total,29);assert.equal(galleryCounts.ts,27);assert.equal(galleryCounts.ir,2);
assert.deepEqual([...irReplayDemos.keys()].sort(),['showcase/basics','showcase/vectors']);
for(const url of irReplayDemos.values()){const file=new URL(`./gallery/${url.replace('./','')}`,import.meta.url);assert.ok((await fs.stat(file)).size>1000,`${url} must be a generated Scene IR asset`);}

// Python/Zig parity fixture: Python's resample_polyline_by_arclength(..., 7)
// and Zig interpolation's six-segment normalization produce these same points.
const arc = resamplePolylineByArcLength([[0,0],[1,0],[1,2],[4,2]], 6);
assert.deepEqual(arc, [[0,0],[1,0],[1,1],[1,2],[2,2],[3,2],[4,2]]);

// replace() is a lifetime handoff, not a mutation/crossfade of the endpoints.
const dummyScene = new Scene({});
const source = dummyScene.add(new Polyline([[0,0],[1,0]], { trim: 0 }));
dummyScene.create(source, { duration: 0.4 });
dummyScene.wait(0.2);
const target = new Polyline([[0,0],[0.5,1],[1,0]]);
const replaceStart = dummyScene.cursor;
dummyScene.replace(source, target, { duration: 0.8 });
assert.equal(source.death, replaceStart);
assert.equal(target.birth, replaceStart + 0.8);
assert.equal(dummyScene.cursor, replaceStart + 0.8);
assert.equal(dummyScene.stateAt(source, 0.2).reveal, 0.5);

// Primitive interpolation is a transient normalized cubic morph, not endpoint mutation.
const primitiveScene=new Scene({});
const circle=primitiveScene.add(new Circle(1,{fill:'#60a6ff'}));
const square=primitiveScene.add(new Square(2,{fill:'#52cd96'}));
const circleBefore=circle.transform,squareBefore=square.transform;
const transient=primitiveScene.interpolate(circle,square,{duration:1.25});
assert.equal(transient.birth,0);assert.equal(transient.death,1.25);assert.equal(circle.transform,circleBefore);assert.equal(square.transform,squareBefore);

// Batch clips reconstruct an absolute state rather than accumulating frame history.
const batchScene=new Scene({});
const lines=batchScene.add(new LineSet([[0,0,1,0,'#60a6ff',.02]],{worldStroke:true}));
batchScene.batch(lines,{to:[[1,2,3,4,'#52cd96',.06]],duration:2});
const midBatch=batchScene.batchAt(lines,1)[0];
assert.deepEqual(midBatch.slice(0,4),[.5,1,2,2]);assert.ok(Math.abs(midBatch[5]-.04)<1e-12);


// Web-only media has its own playback channel and Web Typst can use any async compiler.
const mediaScene=Scene.headless();
const mediaObject=new ZObject();mediaObject._mediaKind='video';mediaObject.duration=2;mediaScene.add(mediaObject);
mediaScene.media(mediaObject,{duration:4,sourceStart:.25,speed:1.5,loop:true,sourceDuration:2});
assert.ok(Math.abs(mediaScene.mediaTimeAt(mediaObject,1)-1.75)<1e-12);
assert.ok(Math.abs(mediaScene.mediaTimeAt(mediaObject,2)-1.5)<1e-12);
const fakeVector={width:1,height:.5,group_count:0,paths:[]};
const webMath=new TypstMath('x^2',{compiler:async()=>fakeVector});
await webMath.ready;assert.equal(webMath.document.width,1);const webMathScene=Scene.headless();webMathScene.add(webMath);assert.throws(()=>sceneToIR(webMathScene),/runtime code|portable/);

// Scene IR is a semantic authoring document, not a frame dump.
const irScene=Scene.headless({width:640,height:360,unitSize:80,fps:60});
const irSquare=irScene.add(new Square(1,{fill:'#60a6ff',stroke:null,trim:0,transform:Transform2D.translation(-1,0)}));
irScene.create(irSquare,{duration:.5});
irScene.animate(irSquare,{transform:Transform2D.translation(2,.5),duration:1,at:.5});
irScene.wait(.2);
const portable=sceneToIR(irScene),parsed=parseSceneIR(stringifySceneIR(portable));
assert.equal(parsed.format,'zanim.scene');assert.equal(parsed.version,1);assert.equal(parsed.duration,2.2);assert.equal(parsed.objects.length,2);assert.equal(parsed.resources.length,0);assert.equal(parsed.clips.length,2);
assert.deepEqual(parsed.objects.find(o=>o.kind==='object2d').state.geometry,{kind:'square',side:1});
const semanticScene=Scene.headless({width:640,height:360,unitSize:80,fps:60});
const expr=X.mul(1.25).add(TIME.mul(.8)).sin().mul(.5).add(X.mul(X).mul(.055)).add(1.2);
const functionPlot=semanticScene.add(new FunctionPlot(expr,{xRange:[-3.5,3.5],axesXRange:[-4,4],axesYRange:[-2,3],width:8,height:5,center:[.5,-.25],samples:81,stroke:'#5fdaff',worldStroke:true}));
semanticScene.add(new FourierEpicycles([[0,.2,-.1],[1,1.1,.25],[-2,-.15,.35]],{startTime:.2,drawDuration:1.4,traceSamples:80}));semanticScene.wait(2);
const semanticIR=sceneToIR(semanticScene);
assert.equal(semanticIR.objects.filter(o=>o.kind==='function_plot').length,1);assert.equal(semanticIR.objects.filter(o=>o.kind==='fourier_epicycles').length,1);
assert.deepEqual(semanticIR.objects.find(o=>o.kind==='function_plot').state.expression,expr.toData());
const centerPoint=functionPlot.pointsAt(.75)[40];assert.ok(Math.abs(centerPoint[0]-.5)<1e-12);assert.ok(Math.abs(centerPoint[1]-(.45+.5*Math.sin(.6)))<1e-12); // portable expression evaluates without callbacks
const dynamicExportScene=Scene.headless({width:320,height:180,unitSize:40,fps:20});
const dynamicExport=dynamicExportScene.add(new DynamicPolyline(time=>[[0,0],[1+time,time]],{stroke:'#5fdaff'}));dynamicExportScene.wait(1);
assert.throws(()=>sceneToIR(dynamicExportScene),/sampleDynamicProviders/);
const dynamicExportIR=sceneToIR(dynamicExportScene,{sampleDynamicProviders:true});
assert.equal(dynamicExportIR.objects.find(o=>o.kind==='sampled_object2d').state.samples.length,21);assert.equal(dynamicExportIR.meta.sampled_dynamic_objects,1);
const callbackScene=Scene.headless({width:320,height:180,unitSize:40,fps:60});
const callbackSquare=callbackScene.add(new Square(1));
callbackScene.transformFunction(callbackSquare,a=>Transform2D.translation(a,0).mul(Transform2D.rotation(.75*a)),{duration:1});
assert.throws(()=>sceneToIR(callbackScene),/sampleTransformFunctions/);
const bakedCallback=sceneToIR(callbackScene,{sampleTransformFunctions:true});
const bakedTrack=bakedCallback.clips.find(c=>c.kind==='sampled_transform');
assert.equal(bakedTrack.samples.length,61);assert.equal(bakedTrack.sample_rate,60);

// Python runtime providers arrive as sampled absolute-time objects. The Web
// loader must reconstruct them without any Native frame transport.
const sampledIR={format:'zanim.scene',version:1,canvas:{width:320,height:180,unit_size:40},fps:20,duration:1,resources:[],values:[],clips:[],meta:{portable:true},objects:[
  {id:0,parent:null,birth:0,death:null,kind:'camera2d',state:{transform:[1,0,0,1,0,0],opacity:1,z_index:0}},
  {id:1,parent:null,birth:0,death:null,kind:'sampled_batch2d',state:{sample_rate:20,sample_start:0,sample_offsets:[0,.5,1],samples:[
    {kind:'lines',starts:[[0,0]],ends:[[1,0]],colors:[[255,255,255,255]],widths:[.02]},
    {kind:'lines',starts:[[0,0]],ends:[[2,0]],colors:[[255,255,255,255]],widths:[.02]},
    {kind:'lines',starts:[[0,0]],ends:[[3,0]],colors:[[255,255,255,255]],widths:[.02]}
  ],transform:[1,0,0,1,0,0],opacity:1,z_index:0}}
]};
globalThis.Path2D ??= class { moveTo(){} lineTo(){} rect(){} arc(){} closePath(){} bezierCurveTo(){} };
const noop=()=>{},fakeCtx={save:noop,restore:noop,setTransform:noop,stroke:noop,fill:noop,beginPath:noop,moveTo:noop,lineTo:noop,rect:noop,arc:noop,ellipse:noop,translate:noop,transform:noop,fillText:noop,setLineDash:noop,globalAlpha:1};
const fakeRenderer={canvas:{width:320,height:180},ctx:fakeCtx,baseUnitSize:40,unitSize:40,dpr:1,resize(){},clear(){},time:0,toDevice(x,y){return[x,y]}};
const sampledScene=sceneFromIR(sampledIR,fakeRenderer);
const sampledBatch=sampledScene.objects[0];
assert.deepEqual(sampledBatch.provider(.75)[0].slice(0,4),[0,0,2,0],'sampled tracks hold the exact preceding video frame between samples');
const roundtripScene=sceneFromIR(parsed,fakeRenderer),roundtripSquare=roundtripScene.objects.find(o=>o instanceof Square);
const roundtripMid=roundtripScene.stateAt(roundtripSquare,1.5).transform;
assert.ok(Math.abs(roundtripMid.tx-.5)<1e-12&&Math.abs(roundtripMid.ty-.25)<1e-12,'IR absolute clip starts survive relative-at authoring semantics');

// Bounds-aware Row layout must reproduce the Python reference coordinates exactly.
const layoutFixtureRenderer={canvas:{width:1280,height:720},unitSize:90,resize(){}};
const layoutScene=allDemos['showcase/layout'](layoutFixtureRenderer),layoutGroup=layoutScene.objects.find(o=>o.children?.length===4);
const initialLayout=layoutGroup.children.map(o=>{const tr=layoutScene.initial.get(o.id).transform;return[tr.tx,tr.ty]});
const expectedLayout=[[-2.938897274573418,-.3999999999999999],[-1.138897274573418,-.3999999999999999],[.7500000000000004,-.5699999999999998],[2.7638972745734183,-.3999999999999999]];
for(let i=0;i<4;i++)for(let j=0;j<2;j++)assert.ok(Math.abs(initialLayout[i][j]-expectedLayout[i][j])<1e-9,`layout parity ${i},${j}`);
assert.equal(prototypeDemos.size, 6);
const parityNames=Object.keys(galleryEntries).filter(name=>galleryEntries[name].mode==='ts'&&galleryEntries[name].status==='parity');
const nativeNames=Object.keys(galleryEntries).filter(name=>galleryEntries[name].mode==='ts'&&galleryEntries[name].status==='native');
assert.equal(parityDemos.size,16);assert.equal(parityNames.length,16);assert.equal(nativeNames.length,5);
for(const name of [...parityNames,...nativeNames]) assert.ok(!String(allDemos[name]).includes('CustomObject2D'), `${name} must use public Web primitives`);
const parityDurations={
  'showcase/batches':5.0,
  'showcase/infinite_space':19.8,
  'showcase/kinematics':7.1,
  'showcase/layout':7.75,
  'showcase/state_model':5.2,
  'showcase/timeline':4.95,
  'showcase/transforms':5.5,
  'extras/complex_mapping':17.82,
  'extras/de_casteljau':8.85,
  'extras/fractals':43.57,
  'extras/hilbert_curve':10.67,
  'extras/mandelbrot_julia':11.75,
  'extras/modular_multiplication':19.75,
  'extras/neural_network':5.76,
  'extras/red_black_tree':33.0,
  'extras/sorting_algorithms':111.015,
};
assert.deepEqual(Object.keys(parityDurations).sort(),parityNames.sort(),'every PARITY demo needs a Python duration fixture');
const parityRenderer={canvas:{width:1280,height:720},unitSize:90,resize(){}};
for(const [name,expectedDuration] of Object.entries(parityDurations)){
  const scene=allDemos[name](parityRenderer);
  assert.ok(Math.abs(scene.duration-expectedDuration)<1e-9,`${name} duration ${scene.duration} != Python ${expectedDuration}`);
}
for(const [name,duration] of Object.entries({'extras/fourier_draw':7.2,'extras/midi_piano':17.897630714285715,'extras/mnist_training':52.5})){const scene=allDemos[name](parityRenderer);assert.ok(Math.abs(scene.duration-duration)<1e-9,`${name} must match Python duration`);}
console.log(`zanim-web smoke test: ok (${galleryCounts.ts} TS replicas + ${galleryCounts.ir} IR replays = ${galleryCounts.total} demos)`);
const complexCount = wasm.exports.zanim_web_render_complex_grid(1, 64, 36, 0, 0, 5/64, .5, .5, 1, .9, 0,0,0,0,0,0,0,0);
assert.equal(complexCount, 64*36);
const complexPtr = wasm.exports.zanim_web_fractal_data_ptr();
const complexBytes = new Uint8Array(wasm.exports.memory.buffer, complexPtr, complexCount*4);
assert.ok(complexBytes.some((v,i)=>i%4===3 && v>0), 'complex grid should produce visible alpha');
