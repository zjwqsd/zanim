import assert from 'node:assert/strict';
import { Scene, Square, Group, Transform2D, LOCAL, PARENT, WORLD, Easing } from './src/zanim.js';

const near = (a,b) => assert.ok(Math.abs(a-b)<1e-9, `${a} != ${b}`);
for (const frame of [LOCAL,PARENT,WORLD]) {
  const scene=Scene.headless();
  const square=scene.add(new Square(1).shift(2,0));
  scene.rotate(square,2*Math.PI,{frame,duration:2,easing:Easing.LINEAR});
  for (const t of [1,.5,2,0,.5]) {
    const m=scene.stateAt(square,t).transform;
    near(Math.hypot(m.xx,m.yx),1);
    near(m.xx,Math.cos(Math.PI*t));
    near(m.yx,Math.sin(Math.PI*t));
    near(m.tx,frame===LOCAL?2:2*Math.cos(Math.PI*t));
    near(m.ty,frame===LOCAL?0:2*Math.sin(Math.PI*t));
  }
  near(square.transform.tx,2);
}
const scene=Scene.headless();
const child=new Square(1).shift(1,0);
scene.add(new Group([child]).shift(3,0));
scene.rotate(child,Math.PI,{about:[3,0],duration:1,easing:Easing.LINEAR});
const midpoint=scene.worldTransformAt(child,.5);
near(midpoint.tx,3);
near(midpoint.ty,1);
near(Math.hypot(midpoint.xx,midpoint.yx),1);
console.log('Rotation: length, full turn, LOCAL/PARENT/WORLD, nested pivot and reverse seek passed');
