from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from models import CaseTarget
from utils import FoamPydantic, FoamfilePydantic, read_case_foamfiles, scan_case_directory


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = ROOT / "knowledge" / "benchmarks"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return data


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _target_matches(metadata: dict[str, Any], target: CaseTarget) -> bool:
    expected = metadata.get("target") or {}
    return (
        expected.get("channel") == target.channel
        and expected.get("version") == target.version
        and expected.get("solver") == target.solver
    )


def _benchmark_aliases(metadata: dict[str, Any], entry: dict[str, Any]) -> list[str]:
    source = metadata.get("source") or {}
    aliases = list(metadata.get("aliases") or [])
    registry_aliases = entry.get("aliases") or []
    if isinstance(registry_aliases, list):
        aliases.extend(str(alias) for alias in registry_aliases)
    for key in (metadata.get("id"), source.get("doi"), source.get("repo"), source.get("case_path")):
        if key:
            aliases.append(str(key))
    return aliases


def _explicit_model_conflicts(requirement: str, benchmark_model: str) -> bool:
    model = _normalize(benchmark_model)
    mentioned = {
        "oldroyd-b": ("oldroyd", "oldroyd-b"),
        "giesekus": ("giesekus",),
        "ptt": ("ptt",),
        "fene-cr": ("fene-cr", "fene cr"),
    }
    for canonical, aliases in mentioned.items():
        if canonical == model:
            continue
        if any(alias in requirement for alias in aliases):
            return True
    return False


def _explicit_geometry_conflicts(requirement: str, geometry_family: str) -> bool:
    geometry = _normalize(geometry_family)
    user_mentions_cavity = any(term in requirement for term in ("cavity", "lid-driven", "lid driven", "方腔", "空腔", "顶盖驱动", "盖驱动"))
    user_mentions_contraction = any(term in requirement for term in ("contraction", "4:1", "4：1", "收缩"))
    benchmark_is_contraction = "contraction" in geometry or "收缩" in geometry
    benchmark_is_cavity = "cavity" in geometry or "方腔" in geometry or "空腔" in geometry
    return (benchmark_is_contraction and user_mentions_cavity) or (benchmark_is_cavity and user_mentions_contraction)


def _physics_signature_conflicts(requirement: str, metadata: dict[str, Any]) -> bool:
    physics = metadata.get("physics") or {}
    model = str(physics.get("model") or "")
    geometry = str(physics.get("geometry_family") or physics.get("case_category") or "")
    return (model and _explicit_model_conflicts(requirement, model)) or _explicit_geometry_conflicts(requirement, geometry)


def _has_benchmark_supporting_signature(requirement: str, metadata: dict[str, Any]) -> bool:
    source = metadata.get("source") or {}
    doi = _normalize(str(source.get("doi") or ""))
    if doi and doi in requirement:
        return True

    physics = metadata.get("physics") or {}
    model = _normalize(str(physics.get("model") or ""))
    geometry = _normalize(str(physics.get("geometry_family") or physics.get("case_category") or ""))
    has_model = bool(model) and model in requirement
    if "contraction" in geometry:
        has_geometry = any(term in requirement for term in ("contraction", "4:1", "4：1", "收缩"))
    elif "cavity" in geometry:
        has_geometry = any(term in requirement for term in ("cavity", "方腔", "空腔", "顶盖驱动", "盖驱动"))
    else:
        has_geometry = bool(geometry) and geometry in requirement
    return has_model and has_geometry


def _generic_benchmark_alias(alias: str) -> bool:
    normalized = _normalize(alias)
    return normalized in {"rude", "pnas 2023 rude"}


def _alias_allowed_for_benchmark(requirement: str, alias: str, metadata: dict[str, Any]) -> bool:
    if _physics_signature_conflicts(requirement, metadata):
        return False
    if _generic_benchmark_alias(alias):
        return _has_benchmark_supporting_signature(requirement, metadata)
    return True


def find_certified_benchmark_alias_match(
    user_requirement: str,
    root: Path = BENCHMARK_ROOT,
) -> dict[str, Any] | None:
    requirement = _normalize(user_requirement)
    for entry in load_benchmark_registry(root):
        metadata = entry["metadata"]
        if metadata.get("status") != "certified_local_passed":
            continue
        for alias in _benchmark_aliases(metadata, entry):
            normalized_alias = _normalize(str(alias))
            if not normalized_alias or normalized_alias not in requirement:
                continue
            if not _alias_allowed_for_benchmark(requirement, str(alias), metadata):
                continue
            return {
                "entry": entry,
                "metadata": metadata,
                "matched_alias": str(alias),
            }
    return None


