from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import pytest
from zanim import LOCAL, PARENT, RIGHT, WORLD, Group, Line, Scene, Transform2D
from zanim.value import ScalarValue

ROOT = Path(__file__).resolve().parents[1]


def _matrix(m: Transform2D) -> list[float]:
    return [m.xx, m.xy, m.yx, m.yy, m.tx, m.ty]


def _web() -> dict:
    result = subprocess.run(
        ["node", "web/conformance.mjs"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _samples(scene: Scene, obj, times=(0.0, 1.0, 2.0)) -> list[list[float]]:
    return [_matrix(scene.world_transform(obj, time=t)) for t in times]


def _world_scenario() -> list[list[float]]:
    scene = Scene()
    child = Line((0, 0), (1, 0), transform=Transform2D.translation(1, 0))
    parent = Group(
        [child],
        transform=Transform2D.translation(2, 1) @ Transform2D.rotation(math.pi / 2),
    )
    scene.add(parent)
    scene.move(child, by=RIGHT, frame=WORLD, duration=2)
    return _samples(scene, child)


def _framed_scenario(frame) -> list[list[float]]:
    scene = Scene()
    line = Line((0, 0), (1, 0), transform=Transform2D.rotation(math.pi / 2))
    scene.add(line)
    scene.move(line, by=RIGHT, frame=frame, duration=2)
    return _samples(scene, line)


def _value_scenario() -> list[float]:
    scene = Scene()
    value = ScalarValue(2)
    scene.add(value)
    scene.value(value, to=6, duration=2)
    return [value.value_at(t) for t in (0.0, 1.0, 2.0)]


def _relative_at_scenario() -> tuple[float, list[list[float]]]:
    scene = Scene()
    line = Line((0, 0), (1, 0))
    scene.add(line)
    scene.move(line, by=RIGHT, frame=PARENT, duration=1)
    scene.move(line, by=(0, 1), frame=PARENT, duration=1, at=0.5)
    return scene.duration, _samples(scene, line, (0.0, 1.0, 1.5, 2.0, 2.5))


def test_web_scene_matches_python_random_access_semantics() -> None:
    web = _web()
    for actual, expected in [
        (web["world"], _world_scenario()),
        (web["local"], _framed_scenario(LOCAL)),
        (web["parent"], _framed_scenario(PARENT)),
    ]:
        for actual_matrix, expected_matrix in zip(actual, expected, strict=True):
            assert actual_matrix == pytest.approx(expected_matrix, abs=1e-10)
    assert web["value"] == pytest.approx(_value_scenario(), abs=1e-10)
    expected_duration, expected_samples = _relative_at_scenario()
    assert web["relative_at"]["duration"] == pytest.approx(expected_duration, abs=1e-10)
    for actual_matrix, expected_matrix in zip(
        web["relative_at"]["samples"], expected_samples, strict=True
    ):
        assert actual_matrix == pytest.approx(expected_matrix, abs=1e-10)


def test_web_and_python_reject_overlapping_nested_world_motion() -> None:
    web = _web()
    assert web["rejects_transform_overlap"]
    assert web["allows_independent_channels"]
    assert web["rejects_parent_first"]
    assert web["rejects_child_first"]

    child = Line((0, 0), (1, 0))
    parent = Group([child])
    scene = Scene()
    scene.add(parent)
    with pytest.raises(ValueError):
        with scene.parallel():
            scene.move(parent, by=RIGHT, frame=LOCAL, duration=1)
            scene.move(child, by=RIGHT, frame=WORLD, duration=1)

    child = Line((0, 0), (1, 0))
    parent = Group([child])
    scene = Scene()
    scene.add(parent)
    with pytest.raises(ValueError):
        with scene.parallel():
            scene.move(child, by=RIGHT, frame=WORLD, duration=1)
            scene.move(parent, by=RIGHT, frame=LOCAL, duration=1)
