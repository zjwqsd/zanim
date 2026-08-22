"""Minimal Jupyter display support for rendered Zanim output.

Notebook integration deliberately stops at the display boundary: Scene, Timeline,
Preview and source tracking keep their normal semantics.
"""

from __future__ import annotations

import base64
import html
import tempfile
from dataclasses import dataclass
from pathlib import Path


def is_notebook() -> bool:
    """Return True for an IPython kernel-backed notebook session.

    IPython is optional; importing Zanim never requires it.
    """
    try:
        from IPython import get_ipython
    except ImportError:
        return False
    shell = get_ipython()
    if shell is None:
        return False
    return shell.__class__.__name__ == "ZMQInteractiveShell"


@dataclass(frozen=True, slots=True)
class NotebookImage:
    data: bytes

    def _repr_png_(self) -> bytes:
        return self.data


@dataclass(frozen=True, slots=True)
class NotebookVideo:
    data: bytes

    def _repr_html_(self) -> str:
        encoded = base64.b64encode(self.data).decode("ascii")
        return (
            '<video controls autoplay loop playsinline style="max-width:100%;height:auto">'
            f'<source src="data:video/mp4;base64,{html.escape(encoded)}" type="video/mp4">'
            "</video>"
        )


def render_inline(
    scene,
    *,
    time: float | None = None,
    start: float | None = None,
    end: float | None = None,
    **video_kwargs,
):
    """Render a Scene and return a Jupyter-displayable image or video object."""
    image = time is not None or scene.duration <= 0
    suffix = ".png" if image else ".mp4"
    with tempfile.TemporaryDirectory(prefix="zanim-notebook-") as temp_dir:
        output = Path(temp_dir) / f"render{suffix}"
        scene.render(output, time=time, start=start, end=end, **video_kwargs)
        data = output.read_bytes()
    return NotebookImage(data) if image else NotebookVideo(data)
