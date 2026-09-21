import assert from 'node:assert/strict'
import { Camera3D, Vec3, projectPoint3D } from './src/zanim.js'

const camera=new Camera3D({
  position:new Vec3(0,0,20),
  target:new Vec3(0,0,0),
  up:new Vec3(0,1,0),
  fovYDegrees:2*Math.atan(4/20)*180/Math.PI,
})
const center=projectPoint3D(new Vec3(0,0,0),camera.stateAt(0),1280,720)
assert.ok(Math.abs(center[0]-640)<1e-9)
assert.ok(Math.abs(center[1]-360)<1e-9)
const top=projectPoint3D(new Vec3(0,4,0),camera.stateAt(0),1280,720)
assert.ok(Math.abs(top[1])<1e-9)
const right=projectPoint3D(new Vec3(4,0,0),camera.stateAt(0),1280,720)
assert.ok(Math.abs(right[0]-1000)<1e-9)
console.log('projected 3D vectors: perspective projection passed')
