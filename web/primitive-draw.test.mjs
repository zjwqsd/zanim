import assert from 'node:assert/strict';
import {Scene, Square, Circle, Easing} from './src/zanim.js';
const paths=[];
globalThis.Path2D=class{
  constructor(){this.points=[];paths.push(this);}
  moveTo(...p){this.points.push(p);}
  bezierCurveTo(...p){this.points.push(p);}
  closePath(){}
};
const scene=Scene.headless();
const a=scene.add(new Square(1,{fill:'#60a6ff'}));
const b=scene.add(new Circle(.7,{fill:'#ff975c'}));
const transient=scene.interpolate(a,b,{duration:1,easing:Easing.LINEAR});
const ctx={globalAlpha:1,save(){},restore(){},setTransform(){},fill(){},stroke(){}};
const renderer={ctx,canvas:{width:800,height:600},unitSize:100,dpr:1,time:.5};
transient.draw(renderer);
assert.equal(paths[0].points.length,9);
assert.ok(paths[0].points.flat().every(Number.isFinite));
renderer.time=.8;transient.draw(renderer);
renderer.time=.5;transient.draw(renderer);
assert.deepEqual(paths[0].points,paths[2].points);
console.log('Primitive interpolation: actual draw and reverse sampling passed');
