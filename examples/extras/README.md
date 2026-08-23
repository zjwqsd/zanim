# Zanim extras

These are deliberately not part of the step-by-step tutorial. They are larger end-to-end examples built from ordinary Zanim primitives.

- `fourier_draw.py` imports an SVG contour, computes a Fourier decomposition, draws the epicycle chain, and can drive a dynamic camera that follows the drawing tip.
- `hilbert_curve.py` starts from the first-order Hilbert curve and morphs through progressively finer recursive orders.
- `fractals.py` presents Koch snowflake, Sierpiński arrowhead, Heighway dragon, and Lévy C curve as continuous order-by-order morphs.
- `sorting_algorithms.py` visualizes bubble, selection, insertion, merge, quick, and heap sort on the same shuffled permutation of line lengths `1..n`.
- `modular_multiplication.py` continuously varies the multiplier in a modular multiplication circle, revealing cardioid-like and higher-order line envelopes.
- `de_casteljau.py` visualizes cubic Bézier construction as repeated linear interpolation `4 → 3 → 2 → 1`, while the final point traces the curve.
- `complex_mapping.py` uses the native Zig `ComplexMappedGrid`: target pixels are analytically inverse-mapped to an infinite source lattice for `z^2`, `e^z - 1`, `1/z`, and Möbius maps, with no finite source window or Python polyline sampling.
- `midi_piano.py` parses Standard MIDI files into falling note blocks over a full 88-key piano; note-on/contact, key press, audio, and note-off/trailing-edge arrival share the same absolute timeline.
- `red_black_tree.py` inserts a seeded random key sequence and animates red-black recolors plus left/right rotations until every insertion is repaired.
- `neural_network.py` visualizes forward/backward signal propagation with dense batch geometry.
- `mnist_training.py` trains a real NumPy 784→8→10 MLP and visualizes eight epochs, exact weights/gradients, metrics and inference. It is also a useful performance stress test.

Every official extra also exposes the same default `build_scene() -> Scene` entry as the tutorial, so the generic product commands work uniformly:

```bash
zanim preview examples/extras/fourier_draw.py
zanim preview examples/extras/hilbert_curve.py
zanim preview examples/extras/fractals.py
zanim preview examples/extras/red_black_tree.py
zanim preview examples/extras/sorting_algorithms.py
zanim preview examples/extras/modular_multiplication.py
zanim preview examples/extras/de_casteljau.py
zanim preview examples/extras/complex_mapping.py
zanim preview examples/extras/midi_piano.py
zanim preview examples/extras/neural_network.py
zanim preview examples/extras/mnist_training.py
```

`mnist_training.py` performs its real NumPy training before the Preview opens, so its first startup is intentionally heavier. For task-specific options, run the scripts directly:

```bash
uv run python examples/extras/fourier_draw.py --terms 36 --follow
uv run python examples/extras/hilbert_curve.py --max-order 6
uv run python examples/extras/fractals.py --section dragon
uv run python examples/extras/red_black_tree.py --seed 19 --count 12
uv run python examples/extras/sorting_algorithms.py --n 24 --seed 23
uv run python examples/extras/modular_multiplication.py --points 240 --end 12
uv run python examples/extras/de_casteljau.py --duration 7
uv run python examples/extras/complex_mapping.py --output media/extras/complex_mapping.mp4
uv run python examples/extras/midi_piano.py path/to/song.mid
uv run python examples/extras/midi_piano.py path/to/song.mid --synth soundfont
uv run python examples/extras/midi_piano.py path/to/song.mid --synth builtin
uv run python examples/extras/midi_piano.py examples/assets/canon_in_d.mid --output media/extras/canon_in_d.mp4
uv run python examples/extras/mnist_training.py --dry-run
```

Task-specific helpers stay outside the core when they do not justify a general Scene/Timeline primitive. Fourier utilities, for example, live in `zanim.extras.fourier` rather than in the renderer.

`midi_piano.py` uses `libfluidsynth` plus an installed `.sf2` SoundFont automatically when available, preferring `FluidR3_GM.sf2`; otherwise it falls back to its dependency-free built-in synth. Use `--soundfont path/to/piano.sf2` to choose another SoundFont. SoundFont playback keeps its natural piano release and reverb, so MIDI note-on timing stays exact while the acoustic decay may continue briefly after the falling note's trailing edge.
- `mandelbrot_julia.py` renders native viewport-resolved Mandelbrot and Julia sets; zooming recomputes the unbounded complex field in Zig rather than scaling a finite texture.
