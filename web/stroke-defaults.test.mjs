import assert from 'node:assert/strict'
import {
  getTheme,
  DynamicLineSet,
  Line,
  CircleSet,
  LineSet,
  RectSet,
  Scene,
  Square,
  Transform2D,
} from './src/zanim.js'

assert.equal(new Line().width, getTheme().style.strokeWidth)
assert.equal(new Line().worldStroke, true)

const staticLines = new LineSet()
const staticCircles = new CircleSet()
const staticRects = new RectSet()
for (const batch of [staticLines, staticCircles, staticRects]) {
  assert.equal(batch.width, getTheme().style.strokeWidth)
  assert.equal(batch.worldStroke, true)
}
const dynamic = new DynamicLineSet(() => [[0,0,1,0,'#ffffff']])
assert.equal(dynamic.width, getTheme().style.strokeWidth)
assert.equal(dynamic.worldStroke, true)

const scene = Scene.headless({ width:1280, height:720, unitSize:90 })
const square = scene.add(new Square(2, { fill:'#58C4DD', stroke:'#58C4DD' }))
const before = scene.stateAt(square, 0).style
scene.style(square, {
  to: { fill:'#FF862F', stroke:'#58C4DD' },
  duration:1,
})
const middle = scene.stateAt(square, .5).style
const after = scene.stateAt(square, 1).style
assert.equal(before.width, getTheme().style.strokeWidth)
assert.equal(middle.width, getTheme().style.strokeWidth)
assert.equal(after.width, getTheme().style.strokeWidth)
assert.equal(after.worldStroke, true)


// Stroke is non-scaling visual style: object/group/camera transforms change
// the centerline geometry, not its thickness. The default logical width is
// converted only by the canvas unit scale. Device-pixel width is an explicit
// escape hatch.
const builtPaths=[];
globalThis.Path2D=class{
  constructor(){this.ops=[];this.added=[];builtPaths.push(this);}
  moveTo(...p){this.ops.push(['moveTo',...p]);}
  lineTo(...p){this.ops.push(['lineTo',...p]);}
  rect(...p){this.ops.push(['rect',...p]);}
  arc(...p){this.ops.push(['arc',...p]);}
  ellipse(...p){this.ops.push(['ellipse',...p]);}
  closePath(){this.ops.push(['closePath']);}
  bezierCurveTo(...p){this.ops.push(['bezierCurveTo',...p]);}
  addPath(path,transform){this.added.push({path,transform});}
};
const drawCalls=[];
const transforms=[];
const assertMatrix=(actual,expected)=>{assert.equal(actual.length,expected.length);for(let i=0;i<expected.length;i++)assert.ok(Math.abs(actual[i]-expected[i])<1e-12,`matrix[${i}] ${actual[i]} != ${expected[i]}`);};
const ctx={
  globalAlpha:1,lineWidth:0,lineCap:'butt',lineJoin:'miter',
  save(){},restore(){},
  setTransform(...args){transforms.push(args);},
  stroke(path){drawCalls.push({path,width:this.lineWidth,transform:transforms.at(-1)});},
  fill(){},setLineDash(){},
};
const renderer={
  canvas:{width:800,height:600},ctx,unitSize:100,dpr:1,time:0,
};
const model=Transform2D.scaling(3);
const worldLine=new Line([0,0],[1,0],{strokeWidth:.04,transform:model});
let view=Transform2D.scaling(2);
worldLine.draw(renderer,view);
const worldDraw=drawCalls.at(-1),worldPath=worldDraw.path;
assert.equal(worldDraw.width,.04);
assertMatrix(worldDraw.transform,[100,0,0,-100,400,300]);
assert.equal(worldPath.added[0].transform.a,6);
assert.equal(worldPath.added[0].transform.d,6);

view=Transform2D.scaling(4);
worldLine.draw(renderer,view);
const zoomedDraw=drawCalls.at(-1),zoomedPath=zoomedDraw.path;
assert.equal(zoomedDraw.width,.04);
assertMatrix(zoomedDraw.transform,[100,0,0,-100,400,300]);
assert.equal(zoomedPath.added[0].transform.a,12);
assert.equal(zoomedPath.added[0].transform.d,12);

view=Transform2D.scaling(2);
const screenLine=new Line([0,0],[1,0],{width:4,transform:model});
screenLine.draw(renderer,view);
const screenDraw=drawCalls.at(-1),screenPath=screenDraw.path;
assert.equal(screenDraw.width,4);
assertMatrix(screenDraw.transform,[1,0,0,1,0,0]);
assert.equal(screenPath.added[0].transform.a,600);
assert.equal(screenPath.added[0].transform.d,-600);

const worldBatch=new LineSet([[0,0,1,0,'#ffffff',.04]],{worldStroke:true,transform:model});
worldBatch.draw(renderer,view);
const batchDraw=drawCalls.at(-1),batchPath=batchDraw.path;
assert.equal(batchDraw.width,.04);
assertMatrix(batchDraw.transform,[100,0,0,-100,400,300]);
assert.equal(batchPath.added[0].transform.a,6);
assert.equal(batchPath.added[0].transform.d,6);

console.log('stroke defaults: non-scaling style, camera invariance and partial animation passed')
