# 3Blue1Brown 2026 reconstruction track

This directory is a visual/architectural regression suite for rebuilding the
2026 videos from `3b1b/videos` with Zanim's own scene and timeline model.
It is not an API-port of Manim. Reusable gaps are promoted into Zanim only when
the examples demonstrate that a general primitive is justified.

Reference source is kept outside the repository under
`~/.cache/zanim/reference/3b1b-videos/`.

## 2026-01-16 — The ladybug clock puzzle

Implemented in `ladybug_clock.py`:

- `Ladybug`
- `Question`

Render:

```bash
uv run python -m examples.manim_2026.ladybug_clock all
```

Use `--draft` for 960x540 / 30 fps previews.

## 2026-01-31 — The Hairy Ball Theorem

The main scenes in `_2026/hairy_ball/spheres.py` and `model3d.py` are strongly
3D-oriented (sphere surfaces, 3D vector fields, camera orbits, stereographic
projection, inside-out surface deformation), so they are intentionally deferred
until Zanim has a real 3D renderer.

The reusable 2D teaching/supplement scenes are reconstructed in
`hairy_ball_2d.py`:

- `RenameTheorem`
- `SimpleImplies`
- `WingVectCodeSnippet`
- `LazyPerpCodeSnippet`
- `StatementOfTheorem`
- `WriteAntipode`
- `ThreeCases`
- `ProofOutline`
- `TwoFactsForEachPoint`
- `TwoKeyFeatures`
- `InsideOutsideQuestion`
- `PToNegP`
- `SimplerInsideOutProgression`
- `FluxDecimals`
- `FrameIntuitionVsExamples`
- `DimensionGeneralization`
- `RotationIn2D`
- `HypersphereWords`

Render all 2D scenes:

```bash
uv run python -m examples.manim_2026.hairy_ball_2d all
```

Or a single scene:

```bash
uv run python -m examples.manim_2026.hairy_ball_2d ProofOutline
```

Use `--draft` for 960x540 / 30 fps previews.

Implementation notes:

- Number-plane/grid geometry uses retained `LineSet` batches rather than one
  scene object per line/cell.
- Motion remains absolute-time/random-access; no Manim-style stateful updaters
  were introduced.
- Text-substring styling is expressed with small composed text objects and
  crossfades for now. These examples do not yet justify a new rich-text
  selection API in core.
- PiCreature/classroom reaction shots are not treated as a core engine
  requirement; the mathematical content is represented directly in the 2D
  supplement scenes.
