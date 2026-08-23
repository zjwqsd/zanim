"""Visualize common sorting algorithms with a shuffled permutation of line lengths 1..n."""

from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Callable, NamedTuple

from zanim import (
    BLUE,
    GREEN,
    MUTED,
    ORANGE,
    PINK,
    WHITE,
    YELLOW,
    Canvas,
    Color,
    Scene,
    Text,
    Vec2,
)
from zanim.batch import BatchObject2D, LineSet

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/extras/sorting_algorithms.mp4"

DEFAULT_N = 24
DEFAULT_SEED = 23
STEP_DURATION = 0.065
MOVE_DURATION = 0.06
SECTION_HOLD = 0.175
SECTION_FADE = 0.14

BASELINE_Y = -3.05
MAX_HEIGHT = 5.65
CHART_WIDTH = 10.2
BAR_WIDTH = 0.11

NORMAL = BLUE
COMPARE = YELLOW
MOVE = ORANGE
PIVOT = PINK
SORTED = GREEN
BASELINE = Color(103, 114, 138, 105)


class SortStep(NamedTuple):
    kind: str
    values: tuple[int, ...]
    active: tuple[int, ...] = ()
    pivot: int | None = None
    settled: tuple[int, ...] = ()


class SortTrace(NamedTuple):
    name: str
    subtitle: str
    steps: tuple[SortStep, ...]


class _Recorder:
    def __init__(self, values: tuple[int, ...]) -> None:
        self.values = list(values)
        self.steps: list[SortStep] = []

    def add(
        self,
        kind: str,
        *,
        active: tuple[int, ...] = (),
        pivot: int | None = None,
        settled: tuple[int, ...] = (),
    ) -> None:
        self.steps.append(SortStep(kind, tuple(self.values), active, pivot, settled))

    def compare(
        self,
        i: int,
        j: int,
        *,
        pivot: int | None = None,
        settled: tuple[int, ...] = (),
    ) -> None:
        self.add(
            "compare",
            active=(self.values[i], self.values[j]),
            pivot=pivot,
            settled=settled,
        )

    def swap(
        self,
        i: int,
        j: int,
        *,
        pivot: int | None = None,
        settled: tuple[int, ...] = (),
    ) -> None:
        a, b = self.values[i], self.values[j]
        self.values[i], self.values[j] = b, a
        self.add("move", active=(a, b), pivot=pivot, settled=settled)

    def move_value(
        self,
        source: int,
        target: int,
        *,
        settled: tuple[int, ...] = (),
    ) -> None:
        value = self.values.pop(source)
        self.values.insert(target, value)
        self.add("move", active=(value,), settled=settled)

    def finish(self) -> None:
        self.add("done", settled=tuple(self.values))


def random_permutation(n: int, seed: int = DEFAULT_SEED) -> tuple[int, ...]:
    if n < 2:
        raise ValueError("n must be >= 2")
    values = list(range(1, n + 1))
    random.Random(seed).shuffle(values)
    return tuple(values)


def bubble_sort_trace(values: tuple[int, ...]) -> SortTrace:
    r = _Recorder(values)
    n = len(r.values)
    settled: tuple[int, ...] = ()
    for end in range(n - 1, 0, -1):
        swapped = False
        for i in range(end):
            r.compare(i, i + 1, settled=settled)
            if r.values[i] > r.values[i + 1]:
                r.swap(i, i + 1, settled=settled)
                swapped = True
        settled = tuple(r.values[end:])
        r.add("settle", settled=settled)
        if not swapped:
            break
    r.finish()
    return SortTrace(
        "Bubble sort", "adjacent comparisons · largest value bubbles right", tuple(r.steps)
    )


def selection_sort_trace(values: tuple[int, ...]) -> SortTrace:
    r = _Recorder(values)
    n = len(r.values)
    settled: tuple[int, ...] = ()
    for start in range(n - 1):
        minimum = start
        for j in range(start + 1, n):
            r.compare(minimum, j, pivot=r.values[minimum], settled=settled)
            if r.values[j] < r.values[minimum]:
                minimum = j
                r.add(
                    "pivot", active=(r.values[minimum],), pivot=r.values[minimum], settled=settled
                )
        if minimum != start:
            r.swap(start, minimum, settled=settled)
        settled = tuple(r.values[: start + 1])
        r.add("settle", settled=settled)
    r.finish()
    return SortTrace(
        "Selection sort", "scan for the minimum · place one value per pass", tuple(r.steps)
    )


