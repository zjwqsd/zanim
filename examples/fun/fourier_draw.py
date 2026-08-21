from __future__ import annotations

import argparse
from functools import lru_cache
from math import cos, pi, sin, sqrt
from pathlib import Path

from zanim import (
    Camera2D, Canvas, Color, DynamicGeometryObject2D, Group2D, Math, Object2D,
    Polygon, Polyline, Scene, Style, Transform2D, Vec2, affine2d,
    load_svg,
)
from zanim.extras.fourier import (
    contour_samples, dft, dominant_terms, epicycle_chain, point2,
    select_closed_contour,
)

ROOT = Path(__file__).resolve().parents[2]
SVG = ROOT / "assets/fourier_heart.svg"
OUTPUT = ROOT / "media/fun/fourier_draw.mp4"
FOLLOW_OUTPUT = ROOT / "media/fun/fourier_draw_follow.mp4"

SAMPLE_COUNT = 768
TERM_COUNT = 36
CIRCLE_SAMPLES = 28
TRACE_SAMPLES = 1000
START = 0.55
DRAW_DURATION = 6.2
HOLD = 0.45


def circle_polyline(center: complex, radius: float, samples: int = CIRCLE_SAMPLES) -> Polyline:
    points = tuple(
        Vec2(
            center.real + radius * cos(2*pi*i/samples),
            center.imag + radius * sin(2*pi*i/samples),
        )
        for i in range(samples + 1)
    )
    return Polyline(points)


def arrow_polygon(start: complex, end: complex) -> Polygon:
    dx, dy = end.real-start.real, end.imag-start.imag
    length = sqrt(dx*dx + dy*dy)
    if length <= 1e-8:
        p = point2(start)
        eps = 1e-5
        return Polygon((p, Vec2(p.x+eps, p.y), Vec2(p.x, p.y+eps)))
    ux, uy = dx/length, dy/length
    nx, ny = -uy, ux
    shaft_half = min(0.018, length * 0.08)
    tip_length = min(0.15, length * 0.32)
    tip_half = min(0.065, max(shaft_half * 2.4, length * 0.10))
    bx, by = end.real-ux*tip_length, end.imag-uy*tip_length
    return Polygon((
        Vec2(start.real + nx*shaft_half, start.imag + ny*shaft_half),
        Vec2(bx + nx*shaft_half, by + ny*shaft_half),
        Vec2(bx + nx*tip_half, by + ny*tip_half),
        Vec2(end.real, end.imag),
        Vec2(bx - nx*tip_half, by - ny*tip_half),
        Vec2(bx - nx*shaft_half, by - ny*shaft_half),
        Vec2(start.real - nx*shaft_half, start.imag - ny*shaft_half),
    ))


def tip_polygon(point: complex, radius: float = 0.055, sides: int = 14) -> Polygon:
    return Polygon(tuple(
        Vec2(point.real + radius*cos(2*pi*i/sides), point.imag + radius*sin(2*pi*i/sides))
        for i in range(sides)
    ))


