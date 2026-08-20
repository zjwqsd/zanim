from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import random

from zanim import (
    Canvas,
    Circle,
    Color,
    FormulaLiteral,
    FormulaTemplate,
    MatrixSlot,
    NumberFormat,
    Object2D,
    ObjectSlot,
    Scene,
    Style,
    Transform2D,
)


@dataclass(frozen=True, slots=True)
class MatrixState:
    A: tuple[tuple[int, int], tuple[int, int]]
    B: tuple[tuple[int, int], tuple[int, int]]
    C: tuple[tuple[int, int], tuple[int, int]]


class RandomMatrixProduct:
    """Pure random-access source: equal time tick => equal A, B and C."""

    def __init__(self, *, seed: int = 20260820, hz: float = 10.0, hold: float = 0.45) -> None:
        self.seed = seed
        self.hz = hz
        self.hold = hold

    def tick_at(self, time: float) -> int:
        if time <= self.hold:
            return 0
        return 1 + int((time - self.hold) * self.hz)

    @lru_cache(maxsize=256)
    def state_for_tick(self, tick: int) -> MatrixState:
        rng = random.Random(self.seed + tick * 1_000_003)
        A = tuple(tuple(rng.randint(-9, 9) for _ in range(2)) for _ in range(2))
        B = tuple(tuple(rng.randint(-9, 9) for _ in range(2)) for _ in range(2))
        C = tuple(
            tuple(sum(A[i][k] * B[k][j] for k in range(2)) for j in range(2))
            for i in range(2)
        )
        return MatrixState(A=A, B=B, C=C)  # type: ignore[arg-type]

    def state_at(self, time: float) -> MatrixState:
        return self.state_for_tick(self.tick_at(time))


def build_scene() -> tuple[Scene, RandomMatrixProduct]:
    source = RandomMatrixProduct()
    white = Color(238, 242, 250)
    result = Color(255, 184, 108)

    small_int = NumberFormat(width=2, sign="negative")
    product_int = NumberFormat(width=4, sign="negative")

    template = FormulaTemplate(
        MatrixSlot("A", 2, 2, small_int, font_size=44, color=white),
        # Geometry object inside the fixed formula skeleton, not a text glyph.
        ObjectSlot("multiply", box_width=0.34, box_height=0.34, padding=0.07, math_class="binary"),
        MatrixSlot("B", 2, 2, small_int, font_size=44, color=white),
        FormulaLiteral("=", font_size=44, color=white),
        MatrixSlot("C", 2, 2, product_int, font_size=44, color=result),
        gap=0.0,
        font_size=44,
        color=white,
    )

    multiply_dot = Object2D(
        Circle(0.12),
        style=Style(fill=Color(154, 176, 224), stroke=None),
    )

    scene = Scene(canvas=Canvas(width=1920, height=1080, unit_size=100), fps=60)
    template.mount(
        scene,
        {
            "A": lambda t: source.state_at(t).A,
            "B": lambda t: source.state_at(t).B,
            "C": lambda t: source.state_at(t).C,
            "multiply": multiply_dot,
        },
        transform=Transform2D.scaling(1.30),
    )

    # Dynamic slots derive their values directly from absolute scene time.
    # The template itself never changes dimensions or reflows.
    scene.wait(5.0)
    return scene, source


def verify_product(source: RandomMatrixProduct) -> None:
    for time in (0.0, 0.51, 1.37, 2.91, 4.73, 1.37):
        state = source.state_at(time)
        expected = tuple(
            tuple(sum(state.A[i][k] * state.B[k][j] for k in range(2)) for j in range(2))
            for i in range(2)
        )
        assert state.C == expected


def main() -> None:
    scene, source = build_scene()
    verify_product(source)
    output = scene.render_video(
        "media/dynamic_matrix_formula.mp4",
        fps=60,
        verify_random_access=True,
    )
    print(output)
    print("duration=5.00s fps=60 updates=10Hz product-sync=ok random-access=ok")


if __name__ == "__main__":
    main()
