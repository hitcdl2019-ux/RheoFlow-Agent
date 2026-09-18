import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.intake import evaluate_requirement  # noqa: E402


def _load_cases():
    path = ROOT / "tests" / "business_prompts" / "real_business_prompts.yaml"
    # YAML-compatible JSON: keeps this test independent of PyYAML.
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_business_prompt_intake_statuses_are_met():
    cases = _load_cases()
    assert len(cases) >= 40
    solver_named = (
        "rheofoam", "rheotestfoam", "rheointerfoam",
        "simplefoam", "pimplefoam", "interfoam", "icofoam",
    )
    assert sum(not any(name in case["prompt"].lower() for name in solver_named) for case in cases) >= 35

    for case in cases:
        result = evaluate_requirement(case["prompt"])
        assert result["status"] == case["expected_status"], case["id"]

        if case["expected_status"] == "ready":
            target = result["target_preview"]
            assert target is not None, case["id"]
            assert target["channel"] == case["expected_channel"], case["id"]
            assert target["version"] == case["expected_version"], case["id"]
            assert target["solver"] == case["expected_solver"], case["id"]

        for field in case.get("expected_blocking_fields", []):
            assert any(item["field"] == field for item in result["blocking_missing"]), case["id"]

        if "expected_missing_parameters" in case:
            missing = []
            for item in result["blocking_missing"]:
                missing.extend(item.get("missing", []))
            assert tuple(case["expected_missing_parameters"]) == tuple(missing), case["id"]

        if "expected_question_contains" in case:
            questions = "\n".join(result["clarification_questions"])
            assert case["expected_question_contains"] in questions, case["id"]

        if "expected_rejection_contains" in case:
            assert case["expected_rejection_contains"].lower() in result["rejection_reason"].lower(), case["id"]

        if "expected_infer_field" in case:
            assert any(
                item["field"] == case["expected_infer_field"]
                for item in result["infer_with_disclosure"]
            ), case["id"]


def test_rude_doi_short_prompt_uses_certified_benchmark_without_clarify():
    result = evaluate_requirement(
        "我想复现 DOI 10.1073/pnas.2304669120 这篇 RUDE 论文里的图 4，"
        "用 OpenFOAM 生成可以作为真值对比的收缩流结果。"
    )
    assert result["status"] == "ready"
    assert result["target_preview"]["channel"] == "v9-rheotool"
    assert result["target_preview"]["solver"] == "rheoFoam"
    assert result.get("benchmark_match")
    assert not result["blocking_missing"]
