from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.workflow_compiler import compile_workflow  # noqa: E402
from services.case_manifest import (  # noqa: E402
    create_case_manifest,
    update_case_manifest_status,
    validate_case_manifest,
)
from services import review  # noqa: E402
from models import CaseTarget  # noqa: E402


class FakeLLM:
    def __init__(self):
        self.calls = []

    def invoke(self, user_prompt, system_prompt, **kwargs):
        self.calls.append((user_prompt, system_prompt, kwargs))
        return "fixed"


def test_mixed_workflow_sequence_keeps_distinct_case_targets(tmp_path):
    v9 = compile_workflow("Oldroyd-B 聚合物流动 etaS=1 etaP=2 lambda=0.5")
    v10 = compile_workflow("水在管道中的稳态压降")

    assert v9.plan.target == CaseTarget.for_solver("rheoFoam")
    assert v10.plan.target == CaseTarget.for_solver("simpleFoam")
    assert v9.plan.target.channel == "v9-rheotool"
    assert v10.plan.target.channel == "v10-foundation"

    v9_dir = tmp_path / "v9_case"
    v10_dir = tmp_path / "v10_case"
    v9_dir.mkdir()
    v10_dir.mkdir()
    create_case_manifest(v9_dir, v9.plan.target, physics_spec=v9.physics, workflow_plan=v9.plan)
    create_case_manifest(v10_dir, v10.plan.target, physics_spec=v10.physics, workflow_plan=v10.plan)

    update_case_manifest_status(v9_dir, v9.plan.target, validation_status="passed")
    update_case_manifest_status(v10_dir, v10.plan.target, validation_status="passed")

    assert validate_case_manifest(v9_dir, v9.plan.target)["solver"] == "rheoFoam"
    assert validate_case_manifest(v10_dir, v10.plan.target)["solver"] == "simpleFoam"
    with pytest.raises(ValueError, match="MANIFEST_TARGET_MISMATCH"):
        validate_case_manifest(v9_dir, v10.plan.target)


def test_reviewer_discards_v9_history_before_v10_review(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(review, "global_llm_service", fake)
    old_history = ['<CaseTarget channel="v9-rheotool" solver="rheoFoam"/>', "old-v9-history"]
    target = CaseTarget.for_solver("simpleFoam")

    _, history = review.review_error_logs(
        tutorial_reference="",
        foamfiles=None,
        error_logs=["OpenFOAM-10 error"],
        user_requirement="steady incompressible pipe pressure drop",
        case_target=target,
        physics_spec={"phase_type": "single-phase"},
        workflow_plan={"workflow_type": "newtonian-steady", "target": target.as_dict()},
        history_text=old_history,
    )

    user_prompt, system_prompt, _ = fake.calls[-1]
    assert history[0] == '<CaseTarget channel="v10-foundation" solver="simpleFoam"/>'
    assert "old-v9-history" not in history
    assert "old-v9-history" not in user_prompt
    assert "v10-foundation" in user_prompt
    assert "simpleFoam" in user_prompt
    assert "Foundation OpenFOAM v10" in system_prompt


def test_reviewer_discards_v10_history_before_v9_review(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(review, "global_llm_service", fake)
    old_history = ['<CaseTarget channel="v10-foundation" solver="interFoam"/>', "old-v10-history"]
    target = CaseTarget.for_solver("rheoInterFoam")

    _, history = review.review_error_logs(
        tutorial_reference="",
        foamfiles=None,
        error_logs=["OpenFOAM-9 rheoTool error"],
        user_requirement="Oldroyd-B 粘弹性两相自由液面 etaS=1 etaP=2 lambda=0.5",
        case_target=target,
        physics_spec={"phase_type": "two-phase", "free_surface": True},
        rheology_spec={"selected_model": "Oldroyd-B"},
        workflow_plan={"workflow_type": "rheological-two-phase", "target": target.as_dict()},
        history_text=old_history,
    )

    user_prompt, system_prompt, _ = fake.calls[-1]
    assert history[0] == '<CaseTarget channel="v9-rheotool" solver="rheoInterFoam"/>'
    assert "old-v10-history" not in history
    assert "old-v10-history" not in user_prompt
    assert "v9-rheotool" in user_prompt
    assert "rheoInterFoam" in user_prompt
    assert "OpenFOAM v9" in system_prompt


def test_reviewer_rejects_missing_immutable_case_target():
    with pytest.raises(TypeError, match="CaseTarget"):
        review.review_error_logs(
            tutorial_reference="",
            foamfiles=None,
            error_logs=["error"],
            user_requirement="steady flow",
            case_target=None,
        )
