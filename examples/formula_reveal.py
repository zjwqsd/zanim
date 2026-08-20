from zanim import Canvas, Color, Easing, Math, Scene, Transform2D


def build_scene() -> tuple[Scene, tuple[Math, ...]]:
    scene = Scene(canvas=Canvas(width=1920, height=1080, unit_size=100))

    formulas = (
        Math(
            'z_1 = x W_1 + b_1',
            font_size=48,
            color=Color(238, 242, 250),
            transform=Transform2D.translation(0, 2.25),
        ),
        Math(
            'h = sigma(z_1)',
            font_size=48,
            color=Color(132, 196, 255),
            transform=Transform2D.translation(0, 0.75),
        ),
        Math(
            'z_2 = h W_2 + b_2',
            font_size=48,
            color=Color(238, 242, 250),
            transform=Transform2D.translation(0, -0.75),
        ),
        Math(
            'hat(y) = "softmax"(z_2)',
            font_size=48,
            color=Color(255, 174, 122),
            transform=Transform2D.translation(0, -2.25),
        ),
    )

    scene.add(*formulas)
    scene.wait(0.3)

    # Each equation is a stable VectorDocument. Only reveal changes over time;
    # Typst layout and glyph geometry are never recomputed per frame.
    for formula in formulas:
        scene.play_reveal(formula, duration=1.15, easing=Easing.LINEAR)
        scene.wait(0.18)

    scene.wait(0.7)
    return scene, formulas


def main() -> None:
    scene, formulas = build_scene()
    output = scene.render_video('media/formula_reveal.mp4', fps=30)
    print(output)
    print(f'duration={scene.timeline.cursor:.2f}s')
    for i, formula in enumerate(formulas, 1):
        print(
            f'formula{i}: groups={formula.document.group_count} '
            f'paths={len(formula.document.paths)} '
            f'size={formula.document.width:.3f}x{formula.document.height:.3f}'
        )


if __name__ == '__main__':
    main()
