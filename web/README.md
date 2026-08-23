# Zanim Web

`@zanim/web` is the browser-native frontend of Zanim. It is not a video player and
users do not need to know WebAssembly: JavaScript/TypeScript owns authoring and the
Zig/WASM module is an implementation detail for procedural math kernels.

## Run locally

```bash
./web/build.sh
python -m http.server 8000 -d web
```

- Gallery: `http://localhost:8000/gallery/`
- Interactive infinite-plane demo: `http://localhost:8000/demo/`
- Retained-batch stress benchmark: `http://localhost:8000/bench/`

## Current native runtime

Public browser primitives currently include:

- deterministic random-access `Scene` timeline with independent transform/opacity/style/trim/value/batch channels
- pure `transformFunction(alpha)` clips
- recursively tracked `Group` children (timeline-addressable without duplicate rendering)
- `Transform2D`, `Mat2`, inverse/composition, `ScalarValue`, and LOCAL/PARENT/WORLD frame semantics
- retained `Polyline` with Python-compatible path trim/create semantics
- `Scene.interpolate()` / `Scene.replace()`: dense Polyline arc-length morphs plus native-style 8-cubic primitive normalization for Circle/Rectangle/Line, with transform/style interpolation and lifetime handoff
- basic shapes/text plus Python-compatible `Bounds2D`, `Frame`, `Anchor`, `Row`, `Column`, `Grid`, and animated `Scene.layout()`
- retained `LineSet`, `CircleSet`, `RectSet`, `TextSet` using cached `Path2D`, with random-access `BatchClip` interpolation
- `DynamicPolyline`, dynamic batch sets and `DynamicNumber`
- `InfiniteLine` / `InfiniteGrid`
- native Zig/WASM `MandelbrotSet`, `JuliaSet`, and inverse-mapped `ComplexMappedGrid`, sharing Native palette/homotopy semantics
- explicit realtime quality controls for procedural fields

The Gallery now uses three deliberately strict levels:

- **PARITY**: public Web API only, and timeline/geometry/transition semantics checked against the Python scene.
- **NATIVE**: public Web API only, but visual/timeline parity has not yet been certified.
- **PROTOTYPE**: still demonstrates a deferred subsystem with custom drawing code.

The project goal is to grow PARITY slowly rather than call every browser-native demo finished.
At this checkpoint the 29-page gallery contains **16 PARITY / 6 NATIVE / 7 PROTOTYPE** pages.
PARITY currently covers the major 2D timing/interpolation paths: layout, coordinate-frame
transforms, open-chain kinematics, lifetime/state, transient primitive morphs, batched neural
signals, complete six-algorithm sorting traces, the complete red-black-tree trace, Hilbert and
classic path fractals, De Casteljau, modular multiplication, infinite linear algebra, complex
mapping, and Mandelbrot/Julia. The seven raster/media/3D compatibility pages remain intentionally
deferred. Math/Typst, SVG VectorDocument, MIDI/audio and MNIST-specific parity are not claimed yet.

## Performance model

The primary 2D renderer remains Canvas2D, but it is retained rather than immediate:
batch geometry compiles to `Path2D` once and animation changes the affine CTM. Dynamic
geometry rebuilds one batched path per frame rather than constructing one JS object per
primitive. Heavy mathematical pixel fields run in Zig/WASM and expose explicit realtime
resolution tradeoffs. Their mathematical path, transform timeline and palette remain aligned to
Native Zanim; browser playback may use a lower spatial sampling resolution to preserve 60 Hz.

WebGPU/WebGL is therefore not required for ordinary 2D animation yet; it remains a
future backend for cases whose real browser frame-time benchmarks exceed the 60 Hz
budget after retained/batched optimization.


## Parity contract

For features claimed as PARITY, Python is the semantic reference implementation. In
particular, Web must preserve absolute-time random access, authored object lifetimes,
clip easing/durations, path create/trim behavior, and geometry replacement semantics.
Polyline replacement uses the denser endpoint segment count and uniform arc-length
resampling, mirroring `src/interpolation.zig`; color, stroke width and affine transform
are interpolated continuously. If a subsystem cannot satisfy this contract yet, it
stays NATIVE or PROTOTYPE instead of receiving an approximate compatibility shim.
