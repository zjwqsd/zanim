from __future__ import annotations

import math

from zanim import (
    RIGHT,
    WORLD,
    Canvas,
    Circle,
    Color,
    Easing,
    Group,
    Rectangle,
    Scene,
    Style,
    Text,
    Transform2D,
    Vec2,
    affine2d,
)
from zanim.batch import BatchObject2D, CircleSet
from zanim.geometry import PolygonGeometry
from zanim.plot import DynamicGeometryObject2D
from zanim.raster import AlphaMaskSource, RasterObject2D, SceneRasterSource

WHITE = Color(245, 247, 251)
YELLOW = Color(248, 210, 68)
LIGHT_BROWN = Color(183, 139, 100)
PURPLE_E = Color(92, 55, 130)
MASK_CANVAS = Canvas(width=960, height=540, unit_size=67.5)
FRAME_W = MASK_CANVAS.width / MASK_CANVAS.unit_size
FRAME_H = MASK_CANVAS.height / MASK_CANVAS.unit_size


def _subscene() -> Scene:
    return Scene(canvas=MASK_CANVAS, fps=30)


def _full(source) -> RasterObject2D:
    return RasterObject2D(source, width=FRAME_W, height=FRAME_H)


def _smooth(a: float) -> float:
    a = max(0.0, min(1.0, a))
    return a * a * (3 - 2 * a)


def _rect_circle_polygon(
    t: float, *, width=6.1, height=1.25, radius=1.25, count=64
) -> PolygonGeometry:
    a = _smooth(t)
    pts = []
    for i in range(count):
        angle = math.tau * i / count
        c, s = math.cos(angle), math.sin(angle)
        scale = min(width / (2 * max(abs(c), 1e-9)), height / (2 * max(abs(s), 1e-9)))
        rx, ry = c * scale, s * scale
        cx, cy = c * radius, s * radius
        pts.append(Vec2(rx + (cx - rx) * a, ry + (cy - ry) * a))
    return PolygonGeometry(tuple(pts))


def _stage1(duration=4.0) -> Scene:
    content = _subscene()
    chars = [Text(ch, font_size=56) for ch in "Mask Example!"]
    group = Group(chars)
    group.arrange(RIGHT, buff=0.015)
    group.move_to(Vec2(0, 0.45))
    finals = [c.transform for c in chars]
    for c in chars:
        c.shift(Vec2(0, -1.65))
    content.add(group)
    with content.parallel():
        for i, (c, target) in enumerate(zip(chars, finals)):
            content.transform(
                c, to=target, duration=1.15, easing=Easing.SMOOTHSTEP, at=0.55 + i * 0.09
            )
    content.wait(max(0.0, duration - content.duration))

    mask = _subscene()
    mask.add(Rectangle(6.25, 1.28, position=(0, 0.45), fill=WHITE))
    mask.wait(duration)

    stage = _subscene()
    stage.add(_full(AlphaMaskSource(SceneRasterSource(content), SceneRasterSource(mask))))
    stage.media(stage.objects[0], duration=duration)
    return stage


