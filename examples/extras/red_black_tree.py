"""Animate random red-black-tree insertions, recolors, and rotations."""

from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import NamedTuple

from zanim import (
    GRAY,
    MUTED,
    RED,
    WHITE,
    YELLOW,
    Canvas,
    Color,
    Scene,
    Text,
    Vec2,
)
from zanim.batch import BatchObject2D, CircleSet, LineSet

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/extras/red_black_tree.mp4"

DEFAULT_SEED = 19
DEFAULT_COUNT = 12
VALUE_MIN = 10
VALUE_MAX = 99

NODE_RADIUS = 0.34
TREE_TOP = 2.55
LEVEL_GAP = 1.18
TREE_WIDTH = 10.2
HIDDEN_Y = -4.15

STATUS_FADE = 0.12
INSERT_DURATION = 0.58
RECOLOR_DURATION = 0.48
ROTATE_DURATION = 0.72
STEP_HOLD = 0.12
INSERT_HOLD = 0.20

BLACK_NODE = Color(22, 26, 34)
RED_NODE = RED
EDGE_COLOR = Color(135, 148, 174, 190)
NODE_STROKE = Color(188, 198, 220, 210)
TRANSPARENT_EDGE = Color(135, 148, 174, 0)
TRANSPARENT_BLACK = Color(BLACK_NODE.r, BLACK_NODE.g, BLACK_NODE.b, 0)


class RBNode:
    __slots__ = ("value", "red", "left", "right", "parent")

    def __init__(self, value: int) -> None:
        self.value = int(value)
        self.red = True
        self.left: RBNode | None = None
        self.right: RBNode | None = None
        self.parent: RBNode | None = None


class NodeState(NamedTuple):
    value: int
    red: bool
    parent: int | None
    depth: int


class TraceStep(NamedTuple):
    kind: str
    message: str
    nodes: tuple[NodeState, ...]
    active: tuple[int, ...] = ()


