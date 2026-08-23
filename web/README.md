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

`core.js` owns browser objects/rendering, `scene.js` owns authoring and timeline validation, `evaluator.js` owns absolute-time evaluation, and `player.js` owns playback. `at` is a relative offset from the current scheduling base; `parallel()` freezes one shared base, matching Python.

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
- Web `Math` / `Typst` compiled asynchronously into `VectorObject2D`
- `Image`, `GIF`, `Video`, `Audio` with the Scene media timeline

Canvas2D is the default 2D backend. Batch paths are retained with `Path2D`; procedural fields use configurable WASM resolution.


## Math / Typst

Python-authored `Text` / `Math` already arrive as portable `VectorDocument` resources. Web authoring can compile Typst at runtime and keeps the result as the same vector object:

```ts
import { Math, Scene } from "@zanim/web";

const formula = new Math("integral_0^1 x^2 dif x = 1/3", { fontSize: 34 });
await formula.ready;
scene.add(formula);
formula.create({ duration: 1 });
```

The Python Preview provides `/api/typst`. Standalone Web apps can call `configureTypstCompiler(...)` with their own browser/WASM or server compiler. Web-authored `Math` / `Typst` is runtime-only and `sceneToIR()` rejects it.

## External media

```ts
import { Audio, GIF, Image, Video } from "@zanim/web";

const image = new Image("cover.png", { width: 3 });
const gif = new GIF("motion.gif", { width: 3 });
const video = new Video("clip.mp4", { width: 4, muted: true });
const audio = new Audio("tone.wav", { gain: .4 });
scene.add(image, gif, video, audio);
scene.parallel(api => {
  api.media(gif, { duration: 5, loop: true });
  api.media(video, { duration: 5, sourceDuration: 2, loop: true });
  api.media(audio, { duration: 5, sourceDuration: 2, loop: true });
});
```

Python Preview exposes local media through opaque `/api/media/...` URLs with HTTP Range support for video. Those `external_media` resources are explicitly non-portable Preview data.

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
