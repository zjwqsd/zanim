# Zanim showcase — executable tutorial

This directory is the recommended way to learn Zanim. Each lesson is a small complete scene, and the ordering follows the framework's mental model rather than renderer internals.

Every lesson uses the product-default syntax: ordinary top-level Python with a `scene` variable. There is no `main()`, `build_scene()` wrapper or decorator.

The lessons also use the built-in palette (`BLUE`, `GREEN`, `RED`, `WHITE`, `MUTED`, etc.) and angle constants (`PI`, `TAU`, `DEGREES`) instead of redefining common values in every file. `Color(...)` is still used where a scene needs a deliberately custom color.

Use the same workflow for every lesson:

```bash
zanim preview examples/showcase/basics.py
```

`zanim preview` observes the file while it executes, so object variable names and clip source locations are still available in the Inspector. Scrub to any absolute time, edit/save the file, and press `↻`. To produce a file, replace `preview` with `render`.

| # | File | Learn this first |
|---:|---|---|
| 01 | `basics.py` | declare → layout → `Scene.add()` → bound handles → animate; style, groups and Preview |
| 02 | `state_model.py` | object lifetime is `[add, remove)`; fade/create are explicit state changes, not hidden `add()` behavior |
| 03 | `layout.py` | `Frame`, anchors, `place()`, `Row`/`Column`/`Grid`, one-time layout vs animated layout |
| 04 | `timeline.py` | sequential clips, `parallel()`, relative `at`, easing, transform functions and transient interpolation |
| 05 | `transforms.py` | the difference between `LOCAL`, `PARENT`, `WORLD`; nested frames and `Camera2D` |
| 06 | `vectors.py` | SVG import, immutable `VectorDocument`, `VectorObject2D`, reveal/create and resource reuse |
| 07 | `math.py` | plots, absolute-time dynamic geometry, Typst formulas, dynamic slots and deterministic providers |
| 08 | `batches.py` | hundreds/thousands of primitives with `BatchObject2D`; batch transitions without object explosion |
| 09 | `media.py` | image/GIF/video/audio on the same absolute-time timeline, looping and source offsets |
| 10 | `compositing.py` | offscreen `SceneRasterSource`, `AlphaMaskSource`, feathering and raster composition |
| 11 | `three_d.py` | `Camera3D`, meshes, surfaces, SO(3), `Transform3D`, and ordinary 2D overlays in one Scene |
| 12 | `kinematics.py` | capstone: nested `Group` frames, SE(2), function transforms and robot-style forward kinematics |
| 13 | `infinite_space.py` | linear algebra on native unbounded `InfiniteGrid`/`InfiniteLine`, synchronized with finite reference geometry |

## What to pay attention to

### 01–03: authoring state

Do not think of Zanim as a sequence of imperative drawing commands. Objects are declared and laid out first; `Scene.add()` establishes temporal lifetime; Timeline operations then describe state as a function of absolute time.

```text
declare → layout → add → animate
```

### 04–05: time and space

These lessons establish the two rules that make larger scenes predictable:

```text
Frame = F(t)
local → parent → world → camera → device
```

Once those are clear, random-access Preview and nested articulated structures are natural consequences rather than special features.

### 06–11: representations

Geometry, imported vector data, dense batches, raster media and 3D meshes use different efficient representations but share Scene lifetime, transforms, opacity, ordering and Timeline semantics. Choose the representation that matches the data; do not rebuild everything as individual shapes.

### 12–13: combine the pieces

`kinematics.py` intentionally contains no special robotics subsystem. The arm is ordinary nested groups and SE(2) transforms. It demonstrates the goal of Zanim's core design: domain-specific animations should emerge from reusable scene/time/space primitives.

## Suggested exercises

After each lesson, make one small modification and inspect it in Preview instead of only reading the code:

1. change a color and timing in `basics.py`;
2. move `remove()` earlier in `state_model.py` and scrub exactly across the lifetime boundary;
3. add a fifth object to the layouts;
4. change one `parallel()` offset;
5. enable the `⊹` local-frame overlay on nested objects in `transforms.py`;
6. replace `fourier_heart.svg` with another simple SVG;
7. change a dynamic provider in `math.py`;
8. double the primitive count in `batches.py`;
9. change media source speed/offset;
10. change the moving mask or feather amount in `compositing.py`;
11. alter the 3D camera;
12. change one joint law in `kinematics.py`;
13. apply more 2×2 matrices in `infinite_space.py`; the infinite plane and reference polygon must stay synchronized, including singular maps.
