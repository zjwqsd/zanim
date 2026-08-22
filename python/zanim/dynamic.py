from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from numbers import Real
from typing import Callable, Literal

from .geometry import Color, CubicBezierGeometry
from .space import Transform2D
from .typst import Math
from .value import ScalarValue
from .vector import (
    VectorContour,
    VectorDocument,
    VectorObject2D,
    VectorPath,
    vector_path_bounds,
)


@dataclass(frozen=True, slots=True)
class NumberFormat:
    """Strict fixed-format number slot.

    ``width`` is the exact formatted character count. Values that do not fit
    are rejected; the formula is never allowed to reflow because of data.
    """

    width: int
    decimals: int = 0
    sign: Literal["negative", "space", "always"] = "space"

    def __post_init__(self) -> None:
        if self.width <= 0:
            raise ValueError("number format width must be positive")
        if self.decimals < 0:
            raise ValueError("number format decimals must be >= 0")
        if self.sign not in ("negative", "space", "always"):
            raise ValueError("invalid number sign policy")

    def format(self, value: Real) -> str:
        if not isinstance(value, Real):
            raise TypeError("dynamic number value must be real")
        sign_char = {"negative": "-", "space": " ", "always": "+"}[self.sign]
        if self.decimals == 0:
            text = format(int(round(float(value))), f"{sign_char}{self.width}d")
        else:
            text = format(float(value), f"{sign_char}{self.width}.{self.decimals}f")
        if len(text) != self.width:
            raise ValueError(
                f"value {value!r} does not fit fixed "
                f"NumberFormat(width={self.width}, decimals={self.decimals})"
            )
        return text


_GLYPHS = "0123456789-+."


def _transform_path(path: VectorPath, transform: Transform2D, *, group: int = 0) -> VectorPath:
    contours = tuple(
        VectorContour(
            tuple(
                CubicBezierGeometry(
                    transform.apply(seg.p0),
                    transform.apply(seg.p1),
                    transform.apply(seg.p2),
                    transform.apply(seg.p3),
                )
                for seg in contour.segments
            ),
            contour.closed,
        )
        for contour in path.contours
    )
    return VectorPath(contours, fill=path.fill, stroke=path.stroke, group=group)


