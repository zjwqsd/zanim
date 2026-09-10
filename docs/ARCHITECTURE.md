# Architecture

## Native video

```text
Python Scene
→ absolute-time evaluator
→ RenderSnapshot
→ wire ABI
→ Zig/z2d + software 3D rasterizer
→ FFmpeg/libx264
```

The hot video path stays in memory and does not round-trip through Scene IR.

## Web

```text
TypeScript Scene
→ absolute-time evaluator
→ retained Canvas2D
→ Zig/WASM procedural + 3D kernels
```

Main modules:

- `web/src/core.js`: public objects, renderer and WASM bridge.
- `web/src/scene.js`: authoring and timeline.
- `web/src/evaluator.js`: random-access state evaluation.
- `web/src/player.js`: playback.
- `web/src/ir.js`: portable Scene IR.
- `web/src/media.js`: external media.
- `web/src/three.js`: Web 3D authoring/layer.
- `web/src/typst.js`: Web Math/Typst compiler boundary.
- `web/src/svg.js`: SVG → `VectorDocument` lowering.

## State ownership

```text
raw declaration --layout--> initial state --Scene.add()--> Scene authored head + Timeline
                                                        |
                                                        +--> evaluate(t) --> RenderSnapshot / Web draw state
```

The raw declaration remains the captured initial definition after registration. Python bound handles and Web Scene authoring operations read/write the Scene-owned authored head. Seeking and rendering reconstruct state from `initial + clips`; Web applies sampled state only for the duration of a draw and restores raw objects afterward.

`Camera2D` follows the same timeline model. Python `Camera3D` is constructed with the Scene and uses `camera3d.configure(...)` for temporal state; it cannot be replaced or field-mutated after Scene construction.

## Typst

```text
Python authoring: Text/Math → local Typst CLI → persistent SVG cache → VectorDocument
Web authoring:    static Math/Typst → Vite plugin → local Typst CLI → SVG asset
Web runtime:      SVG asset → VectorDocument
```

Runtime code never owns Typst layout. Production Web packages contain no Typst compiler. Python Preview explicitly injects its `/api/typst` development bridge.

## Scene IR

Scene IR v1 stores portable object state, hierarchy/lifetimes, resources and timeline clips. `VectorDocument` is the common vector representation for SVG/Typst output.

Callbacks are runtime behavior and therefore require explicit sampling when crossing the IR boundary.

## Repository boundary

The core repository contains runtime code, tests and technical documentation. Tutorials/examples live in a separate repository and are not imported by core tests.


## Class-based authoring

Python Scene subclasses may define `setup()` and `construct()`. The CLI runs them in that order. `setup()` prepares raw declarations/resources and one-time initial layout; `construct()` crosses `Scene.add()` and authors the Timeline. Temporally-created objects may still be declared inside `construct()` at the point their lifetime begins. These hooks are a thin frontend only: `Scene.add()` remains the state-ownership boundary and Timeline/evaluation semantics are unchanged.
