from pathlib import Path
import os
import json
import threading
import time
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.mcp.fastmcp_server import (  # noqa: E402
    FoamAgentExecuteStatusRequest,
    _summarize_execute_progress,
    _watch_execute_progress,
)




def test_execute_status_keeps_stage3_running_while_input_writer_is_open(tmp_path):
    case = tmp_path / "case"
    (case / "system").mkdir(parents=True)
    (case / "constant").mkdir()
    (case / "manifest.json").write_text(json.dumps({
        "solver": "rheoFoam",
        "channel": "v9-rheotool",
        "version": "v9",
        "distribution": "foundation+rheotool",
        "validation_status": "pending",
        "run_status": "pending",
    }), encoding="utf-8")
    (case / "workflow.log").write_text(
        "<planner>\n</planner>\n"
        "<router>Standard mesh generation. Routing to input_writer node.</router>\n"
        "<input_writer mode=\"initial\">\n"
        "Wrote system/controlDict\n"
        "Wrote constant/viscoelasticProperties\n",
        encoding="utf-8",
    )
    (case / "system" / "controlDict").write_text("endTime 8;\n", encoding="utf-8")
    (case / "constant" / "viscoelasticProperties").write_text("parameters{}\n", encoding="utf-8")

    status = _summarize_execute_progress(case)

    assert status.status == "running"
    assert status.current_stage == "3"
    assert status.stages["3"] == "running"
    assert status.stages["4"] == "pending"
    assert status.stages["5"] == "pending"


def test_execute_status_reports_stage4_only_after_runner_starts(tmp_path):
    case = tmp_path / "case"
    (case / "system").mkdir(parents=True)
    (case / "manifest.json").write_text(json.dumps({
        "solver": "rheoFoam",
        "channel": "v9-rheotool",
        "version": "v9",
        "distribution": "foundation+rheotool",
        "validation_status": "pending",
        "run_status": "pending",
    }), encoding="utf-8")
    (case / "workflow.log").write_text(
        "<input_writer mode=\"initial\">\n</input_writer>\n<runner>\n",
        encoding="utf-8",
    )

    status = _summarize_execute_progress(case)

    assert status.status == "running"
    assert status.current_stage == "4"
    assert status.stages["3"] == "passed"
    assert status.stages["4"] == "running"
    assert status.stages["5"] == "pending"




def test_execute_status_reports_tutorial_template_match_from_workflow_log(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "manifest.json").write_text(json.dumps({
        "solver": "rheoFoam",
        "channel": "v9-rheotool",
        "version": "v9",
        "distribution": "foundation+rheotool",
        "validation_status": "pending",
        "run_status": "pending",
    }), encoding="utf-8")
    (case / "workflow.log").write_text(
        '<rheotool_tutorial_template_match id="rheotool_5_1_4_cavity_oldroydb_log" '
        'tier="A" alias="Fattal & Kupferman 2005 / RheoTool 5.1.4 Cavity/Oldroyd-BLog"/>\n',
        encoding="utf-8",
    )

    status = _summarize_execute_progress(case)

    assert status.template_match == {
        "source": "workflow.log",
        "template_id": "rheotool_5_1_4_cavity_oldroydb_log",
        "tier": "A",
        "rag_confidence": None,
        "matched_alias": "Fattal & Kupferman 2005 / RheoTool 5.1.4 Cavity/Oldroyd-BLog",
        "import_policy": "rheotool tutorial template import; no LLM dictionary regeneration",
    }


