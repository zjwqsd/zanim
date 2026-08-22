"""Lesson 02: explicit object lifetime and explicit visual state."""

from __future__ import annotations

from zanim import (
    BLUE,
    BOTTOM,
    DOWN,
    GREEN,
    LEFT_CENTER,
    MUTED,
    ORANGE,
    PURPLE,
    RED,
    RIGHT_CENTER,
    TOP,
    UP,
    Canvas,
    Circle,
    Row,
    Scene,
    Square,
    Text,
    Vec2,
)


def card_label(text: str) -> Text:
    return Text(text, font_size=22, color=MUTED)


scene = Scene(canvas=Canvas(1280, 720, 92), fps=60)

# Declare.
title = Text("Explicit state, explicit time", font_size=36)
rule = Text(
    "add/remove define lifetime; animations only change authored state",
    font_size=23,
    color=MUTED,
)
immediate = Square(1.25, fill=BLUE)
hidden = Circle(0.68, fill=GREEN, opacity=0)
drawn = Square(1.25, stroke=PURPLE, stroke_width=0.055, trim=0)
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
    title,
    rule,
    immediate,
    hidden,
    drawn,
    immediate_label,
    hidden_label,
    drawn_label,
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
late = Circle(0.36, fill=ORANGE)
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

scene.preview()
