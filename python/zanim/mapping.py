from __future__ import annotations

from collections.abc import Iterable

from .geometry import Color


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def grayscale(values: Iterable[float], *, alpha: int = 255) -> tuple[Color, ...]:
    """Map values in [0, 1] to grayscale colors."""
    out = []
    for value in values:
        q = round(255 * _clamp01(value))
        out.append(Color(q, q, q, alpha))
    return tuple(out)


def activation_colors(
    values: Iterable[float],
    *,
    base: Color = Color(72, 133, 237),
    min_alpha: int = 28,
    max_alpha: int = 255,
) -> tuple[Color, ...]:
    """Encode normalized activations primarily through opacity."""
    span = max_alpha - min_alpha
    return tuple(
        Color(base.r, base.g, base.b, round(min_alpha + span * _clamp01(value))) for value in values
    )


def activation_radii(
    values: Iterable[float], *, minimum: float = 0.12, maximum: float = 0.24
) -> tuple[float, ...]:
    if minimum <= 0 or maximum < minimum:
        raise ValueError("invalid radius range")
    return tuple(minimum + (maximum - minimum) * _clamp01(value) for value in values)


def signed_weight_colors(
    values: Iterable[float],
    *,
    scale: float | None = None,
    positive: Color = Color(72, 151, 255),
    negative: Color = Color(255, 92, 105),
    min_alpha: int = 8,
    max_alpha: int = 150,
) -> tuple[Color, ...]:
    """Encode sign as hue and |weight| as opacity.

    `scale` is the magnitude mapped to full intensity. If omitted, the maximum
    absolute value in the supplied data is used.
    """
    data = tuple(float(v) for v in values)
    if not data:
        return ()
    magnitude_scale = max(abs(v) for v in data) if scale is None else float(scale)
    if magnitude_scale <= 0:
        magnitude_scale = 1.0
    span = max_alpha - min_alpha
    out = []
    for value in data:
        strength = _clamp01(abs(value) / magnitude_scale)
        base = positive if value >= 0 else negative
        out.append(Color(base.r, base.g, base.b, round(min_alpha + span * strength)))
    return tuple(out)


def weight_widths(
    values: Iterable[float],
    *,
    scale: float | None = None,
    minimum: float = 0.002,
    maximum: float = 0.009,
) -> tuple[float, ...]:
    """Encode |weight| as logical stroke width.

    Defaults stay within the LineSet sub-pixel fast path for a 100 px/unit
    canvas while still visibly separating weak and strong connections.
    """
    data = tuple(float(v) for v in values)
    if not data:
        return ()
    magnitude_scale = max(abs(v) for v in data) if scale is None else float(scale)
    if magnitude_scale <= 0:
        magnitude_scale = 1.0
    return tuple(minimum + (maximum - minimum) * _clamp01(abs(v) / magnitude_scale) for v in data)
