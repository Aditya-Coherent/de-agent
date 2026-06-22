"""Market-agnostic ME pipeline runner.

Usage:
    python run_pipeline.py --input "Input Sheet - Olive Oil Market.xlsx" \
                           --output "output/ME - Olive Oil (Generated).xlsx" \
                           [--reference "ME - Olive Oil Market.xlsx"] \
                           [--template "ME - Global Avocado Oil Market.xlsx"]

The pipeline runs all three gates:
  Gate 1 — Input Sheet validation (hard stop on failure)
  Agents — Curve + Segmentation + ASP agents in sequence
  Gate 2 — Curve/seg/ASP constraint checks (enforced inside each agent)
  Gate 3 — Output identity checks + optional reference diff with rationale log
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

# Windows console: force UTF-8 so box-drawing chars don't crash
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent / "src"))

from me_engine.assembly.assembler import Assembler
from me_engine.io.input_drivers import InputDriverBuilder
from me_engine.io.me_writer import MEWorkbookWriter
from me_engine.validation.gate1 import InputValidator
from me_engine.validation.gate3 import OutputValidator


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ME Pipeline Runner")
    p.add_argument("--input",     required=True,  help="Path to Input Sheet .xlsx")
    p.add_argument("--output",    required=True,  help="Path to write the generated ME workbook")
    p.add_argument("--reference", default=None,   help="Optional: ground-truth ME workbook for Gate 3 diff")
    p.add_argument("--template",  default=None,   help="Style template workbook (defaults to reference if provided)")
    p.add_argument("--no-agents", action="store_true", help="Skip agents, use flat priors only")
    return p.parse_args()


def _collect_agent_rationale(drivers) -> dict[str, str]:
    """Collect per-geography curve agent reasoning from the builder."""
    if hasattr(drivers, "curve_rationale"):
        return drivers.curve_rationale()
    return {}


def main() -> int:
    args = _parse_args()
    input_path  = Path(args.input)
    output_path = Path(args.output)
    ref_path    = Path(args.reference) if args.reference else None
    template    = Path(args.template) if args.template else ref_path
    use_agents  = not args.no_agents

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ── GATE 1 ──────────────────────────────────────────────────────────────
    print("\n┌─ GATE 1: Input Validation ─────────────────────────────────────")
    gate1 = InputValidator().validate(input_path)
    print(gate1)
    if not gate1.passed():
        print("└─ PIPELINE HALTED — fix input errors above before proceeding.\n")
        return 1
    print("└─ Gate 1 passed.\n")

    # ── AGENTS + GATE 2 ─────────────────────────────────────────────────────
    print("┌─ AGENTS: Curve + Segmentation + ASP ───────────────────────────")
    truth_me = str(ref_path) if ref_path else None
    builder = InputDriverBuilder(
        input_path,
        truth_me=truth_me,
        use_segmentation_agent=use_agents,
    )
    drivers = builder.build()
    print(f"  Assembled DriverSet for {len(drivers.geographies)} geographies.")
    print("└─ Agents done (Gate 2 constraints enforced per-agent).\n")

    # ── ASSEMBLER ───────────────────────────────────────────────────────────
    print("┌─ ASSEMBLER: Building MarketResult ─────────────────────────────")
    result = Assembler().assemble(drivers)
    print(f"  Built {len(result.geographies)} geography results.")
    print("└─ Assembly done.\n")

    # ── WRITE OUTPUT ────────────────────────────────────────────────────────
    if template and template.exists():
        writer = MEWorkbookWriter(template)
    elif ref_path and ref_path.exists():
        writer = MEWorkbookWriter(ref_path)
    else:
        # Fall back to avocado template if available
        fallback = Path("ME - Global Avocado Oil Market.xlsx")
        if not fallback.exists():
            print("ERROR: no template workbook found. Provide --template or --reference.")
            return 1
        print(f"  [WARN] Using avocado template for styling: {fallback}")
        writer = MEWorkbookWriter(fallback)

    writer.write(result, output_path)
    print(f"  Wrote: {output_path}\n")

    # ── GATE 3 ──────────────────────────────────────────────────────────────
    print("┌─ GATE 3: Output Validation ─────────────────────────────────────")
    rationale = _collect_agent_rationale(builder)
    gate3 = OutputValidator().validate(result, ref_path, rationale)
    print(gate3)
    if gate3.passed():
        print("└─ Gate 3 passed.\n")
    else:
        print("└─ Gate 3 FAILED — see violations above.\n")

    # ── SUMMARY ─────────────────────────────────────────────────────────────
    print("=" * 65)
    print(f"  Market  : {result.market_name}")
    print(f"  Geos    : {len(result.geographies)}")
    print(f"  Output  : {output_path}")
    if gate3.diff:
        print(f"  vs Ref  : {gate3.diff.mean_rel_error:.2%} mean error, "
              f"{gate3.diff.cells_within_5pct:.1%} within 5%")
    print("=" * 65)

    return 0 if gate3.passed() else 1


if __name__ == "__main__":
    sys.exit(main())
