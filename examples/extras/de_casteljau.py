"""Visualize a cubic Bézier curve through the De Casteljau construction."""

from __future__ import annotations

import argparse
from pathlib import Path

from zanim import (
    CYAN,
    GREEN,
    MUTED,
    ORANGE,
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
OUTPUT = ROOT / "media/extras/de_casteljau.mp4"

DURATION = 7.0
CONTROL_POINTS = (
    Vec2(-4.4, -2.2),
    Vec2(-2.2, 3.0),
    Vec2(2.0, -3.0),
    Vec2(4.4, 2.0),
)

CONTROL_COLOR = Color(154, 166, 191, 175)
CONTROL_LINE_COLOR = Color(118, 130, 154, 115)
TRACE_COLOR = GREEN
TRACE_SEGMENTS = 220


def lerp_point(a: Vec2, b: Vec2, t: float) -> Vec2:
    t = float(t)
    return Vec2(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)


def de_casteljau_levels(
    control_points: tuple[Vec2, Vec2, Vec2, Vec2], t: float
) -> tuple[
    tuple[Vec2, ...],
    tuple[Vec2, ...],
    tuple[Vec2, ...],
    tuple[Vec2, ...],
    Vec2,
]:
    """Return control, first, second and final levels of cubic De Casteljau."""
    if not 0.0 <= t <= 1.0:
        raise ValueError("t must be in [0, 1]")
    p0, p1, p2, p3 = control_points
    first = (
        lerp_point(p0, p1, t),
        lerp_point(p1, p2, t),
        lerp_point(p2, p3, t),
    )
    second = (
        lerp_point(first[0], first[1], t),
        lerp_point(first[1], first[2], t),
    )
    final = lerp_point(second[0], second[1], t)
    return control_points, first, second, (final,), final


def cubic_bezier_point(control_points: tuple[Vec2, Vec2, Vec2, Vec2], t: float) -> Vec2:
    """Evaluate the same cubic in Bernstein form for validation and tracing."""
    if not 0.0 <= t <= 1.0:
        raise ValueError("t must be in [0, 1]")
    p0, p1, p2, p3 = control_points
    u = 1.0 - t
    weights = (u**3, 3.0 * u * u * t, 3.0 * u * t * t, t**3)
    return Vec2(
        sum(weight * point.x for weight, point in zip(weights, control_points)),
        sum(weight * point.y for weight, point in zip(weights, control_points)),
    )


def _line_chain(points: tuple[Vec2, ...], color: Color, width: float) -> LineSet:
    if len(points) < 2:
        raise ValueError("line chain requires at least two points")
    starts = points[:-1]
    ends = points[1:]
    count = len(starts)
    return LineSet(
        starts,
        ends,
        tuple(color for _ in range(count)),
        tuple(width for _ in range(count)),
    )


def control_geometry(control_points: tuple[Vec2, Vec2, Vec2, Vec2]) -> tuple[LineSet, CircleSet]:
    lines = _line_chain(control_points, CONTROL_LINE_COLOR, 0.018)
    dots = CircleSet(
        control_points,
        tuple(0.095 for _ in control_points),
        tuple(CONTROL_COLOR for _ in control_points),
        tuple(WHITE for _ in control_points),
        tuple(0.014 for _ in control_points),
    )
    return lines, dots


def construction_lines(control_points: tuple[Vec2, Vec2, Vec2, Vec2], t: float) -> LineSet:
    _, first, second, _, _ = de_casteljau_levels(control_points, t)
    starts = (first[0], first[1], second[0])
    ends = (first[1], first[2], second[1])
    return LineSet(
        starts,
        ends,
        (CYAN, CYAN, ORANGE),
        (0.026, 0.026, 0.032),
    )


def construction_points(control_points: tuple[Vec2, Vec2, Vec2, Vec2], t: float) -> CircleSet:
    _, first, second, final_level, _ = de_casteljau_levels(control_points, t)
    centers = (*first, *second, *final_level)
    fills = (CYAN, CYAN, CYAN, ORANGE, ORANGE, YELLOW)
    return CircleSet(
        centers,
        tuple((0.078, 0.078, 0.078, 0.085, 0.085, 0.115)),
        fills,
        tuple(WHITE for _ in centers),
        tuple(0.012 for _ in centers),
    )


def curve_trace(
    control_points: tuple[Vec2, Vec2, Vec2, Vec2], t: float, *, segments: int = TRACE_SEGMENTS
) -> LineSet:
    if segments < 2:
        raise ValueError("trace requires at least two segments")
    if not 0.0 <= t <= 1.0:
        raise ValueError("t must be in [0, 1]")
    points = tuple(
        cubic_bezier_point(control_points, t * i / segments) for i in range(segments + 1)
    )
    return LineSet(
        points[:-1],
        points[1:],
        tuple(TRACE_COLOR for _ in range(segments)),
        tuple(0.045 for _ in range(segments)),
    )


def _build_scene(*, duration: float = DURATION) -> Scene:
    if duration <= 0:
        raise ValueError("duration must be positive")

    scene = Scene(canvas=Canvas(width=1280, height=960, unit_size=100), fps=60)
    t_value = ScalarValue(0.0)

    control_lines_data, control_dots_data = control_geometry(CONTROL_POINTS)
    control_lines = BatchObject2D(control_lines_data, opacity=0, z_index=0)
    control_dots = BatchObject2D(control_dots_data, opacity=0, z_index=4)
    trace = DynamicBatchObject2D(
        lambda time: curve_trace(CONTROL_POINTS, t_value.value_at(time)), opacity=0, z_index=1
    )
    construction = DynamicBatchObject2D(
        lambda time: construction_lines(CONTROL_POINTS, t_value.value_at(time)),
        opacity=0,
        z_index=2,
    )
    moving_points = DynamicBatchObject2D(
        lambda time: construction_points(CONTROL_POINTS, t_value.value_at(time)),
        opacity=0,
        z_index=5,
    )

    title = Text("Bézier curve · De Casteljau", font_size=36, color=WHITE, opacity=0, z_index=10)
    subtitle = Text(
        "repeat linear interpolation: 4 points → 3 → 2 → 1",
        font_size=19,
        color=MUTED,
        opacity=0,
        z_index=10,
    )
    level_1 = Text("level 1", font_size=17, color=CYAN, opacity=0, z_index=10)
    level_2 = Text("level 2", font_size=17, color=ORANGE, opacity=0, z_index=10)
    curve_label = Text("B(t)", font_size=18, color=GREEN, opacity=0, z_index=10)
    t_label = Text("t =", font_size=25, color=YELLOW, opacity=0, z_index=10)
    t_number = DynamicNumber(
        t_value,
        number_format=NumberFormat(width=5, decimals=2, sign="space"),
        font_size=27,
        color=YELLOW,
        opacity=0,
        z_index=10,
    )

    title.move_to((0, 4.25))
    subtitle.move_to((0, 3.80))
    level_1.move_to((-4.75, 3.35))
    level_2.move_to((-4.75, 2.98))
    curve_label.move_to((-4.75, 2.61))
    t_label.move_to((-0.42, -4.20))
    t_number.move_to((0.38, -4.20))

    (
        t_bound,
        control_lines,
        trace,
        construction,
        control_dots,
        moving_points,
        title,
        subtitle,
        level_1,
        level_2,
        curve_label,
        t_label,
        t_number,
    ) = scene.add(
        t_value,
        control_lines,
        trace,
        construction,
        control_dots,
        moving_points,
        title,
        subtitle,
        level_1,
        level_2,
        curve_label,
        t_label,
        t_number,
    )

    with scene.parallel(duration=0.75):
        control_lines.fade_in()
        control_dots.fade_in()
        trace.fade_in()
        construction.fade_in()
        moving_points.fade_in()
        title.fade_in()
        subtitle.fade_in()
        level_1.fade_in()
        level_2.fade_in()
        curve_label.fade_in()
        t_label.fade_in()
        t_number.fade_in()
    scene.wait(0.35)
    t_bound.value(to=1.0, duration=duration, easing=Easing.LINEAR)
    scene.wait(0.75)
    return scene


def build_scene() -> Scene:
    return _build_scene()


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize cubic Bézier / De Casteljau")
    parser.add_argument("--duration", type=float, default=DURATION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    scene = _build_scene(duration=args.duration)
    output = scene.render_video(args.output, fps=60, workers=8, verify_random_access=True)
    print(output)
    print(f"duration={scene.duration:.2f}s cubic-bezier de-casteljau random-access=ok")


if __name__ == "__main__":
    main()
