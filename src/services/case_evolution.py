from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = ROOT / "knowledge" / "benchmarks"
CANDIDATE_ROOT = ROOT / "knowledge" / "candidate_cases"

CASE_COPY_DIRS = ("0", "constant", "system")
CASE_COPY_FILES = ("Allrun", "manifest.json", "BENCHMARK_IMPORT.json", "TUTORIAL_TEMPLATE_IMPORT.json")


def _slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", text.strip()).strip("-._")
    return slug.lower() or "case"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _as_text(value: Any, default: str = "unknown") -> str:
    if value in (None, ""):
        return default
    return str(value)


def _lower(value: Any) -> str:
    return _as_text(value).casefold()


def _extract_geometry_from_text(text: str) -> str:
    lowered = text.casefold()
    if "4:1" in lowered and ("contraction" in lowered or "收缩" in lowered):
        return "4:1 planar contraction"
    if "contraction" in lowered or "收缩" in lowered:
        return "contraction"
    if "pipe" in lowered or "tube" in lowered or "管" in lowered:
        return "pipe"
    if "cavity" in lowered or "腔" in lowered:
        return "cavity"
    return "unspecified"


def extract_case_signature(case_dir: str | Path) -> dict[str, Any]:
    case_path = Path(case_dir)
    manifest = _read_json(case_path / "manifest.json")
    problem_intent = manifest.get("problem_intent") or {}
    physics_spec = manifest.get("physics_spec") or {}
    rheology_spec = manifest.get("rheology_spec") or {}
    workflow_plan = manifest.get("workflow_plan") or {}
    application = _as_text(problem_intent.get("application"), "")

    selected_model = rheology_spec.get("selected_model") or "Newtonian"
    behavior = rheology_spec.get("behavior") or "newtonian"
    phase_type = physics_spec.get("phase_type") or "unknown"
    flow_regime = "transient" if physics_spec.get("transient") else "steady"
    objective = "benchmark-reproduction" if any(
        token in application.casefold() for token in ("benchmark", "复现", "doi", "figure", "图")
    ) else "flow-field"

    target = workflow_plan.get("target") or {}
    signature = {
        "channel": manifest.get("channel") or target.get("channel") or "unknown",
        "version": manifest.get("version") or target.get("version") or "unknown",
        "solver": manifest.get("solver") or target.get("solver") or "unknown",
        "distribution": manifest.get("distribution") or target.get("distribution") or "unknown",
        "phase_type": phase_type,
        "constitutive_family": behavior,
        "model": selected_model,
        "geometry_family": _extract_geometry_from_text(application),
        "flow_regime": flow_regime,
        "objective": objective,
        "workflow_type": workflow_plan.get("workflow_type") or "unknown",
        "source_doi": "",
        "source_repo": "",
    }

    doi_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", application)
    if doi_match:
        signature["source_doi"] = doi_match.group(0).rstrip(".,;)")
    repo_match = re.search(r"github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", application)
    if repo_match:
        signature["source_repo"] = "https://" + repo_match.group(0)
    return signature


def _benchmark_signature(metadata: dict[str, Any]) -> dict[str, Any]:
    target = metadata.get("target") or {}
    physics = metadata.get("physics") or {}
    source = metadata.get("source") or {}
    return {
        "channel": target.get("channel", "unknown"),
        "version": target.get("version", "unknown"),
        "solver": target.get("solver", "unknown"),
        "distribution": target.get("distribution", "unknown"),
        "phase_type": physics.get("phase_type", "unknown"),
        "constitutive_family": physics.get("constitutive_family", "unknown"),
        "model": physics.get("model", "unknown"),
        "geometry_family": physics.get("geometry_family", "unknown"),
        "flow_regime": physics.get("flow_regime", "unknown"),
        "objective": physics.get("objective", "unknown"),
        "source_doi": source.get("doi") or "",
        "source_repo": source.get("repo") or "",
    }


def load_benchmark_signatures(root: str | Path = BENCHMARK_ROOT) -> list[dict[str, Any]]:
    root_path = Path(root)
    items = []
    for metadata_path in sorted(root_path.glob("*/metadata.yaml")):
        metadata = _read_yaml(metadata_path)
        if not metadata:
            continue
        items.append({
            "id": metadata.get("id") or metadata_path.parent.name,
            "status": metadata.get("status", "unknown"),
            "path": str(metadata_path.parent),
            "signature": _benchmark_signature(metadata),
        })
    return items


def _matches_existing(signature: dict[str, Any], benchmark: dict[str, Any]) -> bool:
    other = benchmark["signature"]
    hard_keys = ("channel", "version", "solver", "phase_type", "model", "geometry_family")
    if any(_lower(signature.get(key)) != _lower(other.get(key)) for key in hard_keys):
        return False

    # Same DOI/repo is a definitive duplicate when present.
    if signature.get("source_doi") and signature.get("source_doi") == other.get("source_doi"):
        return True
    if signature.get("source_repo") and signature.get("source_repo") == other.get("source_repo"):
        return True

    soft_keys = ("constitutive_family", "flow_regime", "objective")
    return all(_lower(signature.get(key)) == _lower(other.get(key)) for key in soft_keys)


def coverage_check(
    signature: dict[str, Any],
    benchmark_root: str | Path = BENCHMARK_ROOT,
) -> dict[str, Any]:
    for benchmark in load_benchmark_signatures(benchmark_root):
        if benchmark.get("status") != "certified_local_passed":
            continue
        if _matches_existing(signature, benchmark):
            return {
                "decision": "duplicate",
                "reason": "Existing certified benchmark covers the same solver/model/geometry/objective signature.",
                "nearest_match": benchmark["id"],
                "nearest_match_path": benchmark["path"],
            }
    return {
        "decision": "novel_candidate",
        "reason": "No certified benchmark covers this solver/model/geometry signature.",
        "nearest_match": None,
        "nearest_match_path": None,
    }