def insertion_sort_trace(values: tuple[int, ...]) -> SortTrace:
    r = _Recorder(values)
    n = len(r.values)
    for end in range(1, n):
        key = r.values[end]
        i = end
        while i > 0:
            settled = tuple(r.values[:i])
            r.compare(i - 1, i, pivot=key, settled=settled)
            if r.values[i - 1] <= r.values[i]:
                break
            r.swap(i - 1, i, pivot=key)
            i -= 1
        r.add("settle", settled=tuple(r.values[: end + 1]))
    r.finish()
    return SortTrace(
        "Insertion sort", "grow a sorted prefix · insert each next value", tuple(r.steps)
    )


def merge_sort_trace(values: tuple[int, ...]) -> SortTrace:
    r = _Recorder(values)

    def merge(lo: int, mid: int, hi: int) -> None:
        left = list(r.values[lo:mid])
        right = list(r.values[mid:hi])
        merged: list[int] = []
        i = j = 0
        while i < len(left) and j < len(right):
            a, b = left[i], right[j]
            ia, ib = r.values.index(a), r.values.index(b)
            r.compare(ia, ib)
            if a <= b:
                merged.append(a)
                i += 1
            else:
                merged.append(b)
                j += 1
        merged.extend(left[i:])
        merged.extend(right[j:])

        for offset, value in enumerate(merged):
            target = lo + offset
            source = r.values.index(value)
            if source != target:
                r.move_value(source, target)
        r.add("settle", settled=tuple(r.values[lo:hi]))

    def sort(lo: int, hi: int) -> None:
        if hi - lo <= 1:
            return
        mid = (lo + hi) // 2
        sort(lo, mid)
        sort(mid, hi)
        merge(lo, mid, hi)

    sort(0, len(r.values))
    r.finish()
    return SortTrace("Merge sort", "merge sorted runs · stable divide and conquer", tuple(r.steps))


def quick_sort_trace(values: tuple[int, ...]) -> SortTrace:
    r = _Recorder(values)
    fixed: set[int] = set()

    def partition(lo: int, hi: int) -> int:
        pivot = r.values[hi]
        r.add("pivot", active=(pivot,), pivot=pivot, settled=tuple(sorted(fixed)))
        i = lo
        for j in range(lo, hi):
            r.compare(j, hi, pivot=pivot, settled=tuple(sorted(fixed)))
            if r.values[j] < pivot:
                if i != j:
                    r.swap(i, j, pivot=pivot, settled=tuple(sorted(fixed)))
                i += 1
        if i != hi:
            r.swap(i, hi, pivot=pivot, settled=tuple(sorted(fixed)))
        fixed.add(pivot)
        r.add("settle", pivot=pivot, settled=tuple(sorted(fixed)))
        return i

    def sort(lo: int, hi: int) -> None:
        if lo > hi:
            return
        if lo == hi:
            fixed.add(r.values[lo])
            r.add("settle", settled=tuple(sorted(fixed)))
            return
        p = partition(lo, hi)
        sort(lo, p - 1)
        sort(p + 1, hi)

    sort(0, len(r.values) - 1)
    r.finish()
    return SortTrace(
        "Quick sort", "partition around a pivot · recurse on both sides", tuple(r.steps)
    )


