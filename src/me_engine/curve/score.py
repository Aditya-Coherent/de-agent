"""Score a proposed growth shape against the human ME ground truth.

Because the real analyst curves live in the ME workbook, any agent- or
baseline-proposed shape can be measured objectively: how close is its normalised
shape to the human curve, and how far does the resulting value path drift?
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from ..domain.series import Series
from ..domain.taxonomy import YEARS
from .canonical import cosine_similarity, shape_distance
from .shape import NormalizedShape, YOY_YEARS


def shape_from_value_path(path: Series) -> NormalizedShape:
    """Recover the normalised Y-o-Y shape from an actual value path."""
    yoy = path.yoy()
    mean = fmean(yoy.values())
    return NormalizedShape(tuple(yoy[y] / mean for y in YOY_YEARS))


@dataclass(frozen=True, slots=True)
class CurveScore:
    geography: str
    shape_mae: float            # mean abs error vs human shape (0 = perfect)
    cosine: float               # 1.0 = identical direction
    path_max_rel_error: float   # worst per-year relative error of the value path

    def summary(self) -> str:
        return (f"{self.geography:16s} shapeMAE={self.shape_mae:.4f} "
                f"cosine={self.cosine:.4f} pathMaxRel={self.path_max_rel_error:.2%}")


class CurveScorer:
    """Compares a proposed shape (and its path) to the ground-truth path."""

    def score(self, geography: str, proposed: NormalizedShape,
              proposed_path: Series, truth_path: Series) -> CurveScore:
        truth_shape = shape_from_value_path(truth_path)
        return CurveScore(
            geography=geography,
            shape_mae=shape_distance(proposed, truth_shape),
            cosine=cosine_similarity(proposed, truth_shape),
            path_max_rel_error=self._max_rel(proposed_path, truth_path),
        )

    @staticmethod
    def _max_rel(a: Series, b: Series) -> float:
        return max(abs(a.at(y) - b.at(y)) / abs(b.at(y)) for y in YEARS)
