from __future__ import annotations

import argparse
from functools import lru_cache
from math import floor, pi, sin, cos, sqrt
from pathlib import Path
import random

from zanim import (
    Box3D,
    Camera3D,
    Canvas,
    Color,
    Cube3D,
    Easing,
    FormulaLiteral,
    FormulaTemplate,
    MatrixSlot,
    MeshObject3D,
    NumberFormat,
    SO3,
    Scene,
    Text,
    Transform2D,
    Transform3D,
    Vec2,
    Vec3,
)

DURATION = 12.0
KEYFRAME_SECONDS = 1.5
EDGE_THICKNESS = 0.032

X = Color(242, 82, 92)
Y = Color(82, 214, 124)
Z = Color(82, 145, 255)
X_DIM = Color(132, 57, 64)
Y_DIM = Color(53, 126, 78)
Z_DIM = Color(51, 87, 145)
WORLD_X = Color(91, 43, 48)
WORLD_Y = Color(37, 86, 55)
WORLD_Z = Color(38, 62, 101)
WHITE = Color(239, 243, 250)
BODY = Color(150, 183, 232)
BODY_OPACITY = 0.22


class RandomSO3Motion:
    """Deterministic, random-access smooth motion whose every sample is in SO(3)."""

    def __init__(self, seed: int = 20260821, keyframe_seconds: float = KEYFRAME_SECONDS) -> None:
        self.seed = int(seed)
        self.keyframe_seconds = float(keyframe_seconds)

    @lru_cache(maxsize=64)
    def target(self, index: int) -> SO3:
        if index <= 0:
            return SO3()
        rng = random.Random(self.seed + index * 1_000_003)
        # Shoemake uniform random unit quaternion.
        u1, u2, u3 = rng.random(), rng.random(), rng.random()
        x = sqrt(1.0 - u1) * sin(2.0 * pi * u2)
        y = sqrt(1.0 - u1) * cos(2.0 * pi * u2)
        z = sqrt(u1) * sin(2.0 * pi * u3)
        w = sqrt(u1) * cos(2.0 * pi * u3)
        return SO3.from_quaternion(w, x, y, z)

    @lru_cache(maxsize=4096)
    def rotation_at(self, time: float) -> SO3:
        t = max(0.0, float(time))
        position = t / self.keyframe_seconds
        index = int(floor(position))
        alpha = position - index
        # Zero angular velocity at random keyframes while remaining random-access.
        eased = alpha * alpha * (3.0 - 2.0 * alpha)
        return self.target(index).slerp(self.target(index + 1), eased)


def _edge(axis: str, a: float, b: float, *, bright: bool) -> MeshObject3D:
    t = EDGE_THICKNESS * (1.18 if bright else 0.78)
    if axis == "x":
        return Box3D(
            Vec3(1.0, t, t),
            color=X if bright else X_DIM,
            transform=Transform3D.translation(0.5, a, b),
        )
    if axis == "y":
        return Box3D(
            Vec3(t, 1.0, t),
            color=Y if bright else Y_DIM,
            transform=Transform3D.translation(a, 0.5, b),
        )
    if axis == "z":
        return Box3D(
            Vec3(t, t, 1.0),
            color=Z if bright else Z_DIM,
            transform=Transform3D.translation(a, b, 0.5),
        )
    raise ValueError(f"unknown edge axis {axis!r}")


def _local_cube_edges() -> list[MeshObject3D]:
    edges: list[MeshObject3D] = []
    for y in (0.0, 1.0):
        for z in (0.0, 1.0):
            edges.append(_edge("x", y, z, bright=(y == 0.0 and z == 0.0)))
    for x in (0.0, 1.0):
        for z in (0.0, 1.0):
            edges.append(_edge("y", x, z, bright=(x == 0.0 and z == 0.0)))
    for x in (0.0, 1.0):
        for y in (0.0, 1.0):
            edges.append(_edge("z", x, y, bright=(x == 0.0 and y == 0.0)))
    return edges


def _world_axes() -> tuple[MeshObject3D, ...]:
    length = 3.4
    thin = 0.010
    return (
        Box3D(Vec3(length, thin, thin), color=WORLD_X),
        Box3D(Vec3(thin, length, thin), color=WORLD_Y),
        Box3D(Vec3(thin, thin, length), color=WORLD_Z),
    )


