import { showcaseDemos } from './demos.js';
import { extraDemos } from './extras.js';
import { janimDemos } from './janim.js';

const tsFactories = Object.freeze(Object.fromEntries([
  ...Object.entries(showcaseDemos).map(([name, build]) => [`showcase/${name}`, build]),
  ...Object.entries(extraDemos).map(([name, build]) => [`extras/${name}`, build]),
  ...Object.entries(janimDemos).map(([name, build]) => [`janim_api/${name}`, build]),
]));

// IR is deliberately the exception, not the default Gallery implementation.
// These two scenes are Typst/vector-heavy enough that a second hand-written TS
// copy adds drift without demonstrating useful new Web authoring primitives.
export const irReplayDemos = Object.freeze(new Map([
  ['showcase/basics', './generated/ir/showcase_basics.zanim.json'],
  ['showcase/vectors', './generated/ir/showcase_vectors.zanim.json'],
]));

// These TS replicas remain useful visual coverage while their underlying
// renderer systems (compositing/3D/frame effects) are intentionally deferred.
export const prototypeDemos = Object.freeze(new Set([
  'showcase/compositing',
  'showcase/three_d',
  'janim_api/frame_effect_example',
  'janim_api/mask_example',
  'janim_api/suite',
  'janim_api/three_d_shapes_example',
]));

// PARITY is reserved for TS replicas whose timeline/transition semantics have
// been checked against the Python scene. IR replays have their own source mode
// and do not need this label: they are the Python scene document itself.
export const parityDemos = Object.freeze(new Set([
  'showcase/batches',
  'showcase/infinite_space',
  'showcase/kinematics',
  'showcase/layout',
  'showcase/state_model',
  'showcase/timeline',
  'showcase/transforms',
  'extras/complex_mapping',
  'extras/de_casteljau',
  'extras/fractals',
  'extras/hilbert_curve',
  'extras/mandelbrot_julia',
  'extras/modular_multiplication',
  'extras/neural_network',
  'extras/red_black_tree',
  'extras/sorting_algorithms',
]));

const names = Object.keys(tsFactories);
export const galleryEntries = Object.freeze(Object.fromEntries(names.map(name => {
  if (irReplayDemos.has(name)) {
    return [name, Object.freeze({name, mode:'ir', url:irReplayDemos.get(name), status:'source'})];
  }
  return [name, Object.freeze({
    name,
    mode:'ts',
    build:tsFactories[name],
    status: prototypeDemos.has(name) ? 'prototype' : parityDemos.has(name) ? 'parity' : 'native',
  })];
})));

// Compatibility export for tests/tools that need only TS factories. IR entries
// are intentionally absent so callers cannot accidentally pretend they are TS.
export const allDemos = Object.freeze(Object.fromEntries(
  Object.entries(tsFactories).filter(([name]) => !irReplayDemos.has(name))
));

export const demoMeta = Object.freeze(Object.fromEntries(
  Object.entries(galleryEntries).map(([name, entry]) => [name, Object.freeze({
    mode: entry.mode,
    status: entry.status,
  })]),
));

export const galleryCounts = Object.freeze({
  total: names.length,
  ts: names.length - irReplayDemos.size,
  ir: irReplayDemos.size,
  parity: parityDemos.size,
  prototype: prototypeDemos.size,
});
