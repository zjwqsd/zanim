from zanim import (
    BLUE,
    GREEN,
    RED,
    Axes,
    FunctionPlot,
    Line,
    Scene,
    X,
    get_theme,
)


def test_default_stroke_width_is_shared():
    assert Line(stroke=RED).style.stroke.width == get_theme().style.stroke_width


def test_bound_outline_and_paint_use_shared_default():
    scene = Scene()
    line = scene.add(Line(stroke=RED))
    line.style(stroke=GREEN, duration=1)
    assert line.style_value.stroke.width == get_theme().style.stroke_width

    line.style(fill=BLUE, stroke=RED, duration=1)
    assert line.style_value.stroke.width == get_theme().style.stroke_width


def test_function_plot_uses_shared_default():
    plot = FunctionPlot(X, axes=Axes((-5, 5), (-3, 3)))
    assert plot.style.stroke.width == get_theme().style.stroke_width
