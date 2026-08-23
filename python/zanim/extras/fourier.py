from __future__ import annotations

from cmath import exp
from math import pi
from typing import Iterable

from ..fourier import FourierTerm, epicycle_chain
from ..path import sample_vector_contour_by_arclength
from ..space import Vec2
from ..vector import VectorContour, VectorDocument

__all__ = [
    "FourierTerm",
    "epicycle_chain",
    "closed_contours",
    "select_closed_contour",
    "contour_samples",
    "dft",
    "dominant_terms",
    "point2",
]


def closed_contours(document: VectorDocument) -> tuple[VectorContour, ...]:
    """Return every closed contour in document paint order."""
    return tuple(contour for path in document.paths for contour in path.contours if contour.closed)


def select_closed_contour(
    document: VectorDocument,
    *,
    strategy: str = "longest",
    probe_samples: int = 512,
) -> VectorContour:
    """Select one closed contour for single-stroke Fourier drawing.

    ``longest`` is intentionally an extras-level policy, not an SVG-core rule.
    Complex/multi-contour artwork can later provide its own traversal policy.
    """
    contours = closed_contours(document)
    if not contours:
        raise ValueError("SVG/vector document contains no closed contour")
    if strategy == "first":
        return contours[0]
    if strategy != "longest":
        raise ValueError("contour strategy must be 'first' or 'longest'")

    def approximate_length(contour: VectorContour) -> float:
        points = sample_vector_contour_by_arclength(contour, probe_samples, tolerance=2e-3)
        return sum(
            ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5
            for a, b in zip(points, (*points[1:], points[0]))
        )

    return max(contours, key=approximate_length)


def contour_samples(
    contour: VectorContour,
    count: int = 1024,
    *,
    tolerance: float = 1e-3,
) -> tuple[complex, ...]:
    if not contour.closed:
        raise ValueError("Fourier drawing requires a closed contour")
    points = sample_vector_contour_by_arclength(contour, count, tolerance=tolerance)
    return tuple(complex(point.x, point.y) for point in points)


def dft(samples: Iterable[complex]) -> tuple[FourierTerm, ...]:
    """Direct DFT with centered integer frequency labels.

    This is setup-time code.  For the typical 512-2048 outline samples used by
    animation, keeping the implementation dependency-free is preferable to
    adding a numerical-runtime requirement to Zanim core.
    """
    values = tuple(complex(value) for value in samples)
    n = len(values)
    if n < 2:
        raise ValueError("DFT requires at least two samples")
    terms: list[FourierTerm] = []
    half = n // 2
    for k in range(n):
        frequency = k if k <= half else k - n
        coefficient = (
            sum(value * exp(-2j * pi * k * index / n) for index, value in enumerate(values)) / n
        )
        terms.append(FourierTerm(frequency, coefficient))
    return tuple(terms)


def dominant_terms(
    terms: Iterable[FourierTerm],
    count: int,
    *,
    keep_dc_first: bool = True,
) -> tuple[FourierTerm, ...]:
    """Pick the largest Fourier components while keeping a stable chain order."""
    source = tuple(terms)
    if count <= 0:
        raise ValueError("term count must be positive")
    if count > len(source):
        count = len(source)
    dc = next((term for term in source if term.frequency == 0), None)
    non_dc = sorted(
        (term for term in source if term.frequency != 0),
        key=lambda term: (-term.radius, abs(term.frequency), term.frequency),
    )
    selected = non_dc[: count - (1 if keep_dc_first and dc is not None else 0)]
    # Stable, interpretable order: DC followed by +1,-1,+2,-2... among the
    # selected dominant frequencies.  Reordering terms does not change their sum.
    selected.sort(key=lambda term: (abs(term.frequency), 0 if term.frequency > 0 else 1))
    if keep_dc_first and dc is not None:
        return (dc, *selected)
    return tuple(selected[:count])


def point2(value: complex) -> Vec2:
    return Vec2(float(value.real), float(value.imag))
