# Architecture

## Boundaries

```text
Python authoring → Python evaluator → RenderSnapshot → Native Zig renderer → video
       │
       └→ Scene IR ← TypeScript authoring
              │
              ├→ Web evaluator → Canvas2D
              └→ Native video

Web/WASM ─┐
          ├→ shared Zig procedural kernels
Native ───┘
```

Python direct rendering remains the performance path and never requires IR serialization.

## Rules

- `Scene` owns identity, hierarchy, lifetime and timeline semantics.
- Evaluation is absolute-time and random-access.
- `at` is relative to the current scheduling base; `parallel()` freezes one shared base.
- LOCAL/PARENT/WORLD transform semantics and channel conflicts must match across Python and Web.
- Cross-language semantics are guarded by `tests/test_web_conformance.py` + `web/conformance.mjs`.
- Scene IR carries portable scene state/resources/clips, not Python or JavaScript source. Preview-only external media is marked `portable=false`.
- Web-authored Typst/Math remains runtime-only; Python Typst is already lowered to portable vector resources.
- Renderer-independent procedural math belongs in `src/procedural.zig`; Native/Web files only adapt it to their output backend.

## Web

- `web/src/core.js`: math, objects, layout, Canvas2D renderer, WASM adapter.
- `web/src/scene.js`: scene state, authoring schedule and lifetime/channel validation.
- `web/src/evaluator.js`: absolute-time random-access evaluation.
- `web/src/player.js`: seek/render/playback orchestration.
- `web/src/media.js`: browser image/GIF/video/audio objects and playback synchronization.
- `web/src/typst.js`: async Typst/Math lowering to `VectorDocument`.
- `web/src/ir.js`: portable Scene IR plus explicitly non-portable Preview media loading.
- `web/src/zanim.js`: public barrel only.

## Native

Python evaluates the complete scene into a `RenderSnapshot`. The wire layer converts that snapshot to one ordered native draw stream. Zig owns rasterization; FFmpeg owns H.264 encoding. This path stays independent of Web and IR changes.
