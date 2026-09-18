from __future__ import annotations

import importlib.util
import json
from types import SimpleNamespace
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "knowledge" / "benchmarks" / "rude_giesekus_4to1_pnas2023_fig4"

spec = importlib.util.spec_from_file_location(
    "sync_benchmarks_to_rag", ROOT / "scripts" / "sync_benchmarks_to_rag.py"
)
sync_benchmarks_to_rag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_benchmarks_to_rag)

import sys
sys.path.insert(0, str(ROOT / "src"))

from models import CaseTarget
from nodes.input_writer_node import _initial_write_mode
from services.benchmarks import find_certified_benchmark, import_certified_benchmark_case


def test_rude_benchmark_metadata_and_case_sets_are_registered():
    metadata = yaml.safe_load((BENCH / "metadata.yaml").read_text())

    assert metadata["id"] == "rude_giesekus_4to1_pnas2023_fig4"
    assert metadata["status"] == "certified_local_passed"
    assert metadata["target"] == {
        "channel": "v9-rheotool",
        "version": "v9",
        "solver": "rheoFoam",
        "distribution": "foundation+rheotool",
    }
    assert metadata["physics"]["model"] == "Giesekus"
    assert metadata["case_sets"]["official_case"]["path"] == "official_case"
    assert metadata["case_sets"]["runtime_case"]["path"] == "runtime_case"


READ_REQUIRED = [
    "0/U",
    "0/p",
    "0/tau",
    "constant/constitutiveProperties",
    "system/blockMeshDict",
    "system/controlDict",
    "system/fvSchemes",
    "system/fvSolution",
    "system/sampleDict",
    "Allrun",
]


def test_rude_benchmark_keeps_official_and_runtime_cases_separate():
    for rel in READ_REQUIRED:
        assert (BENCH / "official_case" / rel).is_file(), rel
        assert (BENCH / "runtime_case" / rel).is_file(), rel

    official_u = (BENCH / "official_case" / "0" / "U").read_text()
    runtime_u = (BENCH / "runtime_case" / "0" / "U").read_text()

    assert "codedFixedValue" in official_u
    assert "uniformFixedValue" in runtime_u
    assert "codedFixedValue" not in runtime_u


def test_sync_benchmarks_to_rag_writes_channel_jsonl(tmp_path):
    database = tmp_path / "database"
    result = sync_benchmarks_to_rag.sync_jsonl(ROOT / "knowledge" / "benchmarks", database)

    assert result["benchmarks"] >= 1
    assert result["records"] >= 20

    channel_jsonl = database / "v9-rheotool" / "raw" / "certified_benchmarks.jsonl"
    assert channel_jsonl.is_file()

    records = [json.loads(line) for line in channel_jsonl.read_text().splitlines() if line.strip()]
    assert any(r["metadata"]["benchmark_id"] == "rude_giesekus_4to1_pnas2023_fig4" for r in records)
    assert all(r["metadata"]["channel"] == "v9-rheotool" for r in records)
    assert all(r["metadata"]["version"] == "v9" for r in records)
    assert all(r["metadata"]["solver"] == "rheoFoam" for r in records)

    file_records = [r for r in records if r["metadata"].get("topic") == "openfoam_case_file"]
    assert any(r["metadata"]["case_set"] == "official_case" and r["metadata"]["file_path"] == "0/U" for r in file_records)
    assert any(r["metadata"]["case_set"] == "runtime_case" and r["metadata"]["file_path"] == "0/U" for r in file_records)


def test_find_certified_benchmark_requires_alias_and_case_target():
    requirement = (
        "复现 PNAS 2023 RUDE 论文 doi:10.1073/pnas.2304669120 "
        "图 4 的 Giesekus 4:1 contraction benchmark"
    )

    match = find_certified_benchmark(requirement, CaseTarget.for_solver("rheoFoam"))

    assert match is not None
    assert match["id"] == "rude_giesekus_4to1_pnas2023_fig4"
    assert match["case_set"] == "runtime_case"

    assert find_certified_benchmark(requirement, CaseTarget.for_solver("simpleFoam")) is None
    assert find_certified_benchmark("普通 Giesekus 收缩流，只给材料和几何", CaseTarget.for_solver("rheoFoam")) is None


def test_import_certified_benchmark_case_copies_runtime_case(tmp_path):
    match = find_certified_benchmark(
        "RUDE Giesekus 4:1 contraction 10.1073/pnas.2304669120",
        CaseTarget.for_solver("rheoFoam"),
    )
    assert match is not None

    out = import_certified_benchmark_case(str(tmp_path), match)

    assert (tmp_path / "0" / "U").is_file()
    assert (tmp_path / "system" / "fvSolution").is_file()
    assert (tmp_path / "Allrun").is_file()
    assert (tmp_path / "BENCHMARK_IMPORT.json").is_file()
    assert "uniformFixedValue" in (tmp_path / "0" / "U").read_text()
    assert out["benchmark_import"]["benchmark_id"] == "rude_giesekus_4to1_pnas2023_fig4"


def test_input_writer_initial_mode_imports_benchmark_without_llm_generation(tmp_path):
    match = find_certified_benchmark(
        "RUDE Giesekus 4:1 contraction 10.1073/pnas.2304669120",
        CaseTarget.for_solver("rheoFoam"),
    )
    assert match is not None

    state = {
        "input_writer_mode": "initial",
        "config": SimpleNamespace(openfoam_fork="foundation"),
        "case_dir": str(tmp_path),
        "benchmark_match": match,
        "subtasks": [{"folder_name": "system", "file_name": "fvSolution"}],
        "user_requirement": "RUDE Giesekus benchmark",
        "tutorial_reference": "",
        "case_target": CaseTarget.for_solver("rheoFoam"),
        "similar_case_advice": None,
        "mesh_type": "standard_mesh",
        "mesh_commands": [],
        "case_info": "",
        "allrun_reference": "",
    }

    out = _initial_write_mode(state)

    assert out["benchmark_import"]["benchmark_id"] == "rude_giesekus_4to1_pnas2023_fig4"
    assert (tmp_path / "0" / "U").is_file()
    assert "uniformFixedValue" in (tmp_path / "0" / "U").read_text()
    assert "system" in out["dir_structure"]



def test_rude_generic_alias_does_not_override_explicit_oldroydb_cavity():
    requirement = (
        "Reproduce Fattal & Kupferman 2005 lid-driven cavity benchmark; "
        "Oldroyd-B RUDE-class viscoelastic flow etaS=0.5 etaP=0.5 lambda=1 "
        "square cavity 127x127."
    )

    assert find_certified_benchmark(requirement, CaseTarget.for_solver("rheoFoam")) is None


def test_rude_alias_requires_doi_or_matching_physics_signature():
    assert find_certified_benchmark("RUDE benchmark", CaseTarget.for_solver("rheoFoam")) is None
    assert find_certified_benchmark(
        "RUDE Giesekus 4:1 contraction benchmark",
        CaseTarget.for_solver("rheoFoam"),
    ) is not None
