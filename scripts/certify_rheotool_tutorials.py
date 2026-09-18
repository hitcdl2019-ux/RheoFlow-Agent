#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from services.rheotool_templates import (  # noqa: E402
    DEFAULT_RHEOTOOL_TUTORIAL_ROOT,
    RHEOTOOL_TEMPLATE_DEFINITIONS,
    _template_payload_from_id,
    import_rheotool_tutorial_template,
)
from services.solver_schema_validator import preflight_validate_case  # noqa: E402


def _run_openfoam_command(case_dir: Path, command: str, log_name: str, timeout_s: int) -> dict[str, Any]:
    log_path = case_dir / log_name
    bashrc = os.environ.get("FOAMAGENT_OPENFOAM9_BASHRC", "/opt/openfoam9/etc/bashrc")
    script = f'source "{bashrc}" >/dev/null 2>&1 || true; cd "{case_dir}"; {command}'
    started = time.time()
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.run(
            ["bash", "-lc", script],
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    return {
        "command": command,
        "returncode": proc.returncode,
        "status": "passed" if proc.returncode == 0 else "failed",
        "elapsed_s": round(time.time() - started, 3),
        "log_path": str(log_path),
        "log_tail": _tail(log_path),
    }


def _tail(path: Path, max_lines: int = 40) -> str:
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(lines[-max_lines:])


def _set_control_dict_value(case_dir: Path, key: str, value: str) -> None:
    control_dict = case_dir / "system" / "controlDict"
    if not control_dict.is_file():
        return
    text = control_dict.read_text(encoding="utf-8", errors="ignore")
    replacement = f"{key:<16}{value};"
    if re.search(rf"(?m)^\s*{re.escape(key)}\s+[^;]+;", text):
        text = re.sub(rf"(?m)^\s*{re.escape(key)}\s+[^;]+;", replacement, text, count=1)
    else:
        text = replacement + "\n" + text
    control_dict.write_text(text, encoding="utf-8")


def _detect_application(case_dir: Path, fallback: str) -> str:
    control_dict = case_dir / "system" / "controlDict"
    if not control_dict.is_file():
        return fallback
    text = control_dict.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"(?m)^\s*application\s+([^;]+)\s*;", text)
    return match.group(1).strip() if match else fallback


