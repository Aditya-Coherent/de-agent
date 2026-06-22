"""The canonical growth shape, reverse-engineered from the ME workbook.

Averaging the normalised Y-o-Y curves of 19 geographies collapsed them onto one
shared shape (cross-geography spread of only 0.05-0.10). That mean shape is the
evidence-free baseline / fallback prior. The agent is expected to *beat* it by
tailoring the shape to a market's evidence; this gives us a floor to score against.
"""
from __future__ import annotations

from statistics import fmean

from .shape import NormalizedShape, YOY_YEARS

# Mean normalised shape over 2022..2033 (see CURVE-AGENT.md, Finding B).
_CANONICAL = (
    0.9208, 0.9322, 0.9461, 0.9568, 0.9773, 1.0049,
    1.0325, 1.0481, 1.0569, 1.0561, 1.0431, 1.0251,
)

CANONICAL_SHAPE = NormalizedShape(_CANONICAL)


def shape_distance(a: NormalizedShape, b: NormalizedShape) -> float:
    """Mean absolute difference between two normalised shapes (0 == identical)."""
    return fmean(abs(x - y) for x, y in zip(a.multipliers, b.multipliers))


def cosine_similarity(a: NormalizedShape, b: NormalizedShape) -> float:
    dot = sum(x * y for x, y in zip(a.multipliers, b.multipliers))
    na = sum(x * x for x in a.multipliers) ** 0.5
    nb = sum(y * y for y in b.multipliers) ** 0.5
    return dot / (na * nb)