def test_execute_status_reports_tutorial_template_solver_and_name_from_workflow_log(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "manifest.json").write_text(json.dumps({
        "solver": "rheoFoam",
        "channel": "v9-rheotool",
        "version": "v9",
        "distribution": "foundation+rheotool",
        "validation_status": "pending",
        "run_status": "pending",
    }), encoding="utf-8")
    (case / "workflow.log").write_text(
        '<rheotool_tutorial_template_match id="rheotool_5_1_4_cavity_oldroydb_log" '
        'solver="rheoFoam" name="RheoTool 5.1.4 rheoFoam/Cavity/Oldroyd-BLog" '
        'tier="A" alias="Fattal & Kupferman 2005 / RheoTool 5.1.4 Cavity/Oldroyd-BLog"/>\n',
        encoding="utf-8",
    )

    status = _summarize_execute_progress(case)

    assert status.template_match["solver"] == "rheoFoam"
    assert status.template_match["template_name"] == "RheoTool 5.1.4 rheoFoam/Cavity/Oldroyd-BLog"


def test_execute_status_reports_tutorial_template_import_json(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "manifest.json").write_text(json.dumps({
        "solver": "rheoFoam",
        "validation_status": "passed",
        "run_status": "pending",
    }), encoding="utf-8")
    (case / "TUTORIAL_TEMPLATE_IMPORT.json").write_text(json.dumps({
        "template_id": "rheotool_5_1_4_cavity_oldroydb_log",
        "template_name": "RheoTool 5.1.4 rheoFoam/Cavity/Oldroyd-BLog",
        "solver": "rheoFoam",
        "source_directory": "/opt/build/rheoTool/of90/tutorials/rheoFoam/Cavity/Oldroyd-BLog",
        "matched_alias": "Fattal & Kupferman 2005 / RheoTool 5.1.4 Cavity/Oldroyd-BLog",
        "import_policy": "rheotool tutorial template import; no LLM dictionary regeneration",
        "tier": "A",
        "rag_confidence": "high",
        "parallel_policy": "serial_certified",
        "start_policy": "clean_case_dir_start_from_0",
        "run_user_policy": "non_root_openfoam_user_required",
        "certification": {"status": "serial_certified"},
    }), encoding="utf-8")

    status = _summarize_execute_progress(case)

    assert status.template_match["source"] == "TUTORIAL_TEMPLATE_IMPORT.json"
    assert status.template_match["template_id"] == "rheotool_5_1_4_cavity_oldroydb_log"
    assert status.template_match["tier"] == "A"
    assert status.template_match["rag_confidence"] == "high"
    assert status.template_match["import_policy"] == "rheotool tutorial template import; no LLM dictionary regeneration"
    assert status.template_match["solver"] == "rheoFoam"
    assert status.template_match["template_name"] == "RheoTool 5.1.4 rheoFoam/Cavity/Oldroyd-BLog"
    assert status.template_match["parallel_policy"] == "serial_certified"
    assert status.template_match["start_policy"] == "clean_case_dir_start_from_0"
    assert status.template_match["run_user_policy"] == "non_root_openfoam_user_required"
    assert status.template_match["certification"]["status"] == "serial_certified"


def test_execute_status_reports_running_rheofoam_substep(tmp_path):
    case = tmp_path / "case"
    (case / "system").mkdir(parents=True)
    (case / "manifest.json").write_text(json.dumps({
        "solver": "rheoFoam",
        "channel": "v9-rheotool",
        "version": "v9",
        "distribution": "foundation+rheotool",
        "validation_status": "pending",
        "run_status": "pending",
    }), encoding="utf-8")
    (case / "system" / "controlDict").write_text("endTime         10;\ndeltaT          2e-4;\n", encoding="utf-8")
    (case / "log.blockMesh").write_text("Writing polyMesh\nEnd\n", encoding="utf-8")
    (case / "log.rheoFoam").write_text("Time = 0.5\nExecutionTime = 10 s\n", encoding="utf-8")

    status = _summarize_execute_progress(case)

    assert status.status == "running"
    assert status.stages["3"] == "passed"
    assert status.stages["4"] == "passed"
    assert status.stages["5"] == "running"
    assert status.openfoam_substeps["5.2"] == "passed"
    assert status.openfoam_substeps["5.3"] == "passed"
    assert status.openfoam_substeps["5.4"] == "running"
    assert status.current_time == 0.5
    assert status.end_time == 10
    assert status.progress_percent == 5.0
    assert status.progress_events
    stage5 = next(event for event in status.progress_events if event["id"] == "5")
    assert stage5["children"][3]["name"] == "求解器运行 rheoFoam"
    assert "[5.4] 求解器运行 rheoFoam：running（Time=0.5/10，约 5.00%）" in status.rendered_progress


