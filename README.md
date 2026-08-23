# Zanim

Cross-platform animation with Python and TypeScript authoring. Native video uses Zig/z2d; Web uses retained Canvas2D with small Zig/WASM math kernels.

## Quick start

A release wheel contains the Zig renderer; Zig is a build-time dependency, not a runtime requirement. Text/Math require Typst. Video/media workflows require the FFmpeg toolset (`ffmpeg` + `ffprobe`) on `PATH`, and MP4 export requires an FFmpeg build with `libx264`.

Check the runtime first:

```bash
zanim info
```

A scene file is just ordinary top-level Python:

```python
from zanim import BLUE, Canvas, Circle, Scene

scene = Scene(canvas=Canvas(1280, 720, 90), fps=60)
circle = scene.add(Circle(1, fill=BLUE))
circle.move(to=(2, 0), duration=2)
```

### Common constants

Frequently used authoring values are available directly from `zanim` and are
also collected in `zanim.constants`:

```python
from zanim import (
    BLUE, GREEN, RED, YELLOW, ORANGE, PURPLE, PINK, CYAN,
    WHITE, GRAY, MUTED, BLACK, TRANSPARENT,
    ORIGIN, LEFT, RIGHT, UP, DOWN,
    PI, TAU, DEGREES,
    Color,
)

accent = BLUE
soft_accent = BLUE.with_alpha(128)
quarter_turn = 90 * DEGREES
full_turn = TAU
custom = Color(37, 121, 208)
custom_alpha = Color(37, 121, 208, 140)
```

The default primary palette starts with `BLUE = Color(96, 166, 255)`,
`GREEN = Color(82, 205, 150)`, and `RED = Color(245, 92, 105)`. These constants
are immutable conveniences; `Color(...)` remains unrestricted for custom RGB/RGBA colors.

No `main()` entry point, builder function or decorator is required. Use Preview while authoring and Render for files:

```bash
zanim preview hello.py
zanim render hello.py -o hello.mp4
zanim render hello.py --time 1.25 -o frame.png
```

In Jupyter, use the same Scene API and omit the output path to display the result inline:

```python
scene.render()                 # static -> PNG, animated -> MP4
scene.render(time=1.25)        # one absolute-time PNG
scene.render(start=2, end=5)   # inline MP4 interval
```

No notebook magics or separate authoring mode are required. `scene.preview()` remains the full interactive browser Preview used by normal Python/CLI workflows.

Preview is random-access in the browser: jumping to `t=300` calls the Web Scene evaluator directly rather than asking Python to render the preceding five minutes. `zanim preview` tracks top-level variable identities and runtime clip call sites automatically; edit/save the file and press `↻ Reload` to re-execute Python and replace the Scene IR while preserving the selected time.

By default source reload is available only on loopback Preview hosts. Exposing Preview with `--host 0.0.0.0` keeps rendering/inspection available but disables code reload unless `--allow-remote-reload` is explicitly supplied.

## Architecture

```text
Python authoring ───────────────→ Python evaluator ─→ RenderSnapshot ─→ Zig/z2d ─→ MP4
       │
       └─→ Scene IR v1 ─┐
                        ├─→ Web Scene evaluator ─→ Canvas2D
TypeScript authoring ───┘                 │
       └──────────────→ Scene IR v1 ──────┴─→ Native video

Native + Web/WASM procedural rendering share renderer-independent Zig kernels.
```

Python direct video keeps its in-memory hot path; it does not round-trip through Scene IR. Scene IR is the portable document boundary for cross-language and cross-backend playback. Web authoring, random-access evaluation and playback live in `web/src/scene.js`; browser objects/rendering live in `web/src/core.js`.

```bash
zanim export-ir animation.py -o animation.zanim.json
zanim render-ir animation.zanim.json -o animation.mp4
```

```ts
import { Circle, Scene } from "@zanim/web";
import { sceneToIR } from "@zanim/web/ir";

const scene = Scene.headless({ width: 1280, height: 720, unitSize: 90, fps: 60 });
scene.add(new Circle(1)).move([2, 0], { duration: 2 });
const ir = sceneToIR(scene);
```

