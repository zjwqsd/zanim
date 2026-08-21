"""Zanim's authoring philosophy: lifetime and state changes are explicit."""
from __future__ import annotations

from pathlib import Path

from zanim import (
    BOTTOM, Canvas, Circle, Color, DOWN, LEFT_CENTER, Object2D, RIGHT_CENTER,
    Row, Scene, Square, TOP, Text, UP, Vec2,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/showcase/state_model.mp4"

BLUE = Color(82, 148, 255)
GREEN = Color(82, 210, 155)
ORANGE = Color(255, 164, 88)
PURPLE = Color(178, 118, 255)
MUTED = Color(154, 166, 190)
RED = Color(245, 95, 105)


def card_label(text: str) -> Text:
    return Text(text, font_size=22, color=MUTED)


def build_scene() -> Scene:
    scene = Scene(canvas=Canvas(1280, 720, 92), fps=60)

    # Declare.
    title = Text("Explicit state, explicit time", font_size=36)
    rule = Text(
        "add/remove define lifetime; animations only change authored state",
        font_size=23,
        color=MUTED,
    )
    immediate = Object2D(Square(1.25), fill=BLUE)
    hidden = Object2D(Circle(0.68), fill=GREEN, opacity=0)
    drawn = Object2D(Square(1.25), stroke=PURPLE, stroke_width=0.055, trim=0)
    immediate_label = card_label("add() = visible now")
    hidden_label = card_label("opacity=0; fade_in()")
    drawn_label = card_label("trim=0; create()")

    # Layout.
    header = scene.frame.top_region(height=1.25)
    content = scene.frame.inset(0.65).below(header, gap=0.2)
    title.place(anchor=TOP, at=header.top + 0.24 * DOWN)
    rule.place(anchor=TOP, at=title.anchor(BOTTOM) + 0.14 * DOWN)
    Row(gap=2.7, at=content.center + 0.75 * UP).place(immediate, hidden, drawn)
    for obj, label in zip(
        (immediate, hidden, drawn),
        (immediate_label, hidden_label, drawn_label),
    ):
        label.place(anchor=TOP, at=obj.anchor(BOTTOM) + 0.42 * DOWN)

    # t=0. All three objects enter the lifetime here. Their visual state is
    # exactly the state written above: no entrance behavior is implied by add().
    scene.add(
        title, rule, immediate, hidden, drawn,
        immediate_label, hidden_label, drawn_label,
    )
    immediate, hidden, drawn = map(scene.on, (immediate, hidden, drawn))
    scene.wait(1.2)

    # Because hidden was explicitly authored with opacity=0, this transition
    # has a real 0 -> 1 starting state. create() follows the same rule for trim.
    with scene.parallel():
        hidden.fade_in()
        drawn.create()

    scene.wait(0.8)

    # add() is temporal. This object did not exist in any earlier snapshot and
    # appears immediately at the current cursor because its opacity is already 1.
    late = Object2D(Circle(0.36), fill=ORANGE)
    late_note = Text("wait(); add() → lifetime starts here", font_size=21, color=ORANGE)
    late.place(anchor=BOTTOM, at=content.bottom + 0.45 * UP)
    late_note.place(anchor=LEFT_CENTER, at=late.anchor(RIGHT_CENTER) + 0.35 * Vec2(1, 0))
    scene.add(late, late_note)
    scene.wait(1.0)

    # remove() ends lifetime immediately. It does not fade or mutate the square.
    scene.remove(immediate)
    removed_note = Text("remove() → absent from later snapshots", font_size=21, color=RED)
    removed_note.place(anchor=LEFT_CENTER, at=immediate.anchor(RIGHT_CENTER) + 0.35 * Vec2(1, 0))
    scene.add(removed_note)
    scene.wait(1.2)
    return scene


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scene = build_scene()
    print(scene.render_video(OUTPUT, verify_random_access=True))


if __name__ == "__main__":
    main()
