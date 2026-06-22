# The Growth Curve — How It's Made, and the Agent That Generates It

## 1. What problem the curve solves

The Input Sheet gives **one CAGR per geography** (a single growth number). The ME
deliverable needs a **13-year value path (2021–2033)** for every geography and
every segment. The bridge between "one number" and "a full path" is the **growth
curve**: the year-by-year Y-o-Y shape that, when applied to the 2025 anchor,
produces the whole series.

Historically an analyst picked this shape **by feel** from ~100 manual trend
templates. We are replacing that judgment with an agent that derives the shape
from evidence and the Input Sheet — no fixed template menu.

## 2. How the curve was actually made (reverse-engineered from the ME file)

Decoded from `ME - Global Avocado Oil Market.xlsx` across 19 geographies:

### Finding A — the Input CAGR is the forecast anchor
The Input Sheet's CAGR for a geography equals its **2025→2033 CAGR** in the ME
file, to 4 decimal places, everywhere:

| Geography | Input CAGR | ME 2025→2033 CAGR |
|-----------|-----------:|------------------:|
| Global    | 0.0542 | 0.0548 |
| U.S.      | 0.0424 | 0.0424 |
| India     | 0.0970 | 0.0969 |
| Africa    | 0.0462 | 0.0461 |

➡ The CAGR is **not** applied flat. It is the **average growth over the forecast
window**, around which a curved Y-o-Y path oscillates.

### Finding B — the curve SHAPE is near-universal
Normalising each geography's Y-o-Y path by its own mean collapses them onto one
shared shape (spread of only 0.05–0.10 across all 19 geographies):

```
year :  2022  2023  2024  2025  2026  2027  2028  2029  2030  2031  2032  2033
shape: 0.921 0.932 0.946 0.957 0.977 1.005 1.033 1.048 1.057 1.056 1.043 1.025
                                                         ^peak (2030)
```

A smooth **accelerating hump**: growth starts ~8% below the mean, accelerates
through the late 2020s, **peaks in 2030–2031 at ~6% above the mean**, then eases.

### Finding C — back-cast runs slower than forecast
Mean Y-o-Y for the historical window (2022–2025) is ~88–95% of the forecast
window (2026–2033). The past grew a little slower than the projected future.

### The reconstruction recipe (deterministic, once a shape is chosen)
1. Take the geography's **forecast CAGR** `g` (from Input Sheet).
2. Take a **normalised shape** `s[year]` (mean = 1) — the agent's job.
3. Scale the shape so the resulting 2025→2033 path compounds to exactly `g`.
4. Apply Y-o-Y outward from the 2025 anchor (forward compound, backward divide).
   → reproduces the ME value path.

This recipe is already implemented in `Series.from_anchor_and_yoy`.

## 3. The Curve Agent — design

**Goal:** given the Input Sheet (market name, per-geo CAGR, segmentation, region
context), produce a **normalised growth shape** per geography, **with reasoning
and sources** — no fixed template menu.

### Inputs
- Input Sheet drivers (CAGR, region, segmentation mix, ASP level)
- Evidence the agent gathers (adoption stage, market maturity, macro signals,
  analogous-market growth patterns) via web search / aggregated sources

### Output (structured, validated)
```
CurveDecision
  geography: str
  shape: float[12]                 # normalised Y-o-Y multipliers, mean ≈ 1
  archetype: str                   # e.g. "accelerating-adoption", "maturing", "cyclical"
  peak_year: int
  reasoning: str                   # WHY this shape fits this market
  evidence: [{claim, source, confidence}]
  confidence: float
```

### How it reasons (not a menu lookup)
1. **Classify the market's growth regime** from evidence: is demand early-stage
   (accelerating), maturing (decelerating), saturated (flat), or cyclical?
2. **Propose a shape** consistent with that regime (the LLM proposes the 12
   multipliers, constrained to mean ≈ 1 and smoothness).
3. **Ground it**: each shape choice cites evidence (e.g. "avocado-oil retail
   penetration still rising in APAC → front-load acceleration").
4. **Validate** numerically: shape is smooth, mean ≈ 1, no negative growth unless
   justified; then scaled to hit the Input CAGR.

### Decoupling (consistent with the whole system)
The agent only decides the **shape**. The deterministic assembler still does all
arithmetic (scale to CAGR, compound to a path, split, price). The LLM never emits
final market numbers — it emits a *shape + reasoning*, which is the one genuinely
judgemental input.

### Accuracy harness
Because we have the real ME curves, every agent shape can be scored against the
human curve: cosine/Δ on the normalised shape, and the resulting value-path
deviation. This tells us how close the agent is to the analyst — per geography.

## 4. Build steps
1. `curve/shape.py` — `NormalizedShape` type + scale-to-CAGR + path builder (pure math).
2. `curve/canonical.py` — the reverse-engineered canonical shape as an evidence-free baseline/fallback.
3. `curve/agent.py` — the LLM agent (OpenRouter/OpenAI) that proposes shape + reasoning + evidence.
4. `curve/score.py` — compare agent shape vs ME ground-truth shape.
5. Wire into the pipeline so a full ME workbook can be assembled from Input Sheet + agent curves.