def _certify_template(
    template_id: str,
    *,
    tutorial_root: Path,
    work_root: Path,
    run_solver: bool,
    run_sample: bool,
    short_end_time: float,
    timeout_s: int,
) -> dict[str, Any]:
    definition = RHEOTOOL_TEMPLATE_DEFINITIONS[template_id]
    case_dir = work_root / template_id
    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "template_id": template_id,
        "relative_source": definition["relative_source"],
        "declared_solver": definition["solver"],
        "certification": definition.get("certification"),
        "case_dir": str(case_dir),
        "stages": {},
    }

    try:
        match = _template_payload_from_id(template_id, template_root=tutorial_root)
        import_rheotool_tutorial_template(str(case_dir), match)
        result["stages"]["import"] = {"status": "passed"}
    except Exception as exc:  # noqa: BLE001 - certification must record all failures
        result["stages"]["import"] = {"status": "failed", "error": repr(exc)}
        result["status"] = "failed"
        return result

    actual_solver = _detect_application(case_dir, definition["solver"])
    result["solver"] = actual_solver
    if actual_solver != definition["solver"]:
        result["solver_note"] = f"controlDict application overrides template definition: {definition['solver']} -> {actual_solver}"

    validation = preflight_validate_case(case_dir, "v9", actual_solver)
    if validation is None:
        result["stages"]["schema"] = {"status": "skipped", "reason": "schema_missing"}
    else:
        result["stages"]["schema"] = validation.as_dict()
        result["stages"]["schema"]["status"] = "passed" if validation.ok else "failed"
        if not validation.ok:
            result["status"] = "failed"
            return result

    if (case_dir / "system" / "blockMeshDict").is_file():
        block = _run_openfoam_command(case_dir, "blockMesh", "log.cert.blockMesh", timeout_s)
        result["stages"]["blockMesh"] = block
        if block["status"] != "passed":
            result["status"] = "failed"
            return result
    else:
        result["stages"]["blockMesh"] = {"status": "skipped", "reason": "no system/blockMeshDict"}

    if (case_dir / "constant" / "polyMesh").is_dir():
        check = _run_openfoam_command(case_dir, "checkMesh", "log.cert.checkMesh", timeout_s)
        result["stages"]["checkMesh"] = check
        if check["status"] != "passed":
            result["status"] = "failed"
            return result
    else:
        result["stages"]["checkMesh"] = {"status": "skipped", "reason": "no constant/polyMesh"}

    if run_solver:
        _set_control_dict_value(case_dir, "endTime", f"{short_end_time:g}")
        _set_control_dict_value(case_dir, "writeInterval", "1")
        solver = actual_solver
        solver_result = _run_openfoam_command(case_dir, solver, f"log.cert.{solver}", timeout_s)
        result["stages"]["solver"] = solver_result
        if solver_result["status"] != "passed":
            result["status"] = "failed"
            return result
    else:
        result["stages"]["solver"] = {"status": "skipped", "reason": "use --run-solver for short solver smoke"}

    if run_sample:
        if (case_dir / "system" / "sampleDict").is_file():
            sample = _run_openfoam_command(case_dir, "sample", "log.cert.sample", timeout_s)
            result["stages"]["sample"] = sample
            if sample["status"] != "passed":
                result["status"] = "failed"
                return result
        else:
            result["stages"]["sample"] = {"status": "skipped", "reason": "no system/sampleDict"}
    else:
        result["stages"]["sample"] = {"status": "skipped", "reason": "use --run-sample after solver smoke"}

    result["status"] = "passed"
    return result


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(results),
        "passed": sum(1 for item in results if item.get("status") == "passed"),
        "failed": sum(1 for item in results if item.get("status") == "failed"),
        "skipped": sum(1 for item in results if item.get("status") == "skipped"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Certify imported RheoTool tutorial templates against the local runtime.")
    parser.add_argument("--template-id", action="append", choices=sorted(RHEOTOOL_TEMPLATE_DEFINITIONS), help="Template to certify. May be repeated. Defaults to all templates.")
    parser.add_argument("--tutorial-root", default=str(DEFAULT_RHEOTOOL_TUTORIAL_ROOT))
    parser.add_argument("--work-root", default=str(REPO_ROOT / "runs" / "rheotool_tutorial_certification"))
    parser.add_argument("--run-solver", action="store_true", help="Also run each solver with a shortened endTime.")
    parser.add_argument("--run-sample", action="store_true", help="Run sample after solver smoke when sampleDict exists.")
    parser.add_argument("--short-end-time", type=float, default=0.001)
    parser.add_argument("--timeout-s", type=int, default=120)
    parser.add_argument("--json-out", default="", help="Output JSON path. Defaults to <work-root>/certification_report.json.")
    args = parser.parse_args(argv)

    work_root = Path(args.work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    template_ids = args.template_id or sorted(RHEOTOOL_TEMPLATE_DEFINITIONS)
    results = [
        _certify_template(
            template_id,
            tutorial_root=Path(args.tutorial_root),
            work_root=work_root,
            run_solver=args.run_solver,
            run_sample=args.run_sample,
            short_end_time=args.short_end_time,
            timeout_s=args.timeout_s,
        )
        for template_id in template_ids
    ]
    report = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tutorial_root": str(Path(args.tutorial_root)),
        "work_root": str(work_root),
        "run_solver": args.run_solver,
        "run_sample": args.run_sample,
        "summary": _summary(results),
        "results": results,
    }
    out_path = Path(args.json_out) if args.json_out else work_root / "certification_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"summary": report["summary"], "json_out": str(out_path)}, indent=2, ensure_ascii=False))
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
