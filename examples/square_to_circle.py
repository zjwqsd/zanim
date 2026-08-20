from pathlib import Path

from zanim import Canvas, Circle, Color, Easing, Object2D, Scene, Square, Style


scene = Scene(canvas=Canvas(width=960, height=540, unit_size=80), fps=30)
source = Object2D(Square(2.2), style=Style(fill=Color(90, 165, 255, 70)))
target = Object2D(Circle(1.1), style=Style(fill=Color(255, 145, 95, 70)))
scene.add(source, target)
scene.play_interpolation(source, target, duration=3.0, easing=Easing.SMOOTHSTEP)
print(scene.render_video(Path('media/square_to_circle.mp4'), fps=30, verify_random_access=True))
