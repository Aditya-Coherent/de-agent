"""Canonical segmentation premiums, reverse-engineered from the ME workbook.

Derived by computing (share[2033]/share[2025])^(1/8) * (1+geo_cagr) - (1+geo_cagr)
across all 28 geographies in the avocado oil ME file. Cross-geography spread is
only ±0.001, so a single mean per segment is a tight prior.

These are the default growth-premium priors for the segmentation agent.
The agent *adjusts* these rather than inventing from scratch — same pattern
as the curve agent's canonical shape.
"""
from __future__ import annotations

# Mean implied annual growth premium (vs market CAGR) per segment, per dimension.
# Positive = segment gains share, negative = loses share.
CANONICAL_PREMIUMS: dict[str, dict[str, float]] = {
    "By Product Type": {
        "Extra virgin Oil":         +0.0062,
        "Virgin Oil":               -0.0120,
        "Pure or Refined Oil":      -0.0061,
        "Blends":                   -0.0002,
        "Others (Oil Spray, etc.)": +0.0116,
    },
    "By Packaging": {
        "Bottles":                  +0.0009,
        "Pouches":                  +0.0172,
        "Tins":                     -0.0106,
        "Others (Jars, etc.)":      -0.0048,
    },
    "By End User": {
        "Cosmetics & Personal Care":       +0.0048,
        "Food & Beverages":                -0.0007,
        "Pharmaceuticals":                 -0.0067,
        "Others (Nutraceuticals, etc.)":   +0.0123,
    },
    "By Distribution Channel": {
        "B2B":                             -0.0043,
        "B2C":                             +0.0053,
        "Offline":                         -0.0090,
        "Supermarkets or Hypermarkets":    -0.0009,
        "Convenience Stores":              -0.0062,
        "Others (Specialty Stores, etc.)": +0.0067,
        "Online":                          +0.0249,
        "E commerce Platforms":            +0.0019,
        "Company Owned Websites":          -0.0086,
    },
}