class RedBlackTree:
    """Minimal CLRS-style red-black tree that records visual fix-up steps."""

    def __init__(self) -> None:
        self.root: RBNode | None = None
        self.nodes: dict[int, RBNode] = {}
        self.steps: list[TraceStep] = []

    @staticmethod
    def _is_red(node: RBNode | None) -> bool:
        return node is not None and node.red

    def _snapshot(self, kind: str, message: str, *active: RBNode | None) -> None:
        states: list[NodeState] = []

        def visit(node: RBNode | None, depth: int) -> None:
            if node is None:
                return
            states.append(
                NodeState(
                    node.value,
                    node.red,
                    None if node.parent is None else node.parent.value,
                    depth,
                )
            )
            visit(node.left, depth + 1)
            visit(node.right, depth + 1)

        visit(self.root, 0)
        active_values = tuple(node.value for node in active if node is not None)
        self.steps.append(TraceStep(kind, message, tuple(sorted(states)), active_values))

    def _left_rotate(self, pivot: RBNode) -> None:
        child = pivot.right
        if child is None:
            raise RuntimeError("left rotation requires a right child")
        pivot.right = child.left
        if child.left is not None:
            child.left.parent = pivot
        child.parent = pivot.parent
        if pivot.parent is None:
            self.root = child
        elif pivot is pivot.parent.left:
            pivot.parent.left = child
        else:
            pivot.parent.right = child
        child.left = pivot
        pivot.parent = child

    def _right_rotate(self, pivot: RBNode) -> None:
        child = pivot.left
        if child is None:
            raise RuntimeError("right rotation requires a left child")
        pivot.left = child.right
        if child.right is not None:
            child.right.parent = pivot
        child.parent = pivot.parent
        if pivot.parent is None:
            self.root = child
        elif pivot is pivot.parent.right:
            pivot.parent.right = child
        else:
            pivot.parent.left = child
        child.right = pivot
        pivot.parent = child

    def insert(self, value: int) -> None:
        if value in self.nodes:
            raise ValueError(f"duplicate red-black-tree value: {value}")

        parent: RBNode | None = None
        cursor = self.root
        while cursor is not None:
            parent = cursor
            cursor = cursor.left if value < cursor.value else cursor.right

        node = RBNode(value)
        node.parent = parent
        if parent is None:
            self.root = node
        elif value < parent.value:
            parent.left = node
        else:
            parent.right = node
        self.nodes[value] = node
        self._snapshot("insert", f"insert {value} · new node is red", node, parent)

        self._fix_insert(node)

    def _fix_insert(self, node: RBNode) -> None:
        while node.parent is not None and node.parent.red:
            parent = node.parent
            grand = parent.parent
            if grand is None:
                break

            if parent is grand.left:
                uncle = grand.right
                if self._is_red(uncle):
                    parent.red = False
                    assert uncle is not None
                    uncle.red = False
                    grand.red = True
                    self._snapshot(
                        "recolor",
                        "parent + uncle are red · recolor and move upward",
                        parent,
                        uncle,
                        grand,
                    )
                    node = grand
                    continue

                if node is parent.right:
                    node = parent
                    self._left_rotate(node)
                    self._snapshot(
                        "rotate_left",
                        f"inside case · left rotate at {node.value}",
                        node,
                        node.parent,
                    )
                    parent = node.parent
                    assert parent is not None
                    grand = parent.parent
                    assert grand is not None

                parent.red = False
                grand.red = True
                self._snapshot(
                    "recolor",
                    "outside case · swap parent / grandparent colors",
                    parent,
                    grand,
                )
                pivot_value = grand.value
                self._right_rotate(grand)
                self._snapshot(
                    "rotate_right",
                    f"right rotate at {pivot_value}",
                    grand,
                    grand.parent,
                )
            else:
                uncle = grand.left
                if self._is_red(uncle):
                    parent.red = False
                    assert uncle is not None
                    uncle.red = False
                    grand.red = True
                    self._snapshot(
                        "recolor",
                        "parent + uncle are red · recolor and move upward",
                        parent,
                        uncle,
                        grand,
                    )
                    node = grand
                    continue

                if node is parent.left:
                    node = parent
                    self._right_rotate(node)
                    self._snapshot(
                        "rotate_right",
                        f"inside case · right rotate at {node.value}",
                        node,
                        node.parent,
                    )
                    parent = node.parent
                    assert parent is not None
                    grand = parent.parent
                    assert grand is not None

                parent.red = False
                grand.red = True
                self._snapshot(
                    "recolor",
                    "outside case · swap parent / grandparent colors",
                    parent,
                    grand,
                )
                pivot_value = grand.value
                self._left_rotate(grand)
                self._snapshot(
                    "rotate_left",
                    f"left rotate at {pivot_value}",
                    grand,
                    grand.parent,
                )

        if self.root is not None and self.root.red:
            self.root.red = False
            self._snapshot("root_black", "root must be black", self.root)

    def validate(self) -> int:
        """Validate all red-black invariants and return the black height."""
        if self.root is None:
            return 1
        if self.root.red:
            raise AssertionError("red-black root must be black")

        def visit(node: RBNode | None, lower: int | None, upper: int | None) -> int:
            if node is None:
                return 1
            if lower is not None and node.value <= lower:
                raise AssertionError("BST lower bound violated")
            if upper is not None and node.value >= upper:
                raise AssertionError("BST upper bound violated")
            if node.left is not None and node.left.parent is not node:
                raise AssertionError("left parent link violated")
            if node.right is not None and node.right.parent is not node:
                raise AssertionError("right parent link violated")
            if node.red and (self._is_red(node.left) or self._is_red(node.right)):
                raise AssertionError("red node has red child")
            left = visit(node.left, lower, node.value)
            right = visit(node.right, node.value, upper)
            if left != right:
                raise AssertionError("black heights differ")
            return left + (0 if node.red else 1)

        return visit(self.root, None, None)