Scene IR stores object state, hierarchy/lifetime, resources and timeline clips. `VectorDocument` is portable, so Python Typst output can render on Web without shipping Typst. Runtime callbacks can be explicitly sampled; `FunctionPlot` and `FourierEpicycles` use compact semantic forms. See `docs/scene-ir-v1.md`.

### Browser Preview

`zanim preview file.py` and `scene.preview()` use the Web runtime directly:

```text
Python source → Scene IR → @zanim/web → Browser
```

Play, seek and inspect run in the browser. Reload re-executes Python and preserves the selected time. Remote reload is disabled unless `--allow-remote-reload` is set.

Dynamic transform/geometry/batch/vector callbacks are sampled on the scene FPS grid for Preview. Unsupported portable features report an error instead of falling back to frame streaming.

## Common authoring model

Every visual object shares:

```text
transform
opacity
z_index
bounds()
```

and low-level spatial helpers such as `shift`, `move_to`, `scale_about`, and `rotate_about`.

### Initial-state sugar

Public shapes are renderable objects directly: `Circle(...)`, `Square(...)`,
`Line(...)`, `Polygon(...)`, and the other shape constructors can all be passed
straight to `Scene.add()`. Low-level immutable geometry values live in
`zanim.geometry` for dynamic/custom render representations.

Simple objects do not need to spell out `Style` or `Transform2D` just to declare
an initial visual state:

```python
star = Polygon(
    star_points(),
    stroke=WHITE,
    stroke_width=.045,
    position=(2, 0),
    rotation=.2,
    scale=.5,
)
```

The style sugar is exact: `fill=` means fill, `stroke=` means outline, and giving
both means both. `stroke_width` defaults to `.035` when a stroke is present. The
complete `style=Style(...)` form remains available, but mixing it with
`fill/stroke/stroke_width` is an error rather than an override. `Color.with_alpha()`
is the compact explicit way to change alpha:

```python
Circle(1, fill=BLUE.with_alpha(128), stroke=WHITE)
```

Initial transform sugar uses the same fixed affine convention as `affine2d()`:

```text
Translation(position) @ Rotation(rotation) @ Shear(shear) @ Scale(scale)
```

`position` is the local origin's location in the parent frame; it is not a visual
bounds-center shortcut. Visual placement still uses `place(anchor=..., at=...)`.
`Group` accepts the same `position/rotation/scale/shear` sugar, so kinematic
frame offsets can be written directly as `Group(..., position=(L, 0))`. Mixing
`transform=` with transform sugar is an error.

After `Scene.add()`, bound objects provide the matching style timeline sugar:

```python
obj = scene.add(obj)
obj.fill(BLUE)
obj.outline(WHITE, width=.045)
obj.paint(fill=RED.with_alpha(128), stroke=RED, stroke_width=.045)
```

These are exact shorthands for `obj.style(to=Style...)`; they add no extra channel
or hidden animation.

### Declare, layout, animate

The preferred authoring order is deliberately visible in code:

```python
# 1. Declare visual objects.
title = Text("Layout is data")
square = Square(1, style=Style.solid(BLUE))
circle = Circle(.5, style=Style.solid(ORANGE))
group = Group([square, circle])

# 2. Lay them out once, before they enter the Scene.
header = scene.frame.top_region(height=1.2)
content = scene.frame.inset(.6).below(header, gap=.2)
title.place(anchor=TOP, at=header.top + .25 * DOWN)
Row(gap=.7, at=content.center).place(*group.children)

# 3. Cross the lifetime boundary. add() returns bound timeline handles.
title, group = scene.add(title, group)
square, circle = group.children

# 4. Post-add authoring is naturally object-bound.
square.move(by=UP, frame=WORLD)
```

`scene.frame` is the Canvas expressed as an explicit world-space `Frame`.
`frame.top`, `frame.bottom`, `frame.left`, corners, and `frame.center` are actual
`Vec2` points. `Frame.inset()` and named regions make composition readable
without scattering magic coordinates through constructors.

