#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.case_evolution import evaluate_successful_case_for_evolution


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a successful Foam-Agent run for knowledge-base evolution."
    )
    parser.add_argument("case_dir", type=Path, help="Completed Foam-Agent case directory")
    parser.add_argument("--benchmark-root", type=Path, default=ROOT / "knowledge" / "benchmarks")
    parser.add_argument("--candidate-root", type=Path, default=ROOT / "knowledge" / "candidate_cases")
    parser.add_argument("--no-report", action="store_true", help="Do not write CASE_EVOLUTION_REPORT.json into the case directory")
    args = parser.parse_args()

    report = evaluate_successful_case_for_evolution(
        args.case_dir,
        benchmark_root=args.benchmark_root,
        candidate_root=args.candidate_root,
        write_report=not args.no_report,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
