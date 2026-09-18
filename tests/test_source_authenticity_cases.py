import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_source_authenticity_cases_define_manual_release_gate():
    path = ROOT / "tests" / "business_prompts" / "source_authenticity_cases.yaml"
    cases = json.loads(path.read_text(encoding="utf-8"))
    assert len(cases) >= 10
    for case in cases:
        assert case["id"].startswith("src_")
        assert case["raw_user_prompt"]
        assert case["missing_information"], case["id"]
        assert case["agent_must_ask"], case["id"]
        assert "user_provided" in case["forbidden_source_labels"], case["id"]


def test_source_authenticity_cases_do_not_name_final_solvers():
    path = ROOT / "tests" / "business_prompts" / "source_authenticity_cases.yaml"
    cases = json.loads(path.read_text(encoding="utf-8"))
    solver_names = (
        "rheofoam", "rheotestfoam", "rheointerfoam",
        "simplefoam", "pimplefoam", "interfoam", "icofoam",
    )
    assert all(
        not any(name in case["raw_user_prompt"].lower() for name in solver_names)
        for case in cases
    )
