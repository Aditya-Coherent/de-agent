"""The Segmentation Agent — decides per-segment growth premiums, with reasoning.

For each segmentation dimension the agent assigns every segment a small annual
growth premium vs the market (which segments gain share and how fast). The
deterministic ShareDriftBuilder turns those premiums into the drifting share
paths the assembler consumes. The agent never emits shares directly — only the
judgement (premiums + rationale) — keeping math out of the LLM.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .canonical_premiums import CANONICAL_PREMIUMS
from .config import AgentConfig
from .evidence_agent import EvidenceAgent
from .llm import EvidenceGatherer, LLMClient, LLMError
from .segmentation import SegmentPremium
from ..domain.taxonomy import Dimension

_SYSTEM = (
    "You are a market-segmentation analyst. For a market and a segmentation "
    "dimension, decide each segment's annual growth PREMIUM relative to the "
    "overall market (a small number, typically between -0.015 and +0.015, i.e. "
    "-1.5%/yr to +1.5%/yr). Positive means the segment gains share over time; "
    "negative means it loses share. Premiums should roughly offset (winners vs "
    "losers). Base this on which segments are structurally rising (premium/"
    "innovative) or declining (commoditised). Respond ONLY with JSON."
)

_MAX_ABS_PREMIUM = 0.015     # real-world magnitudes: ±0.5–1.5%/yr, never ±3%
_AGENT_WEIGHT = 0.2          # ponytail: 20% LLM + 80% prior; balances prior accuracy with LLM generalization


@dataclass(frozen=True, slots=True)
class SegmentationDecision:
    dimension: str
    premiums: Mapping[str, SegmentPremium]
    used_fallback: bool


class SegmentationAgent:
    """Assigns growth premiums to the segments of a dimension.

    Two-pass decision:
      Pass 1 — LLM decides from structural market knowledge alone.
      If any segment premium is uncertain (confidence < threshold) →
        Evidence Agent fires DDG queries for that segment's trends.
      Pass 2 — LLM re-decides with curated web evidence.
    """

    def __init__(self, config: AgentConfig | None = None,
                 llm: LLMClient | None = None,
                 evidence: EvidenceGatherer | None = None) -> None:
        self._config = config or AgentConfig.load()
        self._llm = llm or LLMClient(self._config)
        self._evidence = evidence or EvidenceGatherer()
        self._ev_agent = EvidenceAgent(config=self._config, llm=self._llm)

    def decide(self, market_name: str, dim: Dimension) -> SegmentationDecision:
        if not self._config.is_online:
            return self._fallback(dim)
        try:
            # Pass 1: decide from structural knowledge + basic evidence
            snippets = self._gather_evidence(market_name, dim)
            raw = self._llm.complete_json(_SYSTEM, self._prompt(market_name, dim, snippets))
            decision = self._validate(dim, raw)

            # Check if overall decision confidence is weak — use mean premium magnitude
            # as a proxy (all-zero premiums = agent wasn't sure)
            avg_abs_premium = sum(
                abs(p.premium) for p in decision.premiums.values()
            ) / max(len(decision.premiums), 1)

            if avg_abs_premium < 0.003:   # < 0.3%/yr mean → agent gave flat answer
                brief = self._ev_agent.gather_and_evaluate(
                    market=market_name,
                    geography="global",
                    topic=f"{dim.title} segment trends market share growth",
                    extra_queries=[
                        f"{market_name} {dim.title} premium segment share forecast",
                        f"{market_name} segment growth winners losers trend",
                    ],
                )
                print(f"    [EvidenceAgent] {dim.title}: {brief.log_summary()}")
                if brief.has_useful_evidence:
                    enriched = snippets + [s.text for s in brief.snippets]
                    raw2 = self._llm.complete_json(
                        _SYSTEM, self._prompt(market_name, dim, enriched))
                    decision = self._validate(dim, raw2)

            return decision
        except (LLMError, KeyError, ValueError, TypeError):
            return self._fallback(dim)

    def _gather_evidence(self, market_name: str, dim: Dimension) -> list[str]:
        return self._evidence.search(
            f"{market_name} {dim.title} segment trends growth share")

    def _prompt(self, market_name: str, dim: Dimension,
                snippets: list[str] | None = None) -> str:
        segs = "\n".join(f"  - {s}" for s in dim.segments)
        evidence = "\n".join(f"- {s}" for s in (snippets or [])) or "- (no web evidence)"
        return (
            f"Market: {market_name}\nDimension: {dim.title}\nSegments:\n{segs}\n\n"
            f"Evidence:\n{evidence}\n\n"
            f'Return JSON: {{"premiums": [{{"segment": <name>, '
            f'"premium": <float -0.02..0.02>, "rationale": <short>}}]}} '
            f"covering every segment listed."
        )

    def _validate(self, dim: Dimension, raw: dict) -> SegmentationDecision:
        provided = {p["segment"]: p for p in raw.get("premiums", [])
                    if isinstance(p, dict) and "segment" in p}
        premiums = {
            seg: self._one(seg, provided.get(seg), dim.title)
            for seg in dim.segments
        }
        return SegmentationDecision(dim.title, premiums, used_fallback=False)

    def _one(self, segment: str, raw: dict | None, dim_title: str) -> SegmentPremium:
        if not raw:
            # No LLM proposal — use canonical prior directly
            prior = CANONICAL_PREMIUMS.get(dim_title, {}).get(segment, 0.0)
            return SegmentPremium(segment, prior, "canonical prior (no LLM proposal)")
        try:
            proposed = float(raw.get("premium", 0.0))
        except (TypeError, ValueError):
            proposed = 0.0
        proposed = max(-_MAX_ABS_PREMIUM, min(_MAX_ABS_PREMIUM, proposed))
        blended = self._guard(proposed, segment, dim_title)
        return SegmentPremium(segment, blended, str(raw.get("rationale", "")))

    @staticmethod
    def _guard(proposed: float, segment: str, dim_title: str) -> float:
        """Blend LLM proposal 50/50 with the data-derived canonical prior.

        Same pattern as CurveAgent._guard(): keeps the LLM's directional signal
        while preventing 4× over-shoot on magnitude.
        """
        prior = CANONICAL_PREMIUMS.get(dim_title, {}).get(segment, 0.0)
        return _AGENT_WEIGHT * proposed + (1 - _AGENT_WEIGHT) * prior

    @staticmethod
    def _fallback(dim: Dimension) -> SegmentationDecision:
        # ponytail: use canonical priors instead of flat 0% — same floor as curve agent
        canonical = CANONICAL_PREMIUMS.get(dim.title, {})
        premiums = {
            seg: SegmentPremium(seg, canonical.get(seg, 0.0), "canonical prior (offline)")
            for seg in dim.segments
        }
        return SegmentationDecision(dim.title, premiums, used_fallback=True)
