# Notebook support

Zanim treats Jupyter as an output environment, not as a separate authoring mode.

There are no magics, cell hooks, source tracking, notebook reload semantics, widgets, or notebook-specific Preview server.

## Usage

Write ordinary Zanim code:

```python
from zanim import *

scene = Scene()
circle = scene.add(Circle(1, fill=Color(80, 150, 255)))
circle.move(to=(2, 0), duration=2)
```

In a Jupyter kernel, render inline by leaving this as the cell result:

```python
scene.render()
```

Behavior is selected from the same Scene semantics used everywhere else:

- static Scene -> inline PNG;
- `scene.render(time=1.5)` -> inline PNG at absolute time 1.5;
- animated Scene -> inline MP4;
- `scene.render(start=2, end=5)` -> inline MP4 for that absolute-time interval.

Saving output remains unchanged:

```python
scene.render("final.mp4")
scene.render("frame.png", time=1.5)
```

Outside a Jupyter notebook, omitting the path is an error. This prevents `render()` from silently inventing files or changing terminal behavior.

## Preview

Notebook support does not change `scene.preview()`.

The full interactive Preview remains the `.py`/CLI development tool, including random-access inspection and source-aware reload:

```bash
zanim preview demo.py
```

## Implementation boundary

`zanim.notebook` is intentionally small:

- detect an IPython kernel lazily, without making IPython a base dependency;
- render through the existing `Scene.render()` paths;
- read the completed PNG/MP4 into a display object;
- remove the temporary file immediately;
- expose `_repr_png_()` for images or `_repr_html_()` for embedded MP4 video.

Scene, Timeline, renderer, ABI, source tracking and Preview are unchanged.