`obj.place(anchor=..., at=...)` states exactly which visual-bounds point is put
at which point in its parent layout space. For top-level objects that is world
space; children are laid out in their Group's local frame. `obj.anchor(...)`
queries the same parent-space points. `TOP`,
`BOTTOM`, `TOP_LEFT`, etc. are explicit layout anchors; existing `UP`, `RIGHT`,
etc. remain ordinary `Vec2` directions and keep their arithmetic meaning.

`Row`, `Column`, and `Grid` are layout specifications, not persistent constraint
systems. Before `Scene.add()`, `.place()` applies a specification once:

```python
Row(gap=.7, at=content.center).place(a, b, c)
```

After the objects are in the Scene, the exact same specification can be used as
an explicit animation target:

```python
scene.layout(group, to=Grid(rows=2, cols=2, gap=.6, at=content.center))
scene.layout(group, to=Column(gap=.35, at=content.center))
```

`Scene.layout()` computes one target transform per direct child and schedules
those transforms in parallel. It does not create copies, retain a live layout
constraint, or change object identity. Rotation and scale are preserved; the
layout determines target translations from the objects' current authored bounds.
For a `Group`, child layout coordinates are group-local, while the Group keeps
its own independent transform.

`Group.arrange()` / `arrange_in_grid()` remain compact one-time helpers, but the
curated API examples prefer explicit layout specifications because their target
position can be read directly from the code. See `examples/showcase/layout.py`
for independent child motion followed by Row → Grid → Column layout transitions.

### Explicit authoring state and lifetime

Zanim separates **object lifetime**, **initial state**, and **state animation**.
They are three different things.

Before an object joins a Scene, ordinary mutation is layout/configuration:

```python
box = Square(
    1,
    style=Style.outline(Color(120, 170, 255), 0.04),
    opacity=0,
)
box.place(anchor=CENTER, at=2 * LEFT + UP)
```

`Scene.add()` is temporal. It means the object starts existing at the current
timeline cursor. It does not imply a fade, reveal, copy, or any other entrance.
It also returns a **bound timeline handle**, so the same variable can naturally
change roles at the lifetime boundary:

```python
scene.wait(2)
box = scene.add(box)  # declared shape -> Scene-bound handle
                     # box is absent for t < 2; lifetime begins at t = 2

box.move(to=(3, 1))
box.opacity(to=.4)
```

The handle does not replace the render object: `box.raw` is the exact object that
was declared and registered. `scene.on(raw)` returns the same stable handle. For
multiple objects, `a, b = scene.add(a, b)` returns handles in the same order. A
bound `Group` exposes bound direct children through `group.children`.

This makes the phase distinction explicit in Python:

```text
Shape / Group        declare + layout
        |
        | scene.add()
        v
BoundObject2D / BoundGroup     timeline operations
```

Likewise, `Scene.remove()` ends lifetime at the current cursor. Lifetimes are
half-open intervals `[add_time, remove_time)`. Removing an object does not alter
its opacity or other authored state. `add()` and `remove()` are intentionally not
allowed inside `parallel()` because lifetime boundaries must name one exact
timeline cursor.

Entrance animations start from the state that is actually authored. They never
insert a hidden state before the clip:

```python
label = Text("explicit", opacity=0)
path = Circle(1, trim=0)
math = Math("x^2", reveal=0)

label, path, math = scene.add(label, path, math)
scene.wait(1)
label.fade_in()   # valid: opacity is really 0
path.create()     # valid: trim is really 0
math.create()     # valid: reveal is really 0
```

Calling `fade_in()` on an object whose current authored opacity is already 1, or
`create()` on an object whose trim/reveal is already 1, is an error. Arbitrary
state transitions use the explicit target APIs instead:

```python
box.opacity(to=0.4, duration=0.4)
box.style(to=Style.solid(Color(80, 150, 255)), duration=0.6)
box.move(by=3 * RIGHT, frame=WORLD, duration=1.2)
box.move(to=(0, -1), duration=0.8)
box.rotate(by=0.4, about=box.center, duration=0.6)
box.scale(by=1.5, about=box.center, duration=0.6)
```

