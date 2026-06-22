# Stage 1 — Deterministic Assembler (SPEC)

## Goal
Given a **complete driver set**, deterministically reproduce the `ME - <Market>.xlsx`
workbook **cell-for-cell** (within float rounding). No agents, no ML, no network.

This proves the math "spine" and, just as importantly, **defines the exact contract**
that the agent layer must fill in later: every number an agent will source maps to one
field in `DriverSet`.

## Key discovery (why the Input Sheet alone is not enough — yet)
The `Input Sheet` holds **single-year snapshots** only:
- one segmentation `%` per segment (a single year),
- one CAGR per geography,
- one ASP per (product × country).

The `ME` workbook holds **13-year dynamics** (2021–2033) that are NOT in the Input Sheet:
- a **non-constant total growth curve** (Y-o-Y accelerates then eases),
- **per-segment CAGRs** (segments grow at different rates → market-shares drift yearly),
- **per-year ASP paths** (ASP itself grows over time).

These dynamics are the analyst's manual "curve" choices — exactly what the agents will
later *generate from evidence*. For Stage 1 verification we **extract them from the
existing ME file** so the assembler has a complete driver set to reproduce against.

## The three bands (per sheet)
Every geography sheet contains three vertically stacked bands, same taxonomy in each:

| Band | Title row marker (col D) | Unit | Formula |
|------|--------------------------|------|---------|
| Value  | `Market Value (US$ Mn)`   | US$ Mn      | the anchor, allocated & grown |
| ASP    | `ASP`                     | US$ / unit  | per-segment price path (input) |
| Volume | `Market Volume (Th Liters)` | Th Liters | `Value / ASP * 1000` |

## Column layout (within a band)
- **D..P**  = the metric for years **2021..2033** (13 columns)
- **R..AC** = **Y-o-Y** growth for years **2022..2033** (12 columns) = `v[y]/v[y-1] - 1`
- **AE**    = **CAGR** (stored, full-series summary)
- **AK..AW**= **Market Share** for years **2021..2033** = `seg[y] / parent_total[y]`

## Row taxonomy (sub-blocks, in order)
Each band repeats these sub-blocks. A block header row repeats the **band total**;
its member rows are the breakdown.

1. `By Product Type` → Extra virgin Oil, Virgin Oil, Pure or Refined Oil, Blends, Others (Oil Spray, etc.)
2. `By Packaging` → Bottles, Pouches, Tins, Others (Jars, etc.)
3. `By End User` → Cosmetics & Personal Care, Food & Beverages, Pharmaceuticals, Others (Nutraceuticals, etc.)
4. `By Distribution Channel` → B2B, B2C, Offline{Supermarkets, Convenience, Others}, Online{E-commerce, Company sites}
5. `By Country` → children geographies **(region/global sheets only; absent on country sheets)**

## Core identities (verified against the avocado file, diff = 0.0)
- `segment_value[y]      = band_total[y] * segment_share[y]`
- `Y-o-Y[y]              = v[y] / v[y-1] - 1`
- `volume[y] (Th Liters)= value[y] (US$ Mn) / asp[y] * 1000`
- `band_total[2025]      = anchor` (2025 is the base/anchor year)
- child geo `value[y]    = parent value[y] * geo_share[y]`

## DriverSet contract (what the assembler consumes)
```
DriverSet
  market_name: str
  geographies: tree(Global -> regions -> countries)
  anchor_value_2025: float                 # global Value Mn in 2025
  per geography:
    value_path[2021..2033]                 # OR geo_share_path applied to parent
    segmentation:
      for each dimension (product/packaging/enduser/channel):
        for each segment: share_path[2021..2033]
    asp:
      for each product segment: asp_path[2021..2033]
```
For Stage 1, paths are read from the ME file. For Stage 3+, agents fill them.

## Definition of done
`diff` of generated workbook vs source `ME - Global Avocado Oil Market.xlsx` reports
max abs deviation ≈ 0 across all 37 sheets and all bands.