def random_values(seed: int, count: int) -> tuple[int, ...]:
    if count < 1:
        raise ValueError("count must be positive")
    population = VALUE_MAX - VALUE_MIN + 1
    if count > population:
        raise ValueError(f"count must be <= {population}")
    return tuple(random.Random(seed).sample(range(VALUE_MIN, VALUE_MAX + 1), count))


def build_trace(values: tuple[int, ...]) -> tuple[TraceStep, ...]:
    tree = RedBlackTree()
    for value in values:
        tree.insert(value)
        tree.validate()
    return tuple(tree.steps)


def _position_map(step: TraceStep, all_values: tuple[int, ...]) -> dict[int, Vec2]:
    rank = {value: index for index, value in enumerate(sorted(all_values))}
    denominator = max(1, len(all_values) - 1)
    states = {state.value: state for state in step.nodes}
    positions: dict[int, Vec2] = {}
    for value in all_values:
        x = -TREE_WIDTH * 0.5 + TREE_WIDTH * rank[value] / denominator
        if value in states:
            y = TREE_TOP - states[value].depth * LEVEL_GAP
        else:
            y = HIDDEN_Y
        positions[value] = Vec2(x, y)
    return positions


def _edge_endpoints(parent: Vec2, child: Vec2) -> tuple[Vec2, Vec2]:
    dx = child.x - parent.x
    dy = child.y - parent.y
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 1e-12:
        return parent, child
    ux, uy = dx / length, dy / length
    return (
        Vec2(parent.x + ux * NODE_RADIUS, parent.y + uy * NODE_RADIUS),
        Vec2(child.x - ux * NODE_RADIUS, child.y - uy * NODE_RADIUS),
    )


def _node_batch(
    step: TraceStep | None,
    all_values: tuple[int, ...],
) -> CircleSet:
    if step is None:
        positions = {
            value: Vec2(
                -TREE_WIDTH * 0.5 + TREE_WIDTH * index / max(1, len(all_values) - 1),
                HIDDEN_Y,
            )
            for index, value in enumerate(sorted(all_values))
        }
        states: dict[int, NodeState] = {}
        active: set[int] = set()
    else:
        positions = _position_map(step, all_values)
        states = {state.value: state for state in step.nodes}
        active = set(step.active)

    centers = []
    fills = []
    strokes = []
    widths = []
    for value in sorted(all_values):
        centers.append(positions[value])
        state = states.get(value)
        if state is None:
            fills.append(TRANSPARENT_BLACK)
            strokes.append(Color(NODE_STROKE.r, NODE_STROKE.g, NODE_STROKE.b, 0))
        else:
            fills.append(RED_NODE if state.red else BLACK_NODE)
            strokes.append(YELLOW if value in active else NODE_STROKE)
        widths.append(0.055 if value in active else 0.030)
    return CircleSet(
        tuple(centers),
        tuple(NODE_RADIUS for _ in centers),
        tuple(fills),
        tuple(strokes),
        tuple(widths),
    )


def _edge_batch(step: TraceStep | None, all_values: tuple[int, ...]) -> LineSet:
    if step is None:
        states: dict[int, NodeState] = {}
        positions = _position_map(TraceStep("empty", "", ()), all_values)
    else:
        states = {state.value: state for state in step.nodes}
        positions = _position_map(step, all_values)

    starts = []
    ends = []
    colors = []
    widths = []
    for value in sorted(all_values):
        state = states.get(value)
        if state is None or state.parent is None:
            point = positions[value]
            starts.append(point)
            ends.append(point)
            colors.append(TRANSPARENT_EDGE)
        else:
            start, end = _edge_endpoints(positions[state.parent], positions[value])
            starts.append(start)
            ends.append(end)
            colors.append(EDGE_COLOR)
        widths.append(0.025)
    return LineSet(tuple(starts), tuple(ends), tuple(colors), tuple(widths))


def _status_color(kind: str):
    if kind == "insert":
        return WHITE
    if kind == "recolor":
        return YELLOW
    if kind.startswith("rotate"):
        return Color(110, 205, 255)
    if kind == "root_black":
        return GRAY
    return MUTED


