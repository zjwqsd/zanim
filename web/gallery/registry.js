import { showcaseDemos } from './demos.js';
import { extraDemos } from './extras.js';
import { janimDemos } from './janim.js';

export const allDemos = Object.freeze(Object.fromEntries([
  ...Object.entries(showcaseDemos).map(([name, build]) => [`showcase/${name}`, build]),
  ...Object.entries(extraDemos).map(([name, build]) => [`extras/${name}`, build]),
  ...Object.entries(janimDemos).map(([name, build]) => [`janim_api/${name}`, build]),
]));

// These pages are kept as visual prototypes while their underlying systems are
// intentionally deferred. Everything else in the registry is required to be
// expressible using @zanim/web public primitives only.
export const prototypeDemos = Object.freeze(new Set([
  'showcase/compositing',
  'showcase/media',
  'showcase/three_d',
  'janim_api/frame_effect_example',
  'janim_api/mask_example',
  'janim_api/suite',
  'janim_api/three_d_shapes_example',
]));


// PARITY means more than "uses public Web primitives": the demo's authoring
// timeline and transition semantics have been checked against the Python scene.
// This is the release bar we want to grow, deliberately more slowly than NATIVE.
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

export const demoMeta = Object.freeze(Object.fromEntries(
  Object.keys(allDemos).map(name => [name, Object.freeze({
    status: prototypeDemos.has(name) ? 'prototype' : parityDemos.has(name) ? 'parity' : 'native',
  })]),
));
