# Themes and configuration

Zanim themes are runtime authoring defaults. They do not rewrite existing objects: a theme is read when a new Scene/object is created or when an omitted animation default is resolved. Explicit constructor/timeline arguments always win.

The built-in `manim` theme is the default. Its canonical frame uses Manim-style defaults: 1920×1080, 8 world units high (`unit_size=135`), 60 fps, black background, white non-scaling strokes, 48pt text/math, one-second animations, and `smooth` easing.

## Python

```python
from zanim import *

# Already the startup default.
set_theme("manim")

scene = Scene()
square = scene.add(Square(2))
square.rotate(by=PI / 2)
```

A derived theme can be used temporarily without mutating global process state:

```python
paper = MANIM.with_overrides({
    "name": "paper",
    "canvas": {"background": "#f7f4ed"},
    "style": {"stroke": "#20242a", "stroke_width": 0.03},
    "text": {"color": "#20242a"},
    "math": {"color": "#20242a"},
})

with use_theme(paper):
    scene = Scene()
```

Register a derived theme when it should be selectable by name:

```python
register_theme(paper)
set_theme("paper")
```

## Configuration files

The configuration representation uses snake_case and is shared by Python JSON/TOML and Web JSON.

```toml
[theme]
base = "manim"
name = "paper"
mesh3d_color = "#58c4dd"

[theme.canvas]
background = "#f7f4ed"
fps = 30

[theme.style]
stroke = "#20242a"
stroke_width = 0.03

[theme.text]
font_size = 46
color = "#20242a"

[theme.math]
font_size = 46
color = "#20242a"

[theme.animation]
duration = 0.8
wait_duration = 0.5
easing = "smooth"

[theme.shape]
dot_radius = 0.07
arrow_tip_length = 0.32
arrow_tip_width = 0.32
arrow_buff = 0.2
```

Load and activate it explicitly:

```python
apply_config("zanim.toml")
```

CLI authoring commands can apply the same file before importing the scene:

```bash
zanim preview scene.py --config zanim.toml
zanim render scene.py --config zanim.toml -o scene.mp4
zanim export-ir scene.py --config zanim.toml -o scene.zanim.json
```

If `--config` is omitted, those commands honor `ZANIM_CONFIG`. `render-ir` does not apply a theme because Scene IR already stores the authored canvas/background/style state.

`load_config(...)` parses without changing the current theme. `apply_config(...)` parses and switches. `ZANIM_CONFIG=/path/to/zanim.toml` can be consumed through `zanim.config.load_default_config()` by applications that want environment-selected configuration.

Normal RGB/image/video rendering uses `theme.canvas.background`. Transparent RGBA scene rasters remain transparent by design so masks and compositing are unaffected by the presentation theme.

## Web

```js
import { MANIM, Scene, Square, setTheme } from '@zanim/web'

setTheme('manim')
const scene = await Scene.create('#canvas')
scene.add(new Square(2)).rotate(Math.PI / 2)
```

Browser configuration uses the same snake_case representation:

```js
import { applyConfig } from '@zanim/web'

await applyConfig('/zanim.json')
```

or apply an in-memory object:

```js
await applyConfig({
  theme: {
    base: 'manim',
    canvas: { background: '#f7f4ed' },
    style: { stroke: '#20242a', stroke_width: 0.03 },
  },
})
```

The browser renderer treats the built-in canvas dimensions as a canonical frame. When the DOM canvas is responsive and `unitSize` is not explicitly supplied, the unit scale follows the rendered height, so a 1280×720 canvas uses 90 px/unit while retaining the same 14.22×8 logical frame as the canonical 1920×1080 theme.

## What belongs in a theme

Themes control defaults that describe ordinary authoring appearance and timing: canvas/frame defaults, background, global fill/stroke, text/math appearance, default animation duration/easing, common Dot/Arrow geometry, and base 3D color.

Semantically meaningful object-specific styles remain object defaults rather than theme values. For example, a highlight rectangle may remain yellow and coordinate axes may intentionally use distinct x/y colors. This keeps themes from becoming a bag of every constructor argument in the engine.