class _MathNumberGlyphAtlas:
    """Typst math glyphs with natural mathematical advances.

    The whole atlas is compiled once. Runtime numbers are assembled from the
    already-vectorized glyphs, preserving Typst's math font instead of using a
    monospace text face.
    """

    def __init__(self, font_size: float, color: Color) -> None:
        self.font_size = font_size
        self.color = color
        atlas = Math(_GLYPHS, font_size=font_size, color=color).document
        if atlas.group_count != len(_GLYPHS):
            raise RuntimeError(
                f"numeric math atlas expected {len(_GLYPHS)} groups, got {atlas.group_count}"
            )

        glyphs: dict[str, VectorDocument] = {}
        advances: dict[str, float] = {}
        for index, ch in enumerate(_GLYPHS):
            paths = tuple(path for path in atlas.paths if path.group == index)
            if not paths:
                raise RuntimeError(f"missing math glyph {ch!r}")
            left = min(vector_path_bounds(p)[0] for p in paths)
            right = max(vector_path_bounds(p)[2] for p in paths)
            bottom = min(vector_path_bounds(p)[1] for p in paths)
            top = max(vector_path_bounds(p)[3] for p in paths)
            cx, cy = (left + right) * 0.5, (bottom + top) * 0.5
            centered = tuple(
                _transform_path(p, Transform2D.translation(-cx, -cy), group=0) for p in paths
            )
            # Typst's one-symbol equation width is its natural advance. This is
            # cached by compile_typst_svg, so these probes are cheap after the
            # first construction and never happen per frame.
            metric = Math(ch, font_size=font_size, color=color).document
            advances[ch] = metric.width
            glyphs[ch] = VectorDocument(
                centered, max(right - left, 1e-9), max(top - bottom, 1e-9), 1
            )

        self.glyphs = glyphs
        self.advances = advances
        self.digit_advance = advances["8"]
        self.height = Math("8", font_size=font_size, color=color).document.height
        self._runs: dict[tuple[NumberFormat, str], VectorDocument] = {}

    def reserved_width(self, fmt: NumberFormat) -> float:
        # Width is fixed by the worst legal formatted token pattern, while the
        # visible run inside it keeps natural math advances and is right-aligned.
        digit_slots = fmt.width
        extra = 0.0
        if fmt.decimals > 0:
            digit_slots -= 1
            extra += self.advances["."]
        # A negative value can occupy one sign position and is wider than a
        # blank leading sign. This is the worst case for the supported format.
        if fmt.width >= 2:
            negative = self.advances["-"] + max(0, digit_slots - 1) * self.digit_advance + extra
        else:
            negative = self.digit_advance
        positive = digit_slots * self.digit_advance + extra
        return max(negative, positive)

    def document(
        self, text: str, fmt: NumberFormat, align: Literal["left", "center", "right"] = "right"
    ) -> VectorDocument:
        if len(text) != fmt.width:
            raise ValueError("formatted number must exactly match fixed width")
        key = (fmt, text, align)
        cached = self._runs.get(key)
        if cached is not None:
            return cached

        width = self.reserved_width(fmt)
        visible = [ch for ch in text if ch != " "]
        run_width = sum(self.advances[ch] for ch in visible)
        if align == "right":
            cursor = width * 0.5 - run_width
        elif align == "center":
            cursor = -run_width * 0.5
        elif align == "left":
            cursor = -width * 0.5
        else:
            raise ValueError("invalid DynamicNumber alignment")
        paths: list[VectorPath] = []
        for ch in visible:
            advance = self.advances[ch]
            cx = cursor + advance * 0.5
            glyph = self.glyphs[ch]
            for path in glyph.paths:
                paths.append(_transform_path(path, Transform2D.translation(cx, 0.0), group=0))
            cursor += advance

        doc = VectorDocument(
            tuple(paths), width=width, height=self.height, group_count=1 if paths else 0
        )
        self._runs[key] = doc
        return doc


@lru_cache(maxsize=32)
def _atlas(font_size: float, color: Color) -> _MathNumberGlyphAtlas:
    return _MathNumberGlyphAtlas(font_size, color)


def number_metrics(
    fmt: NumberFormat,
    *,
    font_size: float = 38.0,
    color: Color = Color(240, 242, 248),
) -> tuple[float, float]:
    atlas = _atlas(font_size, color)
    return atlas.reserved_width(fmt), atlas.height


class DynamicNumber(VectorObject2D):
    """Fixed-box, high-frequency number rendered with Typst math glyphs."""

    __slots__ = ("provider", "number_format", "font_size", "color", "align", "_atlas")

    def __init__(
        self,
        provider: Callable[[float], Real] | ScalarValue,
        *,
        number_format: NumberFormat,
        font_size: float = 38.0,
        color: Color = Color(240, 242, 248),
        align: Literal["left", "center", "right"] = "right",
        transform: Transform2D = Transform2D(),
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        if isinstance(provider, ScalarValue):
            provider = provider.value_at
        if not callable(provider):
            raise TypeError("DynamicNumber provider must be callable or ScalarValue")
        self.provider = provider
        self.number_format = number_format
        self.font_size = font_size
        self.color = color
        if align not in ("left", "center", "right"):
            raise ValueError("invalid DynamicNumber alignment")
        self.align = align
        self._atlas = _atlas(font_size, color)
        initial = self._document_for_value(provider(0.0))
        super().__init__(
            document=initial, transform=transform, reveal=1.0, opacity=opacity, z_index=z_index
        )

    @property
    def fixed_size(self) -> tuple[float, float]:
        return self._atlas.reserved_width(self.number_format), self._atlas.height

    def value_at(self, time: float) -> Real:
        return self.provider(float(time))

    def _document_for_value(self, value: Real) -> VectorDocument:
        text = self.number_format.format(value)
        return self._atlas.document(text, self.number_format, self.align)

    def document_at(self, time: float) -> VectorDocument:
        return self._document_for_value(self.value_at(time))

    def _document_at(self, time: float, initial: VectorDocument) -> VectorDocument:
        _ = initial
        return self.document_at(time)
