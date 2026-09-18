from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import utils  # noqa: E402
from models import CaseTarget  # noqa: E402
from services import review  # noqa: E402
from services.channel_prompts import load_channel_prompt  # noqa: E402


class FakeDocument:
    def __init__(self, content, metadata):
        self.page_content = content
        self.metadata = metadata


class FakeVectorDB:
    def __init__(self, documents, calls, key):
        self.documents = documents
        self.calls = calls
        self.key = key

    def similarity_search_with_score(self, query, k):
        self.calls.append(self.key)
        return [(document, 0.1) for document in self.documents]


def _structure_doc(channel, version, solver, name):
    return FakeDocument(
        name,
        {
            "channel": channel,
            "version": version,
            "distribution": "foundation",
            "case_name": name,
            "case_domain": "rheology" if version == "v9" else "incompressible",
            "case_category": "test",
            "case_solver": solver,
            "full_content": name,
            "dir_structure": "",
        },
    )


def test_retrieval_uses_only_case_target_channel_and_metadata(monkeypatch):
    calls = []
    v9_docs = [
        _structure_doc("v9-rheotool", "v9", "rheoFoam", "valid-v9"),
        _structure_doc("v10-foundation", "v10", "simpleFoam", "polluted-v10"),
    ]
    v10_docs = [_structure_doc("v10-foundation", "v10", "simpleFoam", "valid-v10")]
    cache = {
        "v9-rheotool/openfoam_tutorials_structure": FakeVectorDB(v9_docs, calls, "v9"),
        "v10-foundation/openfoam_tutorials_structure": FakeVectorDB(v10_docs, calls, "v10"),
    }
    monkeypatch.setattr(utils, "ensure_faiss_dbs_loaded", lambda: cache)

    v9 = utils.retrieve_faiss(
        "openfoam_tutorials_structure", "query", CaseTarget.for_solver("rheoFoam"), topk=5
    )
    v10 = utils.retrieve_faiss(
        "openfoam_tutorials_structure", "query", CaseTarget.for_solver("simpleFoam"), topk=5
    )

    assert [item["case_name"] for item in v9] == ["valid-v9"]
    assert [item["case_name"] for item in v10] == ["valid-v10"]
    assert calls == ["v9", "v10"]


def test_retrieval_rejects_missing_case_target():
    with pytest.raises(TypeError, match="CaseTarget"):
        utils.retrieve_faiss("openfoam_tutorials_structure", "query", None)


def test_all_channel_prompt_sets_exist():
    for solver in ("rheoFoam", "simpleFoam"):
        target = CaseTarget.for_solver(solver)
        for name in ("planner", "input_writer", "reviewer", "error_fix"):
            assert load_channel_prompt(target, name)


def test_reviewer_discards_history_from_another_channel(monkeypatch):
    captured = {}

    class FakeLLM:
        def invoke(self, user_prompt, system_prompt, **kwargs):
            captured["user"] = user_prompt
            captured["system"] = system_prompt
            return "fixed"

    monkeypatch.setattr(review, "global_llm_service", FakeLLM())
    old_history = ['<CaseTarget channel="v9-rheotool" solver="rheoFoam"/>', "old"]
    target = CaseTarget.for_solver("simpleFoam")
    _, history = review.review_error_logs(
        tutorial_reference="",
        foamfiles=None,
        error_logs=["error"],
        user_requirement="steady flow",
        case_target=target,
        physics_spec={"phase_type": "single-phase"},
        workflow_plan={"workflow_type": "newtonian-steady"},
        history_text=old_history,
    )

    assert history[0] == '<CaseTarget channel="v10-foundation" solver="simpleFoam"/>'
    assert "old" not in history
    assert "Foundation OpenFOAM v10" in captured["system"]
    assert "newtonian-steady" in captured["user"]
