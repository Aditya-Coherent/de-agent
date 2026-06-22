"""Command-line entrypoints for the ME engine.

`verify` proves the assembler reproduces a reference ME workbook from drivers
extracted out of that same workbook (Stage-1 definition of done).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .assembly.assembler import Assembler
from .io.me_reader import MEWorkbookReader
from .io.me_writer import MEWorkbookWriter
from .verify.diff import DiffEngine


def verify(reference: Path, market_name: str, tol: float) -> int:
    drivers = MEWorkbookReader(reference).read(market_name)
    result = Assembler().assemble(drivers)
    report = DiffEngine(reference, tol=tol).compare(result)

    print(f"Compared cells       : {report.compared:,}")
    print(f"Deviations > {tol:g}   : {len(report.deviations):,}")
    print(f"Max absolute error   : {report.max_abs:.3e}")
    print(f"Max relative error   : {report.max_rel:.3e}")

    if report.passed(tol):
        print("RESULT: PASS — assembler reproduces the workbook within tolerance.")
        return 0

    print("RESULT: FAIL — worst deviations:")
    for d in report.worst():
        print(f"  {d.sheet:18s} {d.band.name:6s} {d.label:30s} {d.year}"
              f"  expected={d.expected:.6f} actual={d.actual:.6f}"
              f"  |Δ|={d.abs_error:.3e}")
    return 1


def generate(reference: Path, out: Path, market_name: str, tol: float) -> int:
    """Read drivers, assemble, write a new ME workbook, then round-trip diff it."""
    drivers = MEWorkbookReader(reference).read(market_name)
    result = Assembler().assemble(drivers)
    written = MEWorkbookWriter(reference).write(result, out)
    print(f"Wrote ME workbook    : {written}")

    report = DiffEngine(written, tol=tol).compare(result)
    print(f"Round-trip cells     : {report.compared:,}")
    print(f"Round-trip max error : {report.max_abs:.3e}")
    if report.passed(tol):
        print("RESULT: PASS — written workbook matches assembled result.")
        return 0
    print("RESULT: FAIL — written workbook diverged from result.")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="me-engine")
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("verify", help="reproduce & diff a reference ME workbook")
    v.add_argument("reference", type=Path)
    v.add_argument("--market", default="Avocado Oil Market")
    v.add_argument("--tol", type=float, default=1e-6)

    g = sub.add_parser("generate", help="assemble and write an ME workbook")
    g.add_argument("reference", type=Path)
    g.add_argument("--out", type=Path, default=Path("output/ME - Generated.xlsx"))
    g.add_argument("--market", default="Avocado Oil Market")
    g.add_argument("--tol", type=float, default=1e-6)

    c = sub.add_parser("curve", help="run the curve agent over an Input Sheet")
    c.add_argument("input_sheet", type=Path)
    c.add_argument("--truth", type=Path, default=None,
                   help="optional ME workbook to score against")
    c.add_argument("--report", type=Path, default=Path("output/curve-reasoning.md"))

    args = parser.parse_args(argv)
    if args.command == "verify":
        return verify(args.reference, args.market, args.tol)
    if args.command == "generate":
        return generate(args.reference, args.out, args.market, args.tol)
    if args.command == "curve":
        return run_curve(args.input_sheet, args.truth, args.report)
    return 2


def run_curve(input_sheet: Path, truth: Path | None, report: Path) -> int:
    from .curve.runner import CurveRunner, truth_paths_from_me

    truth_paths = truth_paths_from_me(truth) if truth else None
    outcomes = CurveRunner().run(input_sheet, truth_paths)

    lines = [f"# Curve Agent Reasoning Report\n",
             f"Geographies: {len(outcomes)}\n"]
    scored = [o for o in outcomes if o.score]
    for o in outcomes:
        lines.append(o.reasoning_line())
    if scored:
        mae = sum(o.score.shape_mae for o in scored) / len(scored)
        cos = sum(o.score.cosine for o in scored) / len(scored)
        rel = sum(o.score.path_max_rel_error for o in scored) / len(scored)
        print(f"Scored {len(scored)} geographies vs ground truth:")
        print(f"  mean shape MAE      : {mae:.4f}")
        print(f"  mean cosine         : {cos:.4f}")
        print(f"  mean path max-rel   : {rel:.2%}")
        lines.append(f"\n## Aggregate vs ground truth\n"
                     f"- mean shape MAE: {mae:.4f}\n- mean cosine: {cos:.4f}\n"
                     f"- mean path max-rel error: {rel:.2%}\n")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote reasoning report: {report}")
    fallbacks = sum(1 for o in outcomes if o.decision.used_fallback)
    print(f"Agent decisions: {len(outcomes) - fallbacks} live, {fallbacks} fallback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
