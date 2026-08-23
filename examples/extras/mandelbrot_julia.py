"""Native viewport-resolved Mandelbrot and Julia sets.

Both fractals are mathematically unbounded procedural fields. Python authors
only their parameters and transforms; the Zig core evaluates escape-time pixels
for the current viewport on every frame. Zooming therefore reveals newly
computed detail rather than magnifying a finite texture.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from zanim import (
    MUTED,
    WHITE,
    Canvas,
    Color,
    JuliaSet,
    MandelbrotSet,
    Scene,
    Text,
    Transform2D,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/extras/mandelbrot_julia.mp4"


def _centered_transform(center: complex, scale: float) -> Transform2D:
    return Transform2D.translation(-scale * center.real, -scale * center.imag) @ Transform2D.scaling(scale)


def build_scene() -> Scene:
    scene = Scene(canvas=Canvas(1280, 720, 160), fps=60)

    title = Text("Infinite fractals", font_size=35, color=WHITE, opacity=0, z_index=20)
    subtitle = Text(
        "viewport-resolved in Zig · every zoom recomputes the complex plane",
        font_size=18,
        color=MUTED,
        opacity=0,
        z_index=20,
    )
    title.move_to((0.0, 1.94))
    subtitle.move_to((0.0, 1.62))

    mandel_label = Text("Mandelbrot  ·  z ← z² + c", font_size=22, color=WHITE, opacity=0, z_index=20)
    julia_label = Text("Julia  ·  c = -0.8 + 0.156i", font_size=22, color=WHITE, opacity=0, z_index=20)
    mandel_label.move_to((-2.70, -1.88))
    julia_label.move_to((-2.82, -1.88))

    mandelbrot = MandelbrotSet(
        max_iter=360,
        inside_color=Color(4, 6, 13),
        palette_color=Color(105, 185, 255),
        color_shift=0.06,
        color_scale=1.0,
        transform=_centered_transform(-0.55 + 0.0j, 1.18),
        z_index=-10,
    )
    julia_c = -0.8 + 0.156j
    julia = JuliaSet(
        julia_c,
        max_iter=320,
        inside_color=Color(5, 5, 13),
        palette_color=Color(255, 155, 105),
        color_shift=0.40,
        color_scale=1.08,
        opacity=0,
        transform=_centered_transform(0j, 1.28),
        z_index=-9,
    )

    mandelbrot, julia, title, subtitle, mandel_label, julia_label = scene.add(
        mandelbrot, julia, title, subtitle, mandel_label, julia_label
    )

    with scene.parallel(duration=0.65):
        title.fade_in()
        subtitle.fade_in()
        mandel_label.fade_in()
    scene.wait(0.30)

    # Famous Seahorse Valley coordinate. The final image is not a scaled bitmap:
    # Zig evaluates a ~0.044-wide slice of the complex plane at the end.
    mandel_center = -0.743643887037151 + 0.13182590420533j
    mandelbrot.affine(
        position=(-180.0 * mandel_center.real, -180.0 * mandel_center.imag),
        scale=180.0,
        duration=4.2,
    )
    scene.wait(0.55)

    with scene.parallel(duration=0.70):
        mandelbrot.fade_out()
        mandel_label.fade_out()
        julia.fade_in()
        julia_label.fade_in()
    scene.wait(0.25)

    # A boundary point chosen for a long finite orbit for this Julia parameter.
    julia_center = -0.5966666666666667 - 0.15j
    julia.affine(
        position=(-30.0 * julia_center.real, -30.0 * julia_center.imag),
        scale=30.0,
        duration=4.0,
    )
    scene.wait(0.65)

    with scene.parallel(duration=0.45):
        julia.fade_out()
        julia_label.fade_out()
        title.fade_out()
        subtitle.fade_out()
    return scene


scene = build_scene()


def main() -> None:
    parser = argparse.ArgumentParser(description="Render native Mandelbrot and Julia zooms")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    output = scene.render_video(
        args.output,
        fps=60,
        workers=args.workers,
        verify_random_access=True,
    )
    print(output)
    print(f"duration={scene.duration:.2f}s native_fractal_fields=2 random-access=ok")


if __name__ == "__main__":
    main()