def build_scene(*, draft: bool = False) -> tuple[
    Scene, RandomSO3Motion, MeshObject3D, Transform3D,
    tuple[MeshObject3D, ...], tuple[Transform3D, ...],
]:
    canvas = Canvas(960, 540, 75.0) if draft else Canvas(1920, 1080, 150.0)
    scene = Scene(canvas=canvas, fps=30 if draft else 60)
    scene.camera3d = Camera3D(
        position=Vec3(3.55, 2.75, 4.75),
        target=Vec3(0.05, 0.15, 0.05),
        fov_y_degrees=38.0,
    )

    motion = RandomSO3Motion()
    world_axes = _world_axes()
    cube_local = Transform3D.translation(0.5, 0.5, 0.5)
    cube_body = Cube3D(1.0, color=BODY, transform=cube_local)
    cube_body.opacity = BODY_OPACITY
    local_edges = _local_cube_edges()
    origin = Box3D(Vec3(0.075, 0.075, 0.075), color=WHITE)
    scene.add(*world_axes, cube_body, *local_edges, origin)

    # Body and all local edges share the same SO(3) state. The cube's local
    # center is (0.5,0.5,0.5), so its (-0.5,-0.5,-0.5) corner is exactly O.
    # Body and all edges are one rigid local frame, so they must occupy the
    # exact same Timeline span and sample the exact same absolute-time R(t).
    local_transforms = tuple(edge.transform for edge in local_edges)
    with scene.parallel():
        scene.play_transform_function(
            cube_body,
            lambda a: motion.rotation_at(a * DURATION).to_transform3d() @ cube_local,
            duration=DURATION,
            easing=Easing.LINEAR,
        )
        for edge, local in zip(local_edges, local_transforms):
            scene.play_transform_function(
                edge,
                lambda a, local=local: (
                    motion.rotation_at(a * DURATION).to_transform3d() @ local
                ),
                duration=DURATION,
                easing=Easing.LINEAR,
            )

    title = Text("Local frame · SO(3)", font_size=39, color=WHITE)
    title.move_to(Vec2(-4.55, 3.05))
    subtitle = Text("one unit-cube corner fixed at world origin", font_size=23, color=Color(165, 175, 194))
    subtitle.move_to(Vec2(-3.95, 2.61))
    scene.add(title, subtitle)

    matrix_format = NumberFormat(width=6, decimals=3, sign="space")
    matrix = FormulaTemplate(
        FormulaLiteral("R(t) =", font_size=32, color=WHITE),
        MatrixSlot("R", 3, 3, matrix_format, font_size=29, color=WHITE),
        gap=0.08,
        font_size=32,
        color=WHITE,
    )
    matrix.mount(
        scene,
        {"R": lambda t: motion.rotation_at(t).as_rows()},
        transform=Transform2D.translation(4.10, 2.22) @ Transform2D.scaling(0.57),
    )

    return scene, motion, cube_body, cube_local, tuple(local_edges), local_transforms


def verify(
    scene: Scene, motion: RandomSO3Motion, cube_body: MeshObject3D, cube_local: Transform3D,
    local_edges: tuple[MeshObject3D, ...], local_transforms: tuple[Transform3D, ...],
) -> None:
    # The displayed matrix source remains a proper rotation at arbitrary times.
    for time in (0.0, 0.37, 1.49, 2.75, 6.2, 11.83, 2.75):
        rotation = motion.rotation_at(time)
        rows = rotation.as_rows()
        for row in rows:
            assert abs(sum(v*v for v in row) - 1.0) < 1e-7
        assert abs(rotation.determinant - 1.0) < 1e-7

    # The three bright local unit edges start at the same mathematical origin.
    # Their transforms at each time must map that local corner to world O.
    sample_times = (0.0, 0.8, 3.25, 7.9, 11.6)
    for time in sample_times:
        snapshot = scene.evaluate(time)
        by_id = {item.object_id: item.snapshot for item in snapshot.meshes3d}

        body_transform = by_id[scene._require_registered(cube_body).object_id].transform
        anchored_corner = body_transform.apply(Vec3(-0.5, -0.5, -0.5))
        assert anchored_corner.length < 1e-7
        expected_body_center = motion.rotation_at(time).apply(Vec3(0.5, 0.5, 0.5))
        assert (body_transform.apply(Vec3()) - expected_body_center).length < 1e-7

        for edge, local in zip(local_edges, local_transforms):
            registered = scene._require_registered(edge)
            transform = by_id[registered.object_id].transform
            center = Vec3(local.m03, local.m13, local.m23)
            # R*T(center) applied to -center is exactly the shared O corner only
            # for the axis-aligned origin edges; for all edges this still checks
            # that no translation external to R*T_local was introduced.
            expected_center = motion.rotation_at(time).apply(center)
            got_center = transform.apply(Vec3())
            assert (got_center - expected_center).length < 1e-7

        # Origin edges are x[0], y[0], z[0] in the construction order.
        for edge_index, local_start, local_end, basis in (
            (0, Vec3(-0.5, 0, 0), Vec3(0.5, 0, 0), Vec3(1, 0, 0)),
            (4, Vec3(0, -0.5, 0), Vec3(0, 0.5, 0), Vec3(0, 1, 0)),
            (8, Vec3(0, 0, -0.5), Vec3(0, 0, 0.5), Vec3(0, 0, 1)),
        ):
            edge = local_edges[edge_index]
            edge_snapshot = by_id[scene._require_registered(edge).object_id]
            transform = edge_snapshot.transform @ edge_snapshot.geometry_transform
            assert transform.apply(local_start).length < 1e-7
            endpoint = transform.apply(local_end)
            expected = motion.rotation_at(time).apply(basis)
            assert (endpoint - expected).length < 1e-7


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    scene, motion, cube_body, cube_local, local_edges, local_transforms = build_scene(draft=args.draft)
    verify(scene, motion, cube_body, cube_local, local_edges, local_transforms)
    output = Path(args.output) if args.output else Path("media/three_d/local_frame_so3.mp4")
    if args.draft and not args.output:
        output = Path("media/three_d/local_frame_so3_draft.mp4")
    # Prefer NVENC on NVIDIA workstations; render_video(auto) falls back to
    # libx264 on machines without a usable NVIDIA encoder.
    scene.render_video(
        output, verify_random_access=True, preset="veryfast", crf=22, video_encoder="auto",
    )
    print(output.resolve())
    print("SO(3)=ok origin-anchor=ok matrix-sync=ok random-access=ok")


if __name__ == "__main__":
    main()
