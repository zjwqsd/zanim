import assert from 'node:assert/strict'
import {
  Circle,
  Dot,
  Easing,
  Scene,
  Transform2D,
} from './src/zanim.js'

const scene = Scene.headless({ width:1280, height:720, unitSize:90 })
const circle = scene.add(new Circle(1, {
  fill:null,
  transform:Transform2D.affine({ scale:0 }),
}))
const dot = scene.add(new Dot())

circle.affine({ position:[0,0], scale:1, duration:1 })
dot.move([1,0], { duration:1 })
dot.moveAlong(circle, { duration:2, easing:Easing.LINEAR })

const expected = [
  [2.0,  1,  0],
  [2.5,  0,  1],
  [3.0, -1,  0],
  [3.5,  0, -1],
  [4.0,  1,  0],
]
for (const [time,x,y] of expected) {
  const p = scene.worldTransformAt(dot,time).apply(0,0)
  assert.ok(Number.isFinite(p[0]) && Number.isFinite(p[1]))
  assert.ok(Math.abs(p[0]-x) < 3e-3, `x@${time}: ${p[0]}`)
  assert.ok(Math.abs(p[1]-y) < 3e-3, `y@${time}: ${p[1]}`)
}

console.log('moveAlong: finite arc-length circle motion passed')
