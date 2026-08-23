# Zanim Web

Browser frontend for Zanim. Authoring is JavaScript/TypeScript; Canvas2D handles retained 2D rendering and Zig/WASM handles procedural math kernels.

## Run

```bash
./web/build.sh
python -m http.server 8000 -d web
```

- Gallery: `http://localhost:8000/gallery/`
- Demo: `http://localhost:8000/demo/`
- Benchmark: `http://localhost:8000/bench/`

## Runtime

Main public capabilities:

- random-access `Scene` timeline
- transform, opacity, style, trim, value and batch channels
- `Group`, LOCAL/PARENT/WORLD transforms and `Camera2D`
- shapes, text, `Polyline`, create/trim, interpolate/replace
- `LineSet`, `CircleSet`, `RectSet`, dynamic batches and `DynamicNumber`
- bounds, anchors, `Row`, `Column`, `Grid`, animated layout
- `InfiniteLine`, `InfiniteGrid`
- `MandelbrotSet`, `JuliaSet`, `ComplexMappedGrid`
- `FunctionPlot` and `FourierEpicycles`
- `VectorObject2D` for SVG/Typst cubic vector data

Canvas2D is the default 2D backend. Batch paths are retained with `Path2D`; procedural fields use configurable WASM resolution.

## Scene IR

`@zanim/web/ir` loads and exports Scene IR:

```ts
import { Circle, Scene } from "@zanim/web";
import { createSceneFromIR, sceneToIR } from "@zanim/web/ir";

const scene = Scene.headless({ width: 1280, height: 720, unitSize: 90, fps: 60 });
scene.add(new Circle(0.5)).move([3, 1], { duration: 1.5 });
const ir = sceneToIR(scene);

const replay = await createSceneFromIR("#canvas", ir);
```

Runtime callbacks may be exported with sampled fallbacks. `FunctionPlot` and `FourierEpicycles` stay semantic and compact.

Native video from the same IR:

```bash
zanim render-ir scene.zanim.json -o scene.mp4
```

## Preview and Gallery

Python Preview serves Scene IR to this runtime; it does not stream rendered frames.

The Gallery shows all canonical Python example scripts. Entries are labeled as either TypeScript replicas or Python IR replays.
