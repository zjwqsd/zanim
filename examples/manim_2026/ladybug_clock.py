from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

from zanim import (
    Arc,
    BatchObject2D,
    Canvas,
    Circle,
    Color,
    DynamicGeometryObject2D,
    Easing,
    Ellipse,
    Group2D,
    Line,
    LineSet,
    Math,
    Object2D,
    Polygon,
    Scene,
    StrokeStyle,
    Style,
    Text,
    Transform2D,
    Vec2,
    VectorDocument,
    VectorObject2D,
    VectorPath,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "media" / "manim_2026" / "ladybug_clock"

TAU = math.tau
CLOCK_RADIUS = 2.05
NUMBER_RADIUS = 1.50
ARROW_RADIUS = 2.42
STEP_DURATION = 0.44
LAND_DURATION = 3.0

WHITE = Color(238, 241, 247)
GREY = Color(145, 152, 168)
GREY_DARK = Color(72, 78, 90)
RED = Color(230, 67, 78)
RED_DARK = Color(145, 34, 43)
TEAL = Color(72, 203, 188)
YELLOW = Color(246, 204, 71)
BLACK = Color(15, 17, 22)


def _canvas(draft: bool) -> Canvas:
    if draft:
        return Canvas(width=960, height=540, unit_size=67.5)
    return Canvas(width=1920, height=1080, unit_size=135.0)


def _clock_angle(index: int) -> float:
    """Clock index 0=12, 1=1, ...; positive direction is clockwise."""
    return math.pi / 2 - (index % 12) * TAU / 12


def _clock_point(index: int, radius: float = CLOCK_RADIUS) -> Vec2:
    angle = _clock_angle(index)
    return Vec2(radius * math.cos(angle), radius * math.sin(angle))


def _recolor_document(document: VectorDocument, color: Color) -> VectorDocument:
    """Reuse one compiled glyph geometry with a different paint color."""
    return VectorDocument(
        tuple(
            VectorPath(
                path.contours,
                fill=color if path.fill is not None else None,
                stroke=(
                    StrokeStyle(color, path.stroke.width)
                    if path.stroke is not None
                    else None
                ),
                group=path.group,
            )
            for path in document.paths
        ),
        document.width,
        document.height,
        document.group_count,
    )


def _make_clock(scene: Scene):
    circle = Object2D(
        Circle(CLOCK_RADIUS),
        style=Style(fill=None, stroke=StrokeStyle(GREY, 0.025)),
        z_index=-3,
    )

    tick_starts: list[Vec2] = []
    tick_ends: list[Vec2] = []
    tick_colors: list[Color] = []
    tick_widths: list[float] = []
    for index in range(60):
        angle = math.pi / 2 - index * TAU / 60
        major = index % 5 == 0
        outer = CLOCK_RADIUS
        inner = outer - (0.22 if major else 0.10)
        tick_starts.append(Vec2(inner * math.cos(angle), inner * math.sin(angle)))
        tick_ends.append(Vec2(outer * math.cos(angle), outer * math.sin(angle)))
        tick_colors.append(GREY if major else GREY_DARK)
        tick_widths.append(0.025 if major else 0.012)
    ticks = BatchObject2D(
        LineSet(tuple(tick_starts), tuple(tick_ends), tuple(tick_colors), tuple(tick_widths)),
        z_index=-2,
    )

    # Equivalent in spirit to ClockPassesTime(...): a 12-second repeating
    # 12-hour sweep, expressed as absolute-time geometry providers.
    def minute_hand(time: float) -> Line:
        angle = math.pi / 2 - TAU * (time % 1.0)
        return Line(Vec2(), Vec2(1.18 * math.cos(angle), 1.18 * math.sin(angle)))

    def hour_hand(time: float) -> Line:
        angle = math.pi / 2 - TAU * ((time % 12.0) / 12.0)
        return Line(Vec2(), Vec2(0.83 * math.cos(angle), 0.83 * math.sin(angle)))

    hands = [
        DynamicGeometryObject2D(
            hour_hand,
            style=Style(fill=None, stroke=StrokeStyle(Color(183, 189, 204), 0.055)),
            z_index=-1,
        ),
        DynamicGeometryObject2D(
            minute_hand,
            style=Style(fill=None, stroke=StrokeStyle(Color(205, 210, 221), 0.035)),
            z_index=-1,
        ),
        Object2D(Circle(0.065), style=Style(fill=GREY, stroke=None), z_index=0),
    ]

    white_numbers: list[Math] = []
    red_numbers: list[VectorObject2D] = []
    teal_numbers: list[VectorObject2D] = []
    values = [12, *range(1, 12)]
    for index, value in enumerate(values):
        point = _clock_point(index, NUMBER_RADIUS)
        base = Math(str(value), font_size=28, color=WHITE)
        base.move_to(point)
        white_numbers.append(base)
        red_numbers.append(
            VectorObject2D(
                _recolor_document(base.document, RED),
                transform=base.transform,
                opacity=0.0,
                z_index=3,
            )
        )
        teal_numbers.append(
            VectorObject2D(
                _recolor_document(base.document, TEAL),
                transform=base.transform,
                opacity=0.0,
                z_index=4,
            )
        )

    clock = Group2D([circle, ticks, *hands, *white_numbers, *red_numbers, *teal_numbers])
    scene.add(clock)
    return red_numbers, teal_numbers


def _make_ladybug() -> Group2D:
    body = Object2D(
        Ellipse(0.23, 0.31),
        style=Style(fill=RED, stroke=StrokeStyle(BLACK, 0.018)),
        z_index=20,
    )
    head = Object2D(
        Circle(0.095),
        transform=Transform2D.translation(0, 0.285),
        style=Style(fill=BLACK, stroke=None),
        z_index=21,
    )
    seam = Object2D(
        Line(Vec2(0, -0.25), Vec2(0, 0.24)),
        style=Style(fill=None, stroke=StrokeStyle(BLACK, 0.016)),
        z_index=22,
    )
    spots = []
    for x, y, radius in (
        (-0.095, 0.12, 0.040),
        (0.095, 0.12, 0.040),
        (-0.105, -0.07, 0.047),
        (0.105, -0.07, 0.047),
    ):
        spots.append(
            Object2D(
                Circle(radius),
                transform=Transform2D.translation(x, y),
                style=Style(fill=BLACK, stroke=None),
                z_index=22,
            )
        )
    halo = Object2D(
        Circle(0.29),
        style=Style(fill=Color(RED_DARK.r, RED_DARK.g, RED_DARK.b, 90), stroke=None),
        z_index=18,
    )
    return Group2D([halo, body, head, seam, *spots], z_index=20)


def _cubic_point(p0: Vec2, p1: Vec2, p2: Vec2, p3: Vec2, t: float) -> Vec2:
    u = 1.0 - t
    return Vec2(
        u**3 * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t**3 * p3.x,
        u**3 * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t**3 * p3.y,
    )


def _walk_steps(seed: int = 19) -> tuple[int, ...]:
    """Match the reference scene's RNG consumption and lifted clock walk."""
    rng = random.Random(seed)
    # The source scene creates five random landing-path segments first.
    for _ in range(5):
        rng.random()
    current = 0
    covered = {0}
    result: list[int] = []
    while len(covered) < 12:
        current += rng.choice((1, -1))
        result.append(current)
        covered.add(current)
    return tuple(result)


def _active_step(time: float, sim_start: float, steps: tuple[int, ...]) -> tuple[int, int]:
    index = int((time - sim_start) / STEP_DURATION)
    index = max(0, min(len(steps) - 1, index))
    end = steps[index]
    start = 0 if index == 0 else steps[index - 1]
    return start, end


def _arrow_arc_provider(sim_start: float, steps: tuple[int, ...]):
    def provider(time: float):
        start, end = _active_step(time, sim_start, steps)
        direction = 1 if end > start else -1
        return Arc(
            ARROW_RADIUS,
            _clock_angle(start),
            -direction * TAU / 12,
        )

    return provider


def _arrow_tip_provider(sim_start: float, steps: tuple[int, ...]):
    def provider(time: float):
        start, end = _active_step(time, sim_start, steps)
        direction = 1 if end > start else -1
        angle = _clock_angle(end)
        tip = Vec2(ARROW_RADIUS * math.cos(angle), ARROW_RADIUS * math.sin(angle))
        # CCW tangent is (-sin, cos); clockwise is the negative of it.
        tangent = Vec2(-math.sin(angle) * -direction, math.cos(angle) * -direction)
        normal = Vec2(-tangent.y, tangent.x)
        base = Vec2(tip.x - 0.18 * tangent.x, tip.y - 0.18 * tangent.y)
        left = Vec2(base.x + 0.075 * normal.x, base.y + 0.075 * normal.y)
        right = Vec2(base.x - 0.075 * normal.x, base.y - 0.075 * normal.y)
        return Polygon((tip, left, right))

    return provider


def build_ladybug_scene(*, draft: bool = False) -> Scene:
    scene = Scene(canvas=_canvas(draft), fps=30 if draft else 60)
    red_numbers, teal_numbers = _make_clock(scene)

    bug = _make_ladybug()
    start = Vec2(-7.0, -0.25)
    bug.transform = Transform2D.translation(start.x, start.y)
    scene.add(bug)

    landing_end = _clock_point(0)
    p1 = Vec2(-4.9, 1.35)
    p2 = Vec2(-1.7, 3.05)

    scene.play_transform_function(
        bug,
        lambda alpha: Transform2D.translation(
            *(
                lambda p: (p.x, p.y)
            )(_cubic_point(start, p1, p2, landing_end, alpha))
        ),
        duration=LAND_DURATION,
        easing=Easing.SMOOTHSTEP,
    )
    scene.fade_in(red_numbers[0], duration=0.35)
    scene.wait(0.35)

    steps = _walk_steps()
    sim_start = scene.timeline.cursor

    arrow_arc = DynamicGeometryObject2D(
        _arrow_arc_provider(sim_start, steps),
        style=Style(fill=None, stroke=StrokeStyle(YELLOW, 0.045)),
        opacity=0.0,
        z_index=12,
    )
    arrow_tip = DynamicGeometryObject2D(
        _arrow_tip_provider(sim_start, steps),
        style=Style(fill=YELLOW, stroke=None),
        opacity=0.0,
        z_index=13,
    )
    scene.add(arrow_arc, arrow_tip)
    with scene.parallel():
        scene.fade_in(arrow_arc, duration=0.08)
        scene.fade_in(arrow_tip, duration=0.08)

    visited = {0}
    current = 0
    for lifted_end in steps:
        lifted_start = current
        direction = 1 if lifted_end > lifted_start else -1
        start_angle = _clock_angle(lifted_start)
        sweep = -direction * TAU / 12

        def transform_at(alpha: float, a0=start_angle, da=sweep):
            angle = a0 + da * alpha
            return Transform2D.translation(
                CLOCK_RADIUS * math.cos(angle),
                CLOCK_RADIUS * math.sin(angle),
            )

        physical = lifted_end % 12
        is_new = physical not in visited
        is_final = is_new and len(visited) == 11
        with scene.parallel():
            scene.play_transform_function(
                bug,
                transform_at,
                duration=STEP_DURATION,
                easing=Easing.SMOOTHSTEP,
            )
            if is_new:
                scene.fade_in(
                    teal_numbers[physical] if is_final else red_numbers[physical],
                    duration=min(0.26, STEP_DURATION),
                )
        visited.add(physical)
        current = lifted_end

    with scene.parallel():
        scene.fade_out(arrow_arc, duration=0.16)
        scene.fade_out(arrow_tip, duration=0.16)
    scene.wait(1.5)
    return scene


def build_question_scene(*, draft: bool = False) -> Scene:
    scene = Scene(canvas=_canvas(draft), fps=30 if draft else 60)
    first = Text("What is the probability that", font_size=43, color=WHITE)
    second = Text("the last number painted is 6?", font_size=43, color=WHITE)
    first.move_to(Vec2(0, 0.42))
    second.move_to(Vec2(0, -0.42))
    scene.add(first, second)
    scene.create(first, duration=1.05)
    scene.create(second, duration=1.15)
    scene.wait(1.5)
    return scene


BUILDERS = {
    "Ladybug": build_ladybug_scene,
    "Question": build_question_scene,
}


def render_one(name: str, *, draft: bool, workers: int, preset: str) -> Path:
    scene = BUILDERS[name](draft=draft)
    out_dir = OUTPUT_DIR / "draft" if draft else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{name}.mp4"
    scene.render_video(
        output,
        fps=scene.fps,
        workers=workers,
        verify_random_access=True,
        preset=preset,
    )
    print(
        f"{name}: duration={scene.timeline.cursor:.2f}s "
        f"fps={scene.fps} random-access=ok -> {output}"
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Zanim recreation of the 2026 ladybug clock scenes")
    parser.add_argument("scene", nargs="?", choices=[*BUILDERS, "all"], default="all")
    parser.add_argument("--draft", action="store_true", help="render 960x540 at 30 fps")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--preset", default="veryfast")
    args = parser.parse_args()

    names = BUILDERS if args.scene == "all" else (args.scene,)
    for name in names:
        render_one(name, draft=args.draft, workers=args.workers, preset=args.preset)


if __name__ == "__main__":
    main()
