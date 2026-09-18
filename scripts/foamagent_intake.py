#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.intake import evaluate_requirement, issue_receipt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Foam-Agent user_requirement.txt before running main.py")
    parser.add_argument("requirement_path", type=Path)
    parser.add_argument("--write-receipt", action="store_true")
    parser.add_argument("--receipt-path", type=Path, default=None)
    args = parser.parse_args()

    text = args.requirement_path.read_text(encoding="utf-8")
    result = evaluate_requirement(text)
    if args.write_receipt and result["status"] == "ready":
        result["receipt"] = issue_receipt(args.requirement_path, args.receipt_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
