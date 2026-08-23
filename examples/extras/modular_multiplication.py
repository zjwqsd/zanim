"""Animate modular multiplication on a circle as the multiplier changes continuously."""

from __future__ import annotations

import argparse
from math import cos, sin, tau
from pathlib import Path

from zanim import (
    CYAN,
    MUTED,
    WHITE,
    YELLOW,
    Canvas,
    Color,
    DynamicNumber,
    Easing,
    NumberFormat,
    Scene,
    Text,
    Vec2,
)
from zanim.batch import BatchObject2D, CircleSet, DynamicBatchObject2D, LineSet
from zanim.value import ScalarValue

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/extras/modular_multiplication.mp4"
DEFAULT_POINTS = 240
DEFAULT_START = 0.0
DEFAULT_END = 12.0
DEFAULT_DURATION = 18.0
RADIUS = 3.35
LINE_WIDTH = 0.012
DOT_RADIUS = 0.018
CIRCLE_COLOR = Color(135, 148, 174, 110)
DOT_COLOR = Color(190, 205, 230, 175)


def point_on_circle(index: float, count: int, *, radius: float = RADIUS) -> Vec2:
    if count < 2:
        raise ValueError("count must be >= 2")
    angle = tau * float(index) / count
    return Vec2(radius * cos(angle), radius * sin(angle))


def modular_lines(count: int, multiplier: float, *, radius: float = RADIUS) -> LineSet:
    if count < 2:
        raise ValueError("count must be >= 2")
    starts, ends, colors, widths = [], [], [], []
    for i in range(count):
        u = i / count
        starts.append(point_on_circle(i, count, radius=radius))
        ends.append(point_on_circle(multiplier * i, count, radius=radius))
        r = round(105 + 70 * (0.5 + 0.5 * sin(tau * u)))
        g = round(150 + 70 * (0.5 + 0.5 * sin(tau * u + 2.094)))
        b = round(205 + 45 * (0.5 + 0.5 * sin(tau * u + 4.189)))
        colors.append(Color(r, g, min(255, b), 145))
        widths.append(LINE_WIDTH)
    return LineSet(tuple(starts), tuple(ends), tuple(colors), tuple(widths))


def circle_outline(count: int = 256, *, radius: float = RADIUS) -> LineSet:
    if count < 3:
        raise ValueError("circle outline requires at least 3 segments")
    points = tuple(point_on_circle(i, count, radius=radius) for i in range(count))
    return LineSet(
        points,
        points[1:] + points[:1],
        tuple(CIRCLE_COLOR for _ in range(count)),
        tuple(0.014 for _ in range(count)),
    )


def circle_dots(count: int, *, radius: float = RADIUS) -> CircleSet:
    if count < 2:
        raise ValueError("count must be >= 2")
    centers = tuple(point_on_circle(i, count, radius=radius) for i in range(count))
    return CircleSet(
        centers, tuple(DOT_RADIUS for _ in range(count)), tuple(DOT_COLOR for _ in range(count))
    )


def _build_scene(
    *,
    points: int = DEFAULT_POINTS,
    start: float = DEFAULT_START,
    end: float = DEFAULT_END,
    duration: float = DEFAULT_DURATION,
) -> Scene:
    if not 16 <= points <= 2000:
        raise ValueError("points must be between 16 and 2000")
    if duration <= 0:
        raise ValueError("duration must be positive")

    scene = Scene(canvas=Canvas(width=1280, height=960, unit_size=100), fps=60)
    multiplier_value = ScalarValue(float(start))
    lines = DynamicBatchObject2D(
        lambda time: modular_lines(points, multiplier_value.value_at(time)), opacity=0, z_index=1
    )
    outline = BatchObject2D(circle_outline(), opacity=0, z_index=0)
    dots = BatchObject2D(circle_dots(points), opacity=0, z_index=2)

    title = Text("Modular multiplication circle", font_size=36, color=WHITE, opacity=0, z_index=10)
    subtitle = Text(
        "connect i → k·i mod n   ·   the multiplier changes continuously",
        font_size=19,
        color=MUTED,
        opacity=0,
        z_index=10,
    )
    k_label = Text("k =", font_size=26, color=YELLOW, opacity=0, z_index=10)
    k_value = DynamicNumber(
        multiplier_value,
        number_format=NumberFormat(width=6, decimals=2, sign="space"),
        font_size=28,
        color=CYAN,
        opacity=0,
        z_index=10,
    )
    n_label = Text(f"n = {points}", font_size=18, color=MUTED, opacity=0, z_index=10)

    title.move_to((0, 4.25))
    subtitle.move_to((0, 3.80))
    k_label.move_to((-0.48, -4.18))
    k_value.move_to((0.34, -4.18))
    n_label.move_to((4.60, -4.18))

    multiplier, outline, lines, dots, title, subtitle, k_label, k_value, n_label = scene.add(
        multiplier_value, outline, lines, dots, title, subtitle, k_label, k_value, n_label
    )
    with scene.parallel(duration=0.75):
        outline.fade_in()
        lines.fade_in()
        dots.fade_in()
        title.fade_in()
        subtitle.fade_in()
        k_label.fade_in()
        k_value.fade_in()
        n_label.fade_in()
    scene.wait(0.35)
    multiplier.value(to=float(end), duration=duration, easing=Easing.LINEAR)
    scene.wait(0.65)
    return scene


def build_scene() -> Scene:
    return _build_scene()


def main() -> None:
    parser = argparse.ArgumentParser(description="Animate modular multiplication on a circle")
    parser.add_argument("--points", type=int, default=DEFAULT_POINTS)
    parser.add_argument("--start", type=float, default=DEFAULT_START)
    parser.add_argument("--end", type=float, default=DEFAULT_END)
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    scene = _build_scene(points=args.points, start=args.start, end=args.end, duration=args.duration)
    output = scene.render_video(args.output, fps=60, workers=8, verify_random_access=True)
    print(output)
    print(
        f"duration={scene.duration:.2f}s points={args.points} "
        f"multiplier={args.start:g}->{args.end:g} random-access=ok"
    )


if __name__ == "__main__":
    main()
