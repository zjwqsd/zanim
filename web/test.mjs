import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { Circle, LineSet, Mat2, Polyline, Scene, Square, Transform2D, ZanimWasm, resamplePolylineByArcLength } from './src/zanim.js';
import { allDemos, demoMeta, parityDemos, prototypeDemos } from './gallery/registry.js';

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
assert.deepEqual(Object.keys(allDemos).sort(), expected, 'Web gallery must track every Python demo');
assert.equal(expected.length, 29);

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

// Bounds-aware Row layout must reproduce the Python reference coordinates exactly.
const layoutFixtureRenderer={canvas:{width:1280,height:720},unitSize:90,resize(){}};
const layoutScene=allDemos['showcase/layout'](layoutFixtureRenderer),layoutGroup=layoutScene.objects.find(o=>o.children?.length===4);
const initialLayout=layoutGroup.children.map(o=>{const tr=layoutScene.initial.get(o.id).transform;return[tr.tx,tr.ty]});
const expectedLayout=[[-2.938897274573418,-.3999999999999999],[-1.138897274573418,-.3999999999999999],[.7500000000000004,-.5699999999999998],[2.7638972745734183,-.3999999999999999]];
for(let i=0;i<4;i++)for(let j=0;j<2;j++)assert.ok(Math.abs(initialLayout[i][j]-expectedLayout[i][j])<1e-9,`layout parity ${i},${j}`);
assert.equal(prototypeDemos.size, 7);
const parityNames=Object.keys(allDemos).filter(name=>demoMeta[name].status==='parity');
const nativeNames=Object.keys(allDemos).filter(name=>demoMeta[name].status==='native');
assert.equal(parityDemos.size,16);assert.equal(parityNames.length,16);assert.equal(nativeNames.length,6);
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
console.log(`zanim-web smoke test: ok (${parityNames.length} parity, ${nativeNames.length} native, ${prototypeDemos.size} deferred prototypes)`);
const complexCount = wasm.exports.zanim_web_render_complex_grid(1, 64, 36, 0, 0, 5/64, .5, .5, 1, .9, 0,0,0,0,0,0,0,0);
assert.equal(complexCount, 64*36);
const complexPtr = wasm.exports.zanim_web_fractal_data_ptr();
const complexBytes = new Uint8Array(wasm.exports.memory.buffer, complexPtr, complexCount*4);
assert.ok(complexBytes.some((v,i)=>i%4===3 && v>0), 'complex grid should produce visible alpha');
