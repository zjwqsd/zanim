from __future__ import annotations

from pathlib import Path

from zanim import (
    Audio, Canvas, GIF, Group2D, Image, Scene, Text, Transform2D, Video,
)

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets/media_demo"
OUTPUT = ROOT / "media/media_timeline.mp4"


def build_scene() -> Scene:
    image = Image(
        ASSETS / "image.png", width=3.4,
        transform=Transform2D.translation(-3.6, 0), z_index=1,
    )
    gif = GIF(
        ASSETS / "anim.gif", width=3.0,
        transform=Transform2D.translation(0, 0), z_index=1,
    )
    video = Video(
        ASSETS / "clip.mp4", width=3.8,
        transform=Transform2D.translation(3.6, 0), z_index=1,
    )
    video_audio = video.audio_track(gain=0.55)
    tone = Audio(ASSETS / "tone.wav", gain=0.18)
    labels = Group2D([
        Text("PNG", font_size=25, transform=Transform2D.translation(-3.6, -1.65)),
        Text("GIF", font_size=25, transform=Transform2D.translation(0, -1.65)),
        Text("VIDEO", font_size=25, transform=Transform2D.translation(3.6, -1.65)),
    ], z_index=4)

    scene = Scene(canvas=Canvas(1280, 720, 110), fps=30)
    scene.add(image, gif, video, video_audio, tone, labels)
    with scene.parallel():
        scene.play_media(image, duration=5.0)
        scene.play_media(gif, duration=5.0, loop=True)
        scene.play_media(video, duration=4.0, source_start=0.25, speed=1.25, loop=True, at=0.5)
        scene.play_media(video_audio, duration=4.0, source_start=0.25, speed=1.25, loop=True, at=0.5)
        scene.play_media(tone, duration=5.0, loop=True)
        scene.play_transform(
            image,
            Transform2D.translation(-3.6, 0).rotate(0.35).scale(1.08, 1.08),
            duration=5.0,
        )
        scene.play_transform(
            gif, Transform2D.translation(0, 0.25).rotate(-0.16), duration=5.0,
        )
        scene.play_transform(
            video, Transform2D.translation(3.6, 0).rotate(0.18), duration=5.0,
        )
    return scene


def main() -> None:
    scene = build_scene()
    output = scene.render_video(
        OUTPUT, fps=30, workers=6, preset="veryfast", verify_random_access=True,
    )
    print(output)
    print(f"duration={scene.timeline.cursor:.2f}s media-timeline=ok random-access=ok")


if __name__ == "__main__":
    main()
