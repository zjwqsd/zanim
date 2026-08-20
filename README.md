# Zanim

A compact Manim-style 2D animation engine with Python authoring, a Zig 0.16 render core, and z2d as the raster backend.

Zanim keeps the renderer small and explicit while providing the authoring conveniences needed for real mathematical animation: geometry, groups/layout, timeline animation, camera motion, Typst text/math, dynamic formulas, plotting, batched visualization, and random-access video rendering.

## Architecture

```text
Authoring objects
Object2D / BatchObject2D / VectorObject2D / Group2D / Camera2D / ScalarValue
        |
        | Scene + Timeline, evaluate(t)
        v
Render model
RenderSnapshot (flat renderable leaves)
        |
        | encode ordered draw stream
        v
Backend bridge
render/wire.py -> C ABI
        |
        v
Zig renderer
scene_wire.zig -> geometry / batch / vector -> z2d
```

Important boundaries:

- `Scene` has one registry for authoring objects and animated scalar values.
- `Group2D` is a lightweight authoring hierarchy. Group transforms, opacity, and z-index are composed into child leaves during `evaluate(t)`; Zig never receives a scene graph.
- `Camera2D` uses the same transform channel and is composed into every leaf snapshot.
- `RenderSnapshot` is immutable and random-access: rendering frame `t` never depends on rendering frame `t-dt` first.
- `z_index` plus insertion order defines one draw order across geometry, batch, and vector representations.
- Python owns animation and video orchestration. Zig only rasterizes already-evaluated values.

## Common authoring model

Every visual object shares:

```text
transform
opacity
z_index
bounds()
```

and spatial helpers such as `shift`, `move_to`, `next_to`, `align_to`, `to_edge`, `scale_about`, and `rotate_about`.

`Group2D` adds `arrange` and `arrange_in_grid` without adding renderer-side hierarchy.

## Animation channels

The timeline deliberately uses explicit channels rather than a generic component/track framework:

- `TransformClip` — all scene objects including groups and camera
- `OpacityClip` — all visual objects/groups
- `StyleClip` — ordinary geometry style
- `PathTrimClip` — geometry path creation/trimming
- `BatchClip` — retained batch values
- `RevealClip` — vector/text/math reveal
- `ValueClip` — `ScalarValue`
- `InterpolationClip` — transient relation between distinct geometry objects; common open and closed primitives normalize to eight cubic segments for compatible morphing

`Scene.create()` uses path trim for geometry and vector reveal for text/math. `fade_in`/`fade_out` use the common opacity channel.

## Coordinates and camera

- +x points right, +y points up.
- `(0, 0)` is the canvas center by default.
- `unit_size` is pixels per logical unit.
- object transforms may be arbitrary affine maps, including singular transforms.
- the y-axis flip into device coordinates happens only in the Canvas basis.
- `Camera2D` supplies the world-to-view affine transform before object/group transforms.

## Math and plotting

- `Text` / `Math`: Typst -> SVG -> immutable `VectorDocument`.
- `FormulaTemplate`: Typst owns mathematical layout while fixed slots hold high-frequency numbers or embedded Zanim objects.
- `DynamicNumber` uses a cached Typst math glyph atlas; per-frame updates do not invoke Typst.
- `Axes2D` supplies coordinate mapping, plotting, dynamic area geometry, and numerical integration.
- `ScalarValue` is a random-access value source and can bind directly to `DynamicNumber` or formula slots.

## Common objects

Alongside raw primitives, the authoring layer includes `Dot`, `Arrow`, and `NumberLine` (with optional Typst tick labels). `Axes2D.axis_labels()` returns ordinary grouped math objects. More convenience objects should be added only when they remove repeated authoring work; they do not require new renderer mechanisms.

## Setup and checks

```bash
uv sync
zig build
./scripts/check.sh
```

## Examples

```bash
uv run python examples/foundation_showcase.py
uv run python examples/timeline_scene.py
uv run python examples/grid_linear_transform.py
uv run python examples/square_to_circle.py
uv run python examples/text_reveal.py
uv run python examples/formula_reveal.py
uv run python examples/dynamic_matrix_formula.py
uv run python examples/dynamic_integral_scene.py
uv run python examples/mlp_inference_scene.py
```

Videos are written to `media/`.

The project intentionally does **not** introduce ECS, a renderer-side scene graph, a generic updater DAG, or a universal templated track system. New abstractions should continue to be justified by concrete animation workloads.

## Optional extras

Task-specific features live outside the core authoring model when they do not justify a renderer or timeline primitive. Fourier SVG drawing is implemented in `zanim.extras.fourier` on top of the generic cubic-contour arc-length sampler in `zanim.path`:

```bash
uv run python examples/svg_fourier_draw.py --svg assets/fourier_heart.svg --terms 36
```

The example selects one closed contour, computes its DFT, builds a head-to-tail epicycle chain, and draws the moving endpoint trace. The Fourier policy itself is not part of `Scene`, `Timeline`, or the Zig renderer.
