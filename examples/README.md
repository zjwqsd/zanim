# Zanim examples

The examples are intentionally small in number. Each file should either teach a distinct part of the public authoring API or be interesting enough to stand on its own as an animation.

## Start here: `showcase/`

| Example | What it demonstrates |
| --- | --- |
| `basics.py` | declare → layout → `add()` bound handles → animate, `Frame`, anchors, groups, styles, camera transforms |
| `state_model.py` | Zanim design philosophy: temporal `add/remove`, explicit entrance state, no hidden pre-state |
| `layout.py` | independent child motion, `place()`, `scene.layout()`, Row → Grid → Column transitions |
| `kinematics.py` | SE(2), local→parent Group2D composition, `transform_function()`, revolute/prismatic open-chain FK |
| `timeline.py` | sequential clips, `parallel(duration=...)`, relative `at`, transform functions, and pure transient `interpolate()` |
| `math.py` | `Axes2D`, dynamic geometry, `FormulaTemplate`, `NumberSlot`, `MatrixSlot`, absolute-time providers |
| `batches.py` | `BatchObject2D`, `CircleSet`, `LineSet`, bound `batch(to=...)` state animation for hundreds of primitives |
| `media.py` | image, GIF, video, audio, looping, source offsets and synchronized transforms |
| `three_d.py` | `Camera3D`, meshes, `Surface3D`, `SO3`, `Transform3D`, 2D overlays over 3D |

Run one directly, for example:

```bash
uv run python examples/showcase/basics.py
uv run python examples/showcase/state_model.py
uv run python examples/showcase/layout.py
uv run python examples/showcase/math.py
uv run python examples/showcase/three_d.py
uv run python examples/showcase/kinematics.py
```

## `fun/`

These are complete animations rather than API checklists.

- `fourier_draw.py` reconstructs an SVG contour with Fourier epicycles and optionally follows the drawing tip with a dynamic camera.
- `neural_network.py` visualizes signal propagation through a self-contained neural network using batch geometry.
- `mnist_training.py` trains the real NumPy 784→8→10 MNIST MLP in-process and explains all eight epochs. W1 is shown as eight complete 28×28 learned-weight maps, W2 keeps all 80 connections, and each backward phase uses the exact epoch-accumulated gradient `G_e = (W_e - W_{e+1}) / eta` before animating the update.

```bash
uv run python examples/fun/fourier_draw.py --terms 36
uv run python examples/fun/fourier_draw.py --terms 36 --follow
uv run python examples/fun/neural_network.py
uv run python examples/fun/mnist_training.py
```

## Reference suites

`janim_api/` recreates the visible results of JAnim's official API demonstration. It is a parity/regression suite, not an attempt to copy JAnim's API design.

```bash
PYTHONPATH=python uv run python -m examples.janim_api.suite all
```

`manim_2026/` contains effect-oriented reproductions from the 3Blue1Brown/Manim video repository. These stay separate from the curated Zanim API showcase because their purpose is compatibility exploration rather than teaching the smallest Zanim syntax.
