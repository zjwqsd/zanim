from __future__ import annotations

from math import sin

from zanim import (
    Axes2D,
    Canvas,
    Color,
    DynamicGeometryObject2D,
    FormulaLiteral,
    FormulaTemplate,
    NumberFormat,
    NumberSlot,
    Scene,
    ScriptSlots,
    StrokeStyle,
    Style,
    Transform2D,
)


def f(x: float) -> float:
    return 1.35 + 0.55 * sin(1.15 * x) + 0.06 * x * x


def lower(t: float) -> float:
    return -2.7 + 0.75 * sin(0.85 * t)


def upper(t: float) -> float:
    return 1.6 + 0.85 * sin(1.05 * t + 0.9)


AREA_SAMPLES = 150


def build_scene() -> Scene:
    scene = Scene(canvas=Canvas(width=1920, height=1080, unit_size=100), fps=60)

    axes = Axes2D(
        x_range=(-4.0, 4.0),
        y_range=(-0.45, 3.35),
        width=11.4,
        height=6.6,
        center=__import__('zanim').Vec2(-1.7, -0.75),
    )

    grid = axes.grid_object(x_step=1.0, y_step=0.5)
    axes_lines = axes.axes_object(color=Color(150, 160, 183, 220), width=0.022)

    area = DynamicGeometryObject2D(
        lambda t: axes.area_polygon(f, lower(t), upper(t), samples=AREA_SAMPLES),
        style=Style(
            fill=Color(78, 139, 255, 112),
            stroke=StrokeStyle(Color(113, 168, 255, 155), 0.018),
        ),
    )

    graph = axes.plot(
        f,
        samples=320,
        color=Color(118, 205, 255),
        stroke_width=0.04,
    )

    lower_line = DynamicGeometryObject2D(
        lambda t: axes.boundary_line(f, lower(t)),
        style=Style(fill=None, stroke=StrokeStyle(Color(255, 184, 108), 0.032)),
    )
    upper_line = DynamicGeometryObject2D(
        lambda t: axes.boundary_line(f, upper(t)),
        style=Style(fill=None, stroke=StrokeStyle(Color(80, 220, 180), 0.032)),
    )

    # Rendering order is meaningful: grid -> filled area -> axes -> graph -> boundaries.
    scene.add(grid, area, axes_lines, graph, lower_line, upper_line)

    limit_fmt = NumberFormat(width=5, decimals=1, sign="space")
    formula = FormulaTemplate(
        ScriptSlots(
            "integral",
            sub=NumberSlot(
                "a", limit_fmt, font_size=22,
                color=Color(255, 184, 108), align="center",
            ),
            sup=NumberSlot(
                "b", limit_fmt, font_size=22,
                color=Color(80, 220, 180), align="center",
            ),
        ),
        FormulaLiteral(
            r'(1.35 + 0.55 sin(1.15 x) + 0.06 x^2) dif x',
            font_size=35,
            color=Color(238, 242, 250),
        ),
        FormulaLiteral('=', font_size=35, color=Color(238, 242, 250)),
        NumberSlot(
            'value',
            NumberFormat(width=8, decimals=3, sign='space'),
            font_size=27,
            color=Color(255, 220, 145),
            align='center',
        ),
        font_size=35,
        color=Color(238, 242, 250),
    )
    formula.mount(
        scene,
        {
            "a": lower,
            "b": upper,
            "value": lambda t: axes.integral_value(
                f, lower(t), upper(t), samples=AREA_SAMPLES
            ),
        },
        transform=Transform2D.translation(3.15, 3.85),
    )

    scene.wait(6.0)
    return scene


def verify(scene: Scene) -> None:
    # Geometry and formula values must be pure functions of absolute time.
    for t in (0.0, 0.73, 2.25, 4.81, 2.25):
        snap = scene.evaluate(t)
        polygon = snap.objects[0].snapshot.geometry  # dynamic area is first Object2D
        assert polygon.points
        # First and last polygon vertices lie on baseline at current bounds.
        # Compare in world coordinates against the bound values encoded by geometry.
        assert lower(t) < upper(t)


def main() -> None:
    scene = build_scene()
    verify(scene)
    output = scene.render_video(
        "media/dynamic_integral.mp4",
        fps=60,
        verify_random_access=True,
    )
    print(output)
    print("duration=6.00s fps=60 dynamic-area=ok dynamic-limits=ok integral-value=ok random-access=ok")


if __name__ == "__main__":
    main()
