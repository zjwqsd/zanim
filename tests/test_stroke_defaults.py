from zanim import (
    BLUE,
    DEFAULT_STROKE_WIDTH,
    GREEN,
    RED,
    Axes,
    FunctionPlot,
    Line,
    Scene,
    Style,
    StrokeStyle,
    X,
)

def test_default_stroke_width_is_shared():
    assert StrokeStyle().width == DEFAULT_STROKE_WIDTH
    assert Style.outline(RED).stroke.width == DEFAULT_STROKE_WIDTH
    assert Style.paint(BLUE, RED).stroke.width == DEFAULT_STROKE_WIDTH
    assert Line(stroke=RED).style.stroke.width == DEFAULT_STROKE_WIDTH

def test_bound_outline_and_paint_use_shared_default():
    scene = Scene()
    line = scene.add(Line(stroke=RED))
    line.outline(GREEN, duration=1)
    assert line.style_value.stroke.width == DEFAULT_STROKE_WIDTH

    line.paint(fill=BLUE, stroke=RED, duration=1)
    assert line.style_value.stroke.width == DEFAULT_STROKE_WIDTH

def test_function_plot_uses_shared_default():
    plot = FunctionPlot(X, axes=Axes((-5, 5), (-3, 3)))
    assert plot.style.stroke.width == DEFAULT_STROKE_WIDTH
