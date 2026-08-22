"""Lesson 09: image, GIF, video and audio on one absolute-time timeline."""

from __future__ import annotations

from pathlib import Path

from zanim import BOTTOM, DOWN, GIF, TOP, Audio, Canvas, Group, Image, Row, Scene, Text, Vec2, Video

EXAMPLES = Path(__file__).resolve().parents[1]
ASSETS = EXAMPLES / "assets/media_demo"


image = Image(ASSETS / "image.png", width=3.4, z_index=1)
gif = GIF(ASSETS / "anim.gif", width=3.0, z_index=1)
video = Video(ASSETS / "clip.mp4", width=3.8, z_index=1)
video_audio = video.audio_track(gain=0.55)
tone = Audio(ASSETS / "tone.wav", gain=0.18)
image_label = Text("IMAGE", font_size=24)
gif_label = Text("GIF", font_size=24)
video_label = Text("VIDEO + AUDIO", font_size=24)
labels = Group([image_label, gif_label, video_label], z_index=4)

scene = Scene(canvas=Canvas(1280, 720, 110), fps=30)
Row(gap=0.55, at=scene.frame.center + 0.35 * Vec2(0, 1)).place(image, gif, video)
for media, label in zip((image, gif, video), (image_label, gif_label, video_label)):
    label.place(anchor=TOP, at=media.anchor(BOTTOM) + 0.22 * DOWN)
image, gif, video, video_audio, tone, _labels = scene.add(
    image, gif, video, video_audio, tone, labels
)
with scene.parallel(duration=5):
    image.media(duration=5)
    gif.media(duration=5, loop=True)
    video.media(duration=4, source_start=0.25, speed=1.25, loop=True, at=0.5)
    video_audio.media(duration=4, source_start=0.25, speed=1.25, loop=True, at=0.5)
    tone.media(duration=5, loop=True)
    image.transform(to=image.transform_value.rotate(0.30).scale(1.08))
    gif.transform(to=gif.transform_value.translate(0, 0.25).rotate(-0.16))
    video.transform(to=video.transform_value.rotate(0.18))

scene.preview()
