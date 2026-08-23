"""Animate the Hilbert space-filling curve from low to high order."""

from __future__ import annotations

import argparse
from pathlib import Path

from zanim import (
    BLUE,
    CYAN,
    GREEN,
    MUTED,
    ORANGE,
    PINK,
    WHITE,
    YELLOW,
    Canvas,
    Polyline,
    Scene,
    Text,
    Vec2,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/extras/hilbert_curve.mp4"

DEFAULT_MAX_ORDER = 6
SIDE = 7.0
CREATE_DURATION = 1.0
TRANSITION_DURATION = 1.15
HOLD = 0.42
LABEL_FADE = 0.18
PALETTE = (BLUE, CYAN, GREEN, YELLOW, ORANGE, PINK)


def _rotate_quadrant(size: int, x: int, y: int, rx: int, ry: int) -> tuple[int, int]:
    """Rotate/reflect one Hilbert quadrant while decoding an index."""
    if ry == 0:
        if rx == 1:
            x = size - 1 - x
            y = size - 1 - y
        x, y = y, x
    return x, y


def hilbert_grid_point(order: int, index: int) -> tuple[int, int]:
    """Return the integer grid coordinate for one Hilbert traversal index."""
    if order < 1:
        raise ValueError("Hilbert order must be >= 1")
    side = 1 << order
    if not 0 <= index < side * side:
        raise ValueError("Hilbert index is outside the selected order")

    x = 0
    y = 0
    distance = index
    scale = 1
    while scale < side:
        rx = 1 & (distance // 2)
        ry = 1 & (distance ^ rx)
        x, y = _rotate_quadrant(scale, x, y, rx, ry)
        x += scale * rx
        y += scale * ry
        distance //= 4
        scale *= 2
    return x, y


def hilbert_points(order: int, *, side: float = SIDE) -> tuple[Vec2, ...]:
    """Return a centered Hilbert polyline with a fixed outer side length."""
    if order < 1:
        raise ValueError("Hilbert order must be >= 1")
    if side <= 0:
        raise ValueError("side must be positive")

    grid_side = 1 << order
    denominator = grid_side - 1
    half = side * 0.5
    points = []
    for index in range(grid_side * grid_side):
        x, y = hilbert_grid_point(order, index)
        points.append(
            Vec2(
                side * x / denominator - half,
                side * y / denominator - half,
            )
        )
    return tuple(points)


def _order_label(order: int) -> Text:
    return Text(
        f"order {order}   ·   {4**order:,} vertices",
        font_size=21,
        color=MUTED,
        opacity=0,
        z_index=10,
    )


def _curve(order: int) -> Polyline:
    color = PALETTE[min(order - 1, len(PALETTE) - 1)]
    return Polyline(
        hilbert_points(order),
        stroke=color,
        stroke_width=max(0.018, 0.052 - 0.006 * (order - 1)),
        z_index=1,
    )


def _build_scene(
    *,
    max_order: int = DEFAULT_MAX_ORDER,
    transition_duration: float = TRANSITION_DURATION,
    hold: float = HOLD,
) -> Scene:
    if not 1 <= max_order <= 7:
        raise ValueError("max_order must be between 1 and 7")
    if transition_duration <= 0:
        raise ValueError("transition_duration must be positive")
    if hold < 0:
        raise ValueError("hold must be >= 0")

    scene = Scene(canvas=Canvas(width=1280, height=960, unit_size=100), fps=60)

    title = Text("Hilbert curve", font_size=36, color=WHITE, opacity=0, z_index=10)
    title.move_to((0, 4.25))
    label = _order_label(1)
    label.move_to((0, -4.25))

    first = _curve(1)
    first.trim = 0
    curve, title, label = scene.add(first, title, label)
    with scene.parallel():
        curve.create(duration=CREATE_DURATION)
        title.fade_in(duration=0.55)
        label.fade_in(duration=0.55)
    scene.wait(hold)

    for order in range(2, max_order + 1):
        # replace() is a real geometry morph. The renderer resamples both
        # polylines to the denser endpoint, so high-order detail is preserved.
        curve = scene.replace(curve, _curve(order), duration=transition_duration)

        next_label = _order_label(order)
        next_label.move_to((0, -4.25))
        next_label = scene.add(next_label)
        with scene.parallel(duration=LABEL_FADE):
            label.fade_out()
            next_label.fade_in()
        label.remove()
        label = next_label
        scene.wait(hold)

    scene.wait(0.5)
    return scene


def build_scene() -> Scene:
    """Default scene used by ``zanim preview/render``."""
    return _build_scene()


def main() -> None:
    parser = argparse.ArgumentParser(description="Animate increasing Hilbert-curve order")
    parser.add_argument("--max-order", type=int, default=DEFAULT_MAX_ORDER)
    parser.add_argument("--transition", type=float, default=TRANSITION_DURATION)
    parser.add_argument("--hold", type=float, default=HOLD)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    scene = _build_scene(
        max_order=args.max_order,
        transition_duration=args.transition,
        hold=args.hold,
    )
    output = scene.render_video(
        args.output,
        fps=60,
        workers=8,
        verify_random_access=True,
    )
    print(output)
    print(f"duration={scene.duration:.2f}s max_order={args.max_order} random-access=ok")


if __name__ == "__main__":
    main()