Every 2D object's `transform` is rigorously **local -> parent**. Relative motion
therefore requires an explicit frame:

```python
car.move(by=2 * RIGHT, frame=LOCAL)   # T' = T @ delta
box.move(by=2 * RIGHT, frame=PARENT) # T' = delta @ T
box.move(by=2 * RIGHT, frame=WORLD)  # true Scene-world delta
```

`LOCAL` right-multiplies, `PARENT` left-multiplies, and `WORLD` is converted
through the parent world pose before updating the local transform. `by=` without
`frame=` is an error. `to=` is already a complete local-to-parent target and
therefore never accepts a frame. For visual placement, `scene.move(obj, to=...,
anchor=CENTER)` is an absolute world-space anchor target.

`SE2` is a first-class rigid transform and can be passed directly:

```python
robot.transform(
    by=SE2(theta=.4, translation=RIGHT),
    frame=LOCAL,
)
robot.transform(to=SE2(theta=1.0, translation=Vec2(3, 2)))
```

`SE2` endpoints use rigid interpolation (linear translation + shortest-angle
rotation), so the whole clip remains in SE(2). Explicit `Transform2D` endpoints
select general affine interpolation and may include scale/shear. No operation
creates a replacement or hidden copy.

The 2D camera is owned and bound by its `Scene` from construction, so it does
not need `scene.on(scene.camera)`. Its transform has a different, explicit
meaning: **world -> view**. Common camera animation is authored directly:

```python
scene.camera.affine(position=(-.3, -.08), scale=1.15, duration=1.3)
scene.camera.pan(by=(1, 0))          # camera motion in Scene-world coordinates
scene.camera.zoom(by=1.2)            # about view-space origin by default
scene.camera.rotate_view(by=.2)      # exact rotation path, no midpoint shrink
```

`camera.pose()` / `camera.affine()` are complete world-to-view targets.
`camera.pan()` is relative world-space camera motion (`V' = V @ T(-d)`), while
`zoom(..., about=...)` and `rotate_view(..., about=...)` take explicit
view-space pivot points. The low-level `scene.transform(scene.camera, to=...)`
form remains available. Dynamic provider-driven cameras reject timeline clips.

For common absolute motion, bound handles provide two deliberately small
constructor-like shorthands:

```python
# Complete rigid pose. Equivalent to transform(to=SE2(...)).
robot.pose(position=(3, 2), rotation=pi / 2)

# Complete affine target, always composed in this fixed order:
# Translation @ Rotation @ Shear @ Scale
shape.affine(position=(-3, 0), rotation=.2, scale=1.5, shear=(.1, 0))

# The same pure constructors are available inside procedural motion.
star.transform_function(
    lambda a: affine2d(rotation=TAU * a, scale=1.5 * a)
)
```

`pose()` and `affine()` both require `position=`. Omitted rotation/shear/scale use
their identity values; they never inspect the current transform and silently
preserve unspecified components. For relative motion, use `move`, `rotate`,
`scale`, or the full `transform(..., by=..., frame=...)` API. Bound `move()` also
accepts a numeric `(x, y)` tuple as an exact shorthand for `Vec2(x, y)`.

The Scene-level forms remain the complete low-level API and are mechanically
equivalent, for example `box.move(to=(2, 1))` delegates to
`scene.move(box.raw, to=Vec2(2, 1))`. The handle adds no implicit animation,
parallelism, copy, or replacement behavior.

For nested objects, `WORLD` motion is only accepted while the ancestor transform
chain is static over the same time span. Otherwise the requested world frame
would depend on a simultaneously moving parent; Zanim rejects that ambiguity
instead of silently approximating it. Articulated mechanisms should express joint
motion in `LOCAL` or `PARENT`.

After `Scene.add()`, direct public state assignment is rejected because it has no
time semantics:

```python
box.raw.opacity = 0          # error after add()
box.raw.transform = ...      # error after add()

box.opacity(to=0)            # explicit timeline state change
```

