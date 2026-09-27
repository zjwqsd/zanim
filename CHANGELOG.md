# Changelog

## 0.7.0rc2 - 2026-09-27

Second public release candidate.

- Simplified the public authoring API and object-handle workflow.
- Added configurable Manim-style themes, runtime theme switching, and config-file defaults.
- Unified non-scaling stroke semantics across the native and Web runtimes.
- Expanded vector, viewport, and 3D rendering capabilities.
- Optimized runtime source capture used by Preview reloads.
- Refined the project website and documentation presentation.

## 0.7.0rc1 - 2026-09-20

First public release candidate.

- Random-access Python Scene authoring with native Zig rendering.
- Retained 2D/vector/media objects, procedural geometry, and 3D mesh rendering.
- Typst-backed `Text` and `Math` with persistent content-addressed caching.
- Scene IR import/export and browser preview using the shared Web runtime.
- Platform wheels embed the native renderer and Web/WASM preview runtime.
- Improved timeline semantics, batch caching, vector morphing, and multi-scene lifecycle behavior.

The Python API remains pre-1.0 and may evolve between minor releases.