def _coverage_from_benchmark_import(
    case_path: Path,
    benchmark_root: str | Path = BENCHMARK_ROOT,
) -> dict[str, Any] | None:
    benchmark_import = _read_json(case_path / "BENCHMARK_IMPORT.json")
    benchmark_id = benchmark_import.get("benchmark_id")
    if not benchmark_id:
        return None

    for benchmark in load_benchmark_signatures(benchmark_root):
        if benchmark.get("id") == benchmark_id and benchmark.get("status") == "certified_local_passed":
            return {
                "decision": "duplicate",
                "reason": "Case was imported from an existing certified benchmark; do not recapture as a candidate.",
                "nearest_match": benchmark["id"],
                "nearest_match_path": benchmark["path"],
                "imported_benchmark": benchmark_import,
            }
    return None


def _coverage_from_tutorial_template_import(case_path: Path) -> dict[str, Any] | None:
    template_import = _read_json(case_path / "TUTORIAL_TEMPLATE_IMPORT.json")
    template_id = template_import.get("template_id")
    if not template_id:
        return None
    return {
        "decision": "template_import",
        "reason": "Case was imported from a known external tutorial template; do not recapture as a novel candidate during normal user runs.",
        "nearest_match": template_id,
        "nearest_match_path": template_import.get("source_directory"),
        "imported_template": template_import,
    }


def validate_successful_case(case_dir: str | Path) -> dict[str, Any]:
    case_path = Path(case_dir)
    manifest = _read_json(case_path / "manifest.json")
    issues = []
    warnings = []
    if not manifest:
        issues.append("manifest.json missing")
    if manifest and manifest.get("validation_status") != "passed":
        issues.append("manifest validation_status is not passed")
    if manifest and manifest.get("run_status") != "passed":
        if _has_completed_solver_log(case_path):
            warnings.append("manifest run_status is not passed, but completed solver log was found")
        else:
            issues.append("manifest run_status is not passed")
    for required in ("0", "constant", "system"):
        if not (case_path / required).is_dir():
            issues.append(f"required case directory missing: {required}")
    if not (case_path / "Allrun").is_file():
        issues.append("Allrun missing")
    return {"ok": not issues, "issues": issues, "warnings": warnings}


def _has_completed_solver_log(case_path: Path) -> bool:
    for log_path in case_path.glob("log.*"):
        name = log_path.name.lower()
        if any(skip in name for skip in ("blockmesh", "checkmesh", "postprocess")):
            continue
        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if re.search(r"^\s*End\s*$", content, re.MULTILINE) and "FOAM FATAL" not in content:
            return True
    return False


def _copy_case_for_candidate(source: Path, destination: Path) -> None:
    case_dest = destination / "case"
    case_dest.mkdir(parents=True, exist_ok=True)
    for dirname in CASE_COPY_DIRS:
        src = source / dirname
        if src.is_dir():
            shutil.copytree(src, case_dest / dirname, dirs_exist_ok=True)
    for filename in CASE_COPY_FILES:
        src = source / filename
        if src.is_file():
            shutil.copy2(src, case_dest / filename)


def capture_candidate_case(
    case_dir: str | Path,
    signature: dict[str, Any],
    validation: dict[str, Any],
    candidate_root: str | Path = CANDIDATE_ROOT,
) -> dict[str, Any]:
    source = Path(case_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    case_id = f"{_slug(source.name)}-{stamp}"
    destination = Path(candidate_root) / case_id
    destination.mkdir(parents=True, exist_ok=False)
    _copy_case_for_candidate(source, destination)

    metadata = {
        "id": case_id,
        "status": "validated_candidate" if validation.get("ok") else "candidate_needs_review",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_case_dir": str(source),
        "signature": signature,
        "validation": validation,
        "promotion_policy": "manual approval required before moving to knowledge/benchmarks",
    }
    (destination / "metadata.yaml").write_text(
        yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (destination / "validation_report.json").write_text(
        json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (destination / "provenance.json").write_text(
        json.dumps({"source_case_dir": str(source), "captured_at": metadata["created_at"]}, indent=2),
        encoding="utf-8",
    )
    return {"candidate_id": case_id, "candidate_path": str(destination), "status": metadata["status"]}


def evaluate_successful_case_for_evolution(
    case_dir: str | Path,
    *,
    benchmark_root: str | Path = BENCHMARK_ROOT,
    candidate_root: str | Path = CANDIDATE_ROOT,
    write_report: bool = True,
) -> dict[str, Any]:
    case_path = Path(case_dir)
    signature = extract_case_signature(case_path)
    validation = validate_successful_case(case_path)
    coverage = (
        _coverage_from_benchmark_import(case_path, benchmark_root)
        or _coverage_from_tutorial_template_import(case_path)
        or coverage_check(signature, benchmark_root)
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "case_dir": str(case_path),
        "signature": signature,
        "validation": validation,
        "coverage_status": coverage,
        "candidate": None,
    }

    if validation.get("ok") and coverage.get("decision") == "novel_candidate":
        report["candidate"] = capture_candidate_case(case_path, signature, validation, candidate_root)

    if write_report:
        (case_path / "CASE_EVOLUTION_REPORT.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return report
