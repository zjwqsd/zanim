import assert from 'node:assert/strict'
import {
  DEFAULT_STROKE_WIDTH,
  DynamicLineSet,
  Line,
  Scene,
  Square,
} from './src/zanim.js'

assert.equal(new Line().width, DEFAULT_STROKE_WIDTH)
assert.equal(new Line().worldStroke, true)

const dynamic = new DynamicLineSet(() => [[0,0,1,0,'#ffffff']])
assert.equal(dynamic.width, DEFAULT_STROKE_WIDTH)
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
assert.equal(before.width, DEFAULT_STROKE_WIDTH)
assert.equal(middle.width, DEFAULT_STROKE_WIDTH)
assert.equal(after.width, DEFAULT_STROKE_WIDTH)
assert.equal(after.worldStroke, true)

console.log('stroke defaults: static, dynamic and partial style animation passed')
