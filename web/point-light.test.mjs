import assert from 'node:assert/strict'
import fs from 'node:fs'
import {
  Camera3D,
  MeshObject3D,
  Transform3D,
  TriangleMesh,
  Vec3,
  ZanimWasm,
} from './src/zanim.js'

const bytes=fs.readFileSync(new URL('./dist/zanim_web_core.wasm',import.meta.url))
const {instance}=await WebAssembly.instantiate(bytes,{})
const wasm=new ZanimWasm(instance)

const mesh=new TriangleMesh(
  [
    new Vec3(-1,-1,0),
    new Vec3(1,-1,0),
    new Vec3(0,1,0),
  ],
  [
    new Vec3(0,0,1),
    new Vec3(0,0,1),
    new Vec3(0,0,1),
  ],
  [0,1,2],
)
const object=new MeshObject3D(mesh,{color:'#ffffff',transform:Transform3D.identity()})
const upload=wasm.upload3DGeometry([mesh])
const camera=new Camera3D({
  position:new Vec3(0,0,5),
  target:new Vec3(0,0,0),
  up:new Vec3(0,1,0),
  fovYDegrees:45,
}).stateAt(0)

function brightness(pixels){
  let sum=0
  for(let i=0;i<pixels.length;i+=4)sum+=pixels[i]+pixels[i+1]+pixels[i+2]
  return sum
}

const above=new Uint8ClampedArray(wasm.render3D(96,96,camera,upload,[object.stateAt(0)],{position:new Vec3(0,0,3)}))
const below=new Uint8ClampedArray(wasm.render3D(96,96,camera,upload,[object.stateAt(0)],{position:new Vec3(0,0,-3)}))
assert.ok(brightness(above)>brightness(below)*2,'point light position should affect diffuse shading')
console.log('3D point light: position-dependent shading passed')
