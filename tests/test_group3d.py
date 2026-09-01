import math

import pytest
from zanim import LOCAL, PARENT, SE3, SO3, Cube3D, Group3D, Scene, Vec3


def test_group3d_composes_transform_and_opacity_into_mesh():
    child = Cube3D(1.0, transform=SE3(translation=Vec3(0.5, 0, 0)).as_affine())
    group = Group3D(
        [child],
        transform=SE3(translation=Vec3(2, 0, 0)).as_affine(),
        opacity=0.5,
    )
    scene = Scene()
    scene.add(group)
    rendered = scene.evaluate(0).meshes3d
    assert len(rendered) == 1
    assert rendered[0].snapshot.transform.apply(Vec3()) == Vec3(2.5, 0, 0)
    assert rendered[0].snapshot.opacity == pytest.approx(0.5)


def test_group3d_transform_animates_all_descendant_meshes():
    a = Cube3D(1.0, transform=SE3(translation=Vec3(1, 0, 0)).as_affine())
    b = Cube3D(1.0, transform=SE3(translation=Vec3(0, 1, 0)).as_affine())
    group = Group3D([a, b])
    scene = Scene()
    handle = scene.add(group)
    handle.transform(
        by=SE3(rotation=SO3.rotation_z(math.pi / 2)),
        frame=PARENT,
        duration=1.0,
    )

    end = scene.evaluate(1.0).meshes3d
    centers = [item.snapshot.transform.apply(Vec3()) for item in end]
    assert centers[0].x == pytest.approx(0, abs=1e-8)
    assert centers[0].y == pytest.approx(1, abs=1e-8)
    assert centers[1].x == pytest.approx(-1, abs=1e-8)
    assert centers[1].y == pytest.approx(0, abs=1e-8)


def test_nested_group3d_world_transform_random_access():
    mesh = Cube3D(1.0, transform=SE3(translation=Vec3(0, 0, 1)).as_affine())
    child = Group3D([mesh], transform=SE3(translation=Vec3(0, 2, 0)).as_affine())
    root = Group3D([child], transform=SE3(translation=Vec3(3, 0, 0)).as_affine())
    scene = Scene()
    root_handle = scene.add(root)
    root_handle.transform(
        by=SE3(rotation=SO3.rotation_y(math.pi / 2)),
        frame=LOCAL,
        duration=1,
    )

    expected = scene.evaluate(0.5).meshes3d[0].snapshot.transform
    assert scene.world_transform3d(mesh, time=0.5) == expected


def test_group3d_hierarchy_is_immutable_after_add():
    group = Group3D([Cube3D(1)])
    scene = Scene()
    scene.add(group)
    with pytest.raises(RuntimeError, match="after Scene.add"):
        group.add(Cube3D(1))


def test_relative_se3_rotation_follows_arc_not_endpoint_chord():
    cube = Group3D([Cube3D(0.2)], position=(1, 0, 0))
    scene = Scene()
    handle = scene.add(cube)
    handle.transform(
        by=SE3(rotation=SO3.rotation_z(math.pi / 2)),
        frame=PARENT,
        duration=1.0,
        easing=__import__("zanim").Easing.LINEAR,
    )
    center = scene.world_transform3d(cube, time=0.5).apply(Vec3())
    root2 = math.sqrt(0.5)
    assert center.x == pytest.approx(root2, abs=1e-7)
    assert center.y == pytest.approx(root2, abs=1e-7)
