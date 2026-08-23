from __future__ import annotations

import json

import pytest
from zanim import (
    BLUE,
    GREEN,
    SE2,
    TIME,
    WORLD,
    Axes,
    Canvas,
    Circle,
    FourierEpicycles,
    FourierTerm,
    Scene,
    Square,
    Transform2D,
    Vec2,
    X,
)
from zanim.batch import DynamicBatchObject2D, LineSet
from zanim.geometry import Color, CubicBezierGeometry, PolylineGeometry
from zanim.ir import SceneIRUnsupported, scene_from_ir, scene_to_ir
from zanim.plot import DynamicGeometryObject2D
from zanim.vector import (
    DynamicVectorObject2D,
    VectorContour,
    VectorDocument,
    VectorObject2D,
    VectorPath,
)


def _snapshot_signature(scene: Scene, time: float):
    snap = scene.evaluate(time)
    return (snap.objects, snap.batches, snap.vectors, snap.infinite2d, snap.transients)


def test_scene_ir_round_trip_preserves_random_access_state():
    scene = Scene(canvas=Canvas(640, 360, 80), fps=60)
    square = Square(1.2, fill=BLUE, trim=0, position=(-1, 0))
    circle = Circle(0.5, fill=GREEN, opacity=0, position=(1, 0))
    square, circle = scene.add(square, circle)
    with scene.parallel(duration=1.2):
        square.create()
        circle.fade_in(at=0.2)
    square.move(by=(2, 0.5), frame=WORLD, duration=0.8)
    scene.wait(0.3)

    ir = json.loads(json.dumps(scene_to_ir(scene)))
    restored = scene_from_ir(ir)
    assert restored.duration == scene.duration == 2.5
    for time in (0.0, 0.4, 1.2, 1.7, 2.3):
        assert _snapshot_signature(restored, time) == _snapshot_signature(scene, time)


def test_scene_ir_deduplicates_immutable_vector_resources():
    cubic = CubicBezierGeometry(Vec2(0, 0), Vec2(0.3, 0.8), Vec2(0.7, 0.8), Vec2(1, 0))
    document = VectorDocument(
        (VectorPath((VectorContour((cubic,), False),), fill=None),),
        width=1,
        height=0.8,
        group_count=1,
    )
    scene = Scene()
    scene.add(
        VectorObject2D(document, transform=Transform2D.translation(-1, 0)),
        VectorObject2D(document, transform=Transform2D.translation(1, 0)),
    )
    ir = scene_to_ir(scene)
    vectors = [obj for obj in ir["objects"] if obj["kind"] == "vector2d"]
    assert len(ir["resources"]) == 1
    assert vectors[0]["state"]["resource"] == vectors[1]["state"]["resource"] == 1
    restored = scene_from_ir(ir)
    assert restored.evaluate(0).vectors == scene.evaluate(0).vectors


def test_scene_ir_transform_function_is_strict_or_explicitly_sampled():
    scene = Scene(fps=60)
    square = scene.add(Square(1, fill=Color(120, 180, 255)))
    square.transform_function(
        lambda a: Transform2D.translation(a, 0) @ Transform2D.rotation(a * 0.75),
        duration=1.0,
    )
    with pytest.raises(SceneIRUnsupported, match="TransformFunctionClip"):
        scene_to_ir(scene)

    ir = scene_to_ir(scene, sample_transform_functions=True)
    sampled = [clip for clip in ir["clips"] if clip["kind"] == "sampled_transform"]
    assert len(sampled) == 1
    assert len(sampled[0]["samples"]) == 61
    restored = scene_from_ir(ir)
    for frame in (0, 1, 17, 31, 59, 60):
        time = frame / 60
        assert (
            restored.evaluate(time).objects[0].snapshot.transform
            == scene.evaluate(time).objects[0].snapshot.transform
        )


def test_scene_ir_preserves_se2_rigid_interpolation():
    scene = Scene(fps=60)
    square = Square(1)
    scene.add(square)
    scene.transform(
        square,
        to=SE2(theta=1.5, translation=Vec2(2.0, -0.5)),
        duration=2.0,
    )
    ir = scene_to_ir(scene)
    assert [clip["kind"] for clip in ir["clips"]] == ["se2_transform"]
    restored = scene_from_ir(ir)
    for time in (0.0, 0.5, 1.0, 1.5, 2.0):
        assert (
            restored.evaluate(time).objects[0].snapshot.transform
            == scene.evaluate(time).objects[0].snapshot.transform
        )