def test_execute_status_prefers_live_solver_over_stale_failed_manifest(tmp_path):
    case = tmp_path / "case"
    (case / "system").mkdir(parents=True)
    (case / "manifest.json").write_text(json.dumps({
        "solver": "rheoFoam",
        "validation_status": "passed",
        "run_status": "failed",
    }), encoding="utf-8")
    (case / "foamagent_execute.pid").write_text(str(os.getpid()), encoding="utf-8")
    (case / "system" / "controlDict").write_text("endTime         20;\n", encoding="utf-8")
    (case / "log.blockMesh").write_text("Writing polyMesh\nEnd\n", encoding="utf-8")
    (case / "log.rheoFoam").write_text("Time = 0.8372\nExecutionTime = 183 s\n", encoding="utf-8")

    status = _summarize_execute_progress(case)

    assert status.status == "running"
    assert status.current_stage == "5"
    assert status.stages["5"] == "running"
    assert status.openfoam_substeps["5.4"] == "running"
    assert status.current_time == 0.8372


def test_execute_status_reports_passed_from_manifest(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "manifest.json").write_text(json.dumps({
        "solver": "rheoFoam",
        "validation_status": "passed",
        "run_status": "passed",
    }), encoding="utf-8")

    status = _summarize_execute_progress(case)

    assert status.status == "passed"
    assert status.stages["5"] == "passed"
    assert status.stages["6"] == "passed"


def test_execute_status_reports_failed_when_planner_crashes_before_case_files(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "foamagent_execute.log").write_text(
        "Traceback (most recent call last):\n"
        "Exception: Maximum retries (10) exceeded for throttling error: "
        "Error code: 503 - {'error': {'code': 'model_not_found'}}\n",
        encoding="utf-8",
    )

    status = _summarize_execute_progress(case)

    assert status.status == "failed"
    assert status.current_stage == "3"
    assert status.stages["3"] == "failed"


def test_execute_status_reports_sample_failure_after_solver_passed(tmp_path):
    case = tmp_path / "case"
    (case / "system").mkdir(parents=True)
    (case / "manifest.json").write_text(json.dumps({
        "solver": "rheoFoam",
        "validation_status": "passed",
        "run_status": "pending",
    }), encoding="utf-8")
    (case / "system" / "controlDict").write_text("endTime         30;\n", encoding="utf-8")
    (case / "log.blockMesh").write_text("Writing polyMesh\nEnd\n", encoding="utf-8")
    (case / "log.rheoFoam").write_text("Time = 30\nExecutionTime = 100 s\n", encoding="utf-8")
    (case / "log.sample").write_text(
        "/opt/openfoam9/bin/tools/RunFunctions: line 93: sample: command not found\n",
        encoding="utf-8",
    )
    (case / "Allrun.err").write_text("[Foam-Agent] Allrun exited with status 127.\n", encoding="utf-8")

    status = _summarize_execute_progress(case)

    assert status.status == "failed"
    assert status.current_stage == "5"
    assert status.openfoam_substeps["5.4"] == "passed"
    assert status.openfoam_substeps["5.5"] == "failed"
    assert "sample: command not found" in status.log_tail


