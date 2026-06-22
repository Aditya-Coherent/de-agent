"""The DriverSet — the complete, structured input the assembler consumes.

Every field here is a number (or path of numbers) that, in the live system, an
agent will source from evidence. In Stage 1 they are extracted from an existing
ME workbook so the assembler can be verified. The assembler depends ONLY on this
type — never on a spreadsheet — which is what lets the data source swap freely.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .series import Series
from .taxonomy import Dimension


@dataclass(frozen=True, slots=True)
class SegmentationDrivers:
    """Per-dimension market-share paths for one geography.

    `shares[dimension.title][segment]` is the year-by-year share of that segment
    within its dimension. Shares may drift across years (segments grow at
    different rates) — that drift is the curve, captured here explicitly.
    """

    shares: Mapping[str, Mapping[str, Series]]

    def for_dimension(self, dim: Dimension) -> Mapping[str, Series]:
        return self.shares[dim.title]


@dataclass(frozen=True, slots=True)
class AspDrivers:
    """Per-product average-selling-price paths for one geography."""

    asp: Mapping[str, Series]

    def for_product(self, product: str) -> Series:
        return self.asp[product]


@dataclass(frozen=True, slots=True)
class GeographyDrivers:
    """The full driver bundle for a single geography node."""

    name: str
    value: Series                      # Market Value (US$ Mn) path
    segmentation: SegmentationDrivers
    asp: AspDrivers


@dataclass(frozen=True, slots=True)
class DriverSet:
    """All drivers for an entire market, keyed by geography name."""

    market_name: str
    geographies: Mapping[str, GeographyDrivers]

    def of(self, geography_name: str) -> GeographyDrivers:
        return self.geographies[geography_name]