def _step_duration(kind: str) -> float:
    if kind == "insert":
        return INSERT_DURATION
    if kind.startswith("rotate"):
        return ROTATE_DURATION
    return RECOLOR_DURATION


def _build_scene(*, seed: int = DEFAULT_SEED, count: int = DEFAULT_COUNT) -> tuple[Scene, dict]:
    values = random_values(seed, count)
    trace = build_trace(values)

    scene = Scene(canvas=Canvas(width=1280, height=960, unit_size=100), fps=60)
    title = Text("Random red-black tree insertion", font_size=34, color=WHITE)
    sequence = Text(
        "sequence  " + "  ".join(str(value) for value in values),
        font_size=18,
        color=MUTED,
    )
    title.move_to((0, 4.35))
    sequence.move_to((0, 3.90))

    nodes = BatchObject2D(_node_batch(None, values), z_index=2)
    edges = BatchObject2D(_edge_batch(None, values), z_index=0)
    edges, nodes, title, sequence = scene.add(edges, nodes, title, sequence)

    labels = {}
    initial_positions = _position_map(TraceStep("empty", "", ()), values)
    for value in values:
        label = Text(str(value), font_size=18, color=WHITE, opacity=0, z_index=4)
        label.move_to(initial_positions[value])
        labels[value] = scene.add(label)

    status = Text(
        f"seed {seed} · {count} unique keys",
        font_size=20,
        color=MUTED,
        opacity=0,
        z_index=10,
    )
    status.move_to((0, 3.43))
    status = scene.add(status)
    status.fade_in(duration=0.25)
    scene.wait(0.22)

    visible: set[int] = set()
    previous_step: TraceStep | None = None
    kind_counts: dict[str, int] = {}

    for step in trace:
        kind_counts[step.kind] = kind_counts.get(step.kind, 0) + 1
        next_status = Text(
            step.message,
            font_size=20,
            color=_status_color(step.kind),
            opacity=0,
            z_index=10,
        )
        next_status.move_to((0, 3.43))
        next_status = scene.add(next_status)
        with scene.parallel(duration=STATUS_FADE):
            status.fade_out()
            next_status.fade_in()
        status.remove()
        status = next_status

        duration = _step_duration(step.kind)
        positions = _position_map(step, values)
        step_values = {state.value for state in step.nodes}
        newly_visible = step_values - visible

        with scene.parallel(duration=duration):
            nodes.batch(to=_node_batch(step, values))
            edges.batch(to=_edge_batch(step, values))
            for value in step_values:
                labels[value].move(to=positions[value])
            for value in newly_visible:
                labels[value].fade_in()

        visible = step_values
        previous_step = step
        scene.wait(INSERT_HOLD if step.kind == "insert" else STEP_HOLD)

    final_status = Text(
        "all invariants restored · root black · equal black height",
        font_size=20,
        color=Color(120, 220, 165),
        opacity=0,
        z_index=10,
    )
    final_status.move_to((0, 3.43))
    final_status = scene.add(final_status)
    with scene.parallel(duration=0.24):
        status.fade_out()
        final_status.fade_in()
    status.remove()
    scene.wait(0.85)

    info = {
        "seed": seed,
        "count": count,
        "values": values,
        "steps": len(trace),
        "kind_counts": kind_counts,
        "final_step": previous_step,
    }
    return scene, info


def build_scene() -> Scene:
    """Default scene used by ``zanim preview/render``."""
    scene, _ = _build_scene()
    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description="Animate random red-black-tree insertion")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    scene, info = _build_scene(seed=args.seed, count=args.count)
    output = scene.render_video(
        args.output,
        fps=60,
        workers=8,
        verify_random_access=True,
    )
    print(output)
    counts = info["kind_counts"]
    print(
        f"duration={scene.duration:.2f}s seed={args.seed} values={info['values']} "
        f"steps={info['steps']} rotations={counts.get('rotate_left', 0) + counts.get('rotate_right', 0)} "
        f"recolors={counts.get('recolor', 0)} random-access=ok"
    )


if __name__ == "__main__":
    main()
