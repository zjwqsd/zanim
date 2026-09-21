import assert from 'node:assert/strict'
import { SceneViewport, Transform2D } from './src/zanim.js'

const v = new SceneViewport({
  sourceCenter:[1,2],
  sourceSize:[1.8,.3],
  width:6,
  height:1,
  transform:Transform2D.translation(2,1),
})
const b=v.bounds()
assert.ok(Math.abs(b.width-6)<1e-12)
assert.ok(Math.abs(b.height-1)<1e-12)
assert.equal(typeof v.sourceCenter,'object')

const d=new SceneViewport({
  sourceCenter:t=>[t,0],
  sourceSize:t=>[1+t,.5],
})
assert.deepEqual(d._value(d.sourceCenter,2),[2,0])
assert.deepEqual(d._value(d.sourceSize,2),[3,.5])
console.log('SceneViewport: bounds and dynamic source providers passed')
