"""Growth-curve shape mathematics — pure, deterministic, agent-independent.

A `NormalizedShape` is the year-by-year Y-o-Y *shape* (mean ~ 1) over the forecast
window. The judgement of which shape fits a market is the agent's job; turning a
shape + a target CAGR into an exact value path is plain arithmetic and lives here.

This is the bridge the CURVE-AGENT.md recipe describes:
    shape (mean 1)  --scale to hit CAGR-->  Y-o-Y path  --compound from anchor-->  value path
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from ..domain.series import Series
from ..domain.taxonomy import BASE_YEAR, LAST_YEAR, YEARS

# Forecast window: the years the Input-Sheet CAGR describes (2025 -> 2033).
FORECAST_YEARS: tuple[int, ...] = tuple(y for y in YEARS if y > BASE_YEAR)
# Y-o-Y is defined for every year after the first historical year.
YOY_YEARS: tuple[int, ...] = YEARS[1:]


@dataclass(frozen=True, slots=True)
class NormalizedShape:
    """Normalised Y-o-Y multipliers over YOY_YEARS (mean ~ 1).

    The values describe the *relative* pace of growth year to year; absolute
    level is supplied later by scaling to a target CAGR.
    """

    multipliers: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.multipliers) != len(YOY_YEARS):
            raise ValueError(
                f"expected {len(YOY_YEARS)} multipliers, got {len(self.multipliers)}")

    @property
    def by_year(self) -> dict[int, float]:
        return dict(zip(YOY_YEARS, self.multipliers))

    @property
    def peak_year(self) -> int:
        return max(self.by_year, key=self.by_year.get)

    @property
    def mean(self) -> float:
        return fmean(self.multipliers)

    def smoothness(self) -> float:
        """Mean absolute second difference — lower is smoother (a quality gate)."""
        m = self.multipliers
        seconds = [abs(m[i + 1] - 2 * m[i] + m[i - 1]) for i in range(1, len(m) - 1)]
        return fmean(seconds) if seconds else 0.0


class CurvePathBuilder:
    """Turns a normalised shape + target forecast CAGR into an exact value path."""

    # Reverse-engineered: historical growth runs ~0.88x of the forecast pace.
    BACKCAST_RATIO = 0.88

    def build(self, anchor_2025: float, target_cagr: float,
              shape: NormalizedShape) -> Series:
        level = self._solve_forecast_level(shape, target_cagr)
        yoy = {
            year: level * mult * (1.0 if year > BASE_YEAR else self.BACKCAST_RATIO)
            for year, mult in shape.by_year.items()
        }
        return Series.from_anchor_and_yoy(anchor_2025, yoy)

    def _solve_forecast_level(self, shape: NormalizedShape,
                              target_cagr: float) -> float:
        """Find level L so the forecast path compounds exactly to the target CAGR.

        Solve prod(1 + L * s_y) == (1+cagr)^n over the forecast years by bisection.
        L scales the absolute pace; the shape fixes the relative year-to-year path.
        """
        seg = [shape.by_year[y] for y in FORECAST_YEARS]
        target_total = (1.0 + target_cagr) ** len(FORECAST_YEARS)
        return self._bisect_level(seg, target_total)

    @staticmethod
    def _bisect_level(seg: list[float], target_total: float,
                      lo: float = 1e-9, hi: float = 1.0, iters: int = 100) -> float:
        def total(level: float) -> float:
            acc = 1.0
            for s in seg:
                acc *= (1.0 + level * s)
            return acc
        for _ in range(iters):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if total(mid) < target_total else (lo, mid)
        return (lo + hi) / 2