def build_scene(
    svg_path: Path = SVG,
    *,
    sample_count: int = SAMPLE_COUNT,
    term_count: int = TERM_COUNT,
    draw_duration: float = DRAW_DURATION,
    follow: bool = False,
    follow_zoom: float = 2.4,
    follow_lead: float = 0.08,
) -> tuple[Scene, dict[str, float | int | bool]]:
    if sample_count < 16:
        raise ValueError("sample_count must be >= 16")
    if term_count < 1:
        raise ValueError("term_count must be positive")
    if draw_duration <= 0:
        raise ValueError("draw_duration must be positive")
    if follow_zoom <= 0:
        raise ValueError("follow_zoom must be positive")
    if follow_lead < 0:
        raise ValueError("follow_lead must be >= 0")

    document = load_svg(svg_path)
    contour = select_closed_contour(document, strategy="longest")
    samples = contour_samples(contour, sample_count, tolerance=7e-4)
    terms = dominant_terms(dft(samples), term_count, keep_dc_first=True)

    def scene_phase(time: float) -> float:
        return max(0.0, min(1.0, (float(time) - START) / draw_duration))

    @lru_cache(maxsize=2048)
    def chain_at(time: float) -> tuple[complex, ...]:
        return epicycle_chain(terms, scene_phase(time))

    def tip_at_phase(phase: float) -> complex:
        return epicycle_chain(terms, phase)[-1]

    def follow_focus(time: float) -> complex:
        """Stateless, slightly predictive smoothing of the drawing tip."""
        t = float(time)
        phase = scene_phase(t)
        if t <= START or t >= START + draw_duration:
            return tip_at_phase(phase)
        lead_phase = follow_lead / draw_duration
        # Symmetric averaging around a small look-ahead point suppresses the
        # highest-frequency camera jitter without introducing frame history.
        window = min(0.012, 0.5 / max(1, len(terms)))
        offsets = (-window, -window * 0.5, 0.0, window * 0.5, window)
        weights = (1.0, 2.0, 3.0, 2.0, 1.0)
        center = phase + lead_phase
        values = [tip_at_phase((center + offset) % 1.0) for offset in offsets]
        return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)

    def follow_view(time: float) -> Transform2D:
        focus = follow_focus(time)
        return (
            Transform2D.scaling(follow_zoom)
            @ Transform2D.translation(-focus.real, -focus.imag)
        )

    reference_points = tuple(point2(value) for value in samples)
    reference = Object2D(
        Polyline((*reference_points, reference_points[0])),
        stroke=Color(118, 129, 151, 80), stroke_width=0.018, z_index=-5,
    )

    circle_style = Style.outline(Color(132, 157, 198, 82), 0.012)
    arrow_style = Style.solid(Color(205, 220, 245, 190))
    children = []
    visual_indices = [
        index for index, term in enumerate(terms)
        if term.frequency != 0 and term.radius > 2e-4
    ]
    for index in visual_indices:
        radius = terms[index].radius
        circle = DynamicGeometryObject2D(
            lambda t, index=index, radius=radius: circle_polyline(chain_at(float(t))[index], radius),
            style=circle_style,
            z_index=0,
        )
        arrow = DynamicGeometryObject2D(
            lambda t, index=index: arrow_polygon(
                chain_at(float(t))[index], chain_at(float(t))[index+1]
            ),
            style=arrow_style,
            z_index=1,
        )
        children.extend((circle, arrow))
    epicycles = Group2D(children, z_index=0)

    full_trace = tuple(
        epicycle_chain(terms, i/(TRACE_SAMPLES-1))[-1]
        for i in range(TRACE_SAMPLES)
    )

    def trace_geometry(time: float):
        phase = scene_phase(time)
        end = max(1, min(TRACE_SAMPLES-1, round(phase*(TRACE_SAMPLES-1))))
        points = tuple(point2(value) for value in full_trace[:end+1])
        if len(points) < 2:
            points = (points[0], points[0])
        return Polyline(points)

    trace = DynamicGeometryObject2D(
        trace_geometry,
        style=Style.outline(Color(255, 108, 139), 0.045),
        z_index=4,
    )
    tip = DynamicGeometryObject2D(
        lambda t: tip_polygon(chain_at(float(t))[-1]),
        style=Style.solid(Color(255, 204, 214)),
        z_index=5,
    )

    formula = Math(
        'f(t) = sum_k c_k e^(2 pi i k t)',
        font_size=29,
        color=Color(223, 228, 240),
        transform=affine2d(to=(0, 4.25)),
        z_index=10,
    )
    term_label = Math(
        f'N = {len(visual_indices)}',
        font_size=21,
        color=Color(150, 163, 188),
        transform=affine2d(to=(0, 3.72)),
        z_index=10,
    )

    camera = Camera2D(transform_provider=follow_view) if follow else Camera2D()
    scene = Scene(
        canvas=Canvas(width=1920, height=1080, unit_size=104),
        fps=60,
        camera=camera,
    )
    scene.add(reference, epicycles, trace, tip)
    if not follow:
        scene.add(formula, term_label)
    scene.wait(START + draw_duration + HOLD)
    return scene, {
        "samples": sample_count,
        "terms": len(terms),
        "visible_terms": len(visual_indices),
        "trace_samples": TRACE_SAMPLES,
        "follow": follow,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw one closed SVG contour with Fourier epicycles")
    parser.add_argument("--svg", type=Path, default=SVG, help="input SVG; the longest closed contour is used")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--terms", type=int, default=TERM_COUNT, help="number of retained Fourier terms")
    parser.add_argument("--samples", type=int, default=SAMPLE_COUNT, help="uniform arc-length samples for the DFT")
    parser.add_argument("--duration", type=float, default=DRAW_DURATION, help="seconds for one complete drawing cycle")
    parser.add_argument("--follow", action="store_true", help="camera follows the drawing tip")
    parser.add_argument("--follow-zoom", type=float, default=2.4, help="fixed zoom for follow mode")
    parser.add_argument("--follow-lead", type=float, default=0.08, help="look-ahead in seconds for follow mode")
    args = parser.parse_args()

    scene, info = build_scene(
        args.svg.resolve(),
        sample_count=args.samples,
        term_count=args.terms,
        draw_duration=args.duration,
        follow=args.follow,
        follow_zoom=args.follow_zoom,
        follow_lead=args.follow_lead,
    )
    output_path = args.output or (FOLLOW_OUTPUT if args.follow else OUTPUT)
    output = scene.render_video(output_path, fps=60, workers=8, verify_random_access=True)
    print(output)
    print(
        f"duration={scene.timeline.cursor:.2f}s samples={info['samples']} "
        f"terms={info['terms']} visible={info['visible_terms']} "
        f"trace={info['trace_samples']} follow={info['follow']} random-access=ok"
    )


if __name__ == "__main__":
    main()
