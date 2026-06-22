"""Evidence Agent — DDG search + LLM brain evaluator.

Workflow:
  1. Main agent makes a first-pass decision (low evidence).
  2. If confidence < threshold → EvidenceAgent fires targeted DDG queries.
  3. Brain (same LLM) scores each snippet: relevance, data quality, recency.
  4. Only high-quality snippets are forwarded to the main agent for a second pass.
  5. If no good snippets found → log it, return empty; main agent uses its prior.

The brain never changes numbers directly — it just curates which web snippets are
worth passing to the main agent. The main agent still blends against the prior.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from .cache import JsonCache
from .config import AgentConfig
from .llm import LLMClient, LLMError


_BRAIN_SYSTEM = (
    "You are a research quality assessor for market intelligence. You receive "
    "web search snippets and must evaluate each one for usefulness to a specific "
    "market-sizing task. Score each snippet on three dimensions (0-1):\n"
    "  - relevance: does it directly address the market/geography in question?\n"
    "  - data_quality: does it contain quantitative data (CAGR, size, share, rate)?\n"
    "  - recency: is the data from 2020 or later? (0 if clearly old)\n"
    "Return ONLY JSON. Discard snippets scoring below 0.4 on relevance."
)

_CONFIDENCE_THRESHOLD_DEFAULT = 0.65
_MAX_RESULTS_DEFAULT = 6
_MIN_SNIPPET_RELEVANCE = 0.4   # brain must rate this relevant to pass through
_MIN_SNIPPET_DATA_QUALITY = 0.3


@dataclass(frozen=True, slots=True)
class ScoredSnippet:
    text: str
    relevance: float
    data_quality: float
    recency: float

    @property
    def score(self) -> float:
        return (self.relevance * 0.5 + self.data_quality * 0.35 + self.recency * 0.15)

    @property
    def passes(self) -> bool:
        return (self.relevance >= _MIN_SNIPPET_RELEVANCE
                and self.data_quality >= _MIN_SNIPPET_DATA_QUALITY)


@dataclass
class EvidenceBrief:
    """The curated evidence brief passed to the main agent for a second pass."""
    snippets: list[ScoredSnippet] = field(default_factory=list)
    queries_fired: int = 0
    raw_retrieved: int = 0
    passed_brain: int = 0

    @property
    def has_useful_evidence(self) -> bool:
        return self.passed_brain > 0

    def as_prompt_block(self) -> str:
        if not self.snippets:
            return "- (no high-quality web evidence found)"
        lines = [
            f"- [rel={s.relevance:.1f} data={s.data_quality:.1f}] {s.text}"
            for s in sorted(self.snippets, key=lambda x: x.score, reverse=True)
        ]
        return "\n".join(lines)

    def log_summary(self) -> str:
        return (f"DDG: {self.queries_fired} queries → "
                f"{self.raw_retrieved} snippets → "
                f"{self.passed_brain} passed brain filter")


class EvidenceAgent:
    """Fires DDG queries and runs a brain-evaluation pass on the results."""

    def __init__(self,
                 config: AgentConfig | None = None,
                 llm: LLMClient | None = None) -> None:
        self._config = config or AgentConfig.load()
        self._llm = llm or LLMClient(self._config)
        self._threshold = float(
            os.environ.get("ME_EVIDENCE_CONFIDENCE_THRESHOLD",
                           str(_CONFIDENCE_THRESHOLD_DEFAULT)))
        self._max_results = int(
            os.environ.get("ME_EVIDENCE_MAX_RESULTS", str(_MAX_RESULTS_DEFAULT)))

    def needs_evidence(self, confidence: float) -> bool:
        return confidence < self._threshold

    def gather_and_evaluate(
        self,
        market: str,
        geography: str,
        topic: str,
        extra_queries: list[str] | None = None,
    ) -> EvidenceBrief:
        """Run DDG searches, brain-evaluate snippets, return curated brief."""
        queries = self._build_queries(market, geography, topic, extra_queries or [])
        raw_snippets = self._run_searches(queries)

        brief = EvidenceBrief(
            queries_fired=len(queries),
            raw_retrieved=len(raw_snippets),
        )

        if not raw_snippets or not self._config.is_online:
            return brief

        scored = self._brain_evaluate(raw_snippets, market, geography, topic)
        passing = [s for s in scored if s.passes]

        brief.snippets = passing
        brief.passed_brain = len(passing)
        return brief

    # --- query building -------------------------------------------------------

    def _build_queries(self, market: str, geography: str,
                       topic: str, extra: list[str]) -> list[str]:
        base = [
            f"{market} {geography} market growth forecast CAGR 2024 2025",
            f"{geography} {market} demand trend consumption statistics",
            f"{market} {geography} market size annual growth rate",
        ]
        if extra:
            base.extend(extra[:2])   # cap at 2 extra to avoid rate limits
        return base

    # --- DDG search -----------------------------------------------------------

    def _run_searches(self, queries: list[str]) -> list[str]:
        ddgs_cls = self._import_ddgs()
        if ddgs_cls is None:
            return []

        snippets: list[str] = []
        per_query = max(2, self._max_results // len(queries))

        for query in queries:
            try:
                with ddgs_cls() as ddgs:
                    hits = ddgs.text(query, max_results=per_query)
                for h in hits:
                    title = h.get("title", "")
                    body  = h.get("body", "")
                    if title or body:
                        snippets.append(f"{title}: {body}")
            except Exception:
                continue   # rate-limit or network error: skip and continue

        return snippets

    # --- brain evaluation -----------------------------------------------------

    def _brain_evaluate(
        self,
        snippets: list[str],
        market: str,
        geography: str,
        topic: str,
    ) -> list[ScoredSnippet]:
        """Ask the LLM to score each snippet for relevance, data quality, recency."""
        numbered = "\n".join(
            f"[{i}] {s[:400]}" for i, s in enumerate(snippets)
        )
        user_msg = (
            f"Market: {market}\nGeography: {geography}\nTopic: {topic}\n\n"
            f"Snippets to evaluate:\n{numbered}\n\n"
            f"Return JSON: {{\"scores\": ["
            f"{{\"index\": <int>, \"relevance\": <0-1>, "
            f"\"data_quality\": <0-1>, \"recency\": <0-1>}}]}}"
        )

        try:
            raw = self._llm.complete_json(_BRAIN_SYSTEM, user_msg)
        except LLMError:
            # Brain unavailable — pass all snippets through unscored
            return [ScoredSnippet(s, 0.5, 0.5, 0.5) for s in snippets]

        scored: list[ScoredSnippet] = []
        for entry in raw.get("scores", []):
            try:
                idx = int(entry["index"])
                if idx >= len(snippets):
                    continue
                scored.append(ScoredSnippet(
                    text=snippets[idx],
                    relevance=float(entry.get("relevance", 0.0)),
                    data_quality=float(entry.get("data_quality", 0.0)),
                    recency=float(entry.get("recency", 0.0)),
                ))
            except (KeyError, TypeError, ValueError):
                continue

        return scored

    @staticmethod
    def _import_ddgs():
        try:
            from ddgs import DDGS
            return DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
                return DDGS
            except ImportError:
                return None
