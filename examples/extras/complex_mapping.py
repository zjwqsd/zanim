"""Native infinite complex-plane mappings.

Unlike the earlier sampled prototype, this scene never constructs a finite
source rectangle or a Python LineSet. ``ComplexMappedGrid`` is a native Zig
procedural object: each target pixel is analytically inverse-mapped to the
infinite source lattice and shaded from the local complex derivative.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from zanim import (
    CYAN,
    MUTED,
    ORANGE,
    WHITE,
    YELLOW,
    Canvas,
    ComplexMappedGrid,
    Easing,
    Math,
    Scene,
    Text,
)
from zanim.value import ScalarValue

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/extras/complex_mapping.mp4"
MAP_DURATION = 2.6
HOLD_DURATION = 0.65


def _label(scene: Scene, formula: str):
    label = Math(formula, font_size=34, color=YELLOW, opacity=0, z_index=10)
    label.move_to((0.0, -4.12))
    return scene.add(label)


def _animated_map(
    scene: Scene,
    mapping: str,
    formula: str,
    *,
    step: float | tuple[float, float] = 0.5,
    exp_warp: complex = 1.0 + 0.0j,
    mobius: tuple[complex, complex, complex, complex] | None = None,
) -> None:
    """Animate one native analytic complex-map family entirely in Zig."""
    progress = ScalarValue(0.0)
    grid = ComplexMappedGrid(
        mapping,
        step=step,
        progress=progress,
        exp_warp=exp_warp,
        mobius=mobius,
        x_color=ORANGE,
        y_color=CYAN,
        stroke_width=0.022,
        opacity=0,
        z_index=1,
    )
    progress, grid = scene.add(progress, grid)
    label = _label(scene, formula)

    with scene.parallel(duration=0.42):
        grid.fade_in()
        label.fade_in()
    progress.value(to=1.0, duration=MAP_DURATION, easing=Easing.SMOOTHSTEP)
    scene.wait(HOLD_DURATION)
    with scene.parallel(duration=0.34):
        grid.fade_out()
        label.fade_out()
    scene.wait(0.12)


def build_scene() -> Scene:
    scene = Scene(canvas=Canvas(width=1280, height=960, unit_size=100), fps=60)

    title = Text("Infinite complex-plane mappings", font_size=36, color=WHITE, opacity=0, z_index=10)
    subtitle = Text(
        "native inverse mapping · no source window · no sampled polylines",
        font_size=19,
        color=MUTED,
        opacity=0,
        z_index=10,
    )
    legend_h = Text("Re(z) = constant", font_size=17, color=ORANGE, opacity=0, z_index=10)
    legend_v = Text("Im(z) = constant", font_size=17, color=CYAN, opacity=0, z_index=10)
    title.move_to((0.0, 4.25))
    subtitle.move_to((0.0, 3.82))
    legend_h.move_to((-4.75, 3.33))
    legend_v.move_to((-4.75, 3.01))

    title, subtitle, legend_h, legend_v = scene.add(title, subtitle, legend_h, legend_v)
    with scene.parallel(duration=0.7):
        title.fade_in()
        subtitle.fade_in()
        legend_h.fade_in()
        legend_v.fade_in()
    scene.wait(0.25)

    # H_a(z) = (1-a)z + a z^2.  The Zig core analytically solves both inverse
    # branches, including the branch arriving from infinity for every a > 0.
    _animated_map(scene, "square", r"H_a(z)=(1-a)z+a z^2")

    # A one-parameter Möbius subgroup gives a nonsingular identity -> 1/z
    # homotopy: H_a(z)=(cos θ z+i sin θ)/(i sin θ z+cos θ), θ=aπ/2.
    _animated_map(scene, "reciprocal", r"H_a(z): z -> 1/z")

    # This is a genuine periodic analytic homotopy, not a crossfade:
    # F_a(z)=exp(z)-1+(1-a)exp(-z), from 2 cosh(z)-1 to exp(z)-1.
    exp_step = (0.5, 2.0 * math.pi / 12.0)
    _animated_map(
        scene,
        "exp",
        r"F_a(z)=e^z-1+(1-a)e^(-z)",
        step=exp_step,
    )

    # Choose a nontrivial target and let the core construct a guaranteed
    # nonsingular identity -> target Gauss path in PSL(2,C).
    b = 0.70 - 0.32j
    c = 0.24 - 0.16j
    mobius = (1.0 + b * c, b, c, 1.0 + 0.0j)
    _animated_map(
        scene,
        "mobius",
        r"M_a(z): z -> (A_a z+B_a)/(C_a z+D_a)",
        mobius=mobius,
    )

    scene.wait(0.35)
    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description="Render native infinite complex-plane mappings")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    scene = build_scene()
    output = scene.render_video(
        args.output,
        fps=60,
        workers=args.workers,
        verify_random_access=True,
    )
    print(output)
    print(f"duration={scene.duration:.2f}s native_complex_grid=1 random-access=ok")


if __name__ == "__main__":
    main()
