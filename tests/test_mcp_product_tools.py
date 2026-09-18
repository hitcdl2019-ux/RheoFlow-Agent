from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import src.mcp.fastmcp_server as server  # noqa: E402


class DummyContext:
    def __init__(self):
        self.messages = []

    async def info(self, message: str):
        self.messages.append(("info", message))

    async def error(self, message: str):
        self.messages.append(("error", message))


def test_foamagent_intake_ready_writes_receipt(tmp_path):
    requirement = tmp_path / "user_requirement.txt"
    requirement.write_text(
        "Geometry: pipe diameter=0.001 length=0.1.\n"
        "Flow: steady inlet velocity=0.001, laminar.\n"
        "Fluid: Newtonian water, nu=1.004e-6, rho=998.2.\n"
        "Objective: pressure drop and velocity field.\n",
        encoding="utf-8",
    )

    response = asyncio.run(
        server.foamagent_intake(
            server.FoamAgentIntakeRequest(requirement_path=str(requirement)),
            DummyContext(),
        )
    )

    assert response.status == "ready"
    assert response.target_preview is not None
    assert response.receipt_path is not None
    assert Path(response.receipt_path).is_file()


def test_foamagent_postprocess_wraps_standard_report(monkeypatch, tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()

    def fake_postprocess(case_dir_arg, **kwargs):
        return {
            "status": "passed",
            "case_dir": str(case_dir_arg),
            "latest_time": "10",
            "report_json": str(Path(case_dir_arg) / "POSTPROCESS_REPORT.json"),
            "summary_markdown": str(Path(case_dir_arg) / "POSTPROCESS_SUMMARY.md"),
            "artifacts_json": str(Path(case_dir_arg) / "POSTPROCESS_ARTIFACTS.json"),
            "artifacts": [{"kind": "plot", "path": "plot.png", "bytes": 3}],
            "metrics": {"pressure": {"status": "present"}},
        }

    monkeypatch.setattr(server, "run_standard_postprocess", fake_postprocess)

    response = asyncio.run(
        server.foamagent_postprocess(
            server.FoamAgentPostprocessRequest(case_dir=str(case_dir), fields=["U", "p"]),
            DummyContext(),
        )
    )

    assert response.status == "passed"
    assert response.latest_time == "10"
    assert response.artifacts[0]["kind"] == "plot"
    assert response.metrics["pressure"]["status"] == "present"


def test_foamagent_artifacts_reads_manifest(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    (case_dir / "POSTPROCESS_ARTIFACTS.json").write_text(
        json.dumps({"artifacts": [{"kind": "plot", "path": "a.png", "bytes": 1}]}),
        encoding="utf-8",
    )

    response = asyncio.run(
        server.foamagent_artifacts(
            server.FoamAgentArtifactsRequest(case_dir=str(case_dir)),
            DummyContext(),
        )
    )

    assert response.artifacts_json == str(case_dir / "POSTPROCESS_ARTIFACTS.json")
    assert response.artifacts == [{"kind": "plot", "path": "a.png", "bytes": 1}]


def test_foamagent_case_evolution_evaluate_only(monkeypatch, tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()

    def fake_evaluate(case_dir_arg):
        return {
            "coverage_status": {
                "decision": "novel_candidate",
                "nearest_match": None,
            },
            "candidate": {"candidate_path": "knowledge/candidate_cases/example"},
        }

    monkeypatch.setattr(server, "evaluate_successful_case_for_evolution", fake_evaluate)

    response = asyncio.run(
        server.foamagent_case_evolution(
            server.FoamAgentCaseEvolutionRequest(case_dir=str(case_dir)),
            DummyContext(),
        )
    )

    assert response.decision == "novel_candidate"
    assert response.candidate_path == "knowledge/candidate_cases/example"
    assert response.requires_user_approval is True


def test_foamagent_case_evolution_duplicate_does_not_request_approval(monkeypatch, tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()

    def fake_evaluate(case_dir_arg):
        return {
            "coverage_status": {
                "decision": "duplicate",
                "nearest_match": "rude_giesekus_4to1_pnas2023_fig4",
            },
            "candidate": None,
        }

    monkeypatch.setattr(server, "evaluate_successful_case_for_evolution", fake_evaluate)

    response = asyncio.run(
        server.foamagent_case_evolution(
            server.FoamAgentCaseEvolutionRequest(case_dir=str(case_dir)),
            DummyContext(),
        )
    )

    assert response.decision == "duplicate"
    assert response.nearest_match == "rude_giesekus_4to1_pnas2023_fig4"
    assert response.candidate_path is None
    assert response.requires_user_approval is False


def test_foamagent_case_evolution_template_import_does_not_request_approval(monkeypatch, tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()

    def fake_evaluate(case_dir_arg):
        return {
            "coverage_status": {
                "decision": "template_import",
                "nearest_match": "rheotool_5_1_3_channel_oldroydb_log",
            },
            "candidate": None,
        }

    monkeypatch.setattr(server, "evaluate_successful_case_for_evolution", fake_evaluate)

    response = asyncio.run(
        server.foamagent_case_evolution(
            server.FoamAgentCaseEvolutionRequest(case_dir=str(case_dir)),
            DummyContext(),
        )
    )

    assert response.decision == "template_import"
    assert response.nearest_match == "rheotool_5_1_3_channel_oldroydb_log"
    assert response.candidate_path is None
    assert response.requires_user_approval is False


def _write_ready_requirement(path: Path) -> None:
    path.write_text(
        "Geometry: pipe diameter=0.001 length=0.1.\n"
        "Flow: steady inlet velocity=0.001, laminar.\n"
        "Fluid Properties: Newtonian water, nu=1.004e-6, rho=998.2.\n"
        "Objective: pressure drop and velocity field.\n",
        encoding="utf-8",
    )


def test_foamagent_execute_runs_main_with_stamped_requirement(monkeypatch, tmp_path):
    requirement = tmp_path / "user_requirement.txt"
    _write_ready_requirement(requirement)
    server.issue_receipt(requirement)
    output_dir = tmp_path / "case"
    captured = {}

    class Completed:
        returncode = 0
        stdout = "<workflow_end>Workflow completed successfully!</workflow_end>\n"
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Completed()

    monkeypatch.setattr(server.subprocess, "run", fake_run)

    response = asyncio.run(
        server.foamagent_execute(
            server.FoamAgentExecuteRequest(
                requirement_path=str(requirement),
                output_dir=str(output_dir),
                timeout_seconds=5,
            ),
            DummyContext(),
        )
    )

    assert response.status == "passed"
    assert response.case_dir == str(output_dir)
    assert response.returncode == 0
    assert response.target_preview["solver"] == "simpleFoam"
    assert Path(response.log_path).is_file()
    assert "src/main.py" in " ".join(captured["command"])
    assert "--prompt_path" in captured["command"]
    assert str(requirement) in captured["command"]
    assert "--output_dir" in captured["command"]
    assert str(output_dir) in captured["command"]


def test_foamagent_execute_returns_failed_on_main_error(monkeypatch, tmp_path):
    requirement = tmp_path / "user_requirement.txt"
    _write_ready_requirement(requirement)
    server.issue_receipt(requirement)

    class Completed:
        returncode = 2
        stdout = "<workflow_error>provider missing</workflow_error>\n"
        stderr = "missing auth\n"

    monkeypatch.setattr(server.subprocess, "run", lambda *args, **kwargs: Completed())

    response = asyncio.run(
        server.foamagent_execute(
            server.FoamAgentExecuteRequest(
                requirement_path=str(requirement),
                output_dir=str(tmp_path / "case"),
                timeout_seconds=5,
            ),
            DummyContext(),
        )
    )

    assert response.status == "failed"
    assert response.returncode == 2
    assert "provider missing" in response.stdout_tail
    assert "missing auth" in response.stderr_tail
    assert Path(response.log_path).is_file()


def test_default_execute_dir_uses_case_key_and_timestamp(monkeypatch, tmp_path):
    from datetime import datetime

    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    requirement = tmp_path / "sessions" / "dieswell-oldroydb" / "user_requirement.txt"

    case_dir = server._default_execute_dir(
        requirement,
        session_id=None,
        now=datetime(2026, 8, 5, 15, 45, 10),
    )

    assert case_dir == tmp_path / "runs" / "mcp-execute-dieswell-oldroydb-20260805-154510"


def test_default_execute_dir_prefers_session_id_and_sanitizes(monkeypatch, tmp_path):
    from datetime import datetime

    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    requirement = tmp_path / "sessions" / "mcp-20260805" / "user_requirement.txt"

    case_dir = server._default_execute_dir(
        requirement,
        session_id="真实设备/case 01",
        now=datetime(2026, 8, 5, 15, 45, 10),
    )

    assert case_dir == tmp_path / "runs" / "mcp-execute-case-01-20260805-154510"


def test_default_execute_dir_avoids_same_second_collision(monkeypatch, tmp_path):
    from datetime import datetime

    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    existing = tmp_path / "runs" / "mcp-execute-channel-20260805-154510"
    existing.mkdir(parents=True)
    requirement = tmp_path / "sessions" / "channel" / "user_requirement.txt"

    case_dir = server._default_execute_dir(
        requirement,
        session_id=None,
        now=datetime(2026, 8, 5, 15, 45, 10),
    )

    assert case_dir == tmp_path / "runs" / "mcp-execute-channel-20260805-154510-002"
