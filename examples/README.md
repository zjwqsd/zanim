# Zanim examples

The examples have two jobs and are kept separate on purpose:

- [`showcase/`](showcase/) is the executable tutorial. Read it in order; every file is a plain top-level Python scene using only public Zanim authoring APIs; no `main()`, builder function or decorator is required.
- [`extras/`](extras/) contains complete, heavier animations that show what the framework can do after the tutorial concepts are familiar.

`janim_api/` remains a regression/reference suite for reproducing visible JAnim API-demonstration effects. It is not part of the learning path and does not define Zanim's API design.

## Requirements

The `examples/` directory is self-contained for bundled SVG/media assets. Text and Math examples require Typst, and the MNIST extra additionally requires NumPy and local MNIST raw data under `examples/assets/MNIST/raw/`. Install the Python example dependency with `zanim[examples]` when using a published package.

## Start here

```bash
zanim info
zanim preview examples/showcase/basics.py
```

Edit `basics.py`, save it, then press `↻` in Preview. Continue through [`showcase/README.md`](showcase/README.md) in order.

To render instead of previewing:

```bash
zanim render examples/showcase/basics.py -o basics.mp4
zanim render examples/showcase/basics.py --time 2.5 -o frame.png
```

## Extras

After the showcase, the same Preview command works for the larger demos:

```bash
zanim preview examples/extras/fourier_draw.py
zanim preview examples/extras/neural_network.py
zanim preview examples/extras/mnist_training.py
```

The scripts can still be run directly when you want their task-specific flags.

See [`extras/README.md`](extras/README.md) for what each one demonstrates.
