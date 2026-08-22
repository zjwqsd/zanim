# Zanim extras

These are deliberately not part of the step-by-step tutorial. They are larger end-to-end examples built from ordinary Zanim primitives.

- `fourier_draw.py` imports an SVG contour, computes a Fourier decomposition, draws the epicycle chain, and can drive a dynamic camera that follows the drawing tip.
- `neural_network.py` visualizes forward/backward signal propagation with dense batch geometry.
- `mnist_training.py` trains a real NumPy 784→8→10 MLP and visualizes eight epochs, exact weights/gradients, metrics and inference. It is also a useful performance stress test.

Every official extra also exposes the same default `build_scene() -> Scene` entry as the tutorial, so the generic product commands work uniformly:

```bash
zanim preview examples/extras/fourier_draw.py
zanim preview examples/extras/neural_network.py
zanim preview examples/extras/mnist_training.py
```

`mnist_training.py` performs its real NumPy training before the Preview opens, so its first startup is intentionally heavier. For task-specific options, run the scripts directly:

```bash
uv run python examples/extras/fourier_draw.py --terms 36 --follow
uv run python examples/extras/mnist_training.py --dry-run
```

Task-specific helpers stay outside the core when they do not justify a general Scene/Timeline primitive. Fourier utilities, for example, live in `zanim.extras.fourier` rather than in the renderer.
