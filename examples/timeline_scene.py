from zanim import Circle, Color, Easing, Object2D, Scene, Square, Style, Transform2D


def build_scene() -> Scene:
    mover = Object2D(
        Square(1.4),
        transform=Transform2D.translation(-3.5, 1.5),
        style=Style(fill=Color(72, 133, 237, 190)),
    )
    source = Object2D(
        Square(1.8),
        transform=Transform2D.translation(-1.7, -1.1).rotate(-0.15),
        style=Style(fill=Color(84, 174, 255, 125)),
    )
    target = Object2D(
        Circle(0.9),
        transform=Transform2D.translation(2.2, -0.45).rotate(0.3),
        style=Style(fill=Color(242, 133, 83, 155)),
    )
    scene = Scene().add(mover, source, target)
    scene.play_transform(
        mover,
        Transform2D.translation(-0.8, 1.55).rotate(0.55),
        duration=1.5,
        easing=Easing.SMOOTHSTEP,
    )
    scene.wait(0.5)
    scene.play_interpolation(source, target, duration=2.0, easing=Easing.SMOOTHSTEP)
    return scene


if __name__ == '__main__':
    scene = build_scene()
    output = scene.render_video('media/timeline_scene.mp4', fps=30, verify_random_access=True)
    print(output)