Scene operations record the clip first and then update the raw object's authored
target state. A bound handle exposes world-space `center`, `origin`, anchors, and
`transform_value`; `.raw` gives explicit access to the underlying authored object.
`scene.evaluate(t)` reconstructs the actual historical state at any time.

Object-to-object interpolation stays deliberately separate:

```python
scene.interpolate(source, target, duration=1.0)
```

It creates one extra transient relation and **does not modify either endpoint at
all**: no property, opacity, identity, add/remove state, or lifetime changes.
The original source and target continue rendering according to their own state.

A true visual/lifetime handoff is explicit instead:

```python
source = scene.add(source)       # target is intentionally not added
target = scene.replace(source, target, duration=1.0)
```

At the replacement start, `source` leaves the Scene; only the source->target
transient renders during the clip; at the clip end `target` begins its lifetime
with exactly the state it was declared with. `replace()` is a lifetime boundary
and is not allowed inside `parallel()`.

`Vec2` supports arithmetic (`3 * RIGHT + 0.5 * UP`) so spatial intent remains
readable without implicit coercions. The complete lifetime/state philosophy is
shown in `examples/showcase/state_model.py`.

## Frames and planar forward kinematics

Nested `Group` objects form a genuine transform tree. A child transform is
`T_parent_child`, so world pose is ordinary matrix composition:

```text
T_world_ee = T_world_1 @ T_1_2 @ ... @ T_n_ee
```

This is exactly open-chain forward kinematics. Revolute and prismatic joints are
just local rigid transforms:

```python
joint3 = Group([...], position=(L2, 0))
joint2 = Group([..., joint3], position=(L1, 0))
root = Group([link1, joint2])
root = scene.add(root)
joint2, joint3 = scene.on(joint2), scene.on(joint3)

home1 = SE2.from_affine(root.transform_value)
home2 = SE2.from_affine(joint2.transform_value)
home3 = SE2.from_affine(joint3.transform_value)

with scene.parallel(duration=5):
    root.transform_function(lambda a: home1 @ SE2(theta=q1(a)))
    joint2.transform_function(lambda a: home2 @ SE2(theta=q2(a)))
    joint3.transform_function(lambda a: home3 @ SE2(translation=q3(a) * RIGHT))
```

Each provider returns one complete local-to-parent pose; parent composition gives
the full FK automatically. `scene.world_transform(obj)` and
`scene.world_point(obj, local_point)` expose the resulting geometry without
including the camera/view transform. See `examples/showcase/kinematics.py`.

## Animation channels

The timeline deliberately uses explicit channels rather than a generic component/track framework:

- `TransformClip` — general affine interpolation for scene objects/groups/camera
- `SE2TransformClip` — rigid 2D interpolation that remains in SE(2)
- `TransformFunctionClip` — a pure `alpha -> Transform2D` channel for procedural motion without stateful updaters
- `DynamicVectorObject2D` — a pure absolute-time `VectorDocument` source; `zanim.vector.map_vector_document` applies nonlinear mappings directly to cubic control points
- `OpacityClip` — all visual objects/groups
- `StyleClip` — ordinary geometry style
- `PathTrimClip` — geometry path creation/trimming
- `BatchClip` — retained batch values
- `DynamicBatchObject2D` — pure absolute-time `LineSet` / `CircleSet` / `RectSet` providers for dense random-access batch animation
- `RevealClip` — vector/text/math reveal
- `ValueClip` — `ScalarValue`
- `PlaybackClip` — one scene-time → source-time mapping shared by images, GIF/video playback, and audio
- `InterpolationClip` — transient relation between distinct geometry objects; common open and closed primitives normalize to eight cubic segments for compatible morphing

`Scene.create()` uses path trim for geometry and vector reveal for text/math. `fade_in`/`fade_out` use the common opacity channel.

### Shared duration in parallel blocks

A parallel block may provide one local default duration for the animation calls
inside it:

