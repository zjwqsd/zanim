from __future__ import annotations

from pathlib import Path
import numpy as np

from zanim import (
    BatchObject2D,
    Canvas,
    CircleSet,
    Color,
    Easing,
    LineSet,
    RectSet,
    Scene,
    Vec2,
)

from zanim.mapping import (
    activation_colors,
    activation_radii,
    grayscale,
    signed_weight_colors,
    weight_widths,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "assets/mlp_inference_snapshot.npz"
OUTPUT = ROOT / "media/mlp_inference.mp4"


def transparent(colors: tuple[Color, ...]) -> tuple[Color, ...]:
    return tuple(Color(c.r, c.g, c.b, 0) for c in colors)


def build_scene() -> tuple[Scene, dict[str, int]]:
    data = np.load(SNAPSHOT)
    image = data["image"]
    x = data["x"]
    W1 = data["W1"]
    Y1 = data["Y1"]
    W2 = data["W2"]
    Y2 = data["Y2"]
    prediction = int(data["prediction"])
    label = int(data["label"])

    canvas = Canvas(width=1920, height=1080, unit_size=110)
    scene = Scene(canvas=canvas, fps=30)

    # --- Input pixels: true MNIST intensities ---
    cell = 0.105
    image_centers = tuple(
        Vec2(-7.2 + c * cell, (13.5 - r) * cell)
        for r in range(28)
        for c in range(28)
    )
    image_sizes = (Vec2(cell * 0.92, cell * 0.92),) * 784
    pixel_colors = grayscale(x)
    image_batch = RectSet(image_centers, image_sizes, pixel_colors)

    vector_step = 7.5 / 783.0
    vector_centers = tuple(Vec2(-5.4, 3.75 - i * vector_step) for i in range(784))
    vector_sizes = (Vec2(0.14, 0.0075),) * 784
    vector_batch = RectSet(vector_centers, vector_sizes, pixel_colors)
    pixels = BatchObject2D(image_batch)

    # --- Hidden/output node locations ---
    hidden_centers = tuple(Vec2(-0.6, 2.8 - i * 0.8) for i in range(8))
    output_centers = tuple(Vec2(4.4, 3.15 - i * 0.7) for i in range(10))

    hidden_active_colors = activation_colors(
        Y1, base=Color(75, 155, 255), min_alpha=24, max_alpha=245
    )
    hidden_active_radii = activation_radii(Y1, minimum=0.14, maximum=0.27)
    hidden_idle = CircleSet(
        hidden_centers,
        (0.15,) * 8,
        tuple(Color(75, 155, 255, 0) for _ in range(8)),
    )
    hidden_active = CircleSet(hidden_centers, hidden_active_radii, hidden_active_colors)
    hidden = BatchObject2D(hidden_idle)

    output_active_colors = activation_colors(
        Y2, base=Color(255, 150, 72), min_alpha=18, max_alpha=255
    )
    output_active_radii = activation_radii(Y2, minimum=0.13, maximum=0.29)
    output_idle = CircleSet(
        output_centers,
        (0.14,) * 10,
        tuple(Color(255, 150, 72, 0) for _ in range(10)),
    )
    output_active = CircleSet(output_centers, output_active_radii, output_active_colors)
    outputs = BatchObject2D(output_idle)

    # Final argmax ring. Node order top-to-bottom corresponds to 0..9, but no
    # text is drawn; the ring simply exposes the actual argmax result.
    ring_colors = tuple(
        Color(245, 247, 255, 255 if i == prediction else 0) for i in range(10)
    )
    ring_widths = (0.022,) * 10
    highlighted_radii = tuple(
        r * (1.18 if i == prediction else 1.0)
        for i, r in enumerate(output_active_radii)
    )
    output_highlight = CircleSet(
        output_centers,
        highlighted_radii,
        output_active_colors,
        ring_colors,
        ring_widths,
    )

    # --- W1: 784 x 8 true model weights ---
    input_edge_points = tuple(Vec2(-5.30, 3.75 - i * vector_step) for i in range(784))
    w1_values = tuple(float(v) for v in W1.reshape(-1))
    w1_colors = signed_weight_colors(
        w1_values, min_alpha=2, max_alpha=92
    )
    w1_widths = weight_widths(
        w1_values, minimum=0.0013, maximum=0.0075
    )
    w1_starts = tuple(p for p in input_edge_points for _ in range(8))
    w1_ends = tuple(h for _p in input_edge_points for h in hidden_centers)
    w1_hidden = LineSet(w1_starts, w1_ends, transparent(w1_colors), w1_widths)
    w1_visible = LineSet(w1_starts, w1_ends, w1_colors, w1_widths)
    w1_edges = BatchObject2D(w1_hidden)

    # --- W2: 8 x 10 true model weights ---
    w2_values = tuple(float(v) for v in W2.reshape(-1))
    w2_colors = signed_weight_colors(
        w2_values, min_alpha=5, max_alpha=155
    )
    w2_widths = weight_widths(
        w2_values, minimum=0.0018, maximum=0.0075
    )
    w2_starts = tuple(h for h in hidden_centers for _ in range(10))
    w2_ends = tuple(o for _h in hidden_centers for o in output_centers)
    w2_hidden = LineSet(w2_starts, w2_ends, transparent(w2_colors), w2_widths)
    w2_visible = LineSet(w2_starts, w2_ends, w2_colors, w2_widths)
    w2_edges = BatchObject2D(w2_hidden)

    # Draw edges first so nodes/pixels remain legible on top.
    scene.add(w1_edges, w2_edges, pixels, hidden, outputs)

    # 1) Observe the original 28x28 sample.
    scene.wait(0.6)

    # 2) Same pixel batch is rearranged into a 784-vector.
    scene.play_batch(pixels, vector_batch, duration=1.3, easing=Easing.SMOOTHSTEP)
    scene.wait(0.2)

    # 3) W1 appears, then the real hidden activations become visible.
    with scene.parallel():
        scene.play_batch(w1_edges, w1_visible, duration=0.9, easing=Easing.SMOOTHSTEP)
        scene.play_batch(hidden, hidden_active, duration=0.7, at=0.45, easing=Easing.SMOOTHSTEP)
    scene.wait(0.2)

    # 4) W2 appears, followed by the real softmax activations.
    with scene.parallel():
        scene.play_batch(w2_edges, w2_visible, duration=0.7, easing=Easing.SMOOTHSTEP)
        scene.play_batch(outputs, output_active, duration=0.7, at=0.35, easing=Easing.SMOOTHSTEP)
    scene.wait(0.25)

    # 5) Highlight the actual argmax neuron.
    scene.play_batch(outputs, output_highlight, duration=0.45, easing=Easing.SMOOTHSTEP)
    scene.wait(0.8)

    return scene, {"label": label, "prediction": prediction}


def main() -> None:
    scene, info = build_scene()
    out = scene.render_video(OUTPUT, fps=30, verify_random_access=True)
    print(out)
    print(
        f"duration={scene.timeline.cursor:.2f}s label={info['label']} "
        f"prediction={info['prediction']}"
    )


if __name__ == "__main__":
    main()
