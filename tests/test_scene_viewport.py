from zanim import ArrayImage, Canvas, Scene, SceneViewport


def test_array_image_and_scene_viewport_render():
    child = Scene(canvas=Canvas(320, 180, 40))
    child_image = ArrayImage([[0, 255], [255, 0]], height=4)
    child.add(child_image)

    parent = Scene(canvas=Canvas(320, 180, 40))
    view = SceneViewport(
        child,
        source_center=(0, 0),
        source_size=(2, 1),
        width=4,
        height=2,
        duration=1,
    )
    parent.add(view)
    # Raster source should be random-access and have the requested output size.
    frame = view.source.frame_at(0.5)
    assert frame.width == 360
    assert frame.height == 180
    assert len(frame.rgba) == 360 * 180 * 4
