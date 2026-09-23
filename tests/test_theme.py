from __future__ import annotations

import json

from zanim import (
    Arrow,
    Canvas,
    Color,
    Dot,
    Scene,
    Square,
    Theme,
    apply_config,
    get_theme,
    load_config,
    set_theme,
    use_theme,
)
from zanim.ir import scene_from_ir, scene_to_ir
from zanim.render.frame import render_snapshot_rgb0, render_snapshot_rgba
from zanim.theme import AnimationTheme, CanvasTheme, ShapeTheme, StyleTheme, TextTheme


def custom_theme() -> Theme:
    return Theme(
        name="test",
        canvas=CanvasTheme(
            width=640,
            height=360,
            unit_size=45,
            fps=24,
            background=Color(1, 2, 3),
        ),
        style=StyleTheme(
            fill=Color(4, 5, 6, 80),
            stroke=Color(7, 8, 9),
            stroke_width=0.125,
        ),
        text=TextTheme(font_size=31, color=Color(10, 11, 12), font="DejaVu Sans"),
        math=TextTheme(font_size=29, color=Color(13, 14, 15)),
        animation=AnimationTheme(duration=2.5, wait_duration=0.75, easing="linear"),
        shape=ShapeTheme(dot_radius=0.2, arrow_tip_length=0.5, arrow_tip_width=0.4, arrow_buff=0.1),
        mesh3d_color=Color(16, 17, 18),
    )


def test_manim_is_default_theme():
    set_theme("manim")
    theme = get_theme()
    assert theme.name == "manim"
    assert theme.canvas.width == 1920
    assert theme.canvas.height == 1080
    assert theme.canvas.unit_size == 135
    assert theme.canvas.fps == 60
    assert theme.canvas.background == Color(0, 0, 0)
    assert theme.style.stroke == Color(255, 255, 255)
    assert theme.style.stroke_width == 4 / 135


def test_runtime_theme_switch_changes_new_authoring_defaults():
    set_theme("manim")
    before = Canvas()
    with use_theme(custom_theme()):
        canvas = Canvas()
        assert (canvas.width, canvas.height, canvas.unit_size) == (640, 360, 45)
        assert canvas.background == Color(1, 2, 3)

        scene = Scene()
        assert scene.canvas == canvas
        assert scene.fps == 24

        square = Square(1)
        assert square.style.fill == Color(4, 5, 6, 80)
        assert square.style.stroke.color == Color(7, 8, 9)
        assert square.style.stroke.width == 0.125

        dot = Dot()
        assert dot.geometry.radius == 0.2
        assert dot.style.fill == Color(7, 8, 9)

        arrow = Arrow((0, 0), (2, 0))
        assert arrow.buff == 0.1
        assert arrow.children[0].style.stroke.width == 0.125

        square = scene.add(Square(1))
        square.move(by=(1, 0), frame=__import__("zanim").PARENT)
        assert scene.duration == 2.5
        assert scene._timeline.clips[-1].easing.value == "linear"
        scene.wait()
        assert scene.duration == 3.25

        explicit = Canvas(width=800, height=600, unit_size=100, background=Color(20, 21, 22))
        assert (explicit.width, explicit.height, explicit.unit_size) == (800, 600, 100)
        assert explicit.background == Color(20, 21, 22)

    assert get_theme().name == "manim"
    assert before.unit_size == 135


def test_config_can_select_and_override_theme(tmp_path):
    config_path = tmp_path / "zanim.toml"
    config_path.write_text(
        """\n[theme]\nbase = "manim"\n\n[theme.canvas]\nwidth = 1280\nheight = 720\nunit_size = 90\nfps = 30\nbackground = "#112233"\n\n[theme.style]\nstroke = "#abcdef"\nstroke_width = 0.05\n\n[theme.animation]\nduration = 1.5\nwait_duration = 0.25\neasing = "smoothstep"\n""",
        encoding="utf8",
    )
    config = load_config(config_path)
    assert config.theme.name == "manim"
    assert config.theme.canvas.background == Color(17, 34, 51)
    assert config.theme.style.stroke == Color(171, 205, 239)
    assert config.theme.animation.duration == 1.5
    assert config.theme.animation.easing == "smoothstep"

    previous = get_theme()
    try:
        apply_config(config)
        assert Canvas().unit_size == 90
        assert Square(1).style.stroke.width == 0.05
    finally:
        set_theme(previous)

    json_path = tmp_path / "zanim.json"
    json_path.write_text(json.dumps({"theme": "manim"}), encoding="utf8")
    assert load_config(json_path).theme.name == "manim"

    named = load_config({"theme": {"base": "manim", "name": "paper", "canvas": {"fps": 25}}})
    assert named.theme.name == "paper"
    assert named.theme.canvas.fps == 25


def test_theme_background_affects_final_rgb_but_not_transparent_rgba():
    canvas = Canvas(2, 2, 1, background=Color(17, 34, 51))
    scene = Scene(canvas=canvas)

    rgb = bytearray(2 * 2 * 4)
    render_snapshot_rgb0(rgb, scene.evaluate(0), canvas)
    assert list(rgb[:4]) == [17, 34, 51, 0]

    rgba = bytearray(2 * 2 * 4)
    render_snapshot_rgba(rgba, scene.evaluate(0), canvas)
    assert list(rgba[:4]) == [0, 0, 0, 0]

    restored = scene_from_ir(scene_to_ir(scene))
    assert restored.canvas.background == Color(17, 34, 51)


def test_cli_applies_config_before_importing_scene(tmp_path):
    from zanim.cli import main as cli_main

    scene_path = tmp_path / "demo.py"
    scene_path.write_text("from zanim import Scene\nscene = Scene()\n", encoding="utf8")
    config_path = tmp_path / "zanim.toml"
    config_path.write_text(
        """[theme]\nbase = "manim"\n[theme.canvas]\nwidth = 64\nheight = 36\nunit_size = 4.5\nfps = 24\nbackground = "#123456"\n""",
        encoding="utf8",
    )
    output = tmp_path / "scene.json"
    previous = get_theme()
    try:
        assert (
            cli_main(
                ["export-ir", str(scene_path), "--config", str(config_path), "-o", str(output)]
            )
            == 0
        )
        ir = json.loads(output.read_text(encoding="utf8"))
        assert ir["canvas"] == {
            "width": 64,
            "height": 36,
            "unit_size": 4.5,
            "background": [18, 52, 86, 255],
        }
        assert ir["fps"] == 24
    finally:
        set_theme(previous)
