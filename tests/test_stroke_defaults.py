from zanim import (
    BLUE,
    DEFAULT_STROKE_WIDTH,
    GREEN,
    RED,
    Axes,
    FunctionPlot,
    Line,
    Scene,
    X,
)
from zanim.geometry import StrokeStyle


def test_default_stroke_width_is_shared():
    assert StrokeStyle().width == DEFAULT_STROKE_WIDTH
    assert StrokeStyle(RED).width == DEFAULT_STROKE_WIDTH
    assert StrokeStyle(RED).width == DEFAULT_STROKE_WIDTH
    assert Line(stroke=RED).style.stroke.width == DEFAULT_STROKE_WIDTH


def test_bound_outline_and_paint_use_shared_default():
    scene = Scene()
    line = scene.add(Line(stroke=RED))
    line.style(stroke=GREEN, duration=1)
    assert line.style_value.stroke.width == DEFAULT_STROKE_WIDTH

    line.style(fill=BLUE, stroke=RED, duration=1)
    assert line.style_value.stroke.width == DEFAULT_STROKE_WIDTH


def test_function_plot_uses_shared_default():
    plot = FunctionPlot(X, axes=Axes((-5, 5), (-3, 3)))
    assert plot.style.stroke.width == DEFAULT_STROKE_WIDTH
