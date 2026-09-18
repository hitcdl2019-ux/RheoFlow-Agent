"""FastMCP-based OpenFOAM Agent Server.

This module provides a modern MCP server implementation using FastMCP,
exposing OpenFOAM simulation capabilities through clean, well-typed interfaces.
"""

import asyncio
import os
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field

# Import existing services
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.plan import (
    resolve_case_dir,
    retrieve_references,
    generate_simulation_plan
)
from services.input_writer import initial_write
from services.run_local import run_allrun_and_collect_errors

from utils import FoamPydantic, read_case_foamfiles, scan_case_directory
from services.review import review_error_logs
from translation.esi_translator import convert_case_to_esi_if_needed
from services.visualization import (
    ensure_foam_file,
    generate_deterministic_pyvista_script,
    generate_pyvista_script,
    run_pyvista_script,
    fix_pyvista_script
)
from config import Config
from models import CaseTarget
from services.case_manifest import case_target_from_manifest
from services.case_evolution import evaluate_successful_case_for_evolution
from services.intake import evaluate_requirement, issue_receipt, validate_receipt
from services.postprocess import run_standard_postprocess
from services.progress import build_progress_events, render_progress_text


# Global configuration
global_config = Config()
REPO_ROOT = Path(__file__).resolve().parents[2]


# Create FastMCP server
mcp = FastMCP(
    name="Foam-Agent",
    version="2.0.0",
    instructions="""
Foam-Agent is a multi-agent framework that automates the entire OpenFOAM-based CFD simulation workflow from a single natural language prompt.
By managing the full pipeline—from meshing and case setup to execution and post-processing—Foam-Agent dramatically lowers the expertise barrier for Computational Fluid Dynamics.

IMPORTANT: Foam-Agent generates cases using **Foundation OpenFOAM v10** conventions by default. If
`FOAMAGENT_OPENFOAM_FORK=esi` is set, generated input files are translated to ESI OpenFOAM
(openfoam.com) naming and dictionary conventions on a best-effort basis before they are returned.

The run/review/fix workflow is still primarily validated with Foundation OpenFOAM v10. ESI execution
support is experimental and should be verified for each case.
"""
)


# ============================================================================
# Foam-Agent product entry tools
# ============================================================================

def _safe_session_id(value: str | None) -> str:
    if value:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
        if cleaned:
            return cleaned[:80]
    return "mcp-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _write_mcp_requirement(business_prompt: str, session_id: str | None) -> Path:
    session_dir = REPO_ROOT / "sessions" / _safe_session_id(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    requirement_path = session_dir / "user_requirement.txt"
    requirement_path.write_text(business_prompt, encoding="utf-8")
    return requirement_path


def _read_artifact_manifest(case_dir: str | Path) -> dict[str, Any]:
    case_path = Path(case_dir)
    manifest_path = case_path / "POSTPROCESS_ARTIFACTS.json"
    if manifest_path.is_file():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = []
    for path in sorted((case_path / "postprocess").glob("*")) if (case_path / "postprocess").is_dir() else []:
        if path.is_file():
            artifacts.append({"kind": "postprocess", "path": str(path), "bytes": path.stat().st_size})
    return {
        "schema_version": 1,
        "case_dir": str(case_path),
        "latest_time": None,
        "artifacts": artifacts,
    }


class FoamAgentIntakeRequest(BaseModel):
    """Request to run Foam-Agent intake on a business prompt or requirement file."""
    business_prompt: Optional[str] = Field(default=None, description="Business-language CFD request")
    requirement_path: Optional[str] = Field(default=None, description="Existing user_requirement.txt path")
    session_id: Optional[str] = Field(default=None, description="Stable session id for generated requirement files")
    write_receipt: bool = Field(default=True, description="Write intake receipt when status is ready")


class FoamAgentIntakeResponse(BaseModel):
    """Structured intake result for agent entrypoints."""
    status: Literal["ready", "clarify", "reject"]
    target_preview: Optional[Dict[str, str]]
    requirement_path: str
    receipt_path: Optional[str] = None
    clarification_questions: List[str] = Field(default_factory=list)
    blocking_missing: List[Dict[str, Any]] = Field(default_factory=list)
    rejection_reason: Optional[str] = None
    intake_result: Dict[str, Any] = Field(default_factory=dict)


@mcp.tool(name="foamagent_intake")
async def foamagent_intake(
    request: FoamAgentIntakeRequest,
    ctx: Context
) -> FoamAgentIntakeResponse:
    """Validate a business-language request through Foam-Agent intake.

    This is the preferred MCP entrypoint for external agents. It returns
    ready/clarify/reject and only issues a receipt when the deterministic intake
    policy says the requirement is ready.
    """
    try:
        if request.requirement_path:
            requirement_path = Path(request.requirement_path)
        elif request.business_prompt:
            requirement_path = _write_mcp_requirement(request.business_prompt, request.session_id)
        else:
            raise ValueError("Either business_prompt or requirement_path is required")

        if not requirement_path.is_file():
            raise ValueError(f"Requirement file does not exist: {requirement_path}")

        await ctx.info(f"Running Foam-Agent intake for {requirement_path}")
        text = requirement_path.read_text(encoding="utf-8")
        result = evaluate_requirement(text)

        receipt_path = None
        if request.write_receipt and result["status"] == "ready":
            receipt = issue_receipt(requirement_path)
            receipt_path = receipt.get("receipt_path")
            result["receipt"] = receipt

        return FoamAgentIntakeResponse(
            status=result["status"],
            target_preview=result.get("target_preview"),
            requirement_path=str(requirement_path),
            receipt_path=receipt_path,
            clarification_questions=result.get("clarification_questions", []),
            blocking_missing=result.get("blocking_missing", []),
            rejection_reason=result.get("rejection_reason"),
            intake_result=result,
        )
    except Exception as e:
        await ctx.error(f"Foam-Agent intake failed: {str(e)}")
        raise


class FoamAgentExecuteRequest(BaseModel):
    """Request to execute the Foam-Agent main workflow after intake is ready."""
    requirement_path: str = Field(description="Stamped user_requirement.txt path")
    receipt_path: Optional[str] = Field(default=None, description="Optional explicit intake receipt path")
    output_dir: Optional[str] = Field(default=None, description="Output OpenFOAM case directory; defaults to runs/mcp-execute-<case-key>-<YYYYMMDD-HHMMSS>")
    session_id: Optional[str] = Field(default=None, description="Stable session id for default output directory naming")
    custom_mesh_path: Optional[str] = Field(default=None, description="Optional custom mesh path passed to Foam-Agent")
    reuse_generated_dir: Optional[str] = Field(default=None, description="Optional previously generated case files to reuse")
    timeout_seconds: int = Field(default=7200, ge=1, le=86400, description="Maximum wall-clock time for Foam-Agent execution")
    background: bool = Field(default=False, description="Start Foam-Agent in the background and return immediately for status polling")


class FoamAgentExecuteResponse(BaseModel):
    """Structured Foam-Agent execution response."""
    status: Literal["running", "passed", "failed"]
    case_dir: str
    requirement_path: str
    receipt_path: Optional[str] = None
    log_path: str
    returncode: Optional[int] = None
    target_preview: Optional[Dict[str, str]] = None
    message: str = ""
    stdout_tail: str = ""
    stderr_tail: str = ""
    pid: Optional[int] = None


class FoamAgentExecuteStatusRequest(BaseModel):
    """Request current progress for a Foam-Agent execution case directory."""
    case_dir: str = Field(description="OpenFOAM case directory returned by foamagent_execute")
    watch_seconds: int = Field(
        default=0,
        ge=0,
        le=7200,
        description="Optionally keep polling server-side until progress changes/terminal status or this many seconds elapse",
    )
    wait_until_terminal: bool = Field(
        default=False,
        description="When true, do not return merely because solver time advanced; keep polling until passed/failed or watch_seconds timeout",
    )
    poll_interval_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Polling interval used when watch_seconds is greater than zero",
    )


