# Zanim

A compact Manim-style 2D/3D animation engine with Python authoring and a Zig 0.16 render core. z2d handles 2D vector drawing; Zanim owns a deterministic CPU 3D rasterizer.

Zanim keeps the renderer small and explicit while providing the authoring conveniences needed for real mathematical animation: geometry, groups/layout, timeline animation, camera motion, Typst text/math, dynamic formulas, plotting, batched visualization, and random-access video rendering.

## Architecture

```text
Authoring objects
Object2D / BatchObject2D / VectorObject2D / RasterObject2D / Group2D / Camera2D / ScalarValue / AudioObject
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
scene_wire.zig -> geometry / batch / vector / raster -> z2d
```

Important boundaries:

- `Scene` has one registry for visual objects, groups, media, audio, camera state, and animated scalar values.
- `Group2D` is a lightweight authoring hierarchy. Group transforms, opacity, and z-index are composed into child leaves during `evaluate(t)`; Zig never receives a scene graph.
- `Camera2D` uses the same transform channel and is composed into every leaf snapshot.
- `RenderSnapshot` is immutable and random-access: rendering frame `t` never depends on rendering frame `t-dt` first.
- `z_index` plus insertion order defines one draw order across geometry, batch, vector, and raster representations.
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

- `TransformClip` — ordinary affine interpolation for scene objects/groups/camera
- `TransformFunctionClip` — a pure `alpha -> Transform2D` channel for procedural motion without stateful updaters
- `DynamicVectorObject2D` — a pure absolute-time `VectorDocument` source; `zanim.vector.map_vector_document` applies nonlinear mappings directly to cubic control points
- `OpacityClip` — all visual objects/groups
- `StyleClip` — ordinary geometry style
- `PathTrimClip` — geometry path creation/trimming
- `BatchClip` — retained batch values
- `RevealClip` — vector/text/math reveal
- `ValueClip` — `ScalarValue`
- `PlaybackClip` — one scene-time → source-time mapping shared by images, GIF/video playback, and audio
- `InterpolationClip` — transient relation between distinct geometry objects; common open and closed primitives normalize to eight cubic segments for compatible morphing

`Scene.create()` uses path trim for geometry and vector reveal for text/math. `fade_in`/`fade_out` use the common opacity channel.

## Coordinates and camera

- +x points right, +y points up.
- `(0, 0)` is the canvas center by default.
- `unit_size` is pixels per logical unit.
- object transforms may be arbitrary affine maps, including singular transforms.
- the y-axis flip into device coordinates happens only in the Canvas basis.
- `Camera2D` supplies the world-to-view affine transform before object/group transforms.

## External media

Raster and audio media use the same Scene registry and Timeline as geometry. Static images, GIFs, and video frames are represented by `RasterObject2D`; audio is a non-visual `AudioObject`. Animated media and audio share `PlaybackClip`, so source offsets, speed, looping, and scene placement have one time-mapping rule.

```python
image = Image("cover.png", width=4)
gif = GIF("motion.gif", width=3)
video = Video("clip.mp4", width=5)
audio = video.audio_track(gain=0.7)

scene.add(image, gif, video, audio)
with scene.parallel():
    scene.play_media(image, duration=4)
    scene.play_media(gif, duration=4, loop=True)
    scene.play_media(video, duration=4, source_start=0.5, speed=1.25, loop=True)
    scene.play_media(audio, duration=4, source_start=0.5, speed=1.25, loop=True)
```

PNG/JPEG and GIF are decoded through Pillow. Video and audio use ffmpeg/ffprobe; `ffmpeg` must be available on `PATH`. Video uses a streaming raw-RGBA ffmpeg decoder with a bounded in-memory LRU, so decoded frame sequences are not written to disk. Rendering evaluates snapshots inside worker threads, so large raster frames are retained only for active workers rather than for the whole movie. Final audio mixing is sample-based at 48 kHz and muxed into the output MP4 as AAC.

Video output stays RGB-native through the renderer and streams finished RGB0 frames directly to ffmpeg/libx264. The default `veryfast` preset with four encoder threads is the measured throughput/memory sweet spot for the current frame-parallel renderer; `crf`, `preset`, and `encoder_threads` remain explicit tuning knobs. This single software path avoids GPU-specific startup, capability detection, and platform branches while producing standard H.264/yuv420p MP4 output.

