#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path


INDEX_REQUIRED_FIELDS = {
    "openfoam_allrun_scripts": ("case_name", "case_domain", "case_category", "case_solver", "solver", "constitutive_family", "model", "phase_type", "geometry_family", "flow_regime", "objective"),
    "openfoam_tutorials_structure": ("case_name", "case_domain", "case_category", "case_solver", "solver", "constitutive_family", "model", "phase_type", "geometry_family", "flow_regime", "objective"),
    "openfoam_tutorials_details": ("case_name", "case_domain", "case_category", "case_solver", "solver", "constitutive_family", "model", "phase_type", "geometry_family", "flow_regime", "objective"),
    "openfoam_command_help": ("command",),
    "rheotool_manual_rules": ("source_type", "section", "topic"),
    "certified_benchmarks": ("source_type", "benchmark_id", "benchmark_status", "case_name", "case_domain", "case_category", "case_solver", "solver", "constitutive_family", "model", "phase_type", "geometry_family", "flow_regime", "objective", "section", "topic", "case_set", "file_path"),
}


def audit_documents(documents, channel: str, version: str, index_name: str) -> dict:
    required = ("channel", "version", "distribution") + INDEX_REQUIRED_FIELDS[index_name]
    missing = {field: 0 for field in required}
    mismatched = 0
    content_version_mismatches = 0
    for document in documents:
        metadata = document.metadata or {}
        for field in required:
            if metadata.get(field) in (None, ""):
                missing[field] += 1
        if metadata.get("channel") != channel or metadata.get("version") != version:
            mismatched += 1
        content = str(metadata.get("help_text") or metadata.get("full_content") or "")
        wrong_marker = "OpenFOAM-9" if version == "v10" else "OpenFOAM-10"
        if wrong_marker in content:
            content_version_mismatches += 1
    return {
        "documents": len(documents),
        "required_fields": list(required),
        "missing": missing,
        "channel_version_mismatches": mismatched,
        "content_version_mismatches": content_version_mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit channel-isolated FAISS metadata")
    parser.add_argument("--database", type=Path, default=Path("database"))
    parser.add_argument("--output", type=Path, default=Path("rag_inventory.json"))
    args = parser.parse_args()

    report = {"channels": {}, "ok": True}
    for channel, version in (("v9-rheotool", "v9"), ("v10-foundation", "v10")):
        channel_report = {}
        for path in sorted((args.database / channel / "faiss").glob("*/*/index.pkl")):
            index_name = path.parent.name
            if index_name not in INDEX_REQUIRED_FIELDS:
                continue
            # Repository-owned FAISS pickle; never use this on untrusted input.
            with path.open("rb") as stream:
                docstore, _ = pickle.load(stream)
            result = audit_documents(list(docstore._dict.values()), channel, version, index_name)
            channel_report[index_name] = result
            if (
                result["channel_version_mismatches"]
                or result["content_version_mismatches"]
                or any(result["missing"].values())
            ):
                report["ok"] = False
        report["channels"][channel] = channel_report

    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
