from zanim import Canvas, Color, Easing, Scene, Text, Transform2D


def build_scene() -> Scene:
    scene = Scene(canvas=Canvas(width=1920, height=1080, unit_size=100))
    text = Text(
        'Zanim · 神经网络可视化',
        font_size=58,
        font='Noto Sans CJK SC',
        color=Color(238, 242, 250),
        transform=Transform2D.translation(0, 0),
    )
    scene.add(text)
    scene.wait(0.35)
    scene.play_reveal(text, duration=2.6, easing=Easing.LINEAR)
    scene.wait(0.8)
    return scene


def main() -> None:
    scene = build_scene()
    output = scene.render_video('media/text_reveal.mp4', fps=30)
    text = scene.objects[0]
    print(output)
    print(f'duration={scene.timeline.cursor:.2f}s glyph_groups={text.document.group_count}')


if __name__ == '__main__':
    main()
