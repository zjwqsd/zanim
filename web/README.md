# @zanim/web

Browser runtime and TypeScript authoring API for Zanim.

## Runtime

- `src/core.js`: retained 2D objects, Canvas2D rendering and WASM bridge.
- `src/scene.js`: authoring, timeline validation and scheduling.
- `src/evaluator.js`: absolute-time evaluation.
- `src/player.js`: playback.
- `src/ir.js`: Scene IR import/export.
- `src/media.js`: image/GIF/video/audio objects.
- `src/three.js`: mesh/camera API and Web 3D layer.
- `src/typst.js`: loads precompiled SVG/VectorDocument resources; it never embeds a Typst compiler.
- `src/svg.js`: internal SVG-to-cubic-vector importer used by Typst.

The repository no longer contains a Gallery or browser demo suite. User-facing examples are maintained in the separate tutorial repository.

## Math / Typst

Use the Vite plugin once:

```ts
// vite.config.ts
import { zanim } from '@zanim/web/vite';
export default { plugins: [zanim()] };
```

Then author normally:

```ts
import { Math } from '@zanim/web';
const formula = new Math('integral_0^1 x^2 dif x = 1/3', { fontSize: 34 });
await formula.ready;
```

Build flow:

```text
new Math(static source)
  → @zanim/web/vite
  → local Typst CLI
  → content-addressed SVG
  → Vite production asset
  → browser fetch
  → VectorDocument
```

The npm runtime contains no Typst compiler/WASM and makes no font/CDN requests. Typst is required only on the developer/build machine. Resolution order is plugin `typst`, `ZANIM_TYPST`, project `.tools/typst/typst[.exe]`, then `PATH`.

Formula source, `fontSize` and `color` are intentionally build-time static. Use `DynamicNumber` / `FormulaTemplate` for runtime-changing values. A dynamic formula source is a build error rather than a reason to ship a browser compiler.

`configureTypstCompiler(...)` remains available for explicit development integrations. Python Preview uses it to point Web Preview at Python's `/api/typst`; production apps normally use the Vite-precompiled SVG path.

## Build

```bash
cd web
npm install
./build.sh
npm test
```

`build.sh` creates only `dist/zanim_web_core.wasm`. Typst SVGs belong to each consuming application and are emitted by `@zanim/web/vite` during that application's build.

## Scene IR

```ts
import { Scene } from '@zanim/web';
import { createSceneFromIR, sceneToIR } from '@zanim/web/ir';
```

Scene IR is semantic and random-access; it is not a frame dump. Runtime callbacks require explicit sampling when exported.
