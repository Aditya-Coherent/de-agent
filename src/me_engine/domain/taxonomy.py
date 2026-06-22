"""Immutable taxonomy of the market-estimation model.

This module is the single source of truth for *structure*: which years exist,
which segmentation dimensions and segments exist, and how the geography tree is
shaped. Everything downstream (readers, assembler, writer, diff) imports these
definitions instead of hard-coding strings or row numbers, so the layout is
described once and reused.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import Mapping, Sequence

# --- Time horizon -----------------------------------------------------------
BASE_YEAR = 2025          # the anchor year (Value here == the global anchor)
FIRST_YEAR = 2021         # historical start (back-cast)
LAST_YEAR = 2033          # forecast horizon
YEARS: tuple[int, ...] = tuple(range(FIRST_YEAR, LAST_YEAR + 1))


class Band(str, Enum):
    """The three vertically stacked bands present in every geography sheet."""

    VALUE = "Market Value (US$ Mn)"
    ASP = "ASP"
    VOLUME = "Market Volume (Th Liters)"


@dataclass(frozen=True, slots=True)
class Dimension:
    """A segmentation dimension (e.g. 'By Product Type') and its ordered members.

    Most dimensions are flat: every segment's market share is relative to the
    band total. Some (Distribution Channel) are hierarchical: a child's share is
    relative to its immediate parent segment, not the band total. `parent` maps
    a segment to that immediate parent (None == band total).
    """

    title: str
    segments: tuple[str, ...]
    parent: Mapping[str, str | None] = field(default_factory=dict)

    def parent_of(self, segment: str) -> str | None:
        return self.parent.get(segment)


# Ordered exactly as they appear in the source workbook.
PRODUCT_TYPE = Dimension(
    "By Product Type",
    ("Extra virgin Oil", "Virgin Oil", "Pure or Refined Oil", "Blends",
     "Others (Oil Spray, etc.)"),
)
PACKAGING = Dimension(
    "By Packaging",
    ("Bottles", "Pouches", "Tins", "Others (Jars, etc.)"),
)
END_USER = Dimension(
    "By End User",
    ("Cosmetics & Personal Care", "Food & Beverages", "Pharmaceuticals",
     "Others (Nutraceuticals, etc.)"),
)
DISTRIBUTION_CHANNEL = Dimension(
    "By Distribution Channel",
    ("B2B", "B2C", "Offline", "Supermarkets or Hypermarkets",
     "Convenience Stores", "Others (Specialty Stores, etc.)", "Online",
     "E commerce Platforms", "Company Owned Websites"),
    parent={
        # B2B / B2C split the band total.
        "B2B": None, "B2C": None,
        # Offline / Online are the channel mix *within B2C*.
        "Offline": "B2C", "Online": "B2C",
        # Offline outlets sum to Offline; online outlets sum to Online.
        "Supermarkets or Hypermarkets": "Offline",
        "Convenience Stores": "Offline",
        "Others (Specialty Stores, etc.)": "Offline",
        "E commerce Platforms": "Online",
        "Company Owned Websites": "Online",
    },
)

SEGMENTATION_DIMENSIONS: tuple[Dimension, ...] = (
    PRODUCT_TYPE, PACKAGING, END_USER, DISTRIBUTION_CHANNEL,
)

# ASP and Volume are priced per *product*, so only the product dimension carries ASP.
PRICED_DIMENSION = PRODUCT_TYPE


@dataclass(frozen=True, slots=True)
class Geography:
    """A node in the geography tree (Global, a region, or a country)."""

    name: str
    children: tuple["Geography", ...] = ()

    @property
    def is_leaf(self) -> bool:
        return not self.children


def _g(name: str, *children: Geography) -> Geography:
    return Geography(name, tuple(children))


# The full geography tree, mirroring the 37 sheets of the source workbook.
GEOGRAPHY_TREE: Geography = _g(
    "Global",
    _g("North America", _g("U.S."), _g("Canada")),
    _g("Europe", _g("U.K."), _g("Germany"), _g("Romania"), _g("Italy"),
       _g("Poland"), _g("France"), _g("Finland"), _g("Spain"), _g("Belgium"),
       _g("Russia"), _g("Rest of Europe")),
    _g("Asia Pacific", _g("China"), _g("India"), _g("Japan"),
       _g("South Korea"), _g("ASEAN"), _g("Australia"), _g("Philippines"),
       _g("Rest of Asia Pacific")),
    _g("Latin America", _g("Brazil"), _g("Argentina"), _g("Mexico"),
       _g("Rest of Latin America")),
    _g("Middle East", _g("GCC Countries"), _g("Rest of Middle East")),
    _g("Africa", _g("North Africa"), _g("South Africa"), _g("Central Africa")),
)


@dataclass(frozen=True)
class GeographyIndex:
    """Flattened, queryable view of the geography tree.

    Built once and passed around so traversals are dictionary lookups rather
    than repeated tree walks. (No ``slots`` so ``cached_property`` can memoise.)
    """

    root: Geography

    @cached_property
    def in_order(self) -> tuple[Geography, ...]:
        """All geographies, parents before children (sheet order)."""
        return tuple(self._walk(self.root))

    @cached_property
    def by_name(self) -> Mapping[str, Geography]:
        return {g.name: g for g in self.in_order}

    @cached_property
    def parent_of(self) -> Mapping[str, str | None]:
        parents: dict[str, str | None] = {self.root.name: None}
        for parent in self.in_order:
            for child in parent.children:
                parents[child.name] = parent.name
        return parents

    @staticmethod
    def _walk(node: Geography):
        yield node
        for child in node.children:
            yield from GeographyIndex._walk(child)


GEOGRAPHIES = GeographyIndex(GEOGRAPHY_TREE)