```python
with scene.parallel(duration=1.6):
    shapes.move(by=(.8, .25), frame=WORLD)       # 1.6 s
    square.paint(fill=GREEN, stroke=WHITE)       # 1.6 s
    arrow.move(by=(.15, .1), frame=WORLD, at=.2) # starts at +.2, lasts 1.6 s
```

The default is only used when a clip omits `duration`. An explicit per-clip value
always wins:

```python
with scene.parallel(duration=1.6):
    a.fade_out()               # 1.6 s
    b.fade_out(duration=.4)    # .4 s
```

Outside that block, an omitted animation duration is still `1.0` second. The
default never changes `at=`, easing, channels, frame semantics, or the common
parallel base cursor. It is purely a local default-value scope. Media playback
keeps its existing `duration=None` meaning of deriving duration from the source.

## Coordinates and camera

- +x points right, +y points up.
- `(0, 0)` is the canvas center by default.
- `unit_size` is pixels per logical unit.
- object transforms are local-to-parent affine maps; `SE2` is the rigid subset.
- `LOCAL`, `PARENT`, and `WORLD` explicitly name the frame of relative motion.
- object transforms may still be arbitrary affine maps, including singular transforms.
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
    scene.media(image, duration=4)
    scene.media(gif, duration=4, loop=True)
    scene.media(video, duration=4, source_start=0.5, speed=1.25, loop=True)
    scene.media(audio, duration=4, source_start=0.5, speed=1.25, loop=True)
```

PNG/JPEG and GIF are decoded through Pillow. Video and audio use ffmpeg/ffprobe; `ffmpeg` must be available on `PATH`. Video uses a streaming raw-RGBA ffmpeg decoder with a bounded in-memory LRU, so decoded frame sequences are not written to disk. Rendering evaluates snapshots inside worker threads, so large raster frames are retained only for active workers rather than for the whole movie. Final audio mixing is sample-based at 48 kHz and muxed into the output MP4 as AAC.

Video output stays RGB-native through the renderer and streams finished RGB0 frames directly to ffmpeg/libx264. The default `veryfast` preset with four encoder threads is the measured throughput/memory sweet spot for the current frame-parallel renderer; `crf`, `preset`, and `encoder_threads` remain explicit tuning knobs. This single software path avoids GPU-specific startup, capability detection, and platform branches while producing standard H.264/yuv420p MP4 output.

Raster objects share the normal `transform`, `opacity`, `z_index`, bounds/layout helpers, camera transform, fade, and transform animation channels. The Zig backend performs inverse-affine bilinear sampling with source-over alpha compositing, so rotated/scaled raster media participates in the same ordered draw stream as vector and geometry content.

Web exposes matching `Image`, `GIF`, `Video`, and `Audio` runtime objects. Python Preview maps local media to opaque range-capable URLs and preserves `PlaybackClip` timing in the browser; these Preview resources are marked non-portable. Web `Math`/`Typst` compiles asynchronously to the same `VectorDocument` representation, while Web-authored Typst remains runtime-only and is intentionally excluded from Web→IR→MP4 export.

### Offscreen compositing and masks

`SceneRasterSource` renders any nested 2D `Scene` to a transparent, random-access RGBA source. `AlphaMaskSource` then combines two raster sources by alpha and supports time-dependent inversion and feathering. This is the common compositing boundary for shape masks, picture-in-picture, selective frame effects, and future blur/glow operations; geometry and vector renderers do not need mask-specific branches.

```python
from zanim.raster import AlphaMaskSource, RasterObject2D, SceneRasterSource

