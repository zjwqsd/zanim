# Zanim

Cross-platform animation engine with Python and TypeScript authoring.

- Python video rendering: Python Scene → absolute-time evaluator → Zig/z2d → FFmpeg/libx264.
- Web rendering: TypeScript Scene → absolute-time evaluator → Canvas2D + Zig/WASM kernels.
- Scene IR v1 is the portable boundary between Python, Web and native rendering.
- 2D, vector documents, media timelines, procedural math, 3D meshes and random-access animation share one Scene model.

Examples and tutorials are maintained in a separate repository. The core repository intentionally contains no tutorial/example tree.

## Python quick start

```python
from zanim import BLUE, Canvas, Circle, Scene

scene = Scene(canvas=Canvas(1280, 720, 90), fps=60)
circle = scene.add(Circle(1, fill=BLUE))
circle.move(to=(2, 0), duration=2)
```

```bash
zanim preview scene.py
zanim render scene.py -o scene.mp4
zanim render scene.py --time 1.25 -o frame.png
zanim info
```

Jupyter uses the same API:

```python
scene.render()
scene.render(time=1.25)
scene.render(start=2, end=5)
```

`Scene` is absolute-time and random-access. Preview seek does not replay earlier frames.

## Typst on Python

Python `Text` and `Math` compile Typst to SVG once, import the SVG as an immutable `VectorDocument`, then render that vector document normally.

Typst executable resolution is deterministic:

1. `ZANIM_TYPST=/absolute/path/to/typst`.
2. Source checkout tool: `.tools/typst/typst` on Unix or `.tools/typst/typst.exe` on Windows.
3. `typst` found on `PATH`.

`ZANIM_TYPST` is an explicit override. If it points to a missing file, Zanim reports that path instead of silently falling back.

Compiled SVGs are content-addressed and persist across runs. Cache location:

1. `ZANIM_CACHE_DIR/typst` when `ZANIM_CACHE_DIR` is set.
2. Windows: `%LOCALAPPDATA%/zanim/typst`.
3. Unix-like systems: `$XDG_CACHE_HOME/zanim/typst`, or `~/.cache/zanim/typst` when `XDG_CACHE_HOME` is unset.

Changing the Typst source, font size, color or font selection changes the source hash and produces a new cached SVG. Reusing identical content does not invoke Typst again.

## Web quick start

Install `@zanim/web`, then enable its Vite plugin:

```ts
// vite.config.ts
import { defineConfig } from 'vite';
import { zanim } from '@zanim/web/vite';

export default defineConfig({ plugins: [zanim()] });
```

Authoring stays ordinary TypeScript:

```ts
import { Circle, Math, Scene } from '@zanim/web';

const scene = await Scene.create('#canvas', { renderer: { unitSize: 90 } });
scene.add(new Circle(1)).move([2, 0], { duration: 2 });
scene.add(new Math('integral_0^1 x^2 dif x = 1/3'));
```

`Math` / `Typst` are authoring-time resources. During `vite dev` and `vite build`, `@zanim/web/vite` finds static `new Math(...)` / `new Typst(...)` calls, invokes the developer's local Typst, and injects compiled SVG assets. Production browsers only fetch those SVGs and lower them to `VectorDocument`; `@zanim/web` does not ship or download a Typst compiler.

Web Typst resolution follows the same explicit idea as Python: plugin option `zanim({ typst: '/path/to/typst' })`, then `ZANIM_TYPST`, then project `.tools/typst/typst[.exe]`, then `PATH`. If a scene uses Web `Math` / `Typst` and no compiler is available, Vite fails with a clear build error.

The formula source, `fontSize` and `color` must be build-time static. Runtime-changing numeric content uses `DynamicNumber` / `FormulaTemplate`; production runtime never recompiles Typst.

Python Preview is separate: it explicitly configures its local `/api/typst` bridge so Preview can use the Python-side Typst CLI. This is a development integration, not a production browser dependency.

## Scene model

Core authoring rules:

- Objects have stable identity.
- Time is explicit and seekable.
- Transform channels are absolute-time functions, not frame-to-frame mutation.
- Relative transforms require an explicit `LOCAL`, `PARENT` or `WORLD` frame.
- `parallel()` freezes one scheduling base.
- Unsupported portable behavior fails explicitly instead of silently changing semantics.

Python and Web both support retained object state, transform/opacity/style channels, lifetimes, layout, vector documents, media playback and procedural objects.

## Scene IR

```bash
zanim export-ir scene.py -o scene.zanim.json
zanim render-ir scene.zanim.json -o scene.mp4
```

```ts
import { Scene } from '@zanim/web';
import { sceneToIR } from '@zanim/web/ir';

const scene = Scene.headless({ width: 1280, height: 720, unitSize: 90, fps: 60 });
const ir = sceneToIR(scene);
```

`VectorDocument` is portable. Python `Text` / `Math` therefore arrive in Web Preview as ordinary vector resources; the browser does not recompile them.

Runtime callbacks are not portable by default. Explicit sampling options are available when a callback must cross the IR boundary.

See `docs/scene-ir-v1.md` and `docs/ARCHITECTURE.md`.

## 3D

Python exposes `Vec3`, `SO3`, `SE3`, `Transform3D`, `Camera3D`, `Box3D`, `Cube3D` and `Surface3D`. Custom mesh construction uses `TriangleMesh` / `MeshObject3D`.

`SE3` is the rigid-pose type. Its interpolation uses SO(3) slerp plus linear translation. General `Transform3D` remains affine and may contain scale/shear.

Native 3D uses the same ordered Scene draw stream as 2D. The Zig rasterizer implements:

- perspective and orthographic cameras;
- homogeneous frustum clipping;
- back-face culling;
- depth buffering;
- inverse-transpose normal transformation;
- smooth normal interpolation and Lambert shading;
- deterministic mesh-level transparent sorting.

Web 3D uses the same camera/projection conventions in the Zig/WASM rasterizer and composites the resulting RGBA layer into Canvas2D.

## Runtime requirements

Python:

- Python 3.12+
- Typst for `Text` / `Math`
- FFmpeg + ffprobe for media/video workflows
- FFmpeg with libx264 for MP4 output

A release wheel bundles the native Zig renderer. Zig is a build-time dependency for source builds, not a normal runtime dependency.

Web:

- modern browser with WebAssembly and Canvas2D
- no Typst compiler is required in production; Web `Math` / `Typst` loads precompiled SVG assets

Web development/build when authoring `Math` / `Typst`:

- Vite 5+ with `zanim()` from `@zanim/web/vite`
- Typst available through plugin option, `ZANIM_TYPST`, project `.tools/typst`, or `PATH`

## Development

```bash
uv sync
zig build -Doptimize=ReleaseFast
cd web && npm install && ./build.sh && cd ..
./scripts/check.sh
```

Build a wheel:

```bash
uv build --wheel
```

The core repository contains runtime code, tests and technical documentation only. User-facing examples live in the separate tutorial/showcase repository so both projects can evolve independently.