def test_execute_status_prefers_solver_end_over_stale_fatal_marker(tmp_path):
    case = tmp_path / "case"
    (case / "system").mkdir(parents=True)
    (case / "manifest.json").write_text(json.dumps({
        "solver": "rheoFoam",
        "validation_status": "passed",
        "run_status": "pending",
    }), encoding="utf-8")
    (case / "system" / "controlDict").write_text("endTime         30;\n", encoding="utf-8")
    (case / "log.blockMesh").write_text("Writing polyMesh\nEnd\n", encoding="utf-8")
    (case / "log.rheoFoam").write_text(
        "--> FOAM FATAL ERROR:\nold appended failure\n"
        "Time = 30\nExecutionTime = 100 s\nEnd\n",
        encoding="utf-8",
    )
    (case / "log.sample").write_text(
        "/opt/openfoam9/bin/tools/RunFunctions: line 93: sample: command not found\n",
        encoding="utf-8",
    )

    status = _summarize_execute_progress(case)

    assert status.openfoam_substeps["5.4"] == "passed"
    assert status.openfoam_substeps["5.5"] == "failed"


def test_execute_status_request_supports_server_side_watch():
    request = FoamAgentExecuteStatusRequest(
        case_dir="/tmp/case",
        watch_seconds=7200,
        poll_interval_seconds=30,
        wait_until_terminal=True,
    )

    assert request.watch_seconds == 7200
    assert request.poll_interval_seconds == 30
    assert request.wait_until_terminal is True


def test_watch_execute_progress_returns_timeout_when_progress_is_unchanged(tmp_path):
    case = tmp_path / "case"
    (case / "system").mkdir(parents=True)
    (case / "manifest.json").write_text(json.dumps({
        "solver": "rheoFoam",
        "validation_status": "passed",
        "run_status": "pending",
    }), encoding="utf-8")
    (case / "system" / "controlDict").write_text("endTime         10;\n", encoding="utf-8")
    (case / "log.blockMesh").write_text("Writing polyMesh\nEnd\n", encoding="utf-8")
    (case / "log.rheoFoam").write_text("Time = 1\nExecutionTime = 10 s\n", encoding="utf-8")

    status = _watch_execute_progress(case, watch_seconds=1, poll_interval_seconds=1)

    assert status.status == "running"
    assert status.watch_reason == "timeout"
    assert status.watch_elapsed_seconds is not None


def _write_running_rheofoam_case(case: Path, time_value: float = 1.0) -> None:
    (case / "system").mkdir(parents=True, exist_ok=True)
    (case / "manifest.json").write_text(json.dumps({
        "solver": "rheoFoam",
        "validation_status": "passed",
        "run_status": "pending",
    }), encoding="utf-8")
    (case / "system" / "controlDict").write_text("endTime         10;\n", encoding="utf-8")
    (case / "log.blockMesh").write_text("Writing polyMesh\nEnd\n", encoding="utf-8")
    (case / "log.rheoFoam").write_text(f"Time = {time_value}\nExecutionTime = 10 s\n", encoding="utf-8")


def test_watch_execute_progress_can_return_on_progress_change(tmp_path):
    case = tmp_path / "case"
    _write_running_rheofoam_case(case, 1.0)

    def advance():
        time.sleep(0.05)
        (case / "log.rheoFoam").write_text("Time = 2\nExecutionTime = 20 s\n", encoding="utf-8")

    threading.Thread(target=advance, daemon=True).start()
    status = _watch_execute_progress(case, watch_seconds=0.5, poll_interval_seconds=0.05)

    assert status.status == "running"
    assert status.current_time == 2
    assert status.watch_reason == "progress_changed"


def test_watch_until_terminal_ignores_progress_change_until_timeout(tmp_path):
    case = tmp_path / "case"
    _write_running_rheofoam_case(case, 1.0)

    def advance():
        time.sleep(0.05)
        (case / "log.rheoFoam").write_text("Time = 2\nExecutionTime = 20 s\n", encoding="utf-8")

    threading.Thread(target=advance, daemon=True).start()
    status = _watch_execute_progress(
        case,
        watch_seconds=0.2,
        poll_interval_seconds=0.05,
        return_on_progress=False,
    )

    assert status.status == "running"
    assert status.current_time == 2
    assert status.watch_reason == "timeout"
