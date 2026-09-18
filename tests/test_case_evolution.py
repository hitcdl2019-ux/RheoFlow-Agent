from __future__ import annotations

import json
from pathlib import Path

import yaml

from services.case_evolution import (
    coverage_check,
    evaluate_successful_case_for_evolution,
    extract_case_signature,
)


def _write_minimal_success_case(case_dir: Path, *, model: str, application: str) -> None:
    (case_dir / "0").mkdir(parents=True)
    (case_dir / "constant").mkdir()
    (case_dir / "system").mkdir()
    (case_dir / "0" / "U").write_text("FoamFile{}\n", encoding="utf-8")
    (case_dir / "constant" / "constitutiveProperties").write_text("FoamFile{}\n", encoding="utf-8")
    (case_dir / "system" / "controlDict").write_text("application rheoFoam;\n", encoding="utf-8")
    (case_dir / "Allrun").write_text("#!/bin/sh\n", encoding="utf-8")
    manifest = {
        "schema_version": 2,
        "channel": "v9-rheotool",
        "version": "v9",
        "solver": "rheoFoam",
        "distribution": "foundation+rheotool",
        "validation_status": "passed",
        "run_status": "passed",
        "problem_intent": {"application": application},
        "physics_spec": {"phase_type": "single-phase", "transient": True},
        "rheology_spec": {"behavior": "viscoelastic", "selected_model": model},
        "workflow_plan": {"workflow_type": "rheological-single-phase"},
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_duplicate_success_case_writes_report_without_candidate(tmp_path):
    case_dir = tmp_path / "rude-like"
    _write_minimal_success_case(
        case_dir,
        model="Giesekus",
        application="复现 doi:10.1073/pnas.2304669120 RUDE Giesekus 4:1 contraction benchmark",
    )

    report = evaluate_successful_case_for_evolution(case_dir, candidate_root=tmp_path / "candidates")

    assert report["coverage_status"]["decision"] == "duplicate"
    assert report["coverage_status"]["nearest_match"] == "rude_giesekus_4to1_pnas2023_fig4"
    assert report["candidate"] is None
    assert (case_dir / "CASE_EVOLUTION_REPORT.json").is_file()
    assert not (tmp_path / "candidates").exists()


def test_imported_certified_benchmark_is_not_recaptured_even_with_generic_text(tmp_path):
    case_dir = tmp_path / "rude-imported"
    _write_minimal_success_case(
        case_dir,
        model="Giesekus",
        application="复现 DOI 10.1073/pnas.2304669120 的 RUDE 收缩流结果",
    )
    (case_dir / "BENCHMARK_IMPORT.json").write_text(json.dumps({
        "benchmark_id": "rude_giesekus_4to1_pnas2023_fig4",
        "benchmark_path": "rude_giesekus_4to1_pnas2023_fig4",
        "case_set": "runtime_case",
        "import_policy": "certified benchmark import; no LLM dictionary regeneration",
    }), encoding="utf-8")

    report = evaluate_successful_case_for_evolution(case_dir, candidate_root=tmp_path / "candidates")

    assert report["coverage_status"]["decision"] == "duplicate"
    assert report["coverage_status"]["nearest_match"] == "rude_giesekus_4to1_pnas2023_fig4"
    assert report["coverage_status"]["imported_benchmark"]["case_set"] == "runtime_case"
    assert report["candidate"] is None
    assert not (tmp_path / "candidates").exists()


def test_imported_tutorial_template_is_not_recaptured_as_novel_candidate(tmp_path):
    case_dir = tmp_path / "rheotool-channel-template"
    _write_minimal_success_case(
        case_dir,
        model="Oldroyd-B",
        application="RheoTool tutorial 5.1.3 Oldroyd-BLog parallel plate channel benchmark",
    )
    (case_dir / "TUTORIAL_TEMPLATE_IMPORT.json").write_text(json.dumps({
        "template_id": "rheotool_5_1_3_channel_oldroydb_log",
        "source_directory": "/opt/build/rheoTool/of90/tutorials/rheoFoam/Channel/Oldroyd-BLog",
        "matched_alias": "RheoTool user guide 6.0 section 5.1.3 Channel/Oldroyd-BLog",
        "import_policy": "rheotool tutorial template import; no LLM dictionary regeneration",
    }), encoding="utf-8")

    report = evaluate_successful_case_for_evolution(case_dir, candidate_root=tmp_path / "candidates")

    assert report["coverage_status"]["decision"] == "template_import"
    assert report["coverage_status"]["nearest_match"] == "rheotool_5_1_3_channel_oldroydb_log"
    assert report["coverage_status"]["imported_template"]["matched_alias"].startswith("RheoTool user guide")
    assert report["candidate"] is None
    assert not (tmp_path / "candidates").exists()


def test_novel_success_case_is_captured_as_candidate(tmp_path):
    case_dir = tmp_path / "novel-ptt-contraction"
    candidate_root = tmp_path / "candidates"
    _write_minimal_success_case(
        case_dir,
        model="PTT",
        application="PTT viscoelastic fluid through 4:1 contraction, no existing DOI benchmark",
    )

    signature = extract_case_signature(case_dir)
    coverage = coverage_check(signature)
    assert coverage["decision"] == "novel_candidate"

    report = evaluate_successful_case_for_evolution(case_dir, candidate_root=candidate_root)

    assert report["coverage_status"]["decision"] == "novel_candidate"
    assert report["candidate"] is not None
    candidate_path = Path(report["candidate"]["candidate_path"])
    assert candidate_path.is_dir()
    assert (candidate_path / "case" / "system" / "controlDict").is_file()
    metadata = yaml.safe_load((candidate_path / "metadata.yaml").read_text())
    assert metadata["status"] == "validated_candidate"
    assert metadata["signature"]["model"] == "PTT"
