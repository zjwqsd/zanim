import assert from 'node:assert/strict'
import fs from 'node:fs'
import {
  Difference,
  Ellipse,
  Exclusion,
  Intersection,
  Transform2D,
  Union,
  ZanimWasm,
} from './src/zanim.js'

function pair() {
  return [
    new Ellipse(2, 2.5, { transform: Transform2D.translation(-1, 0) }),
    new Ellipse(2, 2.5, { transform: Transform2D.translation(1, 0) }),
  ]
}

{
  const [a, b] = pair()
  const fallback = [new Intersection(a,b), new Union(a,b), new Difference(a,b), new Exclusion(a,b)]
  assert.deepEqual(fallback.map(x => x.document.paths[0]?.contours.length ?? 0), [1,1,1,2])
  assert.ok(fallback.every(x => x.backend === 'vector'))
}

const bytes = fs.readFileSync(new URL('./dist/zanim_web_core.wasm', import.meta.url))
const instance = (await WebAssembly.instantiate(bytes, {})).instance
new ZanimWasm(instance)

{
  const [a, b] = pair()
  const wasm = [new Intersection(a,b), new Union(a,b), new Difference(a,b), new Exclusion(a,b)]
  assert.deepEqual(wasm.map(x => x.document.paths[0]?.contours.length ?? 0), [1,1,1,2])
  assert.ok(wasm.every(x => x.backend === 'vector'))
  assert.ok(wasm[0].bounds().width < wasm[1].bounds().width)
  assert.ok(wasm[2].center.x < 0)
}

console.log('Vector boolean: JS fallback and Zig/WASM backend passed')
