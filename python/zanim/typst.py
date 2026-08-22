from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import ZanimError
from .geometry import Color
from .space import SE2, Transform2D
from .svg import load_svg
from .vector import VectorObject2D

_ROOT = Path(__file__).resolve().parents[2]
_CACHE_SCHEMA = "zanim-typst-v1"


def _typst_executable() -> Path:
    override = os.environ.get("ZANIM_TYPST")
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return path
    local = _ROOT / ".tools" / "typst" / "typst"
    if local.is_file():
        return local
    system = shutil.which("typst")
    if system:
        return Path(system)
    raise ZanimError(
        "Typst is required for Text/Math. Install `typst` or set ZANIM_TYPST to the executable."
    )


def _cache_dir() -> Path:
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    path = root / "zanim" / "typst"
    path.mkdir(parents=True, exist_ok=True)
    return path


def compile_typst_svg(source: str) -> Path:
    """Compile Typst once and return a persistent cached SVG path."""
    digest = hashlib.sha256((_CACHE_SCHEMA + "\0" + source).encode("utf-8")).hexdigest()
    cache = _cache_dir()
    svg_path = cache / f"{digest}.svg"
    if svg_path.is_file():
        return svg_path

    # Source/intermediate files are transactional and stay inside the Zanim
    # cache rather than leaking .typ files or using global /tmp.
    with tempfile.TemporaryDirectory(prefix=".typst-", dir=cache) as td:
        temp = Path(td)
        typ_path = temp / "source.typ"
        compiled = temp / "result.svg"
        typ_path.write_text(source, encoding="utf-8")
        proc = subprocess.run(
            [str(_typst_executable()), "compile", str(typ_path), str(compiled)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Typst compilation failed:\n{proc.stderr}")
        # Atomic on the same cache filesystem; concurrent equal compiles can
        # safely replace the same content-addressed result.
        compiled.replace(svg_path)
    return svg_path


def _hex(color: Color) -> str:
    return f"#{color.r:02x}{color.g:02x}{color.b:02x}{color.a:02x}"


def _font_value(font: str | tuple[str, ...] | None) -> str | None:
    if font is None:
        return None
    if isinstance(font, str):
        return json.dumps(font, ensure_ascii=False)
    if not font:
        raise ValueError("font fallback tuple must not be empty")
    return "(" + ", ".join(json.dumps(x, ensure_ascii=False) for x in font) + ")"


def _page_preamble(font_size: float, color: Color, font: str | tuple[str, ...] | None) -> str:
    if font_size <= 0:
        raise ValueError("font_size must be positive")
    font_part = "" if font is None else f", font: {_font_value(font)}"
    return (
        "#set page(width: auto, height: auto, margin: 0pt, fill: none)\n"
        f'#set text(size: {font_size}pt, fill: rgb("{_hex(color)}"){font_part})\n'
    )


class Text(VectorObject2D):
    """High-quality Unicode text compiled by Typst into VectorDocument."""

    __slots__ = ("content", "font_size", "font", "color")

    def __init__(
        self,
        content: str,
        *,
        font_size: float = 36.0,
        font: str | tuple[str, ...] | None = None,
        color: Color = Color(240, 242, 248),
        transform: Transform2D | SE2 = Transform2D(),
        reveal: float = 1.0,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        self.content = content
        self.font_size = font_size
        self.font = font
        self.color = color
        source = (
            _page_preamble(font_size, color, font)
            + f"#text({json.dumps(content, ensure_ascii=False)})\n"
        )
        document = load_svg(compile_typst_svg(source))
        super().__init__(
            document=document, transform=transform, reveal=reveal, opacity=opacity, z_index=z_index
        )


class Math(VectorObject2D):
    """Typst math source compiled into the same vector representation as Text."""

    __slots__ = ("source", "font_size", "color")

    def __init__(
        self,
        source: str,
        *,
        font_size: float = 36.0,
        color: Color = Color(240, 242, 248),
        transform: Transform2D | SE2 = Transform2D(),
        reveal: float = 1.0,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        self.source = source
        self.font_size = font_size
        self.color = color
        typst_source = _page_preamble(font_size, color, None) + f"$ {source} $\n"
        document = load_svg(compile_typst_svg(typst_source))
        super().__init__(
            document=document, transform=transform, reveal=reveal, opacity=opacity, z_index=z_index
        )
