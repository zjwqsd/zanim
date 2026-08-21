"""Plots and fixed-layout dynamic Typst formulas driven by absolute scene time."""
from __future__ import annotations

from math import sin
from pathlib import Path
import random

from zanim import (
    Axes2D, Canvas, Color, DynamicGeometryObject2D, FormulaLiteral,
    FormulaTemplate, MatrixSlot, NumberFormat, NumberSlot, Scene, ScriptSlots,
    StrokeStyle, Style, Text, Transform2D, Vec2,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/showcase/math.mp4"


def f(x: float) -> float:
    return 1.2 + 0.5 * sin(1.2 * x) + 0.055 * x * x


def lower(t: float) -> float:
    return -2.6 + 0.7 * sin(0.9 * t)


def upper(t: float) -> float:
    return 1.5 + 0.8 * sin(1.1 * t + 0.8)


def matrices(t: float):
    tick = int(max(0.0, t - 0.4) * 3.0)
    rng = random.Random(20260821 + tick * 1009)
    a = tuple(tuple(rng.randint(-4, 4) for _ in range(2)) for _ in range(2))
    b = tuple(tuple(rng.randint(-4, 4) for _ in range(2)) for _ in range(2))
    c = tuple(tuple(sum(a[i][k] * b[k][j] for k in range(2)) for j in range(2)) for i in range(2))
    return a, b, c


def build_scene() -> Scene:
    scene = Scene(canvas=Canvas(1920, 1080, 105), fps=60)
    title = Text("Dynamic geometry and dynamic math", font_size=33, transform=Transform2D.translation(0, 4.35))
    scene.add(title)

    axes = Axes2D(x_range=(-4, 4), y_range=(-0.4, 3.2), width=9.0, height=5.5, center=Vec2(-4.0, -0.8))
    grid = axes.grid_object(x_step=1.0, y_step=0.5)
    axes_lines = axes.axes_object(color=Color(150, 160, 183, 220), width=0.022)
    area = DynamicGeometryObject2D(
        lambda t: axes.area_polygon(f, lower(t), upper(t), samples=120),
        style=Style(fill=Color(78, 139, 255, 105), stroke=StrokeStyle(Color(112, 170, 255), 0.018)),
    )
    graph = axes.plot(f, samples=260, color=Color(118, 205, 255), stroke_width=0.04)
    scene.add(grid, area, axes_lines, graph)

    integral = FormulaTemplate(
        ScriptSlots(
            "integral",
            sub=NumberSlot("a", NumberFormat(width=5, decimals=1, sign="space"), font_size=20, color=Color(255, 180, 105)),
            sup=NumberSlot("b", NumberFormat(width=5, decimals=1, sign="space"), font_size=20, color=Color(82, 220, 180)),
        ),
        FormulaLiteral("f(x) dif x =", font_size=30),
        NumberSlot("value", NumberFormat(width=8, decimals=3, sign="space"), font_size=25, color=Color(255, 220, 145)),
        font_size=30,
    )
    integral.mount(
        scene,
        {
            "a": lower,
            "b": upper,
            "value": lambda t: axes.integral_value(f, lower(t), upper(t), samples=120),
        },
        transform=Transform2D.translation(3.7, 2.25),
    )

    small = NumberFormat(width=2, sign="negative")
    product = FormulaTemplate(
        MatrixSlot("A", 2, 2, small, font_size=31),
        FormulaLiteral(" times ", font_size=29),
        MatrixSlot("B", 2, 2, small, font_size=31),
        FormulaLiteral(" = ", font_size=29),
        MatrixSlot("C", 2, 2, NumberFormat(width=3, sign="negative"), font_size=31, color=Color(255, 177, 102)),
        gap=0.0,
        font_size=31,
    )
    product.mount(
        scene,
        {
            "A": lambda t: matrices(t)[0],
            "B": lambda t: matrices(t)[1],
            "C": lambda t: matrices(t)[2],
        },
        transform=Transform2D.translation(3.7, -1.2),
    )

    scene.fade_in(title, duration=0.7)
    scene.wait(5.3)
    return scene


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scene = build_scene()
    print(scene.render_video(OUTPUT, verify_random_access=True))


if __name__ == "__main__":
    main()