def _stage2(duration=9.8) -> Scene:
    content = _subscene()
    txt = Text("Mask Example!", font_size=64)
    txt2 = Text("The mask should be hold", font_size=54, opacity=0)
    content.add(txt, txt2)
    left = Transform2D.translation(-1, 0)
    right = Transform2D.translation(1, 0)
    with content.parallel():
        content.transform(txt, to=left, duration=0.9, at=3.0)
        content.transform(txt, to=right, duration=0.9, at=3.9)
        content.transform(txt, to=Transform2D(), duration=0.9, at=4.8)
        content.fade_out(txt, duration=1.0, at=6.1)
        content.fade_in(txt2, duration=1.0, at=6.1)
    content.wait(max(0.0, duration - content.duration))

    mask = _subscene()
    shape = DynamicGeometryObject2D(
        lambda t: _rect_circle_polygon(min(1.0, t / 1.1)),
        transform=affine2d(position=(0, 0.5)),
        style=Style.solid(WHITE),
    )
    mask.add(shape)
    mask.wait(duration)

    def feather(t):
        return 0.0 if t < 2.4 else 10.0 * _smooth((t - 2.4) / 1.0)

    masked = AlphaMaskSource(SceneRasterSource(content), SceneRasterSource(mask), feather=feather)

    stage = _subscene()
    brown = Rectangle(3, 3, fill=LIGHT_BROWN, opacity=0, z_index=-2)
    layer = _full(masked)
    layer.z_index = 1
    stage.add(brown, layer)
    with stage.parallel():
        stage.media(layer, duration=duration)
        stage.fade_in(brown, duration=0.8, at=1.8)
        stage.fade_out(brown, duration=0.8, at=7.9)
    return stage


def _circle_mask(center: Vec2, duration: float) -> SceneRasterSource:
    sc = _subscene()
    sc.add(Circle(1.5, position=center, fill=WHITE))
    sc.wait(duration)
    return SceneRasterSource(sc)


def _stage3(duration=6.0) -> Scene:
    text = _subscene()
    label = Text("Some Example Text Here", font_size=44)
    text.add(label)
    text.wait(duration)
    text_source = SceneRasterSource(text)
    m1 = _circle_mask(Vec2(-1, 0), duration)
    m2 = _circle_mask(Vec2(1, 0), duration)
    union_scene = _subscene()
    union_scene.add(
        Circle(1.5, position=(-1, 0), fill=WHITE),
        Circle(1.5, position=(1, 0), fill=WHITE),
    )
    union_scene.wait(duration)
    union = AlphaMaskSource(text_source, SceneRasterSource(union_scene))
    intersection_mask = AlphaMaskSource(m1, m2)
    intersection = AlphaMaskSource(text_source, intersection_mask)

    stage = _subscene()
    d1 = Circle(1.5, position=(-1, 0), fill=YELLOW.with_alpha(64))
    d2 = Circle(1.5, position=(1, 0), fill=YELLOW.with_alpha(64))
    u = _full(union)
    i = _full(intersection)
    stage.add(d1, d2, u, i)
    # union -> intersection -> union, with brief holds matching the reference rhythm
    stage.media(u, duration=1.8)
    stage.media(i, duration=1.2)
    stage.media(u, duration=1.2)
    stage.wait(duration - stage.duration)
    return stage


def _stage4(duration=8.9) -> Scene:
    content = _subscene()
    centers = tuple(
        Vec2(i * 0.3 + 0.15, j * 0.3) for j in range(20, -40, -1) for i in range(-23, 23)
    )
    dots = BatchObject2D(
        CircleSet(centers, tuple(0.10 for _ in centers), tuple(PURPLE_E for _ in centers))
    )
    dots = content.add(dots)
    dots.move(by=(0, 3), frame=WORLD, duration=5.0, easing=Easing.LINEAR)
    content.wait(duration - content.duration)

    mask = _subscene()
    fashion = Text("Fashion", font_size=250)
    mask.add(fashion)
    mask.wait(duration)

    def invert(t):
        return _smooth((t - 4.7) / 0.9)

    masked = AlphaMaskSource(
        SceneRasterSource(content), SceneRasterSource(mask), invert=invert, feather=1.5
    )
    stage = _subscene()
    layer = _full(masked)
    stage.add(layer)
    stage.media(layer, duration=duration)
    return stage


def build_mask_example() -> Scene:
    main = Scene(canvas=Canvas(width=1920, height=1080, unit_size=135), fps=30)
    for stage in (_stage1(), _stage2(), _stage3(), _stage4()):
        source = SceneRasterSource(stage)
        obj = RasterObject2D(source, width=1920 / 135, height=1080 / 135)
        obj = main.add(obj)
        obj.media(duration=source.duration)
    return main
