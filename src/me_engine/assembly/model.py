"""The assembled result model — pure numbers, no spreadsheet concepts.

The assembler produces these structures; the writer renders them. Keeping the
computed result separate from the workbook means the math is unit-testable and
the rendering is swappable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..domain.series import Series
from ..domain.taxonomy import Band


@dataclass(frozen=True, slots=True)
class MetricRow:
    """One label's full set of views within a band."""

    label: str
    series: Series                 # the metric path (Value / ASP / Volume)
    share_of_parent: Series | None  # market-share path, None for band totals


@dataclass(frozen=True, slots=True)
class BandResult:
    """All rows of one band for one geography, in source order."""

    band: Band
    total: Series
    rows_by_label: Mapping[str, MetricRow]


@dataclass(frozen=True, slots=True)
class GeographyResult:
    """The three assembled bands for a single geography."""

    name: str
    bands: Mapping[Band, BandResult]


@dataclass(frozen=True, slots=True)
class MarketResult:
    """Every geography's assembled result for one market."""

    market_name: str
    geographies: Mapping[str, GeographyResult]
