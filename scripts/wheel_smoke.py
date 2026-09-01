"""Clean-install smoke test used by release CI after installing a built wheel."""

from __future__ import annotations

import tempfile
from pathlib import Path

import zanim
from zanim.cli import _load_scene
from zanim.render.abi import ABI_VERSION, load_library
from zanim.runtime import ffmpeg_has_libx264, ffmpeg_path
from zanim.source import get_preview_source


def main() -> None:
    lib = load_library()
    assert int(lib.zanim_abi_version()) == ABI_VERSION
    assert zanim.__version__ != "unknown"

    with tempfile.TemporaryDirectory(prefix="zanim-wheel-smoke-") as tmp:
        root = Path(tmp)
        script = root / "demo.py"
        script.write_text(
            "from zanim import Canvas, Circle, Color, Scene\n"
            "scene = Scene(canvas=Canvas(160, 90, 30), fps=10)\n"
            "marker = scene.add(Circle(.7, fill=Color(90, 160, 255)))\n"
            "marker.move(to=(1, 0), duration=.2)\n",
            encoding="utf-8",
        )

        scene = _load_scene(script)
        source = get_preview_source(scene)
        assert source is not None
        marker = scene._require_registered(scene.items[0])
        assert source.primary_name(marker.object_id) == "marker"
        clip = scene._timeline.clips[0]
        assert scene._timeline._event_actions[id(clip)] == "move"

        scene.render(root / "frame.png", time=0.1)
        if ffmpeg_path() is not None and ffmpeg_has_libx264():
            scene.render(root / "video.mp4")
            assert (root / "video.mp4").stat().st_size > 0
        assert (root / "frame.png").stat().st_size > 0

    print(f"wheel smoke OK: Zanim {zanim.__version__}, ABI {ABI_VERSION}")


if __name__ == "__main__":
    main()
