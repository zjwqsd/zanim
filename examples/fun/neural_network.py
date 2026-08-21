"""A self-contained neural-network pulse built from batch geometry."""
from __future__ import annotations

from pathlib import Path
import random

from zanim import BatchObject2D, Canvas, CircleSet, Color, Easing, LineSet, Scene, Text, Transform2D, Vec2
from zanim.mapping import activation_colors, activation_radii, signed_weight_colors, weight_widths

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/fun/neural_network.mp4"
LAYERS = (6, 9, 7, 4)
XPOS = (-5.4, -1.8, 1.8, 5.2)


def layer_points(x: float, count: int) -> tuple[Vec2, ...]:
    step = 5.4 / max(1, count - 1)
    return tuple(Vec2(x, 2.7 - i*step) for i in range(count))


def transparent(colors: tuple[Color, ...]) -> tuple[Color, ...]:
    return tuple(Color(c.r, c.g, c.b, 0) for c in colors)


def build_scene() -> Scene:
    rng = random.Random(20260821)
    scene = Scene(canvas=Canvas(1280, 720, 82), fps=60)
    points = tuple(layer_points(x, n) for x, n in zip(XPOS, LAYERS))

    edge_objects = []
    edge_targets = []
    for left, right in zip(points, points[1:]):
        starts = tuple(a for a in left for _ in right)
        ends = tuple(b for _ in left for b in right)
        weights = tuple(rng.uniform(-1, 1) for _ in starts)
        colors = signed_weight_colors(weights, min_alpha=18, max_alpha=135)
        widths = weight_widths(weights, minimum=0.0025, maximum=0.008)
        hidden = LineSet(starts, ends, transparent(colors), widths)
        visible = LineSet(starts, ends, colors, widths)
        edge_objects.append(BatchObject2D(hidden, z_index=0))
        edge_targets.append(visible)

    node_objects = []
    node_targets = []
    for layer_index, centers in enumerate(points):
        values = tuple(rng.random() for _ in centers)
        base = Color(80 + 40*layer_index, 150, 255 - 35*layer_index)
        fills = activation_colors(values, base=base, min_alpha=50, max_alpha=255)
        radii = activation_radii(values, minimum=0.13, maximum=0.23)
        idle = CircleSet(centers, (0.14,)*len(centers), tuple(Color(base.r, base.g, base.b, 26) for _ in centers))
        active = CircleSet(centers, radii, fills, tuple(Color(230, 238, 255, 170) for _ in centers), (0.018,)*len(centers))
        node_objects.append(BatchObject2D(idle, z_index=2))
        node_targets.append(active)

    title = Text("Signals flow; geometry stays batched", font_size=31, transform=Transform2D.translation(0, 3.55), z_index=10)
    scene.add(*edge_objects, *node_objects, title)
    scene.fade_in(title, duration=0.6)

    # Propagate left to right. Each layer transition is just two BatchClips.
    for i in range(len(edge_objects)):
        with scene.parallel():
            scene.play_batch(node_objects[i], node_targets[i], duration=0.55)
            scene.play_batch(edge_objects[i], edge_targets[i], duration=0.75, at=0.25)
            scene.play_batch(node_objects[i+1], node_targets[i+1], duration=0.55, at=0.65)
        scene.wait(0.12)

    # Emphasize the winning output neuron.
    out = points[-1]
    winner = 2
    values = tuple(1.0 if i == winner else 0.22 for i in range(len(out)))
    final = CircleSet(
        out,
        activation_radii(values, minimum=0.15, maximum=0.31),
        activation_colors(values, base=Color(255, 158, 82), min_alpha=65, max_alpha=255),
        tuple(Color(255, 240, 210, 240) for _ in out),
        (0.026,)*len(out),
    )
    scene.play_batch(node_objects[-1], final, duration=0.55, easing=Easing.SMOOTHSTEP)
    scene.wait(0.65)
    return scene


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scene = build_scene()
    print(scene.render_video(OUTPUT, verify_random_access=True))


if __name__ == "__main__":
    main()
