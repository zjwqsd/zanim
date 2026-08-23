# Zanim Scene IR v1

Portable scene format shared by Python, TypeScript, Web and Native rendering.

```text
Python / TypeScript → Scene IR → Web
                           └──→ Native Zig/z2d → MP4
```

## Document

```json
{
  "format": "zanim.scene",
  "version": 1,
  "canvas": {"width": 1280, "height": 720, "unit_size": 90},
  "fps": 60,
  "duration": 5.2,
  "objects": [],
  "values": [],
  "resources": [],
  "clips": [],
  "meta": {"portable": true}
}
```

Transforms use `[xx, xy, yx, yy, tx, ty]`. Colors use 8-bit `[r, g, b, a]`. Times are seconds.

## Objects

Each object has a stable id, optional parent, initial state and lifetime `[birth, death)`.

Supported v1 kinds:

- `camera2d`, `group`, `object2d`, `batch2d`, `vector2d`
- `sampled_object2d`, `sampled_batch2d`, `sampled_vector2d`
- `function_plot`, `fourier_epicycles`
- `infinite_line`, `infinite_grid`, `fractal`, `complex_grid`

`ScalarValue` entries are stored in `values`.

## Resources

`vector_document` stores immutable cubic Bézier data used by SVG and Typst. Objects reference resources by id, so data can be shared.

## Clips

Supported v1 clip kinds:

- `transform`
- `se2_transform`
- `sampled_transform`
- `opacity`, `style`, `trim`, `reveal`
- `batch`, `value`, `interpolation`

Easing: `linear`, `smoothstep`.

All clips use absolute scene time and support random access.

## Runtime callbacks

Arbitrary Python/JavaScript source is not serialized. Strict export rejects runtime callbacks.

Optional sampling uses the scene's global `frame / fps` grid:

```bash
zanim export-ir scene.py -o scene.zanim.json \
  --sample-transform-functions --sample-dynamic-providers
```

Transforms store sampled values and interpolate between samples. Dynamic geometry/batch/vector tracks use sample-and-hold, preserving topology changes.

Portable math should use semantic objects when available:

- `FunctionPlot`: scalar expression over `x` and `time`
- `FourierEpicycles`: Fourier coefficients and visualization parameters

## Commands

```bash
zanim export-ir animation.py -o animation.zanim.json
zanim render-ir animation.zanim.json -o animation.mp4
```

Web:

```ts
import { createSceneFromIR, sceneToIR } from "@zanim/web/ir";

const ir = sceneToIR(scene);
const replay = await createSceneFromIR("#canvas", ir);
```
