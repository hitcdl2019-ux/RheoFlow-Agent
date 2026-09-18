# runner_node.py
from typing import List
import os
from pydantic import BaseModel, Field
import re

from services.run_local import run_allrun_and_collect_errors
from services.solver_schema_validator import preflight_validate_case
from services.case_manifest import validate_case_manifest, update_case_manifest_status
from services.case_evolution import evaluate_successful_case_for_evolution
from services.foundation_templates import (
    is_foundation_multi_case_template,
    summarize_foundation_multi_case,
)
from logger import log_review


def local_runner_node(state):
    """
    Runner node: Execute an Allrun script, and check for errors.
    On error, update state.error_command and state.error_content.
    """
    config = state["config"]
    case_dir = state["case_dir"]
    max_time_limit = state["config"].max_time_limit

    print("<runner>")

    schema_validation = None
    case_target = state.get("case_target")
    if case_target is None:
        raise ValueError("CaseTarget is missing; refusing to run without an explicit OpenFOAM channel")

    try:
        validate_case_manifest(case_dir, case_target)
    except (ValueError, OSError) as exc:
        error_logs = [str(exc)]
        log_review(str(error_logs), "error_logs")
        print("</runner>")
        return {**state, "error_logs": error_logs, "schema_validation": None}

    if is_foundation_multi_case_template(case_dir):
        schema_validation = {
            "ok": True,
            "solver": case_target.solver,
            "case_dir": case_dir,
            "multi_case": True,
            "issues": [],
        }
        print(f"<schema_preflight solver=\"{case_target.solver}\" status=\"PASS\" multi_case=\"true\">")
        print("Official Foundation multi-case tutorial import; root directory is a tutorial driver, subcases are validated by execution logs.")
        print("</schema_preflight>")
    else:
        validation_result = preflight_validate_case(
            case_dir, case_target.version, case_target.solver
        )
        if validation_result is not None:
            schema_validation = validation_result.as_dict()
            status = "PASS" if validation_result.ok else "FAIL"
            print(f"<schema_preflight solver=\"{validation_result.solver}\" status=\"{status}\">")
            for issue in validation_result.issues:
                path = f" [{issue.path}]" if issue.path else ""
                print(f"{issue.level.upper()} {issue.code}{path}: {issue.message}")
            print("</schema_preflight>")

            if not validation_result.ok:
                update_case_manifest_status(
                    case_dir, case_target, validation_status="failed", run_status="blocked"
                )
                error_logs = [
                    "Schema preflight validation failed before running Allrun:\n"
                    + "\n".join(
                        f"{issue.level.upper()} {issue.code}"
                        + (f" [{issue.path}]" if issue.path else "")
                        + f": {issue.message}"
                        for issue in validation_result.issues
                    )
                ]
                print("Schema preflight failed; skipping Allrun execution.")
                log_review(str(error_logs), "error_logs")
                print("</runner>")
                return {
                    **state,
                    "error_logs": error_logs,
                    "schema_validation": schema_validation,
                }
        else:
            error_logs = [
                f"SOLVER_SCHEMA_MISSING: no {case_target.version} schema registered for "
                f"{case_target.solver}"
            ]
            update_case_manifest_status(
                case_dir, case_target, validation_status="failed", run_status="blocked"
            )
            log_review(str(error_logs), "error_logs")
            print("</runner>")
            return {**state, "error_logs": error_logs, "schema_validation": None}

    # Execute using service and collect errors
    error_logs = run_allrun_and_collect_errors(
        case_dir, max_time_limit, channel=case_target.channel
    )
    update_case_manifest_status(
        case_dir,
        case_target,
        validation_status="passed",
        run_status="passed" if not error_logs else "failed",
    )

    if len(error_logs) > 0:
        print("Errors detected in the Allrun execution.")
        log_review(str(error_logs), "error_logs")
    else:
        print("Allrun executed successfully without errors.")
        multi_case_summary = summarize_foundation_multi_case(case_dir)
        if multi_case_summary:
            print(
                f"<foundation_multi_case_summary all_passed=\"{multi_case_summary.get('all_passed')}\" "
                f"path=\"FOUNDATION_MULTI_CASE_SUMMARY.json\"/>"
            )
        try:
            evolution_report = evaluate_successful_case_for_evolution(case_dir)
            decision = evolution_report.get("coverage_status", {}).get("decision")
            candidate = evolution_report.get("candidate")
            if candidate:
                print(
                    f"<case_evolution decision=\"{decision}\" "
                    f"candidate=\"{candidate.get('candidate_id')}\"/>"
                )
            else:
                nearest = evolution_report.get("coverage_status", {}).get("nearest_match")
                print(
                    f"<case_evolution decision=\"{decision}\" "
                    f"nearest_match=\"{nearest}\"/>"
                )
        except Exception as exc:
            print(f"<case_evolution status=\"skipped\" reason=\"{exc}\"/>")

    print("</runner>")

    # Return updated state
    return {
        **state,
        "error_logs": error_logs,
        "schema_validation": schema_validation,
    }
