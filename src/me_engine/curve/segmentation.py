"""Segment-share drift — turning per-segment growth premiums into share paths.

Reverse-engineering showed segment shares drift because each segment grows at the
market CAGR plus/minus a small premium (Extra Virgin +0.6%/yr, Virgin -1.2%/yr,
etc.), consistently across geographies. So the judgement an agent must make per
segment is a single number: its growth premium vs the market. The math here turns
{segment: premium} + a base-year share snapshot into the full drifting share path
that the assembler consumes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..domain.series import Series
from ..domain.taxonomy import BASE_YEAR, Dimension, YEARS


@dataclass(frozen=True, slots=True)
class SegmentPremium:
    """A segment's annual growth premium over the market (e.g. +0.006 = +0.6%/yr)."""

    segment: str
    premium: float
    rationale: str = ""


class ShareDriftBuilder:
    """Expands base-year shares + per-segment premiums into share paths.

    A segment's value grows at (1 + market_cagr + premium) each year; shares are
    then re-derived from those drifting values so they always sum to 1 within the
    dimension. This reproduces the smooth share drift seen in the ME file.
    """

    def build(self, dim: Dimension, base_shares: Mapping[str, float],
              market_cagr: float,
              premiums: Mapping[str, SegmentPremium]) -> dict[str, Series]:
        value_paths = {
            seg: self._segment_value_path(base_shares[seg], market_cagr,
                                          premiums.get(seg))
            for seg in dim.segments
            if dim.parent_of(seg) is None or seg in base_shares
        }
        return self._shares_from_values(dim, value_paths)

    def _segment_value_path(self, base_share: float, market_cagr: float,
                            premium: SegmentPremium | None) -> Series:
        rate = market_cagr + (premium.premium if premium else 0.0)
        return Series({
            year: base_share * (1.0 + rate) ** (year - BASE_YEAR)
            for year in YEARS
        })

    def _shares_from_values(self, dim: Dimension,
                            value_paths: Mapping[str, Series]) -> dict[str, Series]:
        """Re-normalise sibling values into shares relative to their parent.

        Flat dimensions normalise across all members; hierarchical ones normalise
        each parent group separately so child shares sum to 1 within the parent.
        """
        groups = self._sibling_groups(dim, value_paths)
        shares: dict[str, Series] = {}
        for siblings in groups:
            totals = {y: sum(value_paths[s].at(y) for s in siblings) for y in YEARS}
            for seg in siblings:
                shares[seg] = Series({
                    y: value_paths[seg].at(y) / totals[y] for y in YEARS})
        return shares

    @staticmethod
    def _sibling_groups(dim: Dimension,
                        present: Mapping[str, Series]) -> list[list[str]]:
        by_parent: dict[str | None, list[str]] = {}
        for seg in dim.segments:
            if seg in present:
                by_parent.setdefault(dim.parent_of(seg), []).append(seg)
        return list(by_parent.values())
