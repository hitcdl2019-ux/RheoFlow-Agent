import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.workflow_compiler import compile_workflow  # noqa: E402


def _load_cases():
    path = ROOT / "tests" / "business_prompts" / "business_prompt_expectations.yaml"
    # The file is YAML-compatible JSON to avoid adding a PyYAML dependency.
    return json.loads(path.read_text(encoding="utf-8"))


def test_business_prompt_expectations_are_met():
    cases = _load_cases()
    assert len(cases) >= 30
    solver_named = ("rheofoam", "rheotestfoam", "rheointerfoam", "simplefoam", "pimplefoam", "interfoam", "icofoam")
    assert sum(not any(name in case["prompt"].lower() for name in solver_named) for case in cases) >= 30

    for case in cases:
        compiled = compile_workflow(case["prompt"])
        target = compiled.plan.target
        if case.get("expected_rejection"):
            assert target is None, case["id"]
            assert compiled.plan.rejection_reason, case["id"]
            continue
        if "expected_solver" in case:
            assert target is not None, case["id"]
            assert target.channel == case["expected_channel"], case["id"]
            assert target.version == case["expected_version"], case["id"]
            assert target.solver == case["expected_solver"], case["id"]
        if "expected_ready" in case:
            assert compiled.plan.ready is case["expected_ready"], case["id"]
        if "expected_missing" in case:
            assert tuple(case["expected_missing"]) == compiled.rheology.missing_parameters, case["id"]
        if "expected_missing_fields" in case:
            assert tuple(case["expected_missing_fields"]) == compiled.intent.missing_critical_fields, case["id"]
        if "expected_contradictions" in case:
            assert set(case["expected_contradictions"]) <= set(compiled.intent.contradictions), case["id"]
        if case.get("expected_clarification"):
            assert compiled.plan.clarification_questions, case["id"]