def heap_sort_trace(values: tuple[int, ...]) -> SortTrace:
    r = _Recorder(values)
    n = len(r.values)
    settled: tuple[int, ...] = ()

    def sift_down(root: int, size: int) -> None:
        while True:
            child = 2 * root + 1
            if child >= size:
                return
            largest = root
            r.compare(largest, child, settled=settled)
            if r.values[child] > r.values[largest]:
                largest = child
            right = child + 1
            if right < size:
                r.compare(largest, right, settled=settled)
                if r.values[right] > r.values[largest]:
                    largest = right
            if largest == root:
                return
            r.swap(root, largest, settled=settled)
            root = largest

    for root in range(n // 2 - 1, -1, -1):
        sift_down(root, n)

    for end in range(n - 1, 0, -1):
        r.swap(0, end, settled=settled)
        settled = tuple(r.values[end:])
        r.add("settle", settled=settled)
        sift_down(0, end)
    r.finish()
    return SortTrace(
        "Heap sort", "build a max heap · repeatedly extract the maximum", tuple(r.steps)
    )


ALGORITHMS: tuple[tuple[str, Callable[[tuple[int, ...]], SortTrace]], ...] = (
    ("bubble", bubble_sort_trace),
    ("selection", selection_sort_trace),
    ("insertion", insertion_sort_trace),
    ("merge", merge_sort_trace),
    ("quick", quick_sort_trace),
    ("heap", heap_sort_trace),
)


def _line_state(step: SortStep, n: int) -> LineSet:
    position = {value: index for index, value in enumerate(step.values)}
    spacing = CHART_WIDTH / max(1, n - 1)
    height_scale = MAX_HEIGHT / n
    x0 = -CHART_WIDTH * 0.5
    active = set(step.active)
    settled = set(step.settled)

    starts: list[Vec2] = []
    ends: list[Vec2] = []
    colors: list[Color] = []
    widths: list[float] = []
    for value in range(1, n + 1):
        x = x0 + position[value] * spacing
        starts.append(Vec2(x, BASELINE_Y))
        ends.append(Vec2(x, BASELINE_Y + value * height_scale))
        if value == step.pivot:
            color = PIVOT
        elif value in active:
            color = MOVE if step.kind == "move" else COMPARE
        elif value in settled:
            color = SORTED
        else:
            color = NORMAL
        colors.append(color)
        widths.append(BAR_WIDTH)
    return LineSet(tuple(starts), tuple(ends), tuple(colors), tuple(widths))


def _initial_step(values: tuple[int, ...]) -> SortStep:
    return SortStep("initial", values)


def _trace_for(name: str, values: tuple[int, ...]) -> SortTrace:
    key = name.casefold().strip()
    matches = [(short, factory) for short, factory in ALGORITHMS if key in short]
    if len(matches) != 1:
        options = ", ".join(short for short, _ in ALGORITHMS)
        raise ValueError(f"algorithm must identify one of: {options}")
    return matches[0][1](values)


def _animate_trace(scene: Scene, trace: SortTrace, initial: tuple[int, ...], n: int) -> None:
    title = Text(trace.name, font_size=35, color=WHITE, opacity=0, z_index=10)
    subtitle = Text(trace.subtitle, font_size=18, color=MUTED, opacity=0, z_index=10)
    legend = Text(
        "yellow compare   ·   orange move   ·   pink pivot   ·   green settled",
        font_size=17,
        color=MUTED,
        opacity=0,
        z_index=10,
    )
    title.move_to((0, 4.2))
    subtitle.move_to((0, 3.76))
    legend.move_to((0, -4.25))

    bars = BatchObject2D(_line_state(_initial_step(initial), n), opacity=0, z_index=1)
    baseline = BatchObject2D(
        LineSet(
            (Vec2(-5.4, BASELINE_Y),),
            (Vec2(5.4, BASELINE_Y),),
            (BASELINE,),
            (0.018,),
        ),
        opacity=0,
        z_index=0,
    )
    bars, baseline, title, subtitle, legend = scene.add(bars, baseline, title, subtitle, legend)
    with scene.parallel(duration=0.2):
        bars.fade_in()
        baseline.fade_in()
        title.fade_in()
        subtitle.fade_in()
        legend.fade_in()
    scene.wait(0.09)

    for step in trace.steps:
        duration = MOVE_DURATION if step.kind == "move" else STEP_DURATION
        bars.batch(to=_line_state(step, n), duration=duration)

    scene.wait(SECTION_HOLD)
    with scene.parallel(duration=SECTION_FADE):
        bars.fade_out()
        baseline.fade_out()
        title.fade_out()
        subtitle.fade_out()
        legend.fade_out()
    for obj in (bars, baseline, title, subtitle, legend):
        obj.remove()


def _build_scene(
    *,
    n: int = DEFAULT_N,
    seed: int = DEFAULT_SEED,
    algorithm: str | None = None,
) -> tuple[Scene, tuple[int, ...], tuple[SortTrace, ...]]:
    if not 2 <= n <= 32:
        raise ValueError("n must be between 2 and 32")
    initial = random_permutation(n, seed)
    traces = (
        (_trace_for(algorithm, initial),)
        if algorithm is not None
        else tuple(factory(initial) for _, factory in ALGORITHMS)
    )

    scene = Scene(canvas=Canvas(width=1280, height=960, unit_size=100), fps=60)
    for trace in traces:
        _animate_trace(scene, trace, initial, n)
    scene.wait(0.125)
    return scene, initial, traces


def build_scene() -> Scene:
    """Default scene used by ``zanim preview/render``."""
    scene, _, _ = _build_scene()
    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize common sorting algorithms")
    parser.add_argument("--n", type=int, default=DEFAULT_N, help="permutation size")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--algorithm", type=str, default=None)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    scene, initial, traces = _build_scene(n=args.n, seed=args.seed, algorithm=args.algorithm)
    output = scene.render_video(args.output, fps=60, workers=8, verify_random_access=True)
    print(output)
    print(f"duration={scene.duration:.2f}s n={args.n} seed={args.seed} initial={initial}")
    for trace in traces:
        moves = sum(step.kind == "move" for step in trace.steps)
        compares = sum(step.kind == "compare" for step in trace.steps)
        print(f"{trace.name}: steps={len(trace.steps)} compares={compares} moves={moves}")
    print("random-access=ok")


if __name__ == "__main__":
    main()