def test_scene_ir_samples_dynamic_geometry_batch_and_vector_on_video_grid():
    scene = Scene(canvas=Canvas(640, 360, 80), fps=20)
    dynamic_geometry = DynamicGeometryObject2D(
        lambda t: PolylineGeometry((Vec2(0, 0), Vec2(1 + t, t))),
        style=Square(1).style,
    )
    dynamic_batch = DynamicBatchObject2D(
        lambda t: LineSet(
            (Vec2(0, 0),),
            (Vec2(t, 1),),
            (Color(255, 255, 255),),
            (0.02,),
        )
    )

    def vector_at(t):
        shifted = CubicBezierGeometry(
            Vec2(t, 0), Vec2(0.3 + t, 0.8), Vec2(0.7 + t, 0.8), Vec2(1 + t, 0)
        )
        return VectorDocument(
            (VectorPath((VectorContour((shifted,), False),), fill=None),),
            width=1,
            height=0.8,
            group_count=1,
        )

    dynamic_vector = DynamicVectorObject2D(vector_at)
    scene.add(dynamic_geometry, dynamic_batch, dynamic_vector)
    scene.wait(1.0)

    with pytest.raises(SceneIRUnsupported, match="sample_dynamic_providers"):
        scene_to_ir(scene)
    ir = scene_to_ir(scene, sample_dynamic_providers=True)
    assert [o["kind"] for o in ir["objects"] if o["id"] != 0] == [
        "sampled_object2d",
        "sampled_batch2d",
        "sampled_vector2d",
    ]
    assert ir["meta"]["sampled_dynamic_objects"] == 3
    restored = scene_from_ir(json.loads(json.dumps(ir)))
    for frame in (0, 1, 7, 13, 19, 20):
        time = frame / 20
        assert _snapshot_signature(restored, time) == _snapshot_signature(scene, time)


def test_fourier_epicycles_stays_semantic_and_round_trips_exactly():
    terms = (
        FourierTerm(0, complex(0.2, -0.1)),
        FourierTerm(1, complex(1.1, 0.25)),
        FourierTerm(-2, complex(-0.15, 0.35)),
    )
    scene = Scene(canvas=Canvas(640, 360, 80), fps=60)
    scene.add(FourierEpicycles(terms, start_time=0.2, draw_duration=1.4, trace_samples=80))
    scene.wait(1.8)
    ir = scene_to_ir(scene)
    semantic = [obj for obj in ir["objects"] if obj["kind"] == "fourier_epicycles"]
    assert len(semantic) == 1
    assert ir["meta"]["sampled_dynamic_objects"] == 0
    assert not any(obj["kind"].startswith("sampled_") for obj in ir["objects"])
    restored = scene_from_ir(json.loads(json.dumps(ir)))
    for time in (0.0, 0.2, 0.55, 1.0, 1.6, 1.8):
        assert _snapshot_signature(restored, time) == _snapshot_signature(scene, time)


def test_function_plot_expression_is_portable_without_geometry_sampling():
    axes = Axes((-4, 4), (-2, 3), width=8, height=5, center=Vec2(0.5, -0.25))
    expression = 1.2 + 0.5 * (1.25 * X + 0.8 * TIME).sin() + 0.055 * X * X
    plot = axes.plot(expression, x_range=(-3.5, 3.5), samples=81)
    scene = Scene(canvas=Canvas(640, 360, 80), fps=60)
    scene.add(plot)
    scene.wait(2.0)
    ir = scene_to_ir(scene)
    records = [obj for obj in ir["objects"] if obj["kind"] == "function_plot"]
    assert len(records) == 1
    assert ir["meta"]["sampled_dynamic_objects"] == 0
    assert len(json.dumps(ir)) < 10_000
    restored = scene_from_ir(json.loads(json.dumps(ir)))
    for time in (0.0, 0.25, 0.8, 1.35, 2.0):
        assert _snapshot_signature(restored, time) == _snapshot_signature(scene, time)