def load_benchmark_registry(root: Path = BENCHMARK_ROOT) -> list[dict[str, Any]]:
    registry_path = root / "benchmark_registry.yaml"
    if registry_path.exists():
        registry = _load_yaml(registry_path)
        entries = registry.get("benchmarks") or []
        if not isinstance(entries, list):
            raise ValueError(f"Invalid benchmark registry: {registry_path}")
    else:
        entries = [
            {"id": path.parent.name, "path": path.parent.name}
            for path in sorted(root.glob("*/metadata.yaml"))
        ]

    loaded = []
    for entry in entries:
        rel_path = entry.get("path") or entry.get("id")
        bench_dir = root / str(rel_path)
        metadata_path = bench_dir / "metadata.yaml"
        if not metadata_path.exists():
            continue
        metadata = _load_yaml(metadata_path)
        loaded.append({"path": str(rel_path), "directory": str(bench_dir), "metadata": metadata})
    return loaded


def find_certified_benchmark(
    user_requirement: str,
    target: CaseTarget,
    root: Path = BENCHMARK_ROOT,
) -> dict[str, Any] | None:
    """Return a certified benchmark match when aliases/DOI and CaseTarget match.

    This is intentionally deterministic. It prevents a generic rheoFoam RAG hit
    from being treated as an exact paper benchmark.
    """

    alias_match = find_certified_benchmark_alias_match(user_requirement, root=root)
    if not alias_match:
        return None

    entry = alias_match["entry"]
    metadata = alias_match["metadata"]
    if not _target_matches(metadata, target):
        return None

    return {
        "id": metadata["id"],
        "path": entry["path"],
        "directory": entry["directory"],
        "case_set": "runtime_case",
        "matched_alias": alias_match["matched_alias"],
        "source": metadata.get("source") or {},
        "target": metadata.get("target") or {},
        "physics": metadata.get("physics") or {},
        "status": metadata.get("status"),
    }


def benchmark_subtasks(benchmark_match: dict[str, Any], case_set: str | None = None) -> list[dict[str, str]]:
    selected_case_set = case_set or benchmark_match.get("case_set") or "runtime_case"
    case_root = Path(benchmark_match["directory"]) / selected_case_set
    if not case_root.is_dir():
        raise FileNotFoundError(f"Benchmark case set not found: {case_root}")

    subtasks: list[dict[str, str]] = []
    for path in sorted(case_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(case_root)
        if len(rel.parts) == 1:
            folder_name = ""
            file_name = rel.parts[0]
        else:
            folder_name = str(Path(*rel.parts[:-1]))
            file_name = rel.parts[-1]
        subtasks.append({"folder_name": folder_name, "file_name": file_name})
    return subtasks


def _copy_case_tree(source_dir: Path, destination_dir: Path) -> None:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Benchmark case set not found: {source_dir}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    for item in source_dir.iterdir():
        destination = destination_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def import_certified_benchmark_case(
    case_dir: str,
    benchmark_match: dict[str, Any],
    case_set: str | None = None,
) -> dict[str, Any]:
    selected_case_set = case_set or benchmark_match.get("case_set") or "runtime_case"
    benchmark_dir = Path(benchmark_match["directory"])
    source_dir = benchmark_dir / selected_case_set
    destination_dir = Path(case_dir)

    _copy_case_tree(source_dir, destination_dir)

    note = {
        "benchmark_id": benchmark_match["id"],
        "benchmark_path": benchmark_match.get("path"),
        "case_set": selected_case_set,
        "source_directory": str(source_dir),
        "matched_alias": benchmark_match.get("matched_alias"),
        "source": benchmark_match.get("source") or {},
        "target": benchmark_match.get("target") or {},
        "import_policy": "certified benchmark import; no LLM dictionary regeneration",
    }
    (destination_dir / "BENCHMARK_IMPORT.json").write_text(
        json.dumps(note, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    dir_structure = scan_case_directory(str(destination_dir))
    foamfiles = read_case_foamfiles(str(destination_dir), dir_structure)
    return {
        "dir_structure": dir_structure,
        "foamfiles": foamfiles,
        "benchmark_import": note,
    }