Raster objects share the normal `transform`, `opacity`, `z_index`, bounds/layout helpers, camera transform, fade, and transform animation channels. The Zig backend performs inverse-affine bilinear sampling with source-over alpha compositing, so rotated/scaled raster media participates in the same ordered draw stream as vector and geometry content.

### Offscreen compositing and masks

`SceneRasterSource` renders any nested 2D `Scene` to a transparent, random-access RGBA source. `AlphaMaskSource` then combines two raster sources by alpha and supports time-dependent inversion and feathering. This is the common compositing boundary for shape masks, picture-in-picture, selective frame effects, and future blur/glow operations; geometry and vector renderers do not need mask-specific branches.

```python
content = SceneRasterSource(content_scene)
mask = SceneRasterSource(mask_scene)
masked = RasterObject2D(AlphaMaskSource(content, mask), width=8)
```

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

Examples are curated rather than accumulated. `examples/showcase/` is the shortest tour of the public authoring API; `examples/fun/` contains complete playful animations. JAnim API parity and Manim/3Blue1Brown reproductions remain separate reference suites. See [`examples/README.md`](examples/README.md) for the map.

```bash
uv run python examples/showcase/basics.py
uv run python examples/showcase/timeline.py
uv run python examples/showcase/math.py
uv run python examples/showcase/batches.py
uv run python examples/showcase/media.py
uv run python examples/showcase/three_d.py

uv run python examples/fun/fourier_draw.py --terms 36
uv run python examples/fun/neural_network.py
```

Videos are written under matching subdirectories in `media/`.

### JAnim API-demonstration parity suite

`examples/janim_api/` reimplements the visible effects from JAnim's public API demonstration, including the four-panel 3D shapes example. It is intentionally an effect-parity/regression suite rather than an API translation:

```bash
PYTHONPATH=python uv run python -m examples.janim_api.suite all
PYTHONPATH=python uv run python -m examples.janim_api.suite ThreeDShapesExample
```

The suite covers geometry creation/morphing, rich text and Typst, complex-plane deformation, number planes, procedural dependent motion, marked points, pixel frame effects, alpha masks and representative 3D surface styles.

### Manim / 3Blue1Brown reproductions

`examples/manim_2026/` is kept as a separate reference suite for effect-oriented reproductions from the 3Blue1Brown video repository. It is useful for finding capability gaps without turning compatibility-specific ideas into core abstractions.

## Optional extras

Task-specific features live outside the core authoring model when they do not justify a renderer or timeline primitive. Fourier SVG drawing is implemented in `zanim.extras.fourier` on top of the generic cubic-contour arc-length sampler in `zanim.path`:

```bash
uv run python examples/fun/fourier_draw.py --svg assets/fourier_heart.svg --terms 36
```

The example selects one closed contour, computes its DFT, builds a head-to-tail epicycle chain, and draws the moving endpoint trace. The Fourier policy itself is not part of `Scene`, `Timeline`, or the Zig renderer.

## 3D rendering

Zanim uses one deterministic CPU render architecture for both 2D and 3D scene composition. `MeshObject3D` participates in the same `Scene`, timeline, absolute-time evaluation and ordered draw stream as 2D objects. A 3D camera contributes one `3d_layer` draw item; when that item is reached, the Zig software rasterizer draws triangles directly into the current RGB/RGBA scene framebuffer. There is no GPU context, framebuffer readback, temporary full-screen 3D `RasterFrame`, or second compositing pass.

The CPU 3D pipeline implements homogeneous frustum clipping, perspective/orthographic projection, back-face culling, a layer-local z-buffer, indexed vertex processing, perspective-correct smooth-normal interpolation, Lambert shading, and deterministic transparent-mesh sorting/source-over blending. Indexed meshes transform each unique vertex once per frame before triangle assembly. Because the renderer is stateless, video frames use the same worker-parallel pipeline as 2D scenes on Linux and Windows.

Public building blocks include `Vec3`, `SO3`, `Transform3D`, `Camera3D`, `TriangleMesh`, `MeshObject3D`, `Box3D`, `Cube3D`, and `Surface3D`. The renderer stays below these semantics: authoring code never depends on rasterizer-specific types.

The curated syntax example is `examples/showcase/three_d.py`; the JAnim parity suite also contains a four-panel 3D shapes scene. Both use the same CPU renderer and ordinary Scene/Timeline semantics.