class FoamAgentExecuteStatusResponse(BaseModel):
    """Human-facing execution progress derived from Foam-Agent/OpenFOAM logs."""
    status: Literal["running", "passed", "failed", "unknown"]
    case_dir: str
    current_stage: str
    stages: Dict[str, str]
    openfoam_substeps: Dict[str, str]
    solver: Optional[str] = None
    current_time: Optional[float] = None
    end_time: Optional[float] = None
    progress_percent: Optional[float] = None
    progress_events: List[Dict[str, Any]] = Field(default_factory=list, description="Canonical stage/substep progress events for external agent UIs")
    rendered_progress: str = Field(default="", description="Canonical Chinese text progress block for agents without custom UI rendering")
    pid: Optional[int] = None
    pid_alive: bool = False
    message: str = ""
    log_tail: str = ""
    template_match: Optional[Dict[str, Any]] = None
    watch_elapsed_seconds: Optional[float] = None
    watch_reason: Optional[Literal["disabled", "progress_changed", "terminal", "timeout"]] = None


def _tail_text(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


def _default_case_key(requirement_path: Path, session_id: str | None) -> str:
    if session_id:
        return _safe_session_id(session_id) or "case"

    parent = requirement_path.parent.name
    if parent and parent not in {"sessions", "runs"}:
        return _safe_session_id(parent) or "case"
    return _safe_session_id(requirement_path.stem) or "case"


def _unique_execute_dir(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.name}-{index:03d}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find a free execute directory for {path}")


def _default_execute_dir(requirement_path: Path, session_id: str | None, now: datetime | None = None) -> Path:
    case_key = _default_case_key(requirement_path, session_id)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    base = REPO_ROOT / "runs" / f"mcp-execute-{case_key}-{stamp}"
    return _unique_execute_dir(base)


def _execute_command(
    requirement_path: Path,
    case_dir: Path,
    custom_mesh_path: str | None,
    reuse_generated_dir: str | None,
) -> list[str]:
    command = [
        sys.executable,
        "-u",
        str(REPO_ROOT / "src" / "main.py"),
        "--prompt_path",
        str(requirement_path),
        "--output_dir",
        str(case_dir),
    ]
    if custom_mesh_path:
        command.extend(["--custom_mesh_path", custom_mesh_path])
    if reuse_generated_dir:
        command.extend(["--reuse_generated_dir", reuse_generated_dir])
    return command


def _execute_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _pid_state(pid: int | None) -> str | None:
    if not pid:
        return None
    status_path = Path(f"/proc/{pid}/status")
    if not status_path.is_file():
        return None
    for line in status_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("State:"):
            parts = line.split()
            return parts[1] if len(parts) > 1 else None
    return None


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return _pid_state(pid) != "Z"


def _read_pid(case_dir: Path) -> int | None:
    path = case_dir / "foamagent_execute.pid"
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def _latest_solver_time(log_text: str) -> float | None:
    matches = re.findall(r"^Time = ([0-9]+(?:\.[0-9]+)?)", log_text, re.MULTILINE)
    return float(matches[-1]) if matches else None


def _control_value(control_text: str, name: str) -> float | None:
    match = re.search(rf"^\s*{re.escape(name)}\s+([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*;", control_text, re.MULTILINE)
    return float(match.group(1)) if match else None


def _progress_signature(status: "FoamAgentExecuteStatusResponse") -> tuple:
    return (
        status.status,
        status.current_stage,
        tuple(sorted(status.stages.items())),
        tuple(sorted(status.openfoam_substeps.items())),
        status.current_time,
        status.end_time,
        status.progress_percent,
    )




def _workflow_log_text(case_dir: Path) -> str:
    path = case_dir / "workflow.log"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _workflow_phase_markers(workflow_text: str) -> dict[str, bool]:
    return {
        "input_writer_started": "<input_writer" in workflow_text,
        "input_writer_finished": "</input_writer>" in workflow_text,
        "runner_started": "<runner>" in workflow_text,
        "schema_started": "<schema_preflight" in workflow_text or "Schema preflight" in workflow_text,
    }




def _xml_attr_value(attrs: str, name: str) -> str | None:
    match = re.search(rf'{re.escape(name)}="([^"]*)"', attrs)
    return match.group(1) if match else None


def _template_match_summary(case: Path, workflow_text: str) -> dict[str, Any] | None:
    import_path = case / "TUTORIAL_TEMPLATE_IMPORT.json"
    if import_path.is_file():
        try:
            data = json.loads(import_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        summary = {
            "source": "TUTORIAL_TEMPLATE_IMPORT.json",
            "template_id": data.get("template_id"),
            "tier": data.get("tier"),
            "rag_confidence": data.get("rag_confidence"),
            "matched_alias": data.get("matched_alias"),
            "import_policy": data.get("import_policy"),
            "source_directory": data.get("source_directory"),
        }
        if data.get("template_name"):
            summary["template_name"] = data.get("template_name")
        if data.get("solver"):
            summary["solver"] = data.get("solver")
        if data.get("parallel_policy"):
            summary["parallel_policy"] = data.get("parallel_policy")
        if data.get("start_policy"):
            summary["start_policy"] = data.get("start_policy")
        if data.get("run_user_policy"):
            summary["run_user_policy"] = data.get("run_user_policy")
        if data.get("certification"):
            summary["certification"] = data.get("certification")
        return summary

    match = re.search(r"<rheotool_tutorial_template_match\s+([^>]*)/>", workflow_text or "")
    if match:
        attrs = match.group(1)
        summary = {
            "source": "workflow.log",
            "template_id": _xml_attr_value(attrs, "id"),
            "tier": _xml_attr_value(attrs, "tier"),
            "rag_confidence": None,
            "matched_alias": _xml_attr_value(attrs, "alias"),
            "import_policy": "rheotool tutorial template import; no LLM dictionary regeneration",
        }
        template_name = _xml_attr_value(attrs, "name")
        solver = _xml_attr_value(attrs, "solver")
        if template_name:
            summary["template_name"] = template_name
        if solver:
            summary["solver"] = solver
        return summary

    candidate = re.search(r"<rheotool_tutorial_template_candidate\s+([^>]*)/>", workflow_text or "")
    if candidate:
        attrs = candidate.group(1)
        return {
            "source": "workflow.log",
            "template_id": _xml_attr_value(attrs, "id"),
            "tier": _xml_attr_value(attrs, "tier"),
            "rag_confidence": "medium",
            "import_policy": "not_imported_low_confidence",
            "candidate_only": True,
        }
    return None


def _summarize_execute_progress(case_dir: str | Path) -> FoamAgentExecuteStatusResponse:
    case = Path(case_dir)
    stages = {
        "0": "passed",
        "1": "passed",
        "2": "passed",
        "3": "pending",
        "4": "pending",
        "5": "pending",
        "6": "pending",
    }
    substeps = {
        "5.1": "pending",
        "5.2": "pending",
        "5.3": "pending",
        "5.4": "pending",
        "5.5": "pending",
        "5.6": "pending",
    }

    pid = _read_pid(case)
    alive = _pid_alive(pid)
    manifest: dict[str, Any] = {}
    manifest_path = case / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}

    solver = manifest.get("solver")
    workflow_text = _workflow_log_text(case)
    workflow_markers = _workflow_phase_markers(workflow_text)
    template_match = _template_match_summary(case, workflow_text)
    if manifest:
        stages["3"] = "passed" if workflow_markers["input_writer_finished"] else "running"

    log_tail = ""
    execute_log_text = ""
    execute_log = case / "foamagent_execute.log"
    if execute_log.is_file():
        execute_log_text = execute_log.read_text(encoding="utf-8", errors="ignore")
        log_tail = _tail_text(execute_log_text, 1200)

    block_log = case / "log.blockMesh"
    solver_log = case / f"log.{solver}" if solver else None
    if solver_log is None or not solver_log.is_file():
        for candidate in sorted(case.glob("log.*Foam")):
            solver_log = candidate
            solver = candidate.name.removeprefix("log.")
            break
    post_log = case / "log.postProcess"
    sample_log = case / "log.sample"

    if block_log.is_file():
        block_text = block_log.read_text(encoding="utf-8", errors="ignore")
        substeps["5.1"] = "passed"
        substeps["5.2"] = "passed" if "End" in block_text else "running"
        stages["3"] = "passed"
        stages["4"] = "passed"
        stages["5"] = "running"
    elif manifest and workflow_markers["runner_started"]:
        stages["3"] = "passed"
        stages["4"] = "running"

    current_time = None
    end_time = None
    progress_percent = None
    control_path = case / "system" / "controlDict"
    if control_path.is_file():
        control_text = control_path.read_text(encoding="utf-8", errors="ignore")
        end_time = _control_value(control_text, "endTime")

    if solver_log and solver_log.is_file():
        solver_text = solver_log.read_text(encoding="utf-8", errors="ignore")
        current_time = _latest_solver_time(solver_text)
        if end_time and current_time is not None:
            progress_percent = max(0.0, min(100.0, current_time / end_time * 100.0))
        solver_finished = "End" in solver_text and end_time and current_time is not None and current_time >= end_time
        if solver_finished:
            substeps["5.4"] = "passed"
        elif "FOAM FATAL ERROR" in solver_text or "Segmentation fault" in solver_text:
            substeps["5.4"] = "failed"
            substeps["5.6"] = "running"
            stages["5"] = "failed"
        elif end_time and current_time is not None and current_time >= end_time:
            substeps["5.4"] = "passed"
        else:
            substeps["5.4"] = "running"
            stages["5"] = "running"
        log_tail = _tail_text(solver_text, 1200)

    if post_log.is_file():
        post_text = post_log.read_text(encoding="utf-8", errors="ignore")
        substeps["5.5"] = "passed" if "End" in post_text else "running"
        log_tail = _tail_text(post_text, 1200)
    elif sample_log.is_file():
        sample_text = sample_log.read_text(encoding="utf-8", errors="ignore")
        if "command not found" in sample_text or "not found" in sample_text or "FOAM FATAL ERROR" in sample_text:
            substeps["5.5"] = "failed"
            substeps["5.6"] = "running"
            stages["5"] = "failed"
        else:
            substeps["5.5"] = "passed" if "End" in sample_text else "running"
        log_tail = _tail_text(sample_text, 1200)
    elif substeps["5.4"] == "passed":
        substeps["5.5"] = "running" if alive else "pending"

    validation_status = manifest.get("validation_status")
    run_status = manifest.get("run_status")
    if validation_status == "passed":
        stages["3"] = "passed"
        stages["4"] = "passed"
        substeps["5.1"] = "passed"
        substeps["5.3"] = "passed"
    elif validation_status == "failed":
        stages["3"] = "passed"
        stages["4"] = "failed"
        substeps["5.1"] = "passed"
        substeps["5.3"] = "failed"
    elif solver_log and solver_log.is_file():
        stages["3"] = "passed"
        stages["4"] = "passed"
        substeps["5.1"] = "passed"
        substeps["5.3"] = "passed"

    allrun_err = case / "Allrun.err"
    if allrun_err.is_file() and allrun_err.stat().st_size > 0:
        substeps["5.6"] = "running"
        stages["5"] = "failed" if not alive else "running"
        if substeps["5.5"] != "failed":
            log_tail = _tail_text(allrun_err.read_text(encoding="utf-8", errors="ignore"), 1200)

    execute_failed_before_case = (
        not manifest
        and not alive
        and any(marker in execute_log_text for marker in ("Traceback", "Maximum retries", "Error occurred in LLM service"))
    )

    active_solver_run = alive and stages["5"] == "running" and substeps.get("5.4") == "running"

    if run_status == "passed":
        stages["3"] = "passed"
        stages["4"] = "passed"
        stages["5"] = "passed"
        stages["6"] = "passed"
        for key, value in list(substeps.items()):
            if value in {"pending", "running"}:
                substeps[key] = "passed"
        status: Literal["running", "passed", "failed", "unknown"] = "passed"
        current_stage = "6"
        message = "Foam-Agent execution completed."
    elif active_solver_run:
        # A reuse/retry run can leave stale manifest validation/run failures while
        # the current Allrun/rheoFoam process is alive and writing fresh time
        # steps.  Prefer the live OpenFOAM signal over stale manifest state.
        stages["3"] = "passed"
        stages["4"] = "passed"
        stages["5"] = "running"
        substeps["5.1"] = "passed"
        substeps["5.2"] = "passed"
        substeps["5.3"] = "passed"
        substeps["5.4"] = "running"
        status = "running"
        current_stage = "5"
        if current_time is not None and end_time:
            message = f"{solver or 'solver'} running: Time={current_time:g}/{end_time:g}."
        else:
            message = "Foam-Agent execution is running."
    elif execute_failed_before_case:
        stages["3"] = "failed"
        status = "failed"
        current_stage = "3"
        message = "Foam-Agent case generation failed before case files were created; inspect logs."
    elif run_status in {"failed", "blocked"} or stages["4"] == "failed" or stages["5"] == "failed":
        status = "failed"
        current_stage = "5" if stages["4"] != "failed" else "4"
        message = "Foam-Agent execution failed; inspect logs."
    elif alive or stages["5"] == "running":
        status = "running"
        current_stage = "5" if stages["5"] == "running" else "4"
        if current_time is not None and end_time:
            message = f"{solver or 'solver'} running: Time={current_time:g}/{end_time:g}."
        else:
            message = "Foam-Agent execution is running."
    elif manifest:
        status = "running" if alive or stages["3"] == "running" or stages["4"] == "running" else "unknown"
        if stages["3"] == "running":
            current_stage = "3"
            message = "Foam-Agent case generation is running."
        elif stages["4"] == "running":
            current_stage = "4"
            message = "Foam-Agent schema/manifest validation is running."
        else:
            current_stage = "4"
            message = "Case exists but execution status is not final."
    else:
        status = "unknown"
        current_stage = "3"
        message = "Case files are not available yet."

    progress_events = build_progress_events(
        stages,
        substeps,
        solver=solver,
        current_time=current_time,
        end_time=end_time,
        progress_percent=progress_percent,
    )
    rendered_progress = render_progress_text(
        stages,
        substeps,
        solver=solver,
        current_time=current_time,
        end_time=end_time,
        progress_percent=progress_percent,
    )

    return FoamAgentExecuteStatusResponse(
        status=status,
        case_dir=str(case),
        current_stage=current_stage,
        stages=stages,
        openfoam_substeps=substeps,
        solver=solver,
        current_time=current_time,
        end_time=end_time,
        progress_percent=progress_percent,
        progress_events=progress_events,
        rendered_progress=rendered_progress,
        pid=pid,
        pid_alive=alive,
        message=message,
        log_tail=log_tail,
        template_match=template_match,
    )


def _watch_execute_progress(
    case_dir: str | Path,
    *,
    watch_seconds: int,
    poll_interval_seconds: int,
    return_on_progress: bool = True,
) -> FoamAgentExecuteStatusResponse:
    started = time.monotonic()
    latest = _summarize_execute_progress(case_dir)
    if watch_seconds <= 0:
        latest.watch_elapsed_seconds = 0.0
        latest.watch_reason = "disabled"
        return latest
    if latest.status in {"passed", "failed"}:
        latest.watch_elapsed_seconds = 0.0
        latest.watch_reason = "terminal"
        return latest

    initial_signature = _progress_signature(latest)
    deadline = started + watch_seconds
    while time.monotonic() < deadline:
        time.sleep(min(poll_interval_seconds, max(0.0, deadline - time.monotonic())))
        latest = _summarize_execute_progress(case_dir)
        if latest.status in {"passed", "failed"}:
            latest.watch_elapsed_seconds = round(time.monotonic() - started, 3)
            latest.watch_reason = "terminal"
            return latest
        if return_on_progress and _progress_signature(latest) != initial_signature:
            latest.watch_elapsed_seconds = round(time.monotonic() - started, 3)
            latest.watch_reason = "progress_changed"
            return latest

    latest.watch_elapsed_seconds = round(time.monotonic() - started, 3)
    latest.watch_reason = "timeout"
    return latest


def _start_foamagent_background(request: FoamAgentExecuteRequest) -> FoamAgentExecuteResponse:
    requirement_path = Path(request.requirement_path)
    if not requirement_path.is_file():
        raise ValueError(f"Requirement file does not exist: {requirement_path}")

    receipt = validate_receipt(requirement_path, request.receipt_path)
    receipt_path = request.receipt_path or str(requirement_path) + ".intake.json"
    case_dir = Path(request.output_dir) if request.output_dir else _default_execute_dir(requirement_path, request.session_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    log_path = case_dir / "foamagent_execute.log"
    command = _execute_command(requirement_path, case_dir, request.custom_mesh_path, request.reuse_generated_dir)

    log_path.write_text(
        "# Foam-Agent execute command\n"
        + " ".join(command)
        + "\n\n# mode\nbackground\n\n# stdout/stderr\n",
        encoding="utf-8",
    )
    log_file = log_path.open("a", encoding="utf-8")
    try:
        process = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            env=_execute_env(),
            text=True,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log_file.close()
    (case_dir / "foamagent_execute.pid").write_text(str(process.pid), encoding="utf-8")
    return FoamAgentExecuteResponse(
        status="running",
        case_dir=str(case_dir),
        requirement_path=str(requirement_path),
        receipt_path=receipt_path,
        log_path=str(log_path),
        returncode=None,
        target_preview=receipt.get("target_preview"),
        message="Foam-Agent execution started in background; poll foamagent_execute_status for progress.",
        pid=process.pid,
    )


def _run_foamagent_main(request: FoamAgentExecuteRequest) -> FoamAgentExecuteResponse:
    requirement_path = Path(request.requirement_path)
    if not requirement_path.is_file():
        raise ValueError(f"Requirement file does not exist: {requirement_path}")

    receipt = validate_receipt(requirement_path, request.receipt_path)
    receipt_path = request.receipt_path or str(requirement_path) + ".intake.json"
    case_dir = Path(request.output_dir) if request.output_dir else _default_execute_dir(requirement_path, request.session_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    log_path = case_dir / "foamagent_execute.log"

    command = _execute_command(requirement_path, case_dir, request.custom_mesh_path, request.reuse_generated_dir)

    try:
        completed = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            env=_execute_env(),
            text=True,
            capture_output=True,
            timeout=request.timeout_seconds,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        log_path.write_text(
            "# Foam-Agent execute command\n"
            + " ".join(command)
            + "\n\n# stdout\n"
            + stdout
            + "\n\n# stderr\n"
            + stderr,
            encoding="utf-8",
        )
        status: Literal["passed", "failed"] = "passed" if completed.returncode == 0 else "failed"
        message = "Foam-Agent execution completed" if status == "passed" else "Foam-Agent execution failed; inspect log_path"
        return FoamAgentExecuteResponse(
            status=status,
            case_dir=str(case_dir),
            requirement_path=str(requirement_path),
            receipt_path=receipt_path,
            log_path=str(log_path),
            returncode=completed.returncode,
            target_preview=receipt.get("target_preview"),
            message=message,
            stdout_tail=_tail_text(stdout),
            stderr_tail=_tail_text(stderr),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        log_path.write_text(
            "# Foam-Agent execute command\n"
            + " ".join(command)
            + f"\n\n# timeout\nTimed out after {request.timeout_seconds} seconds\n\n# stdout\n"
            + stdout
            + "\n\n# stderr\n"
            + stderr,
            encoding="utf-8",
        )
        return FoamAgentExecuteResponse(
            status="failed",
            case_dir=str(case_dir),
            requirement_path=str(requirement_path),
            receipt_path=receipt_path,
            log_path=str(log_path),
            returncode=None,
            target_preview=receipt.get("target_preview"),
            message=f"Foam-Agent execution timed out after {request.timeout_seconds} seconds",
            stdout_tail=_tail_text(stdout),
            stderr_tail=_tail_text(stderr),
        )


@mcp.tool(name="foamagent_execute")
async def foamagent_execute(
    request: FoamAgentExecuteRequest,
    ctx: Context,
) -> FoamAgentExecuteResponse:
    """Execute Foam-Agent main workflow for a stamped ready requirement.

    This product-level tool validates the intake receipt first, then runs the
    existing Foam-Agent main workflow. It returns a case directory and execution
    log path. If the internal Foam-Agent LLM provider is not configured, the
    response is `failed` with details in `log_path` instead of exposing legacy
    step tools to the external agent.
    """
    try:
        await ctx.info(f"Executing Foam-Agent workflow for {request.requirement_path}")
        if request.background:
            return await asyncio.to_thread(_start_foamagent_background, request)
        return await asyncio.to_thread(_run_foamagent_main, request)
    except Exception as e:
        await ctx.error(f"Foam-Agent execute failed: {str(e)}")
        raise


@mcp.tool(name="foamagent_execute_status")
async def foamagent_execute_status(
    request: FoamAgentExecuteStatusRequest,
    ctx: Context,
) -> FoamAgentExecuteStatusResponse:
    """Read Foam-Agent/OpenFOAM logs and return Chinese-progress-friendly execution status."""
    try:
        if request.watch_seconds:
            await ctx.info(
                f"Watching Foam-Agent execution status for {request.case_dir} "
                f"up to {request.watch_seconds}s"
            )
            return await asyncio.to_thread(
                _watch_execute_progress,
                request.case_dir,
                watch_seconds=request.watch_seconds,
                poll_interval_seconds=request.poll_interval_seconds,
                return_on_progress=not request.wait_until_terminal,
            )
        await ctx.info(f"Reading Foam-Agent execution status for {request.case_dir}")
        return await asyncio.to_thread(_summarize_execute_progress, request.case_dir)
    except Exception as e:
        await ctx.error(f"Foam-Agent execute status failed: {str(e)}")
        raise


class FoamAgentPostprocessRequest(BaseModel):
    """Request to run deterministic post-processing for an existing case."""
    case_dir: str = Field(description="OpenFOAM case directory")
    user_requirement: str = Field(default="", description="Business objective for post-processing")
    fields: List[str] = Field(default_factory=lambda: ["U", "p", "tau"], description="Fields to plot/sample")
    run_openfoam_sample: bool = Field(default=True, description="Run sampleDict if system/sampleDict exists")


class FoamAgentPostprocessResponse(BaseModel):
    """Structured postprocess response."""
    status: str
    case_dir: str
    latest_time: Optional[str] = None
    report_json: Optional[str] = None
    summary_markdown: Optional[str] = None
    artifacts_json: Optional[str] = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)


@mcp.tool(name="foamagent_postprocess")
async def foamagent_postprocess(
    request: FoamAgentPostprocessRequest,
    ctx: Context
) -> FoamAgentPostprocessResponse:
    """Run standard Foam-Agent post-processing and visualization for a completed case."""
    try:
        if not os.path.isdir(request.case_dir):
            raise ValueError(f"Case directory does not exist: {request.case_dir}")
        await ctx.info(f"Running Foam-Agent postprocess for {request.case_dir}")
        report = await asyncio.to_thread(
            run_standard_postprocess,
            request.case_dir,
            user_requirement=request.user_requirement,
            fields=tuple(request.fields),
            run_openfoam_sample=request.run_openfoam_sample,
        )
        return FoamAgentPostprocessResponse(
            status=report.get("status", "unknown"),
            case_dir=report.get("case_dir", request.case_dir),
            latest_time=report.get("latest_time"),
            report_json=report.get("report_json"),
            summary_markdown=report.get("summary_markdown"),
            artifacts_json=report.get("artifacts_json"),
            artifacts=report.get("artifacts", []),
            metrics=report.get("metrics", {}),
        )
    except Exception as e:
        await ctx.error(f"Foam-Agent postprocess failed: {str(e)}")
        raise


class FoamAgentArtifactsRequest(BaseModel):
    """Request to list Foam-Agent artifacts for a case."""
    case_dir: str = Field(description="OpenFOAM case directory")


class FoamAgentArtifactsResponse(BaseModel):
    """Artifact manifest response."""
    case_dir: str
    artifacts: List[Dict[str, Any]]
    artifacts_json: Optional[str] = None


@mcp.tool(name="foamagent_artifacts")
async def foamagent_artifacts(
    request: FoamAgentArtifactsRequest,
    ctx: Context
) -> FoamAgentArtifactsResponse:
    """Return postprocess/report artifacts without rerunning the case."""
    try:
        if not os.path.isdir(request.case_dir):
            raise ValueError(f"Case directory does not exist: {request.case_dir}")
        manifest = _read_artifact_manifest(request.case_dir)
        artifacts_path = Path(request.case_dir) / "POSTPROCESS_ARTIFACTS.json"
        await ctx.info(f"Found {len(manifest.get('artifacts', []))} artifact(s)")
        return FoamAgentArtifactsResponse(
            case_dir=str(request.case_dir),
            artifacts=manifest.get("artifacts", []),
            artifacts_json=str(artifacts_path) if artifacts_path.is_file() else None,
        )
    except Exception as e:
        await ctx.error(f"Foam-Agent artifact listing failed: {str(e)}")
        raise


class FoamAgentCaseEvolutionRequest(BaseModel):
    """Request to evaluate a successful case for knowledge evolution."""
    case_dir: str = Field(description="Completed Foam-Agent case directory")
    action: Literal["evaluate"] = Field(default="evaluate", description="Only evaluate is supported; promotion requires explicit non-MCP tooling")


class FoamAgentCaseEvolutionResponse(BaseModel):
    """Case evolution response."""
    decision: Optional[str] = None
    nearest_match: Optional[str] = None
    candidate_path: Optional[str] = None
    requires_user_approval: bool = True
    report: Dict[str, Any] = Field(default_factory=dict)


@mcp.tool(name="foamagent_case_evolution")
async def foamagent_case_evolution(
    request: FoamAgentCaseEvolutionRequest,
    ctx: Context
) -> FoamAgentCaseEvolutionResponse:
    """Evaluate whether a successful case is duplicate or a novel candidate.

    This tool never promotes a candidate into certified benchmarks. Promotion
    remains an explicit user-confirmed repository operation.
    """
    try:
        if request.action != "evaluate":
            raise ValueError("Only action='evaluate' is supported by MCP")
        if not os.path.isdir(request.case_dir):
            raise ValueError(f"Case directory does not exist: {request.case_dir}")
        await ctx.info(f"Evaluating case evolution for {request.case_dir}")
        report = await asyncio.to_thread(evaluate_successful_case_for_evolution, request.case_dir)
        coverage = report.get("coverage_status", {})
        candidate = report.get("candidate") or {}
        return FoamAgentCaseEvolutionResponse(
            decision=coverage.get("decision"),
            nearest_match=coverage.get("nearest_match"),
            candidate_path=candidate.get("candidate_path"),
            requires_user_approval=coverage.get("decision") == "novel_candidate",
            report=report,
        )
    except Exception as e:
        await ctx.error(f"Foam-Agent case evolution failed: {str(e)}")
        raise


# ============================================================================
# Tool: plan
# ============================================================================

class PlanRequest(BaseModel):
    """Request to plan simulation structure."""
    user_requirement: str = Field(description="User requirements for the simulation")


class PlanResponse(BaseModel):
    """Response from simulation planning."""
    subtasks: List[Dict[str, str]] = Field(description="List of subtasks with file and folder information")
    case_name: str = Field(description="Generated case name")
    case_solver: str = Field(description="OpenFOAM solver to use")
    case_domain: str = Field(description="Simulation domain (e.g., 'fluid', 'solid')")
    case_category: str = Field(description="Case category (e.g., 'tutorial', 'advanced')")
    channel: Literal["v9-rheotool", "v10-foundation"]
    version: Literal["v9", "v10"]
    distribution: Literal["foundation+rheotool", "foundation"]


@mcp.tool(name="plan")
async def plan(
    request: PlanRequest,
    ctx: Context
) -> PlanResponse:
    """Plan the simulation structure by analyzing requirements and generating subtasks.

    This function uses AI to break down user requirements into manageable subtasks
    for OpenFOAM file generation.
    """
    try:
        await ctx.info("Planning simulation structure from user requirements")
        
        # Load case statistics, available domains, categories, and solvers
        case_stats_path = os.path.join(global_config.database_path, "raw", "openfoam_case_stats.json")
        with open(case_stats_path, 'r') as f:
            case_stats = json.load(f)
        
        # Generate simulation plan
        plan_data = generate_simulation_plan(
            user_requirement=request.user_requirement,
            case_stats=case_stats,
            case_dir="",  # Will be resolved later
            searchdocs=global_config.searchdocs,
        )
        
        await ctx.info(f"Generated {len(plan_data['subtasks'])} subtasks")
        
        # Convert subtasks to PlanResponse format
        subtasks = [{"file": s["file_name"], "folder": s["folder_name"]} for s in plan_data["subtasks"]]
        
        return PlanResponse(
            subtasks=subtasks,
            case_name=plan_data["case_name"],
            case_solver=plan_data["case_solver"],
            case_domain=plan_data["case_domain"],
            case_category=plan_data["case_category"],
            channel=plan_data["channel"],
            version=plan_data["version"],
            distribution=plan_data["distribution"],
        )
        
    except Exception as e:
        await ctx.error(f"Failed to plan simulation: {str(e)}")
        raise


# ============================================================================
# Tool: input_writer
# ============================================================================

class GenerateFilesRequest(BaseModel):
    """Request to generate OpenFOAM files."""
    case_name: str = Field(description="Case name (from plan response)")
    subtasks: List[Dict[str, str]] = Field(description="List of subtasks to generate files for")
    user_requirement: str = Field(description="User requirements")
    case_solver: str = Field(description="OpenFOAM solver to use")
    case_domain: str = Field(description="Simulation domain")
    case_category: str = Field(description="Case category")


class GenerateFilesResponse(BaseModel):
    """Response from file generation."""
    case_dir: str = Field(description="Path to the case directory")
    foamfiles: FoamPydantic = Field(description="Generated OpenFOAM files with metadata")
    allrun_script: str = Field(description="Path to the generated Allrun script")


@mcp.tool(name="input_writer")
async def input_writer(
    request: GenerateFilesRequest,
    ctx: Context
) -> GenerateFilesResponse:
    """Generate OpenFOAM input files based on subtasks and requirements.

    This function creates all necessary OpenFOAM input files (system/, constant/, 0/).
    It generates files using Foundation v10 conventions by default. If
    FOAMAGENT_OPENFOAM_FORK=esi is set, it applies a best-effort post-generation
    translation to ESI naming and dictionary conventions before returning files.
    """
    try:
        await ctx.info(f"Generating OpenFOAM files for case: {request.case_name}")

        # Resolve case directory
        case_dir = resolve_case_dir(
            case_name=request.case_name,
            case_dir="",
            run_times=global_config.run_times
        )

        await ctx.info(f"Case directory: {case_dir}")

        # Load case statistics and retrieve references
        case_stats_path = os.path.join(global_config.database_path, "raw", "openfoam_case_stats.json")
        with open(case_stats_path, 'r') as f:
            case_stats = json.load(f)

        # Build case info from request
        case_target = case_target_from_manifest(request.case_dir)
        case_info = {
            "case_name": request.case_name,
            "case_solver": request.case_solver,
            "case_domain": request.case_domain,
            "case_category": request.case_category
        }

        await ctx.info(f"Case info: {case_info}")

        # Retrieve references
        tutorial_reference, dir_structure, dir_counts_str, allrun_reference, similar_case_advice = retrieve_references(
            case_name=case_info["case_name"],
            case_solver=case_info["case_solver"],
            case_domain=case_info["case_domain"],
            case_category=case_info["case_category"],
            searchdocs=global_config.searchdocs,
        )

        # Convert subtasks format from {file, folder} to {file_name, folder_name}
        converted_subtasks = []
        for st in request.subtasks:
            if isinstance(st, dict):
                # Handle both formats: {file, folder} or {file_name, folder_name}
                file_name = st.get("file_name") or st.get("file")
                folder_name = st.get("folder_name") or st.get("folder")
                if file_name and folder_name:
                    converted_subtasks.append({
                        "file_name": file_name,
                        "folder_name": folder_name
                    })
                else:
                    raise ValueError(f"Invalid subtask format: {st}. Must have 'file'/'file_name' and 'folder'/'folder_name'")
            else:
                raise ValueError(f"Invalid subtask type: {type(st)}. Expected dict, got {st}")

        await ctx.info(f"converted_subtasks: {converted_subtasks}")

        # Create a sync callback that bridges to async ctx.report_progress.
        # initial_write() is synchronous and will run in a worker thread via
        # asyncio.to_thread(), so we use run_coroutine_threadsafe to schedule
        # progress notifications on the event loop from that thread.
        loop = asyncio.get_running_loop()

        def progress_callback(current: int, total: int, message: str) -> None:
            future = asyncio.run_coroutine_threadsafe(
                ctx.report_progress(current, total, message),
                loop
            )
            try:
                future.result(timeout=5.0)
            except Exception:
                pass  # Don't fail generation if progress reporting fails

        # Run blocking initial_write in a thread to keep the event loop free
        # for sending progress notifications
        result = await asyncio.to_thread(
            initial_write,
            case_dir=case_dir,
            subtasks=converted_subtasks,
            user_requirement=request.user_requirement,
            tutorial_reference=tutorial_reference,
            case_target=CaseTarget.for_solver(request.case_solver),
            case_info=str(case_info),
            allrun_reference=allrun_reference,
            database_path=str(global_config.database_path),
            searchdocs=global_config.searchdocs,
            similar_case_advice=similar_case_advice,
            progress_callback=progress_callback,
        )

        await ctx.info(f"result: {result}")

        # Get foamfiles from result
        foamfiles = result.get("foamfiles")
        if not foamfiles:
            raise ValueError("No foamfiles returned from initial_write")

        # Convert to ESI if needed
        convert_case_to_esi_if_needed(case_dir, global_config)
        
        # Rescan the directory and foam files to reflect any translations
        dir_structure = scan_case_directory(case_dir)
        foamfiles = read_case_foamfiles(case_dir, dir_structure)

        if not foamfiles:
            raise ValueError("No foamfiles returned after translation")

        allrun_script = os.path.join(case_dir, "Allrun")

        num_files = len(foamfiles.list_foamfile) if hasattr(foamfiles, "list_foamfile") else 0
        await ctx.info(f"Generated {num_files} OpenFOAM files in {case_dir}")

        return GenerateFilesResponse(
            case_dir=case_dir,
            foamfiles=foamfiles,
            allrun_script=allrun_script
        )

    except Exception as e:
        await ctx.error(f"Failed to generate OpenFOAM files: {str(e)}")
        raise


# ============================================================================
# Tool: run
# ============================================================================

class RunSimulationRequest(BaseModel):
    """Request to run local simulation."""
    case_dir: str = Field(description="Path to the case directory")
    timeout: int = Field(default=3600, description="Timeout in seconds")
    channel: Literal["v9-rheotool", "v10-foundation"] = Field(
        description="Certified OpenFOAM execution channel"
    )


class RunSimulationResponse(BaseModel):
    """Response from simulation run."""
    status: str = Field(description="Run status: 'success' or 'failed'")
    errors: List[str] = Field(description="List of errors found")
    log_files: Dict[str, str] = Field(description="Paths to log files")


@mcp.tool(name="run")
async def run(
    request: RunSimulationRequest,
    ctx: Context
) -> RunSimulationResponse:
    """Run the OpenFOAM simulation locally.

    This function executes the Allrun script and collects any errors.
    It is primarily validated with Foundation OpenFOAM v10 (openfoam.org). Cases translated
    with FOAMAGENT_OPENFOAM_FORK=esi may run on ESI OpenFOAM, but that path is experimental
    and depends on the active OpenFOAM environment.
    """
    try:
        await ctx.info(f"Running simulation in directory: {request.case_dir}")
        
        # Validate case directory exists
        if not os.path.exists(request.case_dir):
            raise ValueError(f"Case directory does not exist: {request.case_dir}")
        
        # Run locally
        error_logs = run_allrun_and_collect_errors(
            case_dir=request.case_dir,
            timeout=request.timeout,
            max_retries=3,
            channel=request.channel,
        )
        
        # Convert error logs to strings if they're dictionaries
        errors = []
        for err in error_logs:
            if isinstance(err, dict):
                # Format: "file: error_content"
                file_name = err.get("file", "unknown")
                error_content = err.get("error_content", str(err))
                errors.append(f"{file_name}: {error_content}")
            else:
                errors.append(str(err))
        
        # Prepare log file paths (not content)
        log_files = {}
        out_path = os.path.join(request.case_dir, 'Allrun.out')
        err_path = os.path.join(request.case_dir, 'Allrun.err')
        
        if os.path.exists(out_path):
            log_files['Allrun.out'] = out_path
        
        if os.path.exists(err_path):
            log_files['Allrun.err'] = err_path
        
        status = "success" if not errors else "failed"
        
        await ctx.info(f"Simulation {status} with {len(errors)} error(s)")
        
        return RunSimulationResponse(
            status=status,
            errors=errors,
            log_files=log_files
        )
            
    except Exception as e:
        await ctx.error(f"Failed to run simulation: {str(e)}")
        raise


# ============================================================================
# Tool: review
# ============================================================================

class ReviewRequest(BaseModel):
    """Request to review simulation errors."""
    case_dir: str = Field(description="Path to the case directory")
    errors: List[str] = Field(description="List of error messages from simulation")
    user_requirement: str = Field(description="Original user requirements")


class ReviewResponse(BaseModel):
    """Response from simulation review."""
    analysis: str = Field(description="Analysis of simulation errors")


@mcp.tool(name="review")
async def review(
    request: ReviewRequest,
    ctx: Context
) -> ReviewResponse:
    """Review simulation errors and suggest improvements.

    This function analyzes simulation errors and provides suggestions for fixes.
    The RAG references and fix reasoning are based on Foundation OpenFOAM v10 tutorials.
    ESI-translated cases can be reviewed, but suggested fixes should be treated as best-effort.
    """
    try:
        await ctx.info(f"Reviewing errors for case directory: {request.case_dir}")
        
        # Validate case directory exists
        if not os.path.exists(request.case_dir):
            raise ValueError(f"Case directory does not exist: {request.case_dir}")
        
        # Load case statistics
        case_stats_path = os.path.join(global_config.database_path, "raw", "openfoam_case_stats.json")
        with open(case_stats_path, 'r') as f:
            case_stats = json.load(f)
        
        # Extract case name from case_dir for reference lookup
        case_name = os.path.basename(request.case_dir)
        
        # Get tutorial reference
        case_info = {
            "case_name": case_name,
            "case_solver": case_target.solver,
            "case_domain": "fluid",
            "case_category": "tutorial"
        }
        
        tutorial_reference, _, _, _, _ = retrieve_references(
            case_name=case_info["case_name"],
            case_solver=case_info["case_solver"],
            case_domain=case_info["case_domain"],
            case_category=case_info["case_category"],
            searchdocs=global_config.searchdocs,
        )
        
        # Read current foamfiles from case directory for review context
        await ctx.info("Reading OpenFOAM files for review context...")
        from utils import read_case_foamfiles
        foamfiles = read_case_foamfiles(request.case_dir)
        await ctx.info(f"Read {len(foamfiles.list_foamfile)} file(s) for review")
        
        # Review results - directly call review_error_logs
        review_content, _ = review_error_logs(
            tutorial_reference=tutorial_reference,
            foamfiles=foamfiles,
            error_logs=request.errors,
            user_requirement=request.user_requirement,
            case_target=case_target,
            history_text=None
        )
        
        await ctx.info(f"Review completed, found {len(request.errors)} error(s)")
        
        # Format response (suggestions and issues are empty as review_error_logs only returns analysis)
        return ReviewResponse(
            analysis=review_content
        )
        
    except Exception as e:
        await ctx.error(f"Failed to review results: {str(e)}")
        raise


# ============================================================================
# Tool: apply_fixes
# ============================================================================

class ApplyFixesRequest(BaseModel):
    """Request to apply fixes to an OpenFOAM case based on review analysis."""
    case_dir: str = Field(description="Path to the OpenFOAM case directory")
    error_logs: List[str] = Field(description="List of error log messages from simulation")
    review_analysis: str = Field(description="Review analysis with fix suggestions from the review tool. Must be provided.")
    user_requirement: str = Field(description="Original user requirements or simulation description for context")


class ApplyFixesResponse(BaseModel):
    """Response from applying fixes."""
    updated_files: List[str] = Field(description="List of file paths that were updated")
    status: str = Field(description="Fix application status ('ok' or 'no_changes')")


@mcp.tool(name="apply_fixes")
async def apply_fixes(
    request: ApplyFixesRequest,
    ctx: Context
) -> ApplyFixesResponse:
    """Apply fixes to the OpenFOAM case files based on review analysis.

    This tool rewrites OpenFOAM files to fix errors identified during review.
    It must be called after the 'review' tool has provided analysis.
    Fix generation targets Foundation OpenFOAM v10 conventions by default. If the case is
    later translated with FOAMAGENT_OPENFOAM_FORK=esi, those fixes are best-effort for ESI.
    
    The tool directly calls rewrite_files which handles:
    - Reading current foamfiles and directory structure from case_dir
    - Using LLM to generate corrected file contents based on review_analysis
    - Writing updated files back to the case directory
    
    Workflow:
    1. First call 'review' tool to get review_analysis
    2. Then call 'apply_fixes' with the review_analysis to rewrite files
    
    Args:
        request: ApplyFixesRequest containing:
            - case_dir: Path to the OpenFOAM case directory
            - error_logs: List of error messages from simulation
            - review_analysis: Analysis and fix suggestions from review tool (required)
            - user_requirement: Original user requirements (optional)
    
    Returns:
        ApplyFixesResponse with list of updated files and status
    
    Raises:
        ValueError: If case directory does not exist or review_analysis is empty
        RuntimeError: If fix application fails
    
    Example:
        # Two-step workflow (review first, then fix)
        review_resp = await review(case_dir, errors, user_requirement)
        fix_resp = await apply_fixes(case_dir, errors, review_resp.analysis, user_requirement)
    """
    try:
        await ctx.info(f"Applying fixes for case directory: {request.case_dir}")
        
        # Validate case directory exists
        if not os.path.exists(request.case_dir):
            raise ValueError(f"Case directory does not exist: {request.case_dir}")
        
        # Validate review_analysis is provided
        if not request.review_analysis or request.review_analysis.strip() == "":
            raise ValueError(
                "review_analysis is required. Please call the 'review' tool first "
                "to get review analysis, then provide it to this tool."
            )
        
        await ctx.info("Rewriting OpenFOAM files based on review analysis...")
        
        # Directly call rewrite_files - it now handles file reading internally
        from services.input_writer import rewrite_files
        
        result = rewrite_files(
            case_dir=request.case_dir,
            error_logs=request.error_logs,
            review_analysis=request.review_analysis,
            rewrite_plan=None,
            user_requirement=request.user_requirement,
            case_target=case_target_from_manifest(request.case_dir),
            # foamfiles and dir_structure will be read automatically if None
        )
        
        # Extract written file paths
        written_files = []
        if result.get("foamfiles") and hasattr(result["foamfiles"], "list_foamfile"):
            for foamfile in result["foamfiles"].list_foamfile:
                file_path = os.path.join(request.case_dir, foamfile.folder_name, foamfile.file_name)
                written_files.append(file_path)
        
        status = "ok" if written_files else "no_changes"
        
        await ctx.info(f"Successfully applied fixes. Updated {len(written_files)} file(s)")
        
        return ApplyFixesResponse(
            updated_files=written_files,
            status=status
        )
        
    except Exception as e:
        await ctx.error(f"Failed to apply fixes: {str(e)}")
        raise


# ============================================================================
# Tool: visualization
# ============================================================================

class VisualizationRequest(BaseModel):
    """Request to generate visualization."""
    case_dir: str = Field(description="Path to the case directory")
    quantity: str = Field(description="Quantity to visualize (e.g., 'velocity', 'pressure')")
    visualization_type: str = Field(default="pyvista", description="Visualization type")


class VisualizationResponse(BaseModel):
    """Response from visualization generation."""
    artifacts: List[str] = Field(description="List of generated visualization files")
    script: str = Field(description="Visualization script")


@mcp.tool(name="visualization")
async def visualization(
    request: VisualizationRequest,
    ctx: Context
) -> VisualizationResponse:
    """Generate visualization for the simulation results.

    This function creates visualization artifacts using PyVista.
    It is primarily validated with Foundation OpenFOAM v10 outputs; ESI outputs should be
    verified per case.
    """
    try:
        await ctx.info(f"Generating visualization for case directory: {request.case_dir}")
        
        # Validate case directory exists
        if not os.path.exists(request.case_dir):
            raise ValueError(f"Case directory does not exist: {request.case_dir}")
        
        # Ensure foam file exists
        foam_file = ensure_foam_file(request.case_dir)
        
        quantity = request.quantity.lower()
        field = "p" if "pressure" in quantity else "U" if "velocity" in quantity else request.quantity
        output_png = "visualization.png"

        # Prefer deterministic visualization with deterministic artifact detection.
        script = generate_deterministic_pyvista_script(
            foam_file=foam_file,
            output_png=output_png,
            field_preference=field,
        )
        ok, img, errs = run_pyvista_script(
            request.case_dir,
            script,
            filename="visualization.py",
            expected_png=output_png,
        )

        if ok and img:
            artifacts = [img]
        else:
            # Fall back to LLM-generated script while still requiring the same artifact path.
            script = generate_pyvista_script(
                case_dir=request.case_dir,
                foam_file=foam_file,
                user_requirement=request.quantity,
                previous_errors=errs,
            )
            ok, img, errs = run_pyvista_script(
                request.case_dir,
                script,
                filename="visualization_llm.py",
                expected_png=output_png,
            )
            if ok and img:
                artifacts = [img]
            else:
                fixed = fix_pyvista_script(foam_file, script, errs)
                ok2, img2, errs2 = run_pyvista_script(
                    request.case_dir,
                    fixed,
                    filename="visualization_fixed.py",
                    expected_png=output_png,
                )
                artifacts = [img2] if ok2 and img2 else []
        
        await ctx.info(f"Generated {len(artifacts)} visualization artifact(s)")
        
        return VisualizationResponse(
            artifacts=artifacts,
            script=script
        )
        
    except Exception as e:
        await ctx.error(f"Failed to generate visualization: {str(e)}")
        raise



if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="FastMCP OpenFOAM Agent Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="http",
        help="Transport method (default: http)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port for HTTP transport (default: 7860)"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host for HTTP transport (default: localhost)"
    )
    
    args = parser.parse_args()
    
    if args.transport == "stdio":
        mcp.run("stdio")
    else:
        # Configure uvicorn with correct websockets setting
        uvicorn_config = {"ws": "websockets"}
        mcp.run("http", host=args.host, port=args.port, uvicorn_config=uvicorn_config)


# run the server:
# python -m src.mcp.fastmcp_server --transport http --host 0.0.0.0 --port 7860
