import assert from 'node:assert/strict'
import {Camera3D,Vec3} from './src/zanim.js'

const camera=new Camera3D({
  position:t=>new Vec3(10*Math.cos(t),10*Math.sin(t),3),
  target:new Vec3(),
  up:new Vec3(0,0,1),
})
const base=camera.stateAt(.4).position
camera.orbitBy(.3,-.1).zoomBy(1.25)
const moved=camera.stateAt(.4).position
assert.ok(Math.abs(moved.length-base.length*1.25)<1e-9)
assert.ok(moved.sub(base).length>1)
camera.resetViewOverride()
const reset=camera.stateAt(.4).position
assert.ok(reset.sub(base).length<1e-9)
console.log('Camera3D viewer override: orbit, zoom and reset passed')
