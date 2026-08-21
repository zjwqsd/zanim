"""Explicit layout: declare objects, place them, then animate between layouts."""
from __future__ import annotations

from pathlib import Path

from zanim import (
    TOP, BOTTOM, Canvas, Circle, Color, Column, Grid, Group2D,
    Object2D, Rectangle, RegularPolygon, Row, Scene, Square, Text,
    DOWN, Vec2, WORLD,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/showcase/layout.mp4"

BLUE = Color(83, 146, 255)
ORANGE = Color(255, 151, 92)
GREEN = Color(91, 220, 166)
PURPLE = Color(185, 122, 255)
MUTED = Color(155, 170, 200)



def build_scene() -> Scene:
    scene = Scene(canvas=Canvas(1280, 720, 90), fps=60)

    # 1. Declare objects. No position is hidden in the constructors.
    title = Text("Declare → layout → animate", font_size=34)
    note = Text("layout is an explicit target, not a persistent constraint", font_size=21, color=MUTED)

    tile_stroke = Color(225, 235, 255)
    square = Object2D(Square(1.0), fill=BLUE.with_alpha(185), stroke=tile_stroke)
    circle = Object2D(Circle(0.55), fill=ORANGE.with_alpha(185), stroke=tile_stroke)
    triangle = Object2D(RegularPolygon(3, 0.68), fill=GREEN.with_alpha(185), stroke=tile_stroke)
    card = Object2D(Rectangle(1.35, 0.82), fill=PURPLE.with_alpha(185), stroke=tile_stroke)
    group = Group2D([square, circle, triangle, card])

    # 2. Initial layout is a one-time authoring operation before Scene.add().
    header = scene.frame.top_region(height=1.25)
    content = scene.frame.inset(0.7).below(header, gap=0.25)

    title.place(anchor=TOP, at=header.top + 0.28 * DOWN)
    note.place(anchor=TOP, at=title.anchor(BOTTOM) + 0.14 * DOWN)
    Row(gap=0.75, at=content.center).place(*group.children)

    # 3. Only now do the objects enter the timeline.
    title, note, group = scene.add(title, note, group)
    square, circle, triangle, card = group.children
    scene.wait(0.7)

    # Every child remains the same object and can move independently.
    with scene.parallel(duration=1.2):
        square.move(by=(-1.5, 1.0), frame=WORLD)
        circle.rotate(by=0.9, about=circle.center)
        triangle.scale(by=1.45, about=triangle.center)
        card.move(by=(1.3, -0.9), frame=WORLD)

    scene.wait(0.35)

    # A layout specification computes four transform targets. Scene.layout()
    # schedules all four child transforms in parallel.
    scene.layout(
        group,
        to=Row(gap=0.75, at=content.center),
        duration=1.0,
    )

    scene.wait(0.3)
    scene.layout(
        group,
        to=Grid(rows=2, cols=2, gap=Vec2(0.9, 0.65), at=content.center),
        duration=1.1,
    )

    scene.wait(0.3)
    scene.layout(
        group,
        to=Column(gap=0.38, at=content.center),
        duration=1.1,
    )

    scene.wait(0.3)
    scene.layout(
        group,
        to=Row(gap=0.75, at=content.center),
        duration=1.0,
    )

    scene.wait(0.4)
    return scene


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scene = build_scene()
    print(scene.render_video(OUTPUT, verify_random_access=True))


if __name__ == "__main__":
    main()