content = SceneRasterSource(content_scene)
mask = SceneRasterSource(mask_scene)
masked = RasterObject2D(AlphaMaskSource(content, mask), width=8)
```

## Math and plotting

- `Text` / `Math`: Typst -> SVG -> immutable `VectorDocument`.
- `FormulaTemplate`: Typst owns mathematical layout while fixed slots hold high-frequency numbers or embedded Zanim objects.
- `DynamicNumber` uses a cached Typst math glyph atlas; per-frame updates do not invoke Typst.
- `Axes` supplies coordinate mapping, plotting, dynamic area geometry, and numerical integration.
- `ScalarValue` (`zanim.value`) is a low-level random-access value source and can bind directly to `DynamicNumber` or formula slots.

## Common objects

Alongside raw primitives, the authoring layer includes `Dot`, `Arrow`, and `NumberLine` (with optional Typst tick labels). `Axes.axis_labels()` returns ordinary grouped math objects. More convenience objects should be added only when they remove repeated authoring work; they do not require new renderer mechanisms.

## Development

A source checkout needs Zig 0.16 to build the native renderer:

```bash
uv sync
zig build -Doptimize=ReleaseFast
./scripts/check.sh
```

Runtime rendering never invokes Zig. Platform wheels build the renderer once through the Hatch build hook and bundle it under `zanim/_native/`; Python verifies the native ABI when loading it. Build a local wheel with:

```bash
uv build --wheel
```

## Examples

Examples are curated rather than accumulated. [`examples/showcase/`](examples/showcase/) is a 12-lesson executable tutorial; [`examples/extras/`](examples/extras/) contains larger end-to-end animations. See [`examples/README.md`](examples/README.md) for the map.

Start the tutorial with the same product workflow used for your own scene files:

```bash
zanim preview examples/showcase/basics.py
```

Then continue in order through:

```text
basics → state_model → layout → timeline → transforms → vectors
       → math → batches → media → compositing → three_d → kinematics
```

Each showcase file is a plain top-level Python script using only public authoring APIs. `zanim preview` provides object names, runtime source mapping and manual `↻` reload without requiring a wrapper function or decorator.

The larger extras remain intentionally outside that teaching path:

```bash
uv run python examples/extras/fourier_draw.py --terms 36
uv run python examples/extras/neural_network.py
uv run python examples/extras/mnist_training.py
```

### JAnim effect-parity reference

`examples/janim_api/` is retained only as a regression/reference suite for visible JAnim API-demonstration effects. It is not a compatibility promise and does not define Zanim's public API.

```bash
PYTHONPATH=python uv run python -m examples.janim_api.suite all
```

## Optional extras

Task-specific features live outside the core authoring model when they do not justify a renderer or timeline primitive. Fourier SVG drawing is implemented in `zanim.extras.fourier` on top of the generic cubic-contour arc-length sampler in `zanim.path`:

```bash
uv run python examples/extras/fourier_draw.py --svg examples/assets/fourier_heart.svg --terms 36
```

The example selects one closed contour, computes its DFT, builds a head-to-tail epicycle chain, and draws the moving endpoint trace. The Fourier policy itself is not part of `Scene`, `Timeline`, or the Zig renderer.

## 3D rendering

Zanim uses one deterministic CPU render architecture for both 2D and 3D scene composition. `MeshObject3D` participates in the same `Scene`, timeline, absolute-time evaluation and ordered draw stream as 2D objects. A 3D camera contributes one `3d_layer` draw item; when that item is reached, the Zig software rasterizer draws triangles directly into the current RGB/RGBA scene framebuffer. There is no GPU context, framebuffer readback, temporary full-screen 3D `RasterFrame`, or second compositing pass.

The CPU 3D pipeline implements homogeneous frustum clipping, perspective/orthographic projection, back-face culling, a layer-local z-buffer, indexed vertex processing, perspective-correct smooth-normal interpolation, Lambert shading, and deterministic transparent-mesh sorting/source-over blending. Indexed meshes transform each unique vertex once per frame before triangle assembly. Because the renderer is stateless, video frames use the same worker-parallel pipeline as 2D scenes on Linux and Windows.

The root authoring API includes `Vec3`, `SO3`, `Transform3D`, `Camera3D`, `Box3D`, `Cube3D`, and `Surface3D`; custom `TriangleMesh` / `MeshObject3D` construction lives in `zanim.mesh3d`. The renderer stays below these semantics: authoring code never depends on rasterizer-specific types.

The curated syntax example is `examples/showcase/three_d.py`; the JAnim parity suite also contains a four-panel 3D shapes scene. Both use the same CPU renderer and ordinary Scene/Timeline semantics.
