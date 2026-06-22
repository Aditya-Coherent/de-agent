"""A year-indexed numeric series — the atomic value carried through the engine.

`Series` wraps the 13-year horizon and provides the derived views the workbook
needs (Y-o-Y, CAGR) as pure, vectorised computations. Keeping these as methods
on one type means the assembler never re-implements growth math inline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .taxonomy import YEARS, BASE_YEAR


@dataclass(frozen=True, slots=True)
class Series:
    """Immutable map of year -> value over the model horizon."""

    values: Mapping[int, float]

    # --- constructors -------------------------------------------------------
    @classmethod
    def from_iterable(cls, values: Iterable[float]) -> "Series":
        mapped = dict(zip(YEARS, values, strict=True))
        return cls(mapped)

    @classmethod
    def from_anchor_and_yoy(cls, anchor: float, yoy: Mapping[int, float]) -> "Series":
        """Reconstruct a path from a base-year anchor and a Y-o-Y growth map.

        Walks outward from BASE_YEAR: forward by compounding, backward by
        dividing. This is how a non-constant growth *curve* expands to a path.
        """
        out: dict[int, float] = {BASE_YEAR: anchor}
        for year in range(BASE_YEAR + 1, YEARS[-1] + 1):
            out[year] = out[year - 1] * (1.0 + yoy[year])
        for year in range(BASE_YEAR - 1, YEARS[0] - 1, -1):
            out[year] = out[year + 1] / (1.0 + yoy[year + 1])
        return cls(out)

    # --- access -------------------------------------------------------------
    def at(self, year: int) -> float:
        return self.values[year]

    @property
    def anchor(self) -> float:
        return self.values[BASE_YEAR]

    def ordered(self) -> tuple[float, ...]:
        return tuple(self.values[y] for y in YEARS)

    # --- derived views ------------------------------------------------------
    def yoy(self) -> Mapping[int, float]:
        """Year-over-year growth for every year after the first."""
        return {
            year: self.values[year] / self.values[year - 1] - 1.0
            for year in YEARS[1:]
        }

    def cagr(self) -> float:
        """Compound annual growth over the full horizon."""
        span = YEARS[-1] - YEARS[0]
        return (self.values[YEARS[-1]] / self.values[YEARS[0]]) ** (1.0 / span) - 1.0

    # --- algebra (used by the assembler) ------------------------------------
    def scaled_by(self, factors: "Series") -> "Series":
        """Element-wise product — e.g. total * share = segment value."""
        return Series({y: self.values[y] * factors.values[y] for y in YEARS})

    def share_of(self, parent: "Series") -> "Series":
        """Element-wise ratio — e.g. segment / total = market share path."""
        return Series({y: self.values[y] / parent.values[y] for y in YEARS})

    def divided_by(self, other: "Series", scale: float = 1.0) -> "Series":
        """Element-wise division with a unit scale — Value/ASP*1000 = Volume."""
        return Series({y: self.values[y] / other.values[y] * scale for y in YEARS})
