from __future__ import annotations

import json
import re
import subprocess
import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from utils import openfoam_command_args
from .visualization import (
    ensure_foam_file,
    generate_deterministic_pyvista_script,
    run_pyvista_script,
)
from .specialized_postprocess import (
    generate_dambreak_enhanced_figures,
    generate_dambreak_free_surface_postprocess,
    generate_dieswell_enhanced_figures,
    generate_dieswell_free_surface_postprocess,
)


@dataclass(frozen=True)
class PostProcessPlan:
    latest_time: str
    fields: list[str]
    run_sample_dict: bool
    metrics: list[str]
    plots: list[str]
    reports: list[str]


@dataclass(frozen=True)
class PostProcessArtifact:
    kind: str
    path: str
    bytes: int


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _numeric_time_dirs(case_dir: Path) -> list[str]:
    times: list[tuple[float, str]] = []
    for child in case_dir.iterdir():
        if not child.is_dir():
            continue
        try:
            value = float(child.name)
        except ValueError:
            continue
        times.append((value, child.name))
    return [name for _, name in sorted(times)]


def latest_time(case_dir: str | Path) -> str | None:
    times = _numeric_time_dirs(Path(case_dir))
    return times[-1] if times else None


def _manifest_channel(case_dir: Path) -> str | None:
    manifest = _read_json(case_dir / "manifest.json")
    channel = manifest.get("channel")
    return channel if channel in {"v9-rheotool", "v10-foundation"} else None


def _field_exists(case_dir: Path, time_name: str, field: str) -> bool:
    time_dir = case_dir / time_name
    return (time_dir / field).is_file() or (time_dir / f"{field}.gz").is_file()


def _available_fields(case_dir: Path, time_name: str, requested: Iterable[str]) -> list[str]:
    return [field for field in requested if _field_exists(case_dir, time_name, field)]


def _artifact(path: str | Path, kind: str) -> PostProcessArtifact | None:
    p = Path(path)
    if not p.is_file():
        return None
    return PostProcessArtifact(kind=kind, path=str(p), bytes=p.stat().st_size)


def _collect_artifacts(report: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts: list[PostProcessArtifact] = []
    for key, kind in (
        ("report_json", "report"),
        ("summary_markdown", "summary"),
        ("artifacts_json", "artifact_manifest"),
    ):
        item = _artifact(report.get(key, ""), kind)
        if item:
            artifacts.append(item)

    line_plot = report.get("line_plot", {})
    item = _artifact(line_plot.get("output", ""), "plot")
    if item:
        artifacts.append(item)

    for field, field_item in report.get("field_visualizations", {}).get("fields", {}).items():
        item = _artifact(field_item.get("output", ""), f"field_plot:{field}")
        if item:
            artifacts.append(item)

    for field, sample in report.get("generic_line_samples", {}).get("fields", {}).items():
        for key, kind in (("csv", f"centerline_csv:{field}"), ("plot", f"centerline_plot:{field}")):
            item = _artifact(sample.get(key, ""), kind)
            if item:
                artifacts.append(item)

    residual_plot = report.get("residual_plot", {})
    for key, kind in (("csv", "residual_csv"), ("plot", "residual_plot")):
        item = _artifact(residual_plot.get(key, ""), kind)
        if item:
            artifacts.append(item)

    formal_report = report.get("formal_report", {})
    item = _artifact(formal_report.get("path", ""), "formal_report")
    if item:
        artifacts.append(item)

    kinetic_energy = report.get("kinetic_energy", {})
    for key, kind in (("csv", "kinetic_energy_csv"), ("plot", "kinetic_energy_plot")):
        item = _artifact(kinetic_energy.get(key, ""), kind)
        if item:
            artifacts.append(item)

    for sample in report.get("samples", {}).get("files", []):
        item = _artifact(sample.get("path", ""), "sample")
        if item:
            artifacts.append(item)

    for key in ("benchmark_comparison",):
        comparison = report.get(key, {})
        item = _artifact(comparison.get("source_json", ""), key)
        if item:
            artifacts.append(item)

    channel_comparison = report.get("rheotool_channel_comparison", {})
    for key, kind in (("csv", "rheotool_channel_comparison_csv"), ("plot", "rheotool_channel_comparison_plot")):
        item = _artifact(channel_comparison.get(key, ""), kind)
        if item:
            artifacts.append(item)

    dieswell = report.get("dieswell_free_surface", {})
    for key, kind in (
        ("csv", "dieswell_free_surface_csv"),
        ("plot", "dieswell_free_surface_plot"),
        ("metrics_json", "dieswell_swell_metrics"),
    ):
        item = _artifact(dieswell.get(key, ""), kind)
        if item:
            artifacts.append(item)

    enhanced = report.get("dieswell_enhanced_figures", {})
    for key, kind in (
        ("path", "dieswell_mesh_overview"),
    ):
        item = _artifact((enhanced.get("mesh") or {}).get(key, ""), kind)
        if item:
            artifacts.append(item)
    item = _artifact((enhanced.get("mesh_zoom") or {}).get("path", ""), "dieswell_mesh_zoom")
    if item:
        artifacts.append(item)
    for key, kind in (("path", "dieswell_free_surface_overlay"),):
        item = _artifact((enhanced.get("free_surface_overlay") or {}).get(key, ""), kind)
        if item:
            artifacts.append(item)
    history = enhanced.get("swell_ratio_history") or {}
    for key, kind in (("csv", "dieswell_swell_ratio_history_csv"), ("plot", "dieswell_swell_ratio_history_plot")):
        item = _artifact(history.get(key, ""), kind)
        if item:
            artifacts.append(item)
    for name, field_item in (enhanced.get("fields") or {}).items():
        item = _artifact(field_item.get("path", ""), f"dieswell_field_snapshot:{name}")
        if item:
            artifacts.append(item)
    for name, field_item in (enhanced.get("zoom_fields") or {}).items():
        item = _artifact(field_item.get("path", ""), f"dieswell_field_zoom_snapshot:{name}")
        if item:
            artifacts.append(item)

    dambreak = report.get("dambreak_free_surface", {})
    for key, kind in (
        ("csv", "dambreak_free_surface_csv"),
        ("plot", "dambreak_free_surface_plot"),
        ("metrics_json", "dambreak_front_metrics"),
    ):
        item = _artifact(dambreak.get(key, ""), kind)
        if item:
            artifacts.append(item)

    enhanced_dambreak = report.get("dambreak_enhanced_figures", {})
    item = _artifact((enhanced_dambreak.get("mesh") or {}).get("path", ""), "dambreak_mesh_overview")
    if item:
        artifacts.append(item)
    item = _artifact((enhanced_dambreak.get("free_surface_overlay") or {}).get("path", ""), "dambreak_free_surface_overlay")
    if item:
        artifacts.append(item)
    front_history = enhanced_dambreak.get("front_history") or {}
    for key, kind in (("csv", "dambreak_front_history_csv"), ("plot", "dambreak_front_history_plot")):
        item = _artifact(front_history.get(key, ""), kind)
        if item:
            artifacts.append(item)
    for name, field_item in (enhanced_dambreak.get("fields") or {}).items():
        item = _artifact(field_item.get("path", ""), f"dambreak_field_snapshot:{name}")
        if item:
            artifacts.append(item)

    deduped: dict[str, PostProcessArtifact] = {}
    for item in artifacts:
        deduped[item.path] = item
    return [asdict(item) for item in deduped.values()]


def _write_artifact_manifest(case_dir: Path, report: dict[str, Any]) -> str:
    path = case_dir / "POSTPROCESS_ARTIFACTS.json"
    manifest = {
        "schema_version": 1,
        "case_dir": str(case_dir),
        "latest_time": report.get("latest_time"),
        "artifacts": _collect_artifacts(report),
    }
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def run_sample_dict(case_dir: str | Path, *, time_name: str, channel: str | None = None) -> dict[str, Any]:
    """Run OpenFOAM sampleDict when the case already defines one.

    This is intentionally conservative: if system/sampleDict is absent or the manifest does
    not identify a certified channel, the function records a skipped status instead of
    inventing a sampling setup.
    """
    case = Path(case_dir).resolve()
    sample_dict = case / "system" / "sampleDict"
    if not sample_dict.is_file():
        return {"status": "skipped", "reason": "system/sampleDict not found"}

    channel = channel or _manifest_channel(case)
    if not channel:
        return {"status": "skipped", "reason": "certified channel not found in manifest"}

    log_path = case / "log.postProcess.sampleDict.postprocess_node"
    cmd = openfoam_command_args(channel, "postProcess", "-case", str(case), "-func", "sampleDict", "-time", time_name)
    completed = subprocess.run(
        cmd,
        cwd=case,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=300,
        check=False,
    )
    log_path.write_text(
        completed.stdout + "\n--- STDERR ---\n" + completed.stderr,
        encoding="utf-8",
    )
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "log": str(log_path),
        "command": cmd,
    }


def collect_sample_outputs(case_dir: str | Path, *, time_name: str) -> dict[str, Any]:
    sample_dir = Path(case_dir) / "postProcessing" / "sampleDict" / time_name
    if not sample_dir.is_dir():
        return {"sample_dir": str(sample_dir), "files": [], "status": "missing"}
    files = []
    for path in sorted(sample_dir.iterdir()):
        if path.is_file():
            files.append({"name": path.name, "path": str(path), "bytes": path.stat().st_size})
    return {"sample_dir": str(sample_dir), "files": files, "status": "present"}


def _read_text_field(path: Path) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="ignore")
    gz_path = path.with_name(path.name + ".gz")
    if gz_path.is_file():
        import gzip

        with gzip.open(gz_path, "rt", encoding="utf-8", errors="ignore") as stream:
            return stream.read()
    return ""


def _extract_internal_scalar_values(text: str) -> list[float]:
    uniform = re.search(r"internalField\s+uniform\s+([-+0-9.eE]+)\s*;", text)
    if uniform:
        return [float(uniform.group(1))]

    nonuniform = re.search(
        r"internalField\s+nonuniform\s+List<scalar>\s+\d+\s*\((.*?)\)\s*;",
        text,
        re.DOTALL,
    )
    if not nonuniform:
        return []
    return [float(match) for match in re.findall(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?", nonuniform.group(1))]


def _extract_internal_vector_values(text: str) -> list[tuple[float, float, float]]:
    number = r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?"
    uniform = re.search(
        rf"internalField\s+uniform\s+\(\s*({number})\s+({number})\s+({number})\s*\)\s*;",
        text,
    )
    if uniform:
        return [(float(uniform.group(1)), float(uniform.group(2)), float(uniform.group(3)))]

    nonuniform = re.search(
        r"internalField\s+nonuniform\s+(?:List<)?vector(?:>)?\s+\d+\s*\((.*?)\)\s*;",
        text,
        re.DOTALL,
    )
    if not nonuniform:
        return []
    values: list[tuple[float, float, float]] = []
    for match in re.finditer(rf"\(\s*({number})\s+({number})\s+({number})\s*\)", nonuniform.group(1)):
        values.append((float(match.group(1)), float(match.group(2)), float(match.group(3))))
    return values


def _extract_uniform_patch_values(text: str) -> dict[str, float]:
    boundary = re.search(r"boundaryField\s*\{(.*)\}\s*//", text, re.DOTALL)
    if not boundary:
        return {}
    values: dict[str, float] = {}
    for match in re.finditer(r"([A-Za-z0-9_]+)\s*\{(.*?)\n\s*\}", boundary.group(1), re.DOTALL):
        patch, body = match.groups()
        value = re.search(r"value\s+uniform\s+([-+0-9.eE]+)\s*;", body)
        if value:
            values[patch] = float(value.group(1))
    return values


def compute_pressure_metrics(case_dir: str | Path, *, time_name: str) -> dict[str, Any]:
    """Extract conservative scalar pressure metrics from the latest p field."""
    case = Path(case_dir)
    text = _read_text_field(case / time_name / "p")
    if not text:
        return {"status": "skipped", "reason": "pressure field p not found"}

    values = _extract_internal_scalar_values(text)
    patches = _extract_uniform_patch_values(text)
    result: dict[str, Any] = {
        "status": "present",
        "field": "p",
        "time": time_name,
        "patch_uniform_values": patches,
    }
    if values:
        result["internal_min"] = min(values)
        result["internal_max"] = max(values)
        result["internal_range"] = max(values) - min(values)
        result["internal_samples"] = len(values)

    inlet_names = ("inlet", "in", "inletPatch")
    outlet_names = ("outlet", "out", "outletPatch")
    inlet = next((patches[name] for name in inlet_names if name in patches), None)
    outlet = next((patches[name] for name in outlet_names if name in patches), None)
    if inlet is not None and outlet is not None:
        result["pressure_drop"] = inlet - outlet
        result["pressure_drop_source"] = "uniform inlet/outlet patch values"
    else:
        result["pressure_drop_status"] = "skipped"
        result["pressure_drop_reason"] = "uniform inlet/outlet patch pressure values not both available"
    return result


def _solver_logs(case_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in case_dir.iterdir()
        if path.is_file() and path.name.startswith("log.") and "postProcess" not in path.name
    )


def _solver_log_completed(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return "FOAM FATAL" not in text and bool(re.search(r"(?m)^End\s*$", text))


def compute_residual_metrics(case_dir: str | Path) -> dict[str, Any]:
    """Parse OpenFOAM residual lines from solver logs."""
    case = Path(case_dir)
    pattern = re.compile(
        r"Solving for\s+([^,]+),\s+Initial residual\s+=\s+([-+0-9.eE]+),\s+Final residual\s+=\s+([-+0-9.eE]+),\s+No Iterations\s+([0-9]+)"
    )
    by_field: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    source_logs: list[str] = []
    sequence = 0
    for log_path in _solver_logs(case):
        text = log_path.read_text(encoding="utf-8", errors="ignore")
        matches = pattern.findall(text)
        if not matches:
            continue
        source_logs.append(str(log_path))
        for field, initial, final, iterations in matches:
            sequence += 1
            initial_value = float(initial)
            final_value = float(final)
            iteration_count = int(iterations)
            item = by_field.setdefault(
                field.strip(),
                {"count": 0, "initial_max": 0.0, "final_max": 0.0, "iterations_max": 0},
            )
            item["count"] += 1
            item["initial_max"] = max(item["initial_max"], initial_value)
            item["final_max"] = max(item["final_max"], final_value)
            item["iterations_max"] = max(item["iterations_max"], iteration_count)
            records.append(
                {
                    "sequence": sequence,
                    "field": field.strip(),
                    "initial_residual": initial_value,
                    "final_residual": final_value,
                    "iterations": iteration_count,
                    "source_log": str(log_path),
                }
            )
    if not by_field:
        return {"status": "skipped", "reason": "no residual lines found in solver logs"}
    return {"status": "present", "source_logs": source_logs, "fields": by_field, "records": records}


def _downsample_records(records: list[dict[str, Any]], *, max_records: int = 20000) -> list[dict[str, Any]]:
    if len(records) <= max_records:
        return records
    if max_records < 2:
        return records[:1]
    step = (len(records) - 1) / (max_records - 1)
    indices = sorted({round(i * step) for i in range(max_records)})
    return [records[index] for index in indices]


def generate_residual_plot(case_dir: str | Path, residuals: dict[str, Any]) -> dict[str, Any]:
    records = residuals.get("records") or []
    if not records:
        return {"status": "skipped", "reason": "no residual records available"}

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    case = Path(case_dir)
    post_dir = case / "postprocess"
    post_dir.mkdir(exist_ok=True)
    csv_path = post_dir / "residuals.csv"
    plot_path = post_dir / "residuals.png"
    plot_records = _downsample_records(records)

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["sequence", "field", "initial_residual", "final_residual", "iterations", "source_log"],
        )
        writer.writeheader()
        writer.writerows(plot_records)

    by_field: dict[str, list[dict[str, Any]]] = {}
    for record in plot_records:
        by_field.setdefault(record["field"], []).append(record)

    plt.figure(figsize=(8, 5), dpi=160)
    for field, field_records in sorted(by_field.items()):
        x = [record["sequence"] for record in field_records]
        y = [max(record["final_residual"], 1e-300) for record in field_records]
        plt.semilogy(x, y, linewidth=1.3, label=field)
    plt.xlabel("solver residual record")
    plt.ylabel("final residual")
    plt.title("OpenFOAM residual history")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend(fontsize="small")
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()

    return {
        "status": "passed",
        "csv": str(csv_path),
        "plot": str(plot_path),
        "records": len(records),
        "plotted_records": len(plot_records),
        "downsampled": len(plot_records) < len(records),
    }


def compact_residual_metrics(residuals: dict[str, Any]) -> dict[str, Any]:
    """Keep reports compact by moving detailed residual history to residuals.csv."""
    compact = dict(residuals)
    records = compact.pop("records", [])
    compact["records"] = len(records)
    return compact


def _numeric_value_from_mapping(data: Any, keys: set[str]) -> float | None:
    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).casefold() in keys:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass
            found = _numeric_value_from_mapping(value, keys)
            if found is not None:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _numeric_value_from_mapping(value, keys)
            if found is not None:
                return found
    return None


def _extract_density(case: Path, user_requirement: str) -> tuple[float, str]:
    manifest_value = _numeric_value_from_mapping(_read_json(case / "manifest.json"), {"rho", "density"})
    if manifest_value is not None:
        return manifest_value, "manifest"

    for rel in ("constant/transportProperties", "constant/constitutiveProperties"):
        text = _read_text_field(case / rel)
        match = re.search(r"(?m)^\s*(?:rho|density)\s+([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*;", text)
        if match:
            return float(match.group(1)), rel

    match = re.search(
        r"(?:\brho\b|ρ)\s*(?:=|:|为)?\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
        user_requirement,
        flags=re.IGNORECASE,
    )
    if match:
        return float(match.group(1)), "user_requirement"
    return 1.0, "default"


def generate_kinetic_energy_history(case_dir: str | Path, *, user_requirement: str = "") -> dict[str, Any]:
    """Compute an unweighted cell-average kinetic-energy history from written U fields."""
    case = Path(case_dir)
    rho, rho_source = _extract_density(case, user_requirement)
    rows: list[dict[str, Any]] = []
    for time_name in _numeric_time_dirs(case):
        text = _read_text_field(case / time_name / "U")
        if not text:
            continue
        vectors = _extract_internal_vector_values(text)
        if not vectors:
            continue
        mean_speed_sq = sum(ux * ux + uy * uy + uz * uz for ux, uy, uz in vectors) / len(vectors)
        rows.append(
            {
                "time": float(time_name),
                "time_name": time_name,
                "kinetic_energy_average": 0.5 * rho * mean_speed_sq,
                "sample_count": len(vectors),
            }
        )

    if not rows:
        return {"status": "skipped", "reason": "no readable U internalField values found", "rho": rho, "rho_source": rho_source}

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    post_dir = case / "postprocess"
    post_dir.mkdir(exist_ok=True)
    csv_path = post_dir / "kinetic_energy.csv"
    plot_path = post_dir / "kinetic_energy.png"

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["time", "time_name", "kinetic_energy_average", "sample_count", "rho", "rho_source"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "rho": rho, "rho_source": rho_source})

    plt.figure(figsize=(7, 5), dpi=160)
    plt.plot([row["time"] for row in rows], [row["kinetic_energy_average"] for row in rows], linewidth=1.5)
    plt.xlabel("time")
    plt.ylabel("cell-average kinetic energy")
    plt.title("Kinetic energy history")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()

    return {
        "status": "passed",
        "csv": str(csv_path),
        "plot": str(plot_path),
        "rows": len(rows),
        "rho": rho,
        "rho_source": rho_source,
        "method": "unweighted mean of 0.5*rho*|U|^2 over written internalField values",
        "first": rows[0],
        "last": rows[-1],
    }


def collect_benchmark_comparison(case_dir: str | Path) -> dict[str, Any]:
    """Include existing benchmark comparison artifacts in the standard report."""
    case = Path(case_dir)
    candidates = [
        case / "RUDE_GIESEKUS_T10_U_COMPARISON_FILTERED.json",
        case / "RUDE_GIESEKUS_T10_U_COMPARISON.json",
    ]
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        return {"status": "skipped", "reason": "no certified benchmark comparison JSON found"}
    data = _read_json(source)
    summary: dict[str, Any] = {
        "status": "present",
        "source_json": str(source),
    }
    for key in ("all_points", "unique_coordinates_only", "unique_non_inlet_wall_bbox"):
        if isinstance(data.get(key), dict):
            summary[key] = {
                metric: data[key].get(metric)
                for metric in ("n", "l2_relative", "max_vector", "mean_vector", "rms_vector")
                if metric in data[key]
            }
    return summary


def reconcile_manifest_after_postprocess(case_dir: str | Path, report: dict[str, Any]) -> dict[str, Any]:
    """Record postprocess status in manifest without changing immutable CaseTarget fields."""
    case = Path(case_dir)
    path = case / "manifest.json"
    manifest = _read_json(path)
    if not manifest:
        return {"status": "skipped", "reason": "manifest.json not found"}

    artifacts = manifest.setdefault("artifacts", [])
    for artifact in report.get("artifacts", []):
        if artifact.get("path") and artifact not in artifacts:
            artifacts.append(artifact)

    manifest["postprocess_status"] = report.get("status")
    manifest["postprocess_report"] = report.get("report_json")
    manifest["postprocess_artifacts"] = report.get("artifacts_json")

    solver = manifest.get("solver")
    completed_logs = [
        str(path)
        for path in _solver_logs(case)
        if (not solver or solver.lower() in path.name.lower()) and _solver_log_completed(path)
    ]
    if manifest.get("run_status") != "passed" and completed_logs:
        manifest["run_status"] = "passed"
        manifest.setdefault("postprocess_warnings", []).append(
            "run_status was reconciled to passed because completed solver log with End was found"
        )
        manifest["run_status_evidence"] = completed_logs

    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"status": "updated", "path": str(path), "run_status": manifest.get("run_status")}


def _load_xy(path: Path):
    import numpy as np

    data = np.loadtxt(path)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    return data


def _constitutive_scalar(case: Path, name: str, default: float) -> float:
    text = _read_text_field(case / "constant" / "constitutiveProperties")
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s+([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*;", text)
    return float(match.group(1)) if match else default


def generate_rheotool_channel_comparison(case_dir: str | Path, *, time_name: str) -> dict[str, Any]:
    """Plot RheoTool Channel/Oldroyd-BLog lineX35 numerical profiles against analytic fully-developed flow."""
    case = Path(case_dir)
    sample_dir = case / "postProcessing" / "sampleDict" / time_name
    u_path = sample_dir / "lineX35_U.xy"
    tau_path = sample_dir / "lineX35_tau.xy"
    if not u_path.is_file() or not tau_path.is_file():
        return {"status": "skipped", "reason": "lineX35_U.xy/lineX35_tau.xy not found"}

    import csv
    import numpy as np
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    u_data = _load_xy(u_path)
    tau_data = _load_xy(tau_path)
    if u_data.shape[1] < 2 or tau_data.shape[1] < 3:
        return {"status": "skipped", "reason": "lineX35 sample files do not contain expected columns"}

    y = u_data[:, 0]
    ux = u_data[:, 1]
    tau_xx = tau_data[:, 1]
    tau_xy = tau_data[:, 2]

    half_width = float(np.max(np.abs(y))) or 1.0
    y_hat = y / half_width
    bulk_velocity = 1.0
    eta_p = _constitutive_scalar(case, "etaP", 0.99)
    relaxation_time = _constitutive_scalar(case, "lambda", 1.0)

    ux_exact = 1.5 * bulk_velocity * (1.0 - y_hat**2)
    du_dy = -3.0 * bulk_velocity * y / (half_width**2)
    tau_xy_exact = du_dy
    tau_xx_exact = 2.0 * eta_p * relaxation_time * du_dy**2

    post_dir = case / "postprocess"
    post_dir.mkdir(exist_ok=True)
    csv_path = post_dir / "lineX35_oldroydb_analytic_comparison.csv"
    plot_path = post_dir / "lineX35_oldroydb_analytic_comparison.png"

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "y",
            "Ux_numeric",
            "Ux_analytic",
            "Ux_error",
            "tau_xx_numeric",
            "tau_xx_analytic",
            "tau_xx_error",
            "tau_xy_numeric",
            "tau_xy_analytic",
            "tau_xy_error",
        ])
        for row in zip(y, ux, ux_exact, tau_xx, tau_xx_exact, tau_xy, tau_xy_exact):
            yy, ux_n, ux_a, txx_n, txx_a, txy_n, txy_a = row
            writer.writerow([yy, ux_n, ux_a, ux_n - ux_a, txx_n, txx_a, txx_n - txx_a, txy_n, txy_a, txy_n - txy_a])

    def _error_stats(numerical, analytic) -> dict[str, float]:
        error = np.asarray(numerical) - np.asarray(analytic)
        return {
            "max_abs": float(np.max(np.abs(error))),
            "mean_abs": float(np.mean(np.abs(error))),
            "rmse": float(np.sqrt(np.mean(error**2))),
        }

    plt.figure(figsize=(12, 4), dpi=160)
    panels = [
        ("Ux profile", ux, ux_exact, "Ux"),
        ("tau_xx profile", tau_xx, tau_xx_exact, "tau_xx"),
        ("tau_xy profile", tau_xy, tau_xy_exact, "tau_xy"),
    ]
    for index, (title, numerical, analytic, ylabel) in enumerate(panels, start=1):
        ax = plt.subplot(1, 3, index)
        ax.plot(y, analytic, "-", linewidth=1.8, label="analytic")
        ax.plot(y, numerical, "o", markersize=2.5, label="OpenFOAM")
        ax.set_title(title)
        ax.set_xlabel("y / w")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    plt.suptitle(f"RheoTool Channel Oldroyd-BLog, lineX35, t={time_name}")
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()

    return {
        "status": "passed",
        "plot": str(plot_path),
        "csv": str(csv_path),
        "time": time_name,
        "assumptions": {
            "half_width": half_width,
            "bulk_velocity": bulk_velocity,
            "etaP": eta_p,
            "lambda": relaxation_time,
        },
        "errors": {
            "Ux": _error_stats(ux, ux_exact),
            "tau_xx": _error_stats(tau_xx, tau_xx_exact),
            "tau_xy": _error_stats(tau_xy, tau_xy_exact),
        },
    }


def generate_rude_line_plot(case_dir: str | Path, *, time_name: str) -> dict[str, Any]:
    """Generate the RUDE Fig.4-style Ux line plot when expected sample files exist."""
    case = Path(case_dir)
    sample_dir = case / "postProcessing" / "sampleDict" / time_name
    before = sample_dir / "lBeforex0_U.xy"
    after = sample_dir / "lAfterx0_U.xy"
    if not before.is_file() or not after.is_file():
        return {"status": "skipped", "reason": "lBeforex0_U.xy/lAfterx0_U.xy not found"}

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    before_data = _load_xy(before)
    after_data = _load_xy(after)
    post_dir = case / "postprocess"
    post_dir.mkdir(exist_ok=True)
    output = post_dir / "fig4_Ux_curve.png"

    plt.figure(figsize=(7, 5), dpi=160)
    plt.plot(before_data[:, 0], before_data[:, 1], marker="o", linewidth=1.5, markersize=3, label="before contraction Ux")
    plt.plot(after_data[:, 0], after_data[:, 1], marker="o", linewidth=1.5, markersize=3, label="after contraction Ux")
    plt.xlabel("sample coordinate")
    plt.ylabel("Ux")
    plt.title(f"RUDE Giesekus 4:1 contraction, t={time_name}, sampleDict Ux")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output)
    plt.close()

    return {
        "status": "passed",
        "output": str(output),
        "time": time_name,
        "series": [
            {
                "name": "lBeforex0_U",
                "rows": int(before_data.shape[0]),
                "Ux_min": float(before_data[:, 1].min()),
                "Ux_max": float(before_data[:, 1].max()),
            },
            {
                "name": "lAfterx0_U",
                "rows": int(after_data.shape[0]),
                "Ux_min": float(after_data[:, 1].min()),
                "Ux_max": float(after_data[:, 1].max()),
            },
        ],
    }


def generate_field_visualizations(
    case_dir: str | Path,
    *,
    time_name: str,
    fields: Iterable[str] = ("U", "p", "tau"),
) -> dict[str, Any]:
    case = Path(case_dir)
    foam_file = ensure_foam_file(str(case))
    post_dir = case / "postprocess"
    post_dir.mkdir(exist_ok=True)

    outputs: dict[str, Any] = {}
    for field in _available_fields(case, time_name, fields):
        output_png = f"postprocess/visualization_{field}.png"
        script_name = f"postprocess/visualization_{field}.py"
        script = generate_deterministic_pyvista_script(
            foam_file=foam_file,
            output_png=output_png,
            field_preference=field,
        )
        ok, img, errs = run_pyvista_script(
            str(case),
            script,
            filename=script_name,
            expected_png=output_png,
            timeout_s=180,
        )
        outputs[field] = {
            "status": "passed" if ok else "failed",
            "output": img,
            "script": str(case / script_name),
            "errors": errs,
        }
    return {"status": "passed" if outputs else "skipped", "time": time_name, "fields": outputs}


def _centerline_from_bounds(bounds: tuple[float, float, float, float, float, float]) -> dict[str, Any]:
    extents = {
        "x": bounds[1] - bounds[0],
        "y": bounds[3] - bounds[2],
        "z": bounds[5] - bounds[4],
    }
    axis = max(extents, key=extents.get)
    if extents[axis] <= 0:
        return {"status": "skipped", "reason": "mesh bounds are degenerate", "bounds": list(bounds)}

    center = (
        0.5 * (bounds[0] + bounds[1]),
        0.5 * (bounds[2] + bounds[3]),
        0.5 * (bounds[4] + bounds[5]),
    )
    start = list(center)
    end = list(center)
    axis_index = {"x": 0, "y": 1, "z": 2}[axis]
    bound_index = {"x": (0, 1), "y": (2, 3), "z": (4, 5)}[axis]
    start[axis_index] = bounds[bound_index[0]]
    end[axis_index] = bounds[bound_index[1]]
    return {
        "status": "present",
        "axis": axis,
        "bounds": list(bounds),
        "start": start,
        "end": end,
        "length": extents[axis],
    }


def _mesh_has_array(mesh: Any, field: str) -> bool:
    try:
        if field in getattr(mesh, "point_data", {}):
            return True
        if field in getattr(mesh, "cell_data", {}):
            return True
        return field in getattr(mesh, "array_names", [])
    except Exception:
        return False


def _array_to_components(values: Any) -> tuple[list[str], list[list[float]]]:
    import numpy as np

    arr = np.asarray(values)
    if arr.ndim == 1:
        return ["value"], [[float(value)] for value in arr]
    component_names = [f"c{i}" for i in range(arr.shape[1])]
    if arr.shape[1] in (2, 3):
        component_names.append("magnitude")
        rows = []
        for row in arr:
            components = [float(value) for value in row]
            components.append(float(np.linalg.norm(row)))
            rows.append(components)
        return component_names, rows
    return component_names, [[float(value) for value in row] for row in arr]


def generate_generic_centerline_samples(
    case_dir: str | Path,
    *,
    time_name: str,
    fields: Iterable[str] = ("U", "p", "tau"),
    resolution: int = 200,
) -> dict[str, Any]:
    """Sample available fields along the longest mesh-bounds centerline.

    This is the generic fallback when a case does not provide a curated sampleDict.
    It is intentionally disclosed as a centerline/bounds heuristic, not as a
    physics-specific sampling definition.
    """
    case = Path(case_dir)
    available = _available_fields(case, time_name, fields)
    if not available:
        return {"status": "skipped", "reason": "none of the requested fields exist at latest time", "fields": {}}

    try:
        import matplotlib
        import numpy as np
        import pyvista as pv

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        return {"status": "skipped", "reason": f"postprocess plotting dependencies unavailable: {exc}", "fields": {}}

    foam_file = ensure_foam_file(str(case))
    try:
        reader = pv.OpenFOAMReader(str((case / foam_file).resolve()))
        try:
            reader.set_active_time_value(float(time_name))
        except Exception:
            try:
                reader.set_active_time_value(reader.time_values[-1])
            except Exception:
                pass
        data = reader.read()
        mesh = data.combine() if hasattr(data, "combine") else data
    except Exception as exc:
        return {"status": "failed", "reason": f"failed to read OpenFOAM result with PyVista: {exc}", "fields": {}}

    line = _centerline_from_bounds(tuple(float(value) for value in mesh.bounds))
    if line.get("status") != "present":
        return {**line, "fields": {}}

    try:
        sampled = mesh.sample_over_line(line["start"], line["end"], resolution=max(2, resolution) - 1)
    except Exception as exc:
        return {"status": "failed", "reason": f"failed to sample centerline: {exc}", "line": line, "fields": {}}

    post_dir = case / "postprocess"
    post_dir.mkdir(exist_ok=True)
    outputs: dict[str, Any] = {}
    distance = np.linspace(0.0, float(line["length"]), len(sampled.points))

    for field in available:
        if not _mesh_has_array(sampled, field):
            outputs[field] = {"status": "skipped", "reason": "field not present in sampled mesh"}
            continue
        try:
            component_names, rows = _array_to_components(sampled[field])
        except Exception as exc:
            outputs[field] = {"status": "failed", "reason": f"failed to extract sampled field: {exc}"}
            continue

        csv_path = post_dir / f"centerline_{field}.csv"
        plot_path = post_dir / f"centerline_{field}.png"
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["s", "x", "y", "z", *component_names])
            for idx, point in enumerate(sampled.points):
                writer.writerow(
                    [
                        float(distance[idx]),
                        float(point[0]),
                        float(point[1]),
                        float(point[2]),
                        *rows[idx],
                    ]
                )

        plot_column = -1 if component_names[-1] == "magnitude" else 0
        y = [row[plot_column] for row in rows]
        plt.figure(figsize=(7, 5), dpi=160)
        plt.plot(distance, y, linewidth=1.5)
        plt.xlabel(f"centerline distance along {line['axis']}")
        ylabel = f"{field} magnitude" if component_names[-1] == "magnitude" else field
        plt.ylabel(ylabel)
        plt.title(f"Centerline {ylabel}, t={time_name}")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(plot_path)
        plt.close()

        outputs[field] = {
            "status": "passed",
            "csv": str(csv_path),
            "plot": str(plot_path),
            "rows": len(rows),
            "components": component_names,
            "first": rows[0],
            "last": rows[-1],
        }

    pressure = outputs.get("p", {})
    pressure_drop = None
    if pressure.get("status") == "passed" and pressure.get("first") and pressure.get("last"):
        pressure_drop = pressure["first"][0] - pressure["last"][0]

    return {
        "status": "passed" if any(item.get("status") == "passed" for item in outputs.values()) else "skipped",
        "time": time_name,
        "line": line,
        "fields": outputs,
        "pressure_drop_line_estimate": pressure_drop,
        "pressure_drop_source": "generic centerline endpoint estimate" if pressure_drop is not None else None,
    }


def write_postprocess_summary(case_dir: str | Path, report: dict[str, Any]) -> str:
    case = Path(case_dir)
    lines = [
        "# Foam-Agent Postprocess Summary",
        "",
        f"- case_dir: `{case}`",
        f"- latest_time: `{report.get('latest_time')}`",
        f"- plan: `{report.get('postprocess_plan', {}).get('metrics', [])}`",
        f"- sampleDict: `{report.get('sampleDict', {}).get('status')}`",
        f"- samples: `{report.get('samples', {}).get('status')}`",
        f"- line_plot: `{report.get('line_plot', {}).get('status')}`",
        f"- generic_line_samples: `{report.get('generic_line_samples', {}).get('status')}`",
        f"- field_visualizations: `{report.get('field_visualizations', {}).get('status')}`",
        f"- pressure_metrics: `{report.get('metrics', {}).get('pressure', {}).get('status')}`",
        f"- residual_metrics: `{report.get('metrics', {}).get('residuals', {}).get('status')}`",
        f"- residual_plot: `{report.get('residual_plot', {}).get('status')}`",
        f"- kinetic_energy: `{report.get('kinetic_energy', {}).get('status')}`",
        f"- dieswell_free_surface: `{report.get('dieswell_free_surface', {}).get('status')}`",
        f"- formal_report: `{report.get('formal_report', {}).get('status')}`",
        f"- rheotool_channel_comparison: `{report.get('rheotool_channel_comparison', {}).get('status')}`",
        f"- benchmark_comparison: `{report.get('benchmark_comparison', {}).get('status')}`",
        "",
        "## Artifacts",
    ]
    line_plot = report.get("line_plot", {})
    if line_plot.get("output"):
        lines.append(f"- `{line_plot['output']}`")
    for field, item in report.get("field_visualizations", {}).get("fields", {}).items():
        if item.get("output"):
            lines.append(f"- {field}: `{item['output']}`")
    for field, item in report.get("generic_line_samples", {}).get("fields", {}).items():
        if item.get("csv"):
            lines.append(f"- centerline {field} CSV: `{item['csv']}`")
        if item.get("plot"):
            lines.append(f"- centerline {field} plot: `{item['plot']}`")
    residual_plot = report.get("residual_plot", {})
    if residual_plot.get("plot"):
        lines.append(f"- residual plot: `{residual_plot['plot']}`")
    if residual_plot.get("csv"):
        lines.append(f"- residual CSV: `{residual_plot['csv']}`")
    kinetic_energy = report.get("kinetic_energy", {})
    if kinetic_energy.get("plot"):
        lines.append(f"- kinetic energy plot: `{kinetic_energy['plot']}`")
    if kinetic_energy.get("csv"):
        lines.append(f"- kinetic energy CSV: `{kinetic_energy['csv']}`")
    formal_report = report.get("formal_report", {})
    if formal_report.get("path"):
        lines.append(f"- formal Word report: `{formal_report['path']}`")
    for file_item in report.get("samples", {}).get("files", []):
        lines.append(f"- sample: `{file_item['path']}` ({file_item['bytes']} bytes)")
    channel_comparison = report.get("rheotool_channel_comparison", {})
    if channel_comparison.get("plot"):
        lines.append(f"- RheoTool lineX35 analytic comparison plot: `{channel_comparison['plot']}`")
    if channel_comparison.get("csv"):
        lines.append(f"- RheoTool lineX35 analytic comparison CSV: `{channel_comparison['csv']}`")
    dieswell = report.get("dieswell_free_surface", {})
    if dieswell.get("plot"):
        lines.append(f"- DieSwell free-surface plot: `{dieswell['plot']}`")
    if dieswell.get("csv"):
        lines.append(f"- DieSwell free-surface CSV: `{dieswell['csv']}`")
    if dieswell.get("metrics_json"):
        lines.append(f"- DieSwell swell metrics JSON: `{dieswell['metrics_json']}`")
    dambreak = report.get("dambreak_free_surface", {})
    if dambreak.get("plot"):
        lines.append(f"- damBreak free-surface/front plot: `{dambreak['plot']}`")
    if dambreak.get("csv"):
        lines.append(f"- damBreak free-surface CSV: `{dambreak['csv']}`")
    if dambreak.get("metrics_json"):
        lines.append(f"- damBreak front metrics JSON: `{dambreak['metrics_json']}`")

    pressure = report.get("metrics", {}).get("pressure", {})
    if "pressure_drop" in pressure:
        lines.extend(["", "## Pressure Metrics", f"- pressure_drop: `{pressure['pressure_drop']}`"])
    elif "pressure_drop_line_estimate" in pressure:
        lines.extend(
            [
                "",
                "## Pressure Metrics",
                f"- pressure_drop_line_estimate: `{pressure['pressure_drop_line_estimate']}`",
                f"- source: `{pressure.get('pressure_drop_source')}`",
            ]
        )
    elif pressure.get("pressure_drop_reason"):
        lines.extend(["", "## Pressure Metrics", f"- pressure_drop: skipped ({pressure['pressure_drop_reason']})"])

    line = report.get("generic_line_samples", {}).get("line", {})
    if line:
        lines.extend(
            [
                "",
                "## Generic Centerline Sampling",
                f"- axis: `{line.get('axis')}`",
                f"- start: `{line.get('start')}`",
                f"- end: `{line.get('end')}`",
                "- note: automatically selected longest bounding-box centerline; use curated sampleDict for publication-specific sampling.",
            ]
        )

    residuals = report.get("metrics", {}).get("residuals", {})
    if residuals.get("fields"):
        lines.append("")
        lines.append("## Residual Metrics")
        for field, item in residuals["fields"].items():
            lines.append(
                f"- {field}: initial_max={item['initial_max']}, "
                f"final_max={item['final_max']}, count={item['count']}"
            )

    if kinetic_energy.get("status") == "passed":
        lines.extend(
            [
                "",
                "## Kinetic Energy",
                f"- method: `{kinetic_energy.get('method')}`",
                f"- rho: `{kinetic_energy.get('rho')}` ({kinetic_energy.get('rho_source')})",
                f"- rows: `{kinetic_energy.get('rows')}`",
                f"- last_Ek: `{kinetic_energy.get('last', {}).get('kinetic_energy_average')}`",
            ]
        )

    if dieswell.get("status") == "passed":
        lines.extend(
            [
                "",
                "## DieSwell Free Surface",
                f"- definition: `{dieswell.get('definition')}`",
                f"- die_exit_half_height: `{dieswell.get('die_exit_half_height')}`",
                f"- max_half_height: `{dieswell.get('max_half_height')}`",
                f"- swell_ratio: `{dieswell.get('swell_ratio')}`",
                f"- max_location: `{dieswell.get('max_location')}`",
            ]
        )
    elif dieswell:
        lines.extend(["", "## DieSwell Free Surface", f"- status: `{dieswell.get('status')}`", f"- reason: `{dieswell.get('reason')}`"])

    if dambreak.get("status") == "passed":
        lines.extend(
            [
                "",
                "## damBreak Free Surface",
                f"- definition: `{dambreak.get('definition')}`",
                f"- front_x: `{dambreak.get('front_x')}`",
                f"- front_location: `{dambreak.get('front_location')}`",
                f"- max_height: `{dambreak.get('max_height')}`",
            ]
        )
    elif dambreak:
        lines.extend(["", "## damBreak Free Surface", f"- status: `{dambreak.get('status')}`", f"- reason: `{dambreak.get('reason')}`"])

    comparison = report.get("benchmark_comparison", {})
    if comparison.get("status") == "present":
        lines.extend(["", "## Benchmark Comparison", f"- source: `{comparison.get('source_json')}`"])
        all_points = comparison.get("all_points", {})
        if all_points:
            lines.append(f"- all_points_l2_relative: `{all_points.get('l2_relative')}`")

    if channel_comparison.get("status") == "passed":
        lines.append("")
        lines.append("## RheoTool Channel Analytic Comparison")
        for field, stats in channel_comparison.get("errors", {}).items():
            lines.append(
                f"- {field}: max_abs={stats.get('max_abs')}, "
                f"mean_abs={stats.get('mean_abs')}, rmse={stats.get('rmse')}"
            )

    out = case / "POSTPROCESS_SUMMARY.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out)


def run_standard_postprocess(
    case_dir: str | Path,
    *,
    user_requirement: str = "",
    fields: Iterable[str] = ("U", "p", "tau"),
    run_openfoam_sample: bool = True,
) -> dict[str, Any]:
    """Run deterministic post-processing for an existing OpenFOAM case."""
    case = Path(case_dir)
    time_name = latest_time(case)
    requested_fields = list(fields)
    report: dict[str, Any] = {
        "status": "failed" if time_name is None else "passed",
        "case_dir": str(case),
        "latest_time": time_name,
        "user_requirement": user_requirement,
    }
    if time_name is None:
        report["error"] = "No numeric time directories found"
        (case / "POSTPROCESS_REPORT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    plan = PostProcessPlan(
        latest_time=time_name,
        fields=requested_fields,
        run_sample_dict=run_openfoam_sample,
        metrics=["pressure", "residuals", "kinetic_energy", "generic_centerline_pressure_drop_if_available"],
        plots=[
            "field_visualizations",
            "generic_centerline_samples",
            "residual_plot",
            "kinetic_energy_history",
            "dieswell_free_surface_if_applicable",
            "dambreak_free_surface_if_applicable",
            "rude_fig4_Ux_if_available",
            "rheotool_channel_lineX35_analytic_comparison_if_available",
        ],
        reports=["POSTPROCESS_REPORT.json", "POSTPROCESS_SUMMARY.md", "POSTPROCESS_ARTIFACTS.json"],
    )
    report["postprocess_plan"] = asdict(plan)

    print("[5/6] 后处理与可视化：开始")
    print(f"  [5.1] 检查时间步：找到最新时间步 {time_name}")

    report["sampleDict"] = run_sample_dict(case, time_name=time_name) if run_openfoam_sample else {"status": "skipped"}
    print(f"  [5.2] OpenFOAM sampleDict：{report['sampleDict']['status']}")

    report["samples"] = collect_sample_outputs(case, time_name=time_name)
    print(f"  [5.3] 收集采样文件：{len(report['samples'].get('files', []))} 个")

    report["metrics"] = {
        "pressure": compute_pressure_metrics(case, time_name=time_name),
        "residuals": compute_residual_metrics(case),
    }
    print(
        "  [5.4] 提取指标："
        f"pressure={report['metrics']['pressure']['status']}, "
        f"residuals={report['metrics']['residuals']['status']}"
    )

    report["line_plot"] = generate_rude_line_plot(case, time_name=time_name)
    print(f"  [5.5] 生成采样曲线：{report['line_plot']['status']}")

    report["rheotool_channel_comparison"] = generate_rheotool_channel_comparison(case, time_name=time_name)
    print(f"  [5.5b] RheoTool lineX35 解析对比：{report['rheotool_channel_comparison']['status']}")

    report["generic_line_samples"] = generate_generic_centerline_samples(case, time_name=time_name, fields=requested_fields)
    generic_count = len(
        [
            item
            for item in report["generic_line_samples"].get("fields", {}).values()
            if item.get("status") == "passed"
        ]
    )
    print(f"  [5.6] 自动中心线采样：{generic_count} 个字段")
    if (
        "pressure_drop" not in report["metrics"]["pressure"]
        and report["generic_line_samples"].get("pressure_drop_line_estimate") is not None
    ):
        report["metrics"]["pressure"]["pressure_drop_line_estimate"] = report["generic_line_samples"][
            "pressure_drop_line_estimate"
        ]
        report["metrics"]["pressure"]["pressure_drop_source"] = report["generic_line_samples"]["pressure_drop_source"]

    report["residual_plot"] = generate_residual_plot(case, report["metrics"]["residuals"])
    report["metrics"]["residuals"] = compact_residual_metrics(report["metrics"]["residuals"])
    print(f"  [5.7] 生成残差曲线：{report['residual_plot']['status']}")

    report["kinetic_energy"] = generate_kinetic_energy_history(case, user_requirement=user_requirement)
    print(f"  [5.7b] 生成平均动能曲线：{report['kinetic_energy']['status']}")

    report["dieswell_free_surface"] = generate_dieswell_free_surface_postprocess(
        case,
        time_name=time_name,
        user_requirement=user_requirement,
    )
    print(f"  [5.7c] DieSwell 自由液面/胀大比：{report['dieswell_free_surface']['status']}")

    report["dieswell_enhanced_figures"] = generate_dieswell_enhanced_figures(
        case,
        latest_time=time_name,
        user_requirement=user_requirement,
    )
    print(f"  [5.7d] DieSwell 增强图表：{report['dieswell_enhanced_figures']['status']}")

    report["dambreak_free_surface"] = generate_dambreak_free_surface_postprocess(
        case,
        time_name=time_name,
        user_requirement=user_requirement,
    )
    print(f"  [5.7e] damBreak 自由液面/前沿：{report['dambreak_free_surface']['status']}")

    report["dambreak_enhanced_figures"] = generate_dambreak_enhanced_figures(
        case,
        latest_time=time_name,
        user_requirement=user_requirement,
    )
    print(f"  [5.7f] damBreak 增强图表：{report['dambreak_enhanced_figures']['status']}")

    report["field_visualizations"] = generate_field_visualizations(case, time_name=time_name, fields=requested_fields)
    field_count = len(report["field_visualizations"].get("fields", {}))
    print(f"  [5.8] 生成字段图：{field_count} 张")

    report["benchmark_comparison"] = collect_benchmark_comparison(case)
    print(f"  [5.9] Benchmark 对比：{report['benchmark_comparison']['status']}")

    report_path = case / "POSTPROCESS_REPORT.json"
    report["summary_markdown"] = write_postprocess_summary(case, report)
    report["report_json"] = str(report_path)
    report["artifacts_json"] = str(case / "POSTPROCESS_ARTIFACTS.json")
    report["artifacts"] = []
    report["manifest_update"] = {"status": "pending"}
    report["artifacts_json"] = _write_artifact_manifest(case, report)
    report["artifacts"] = _read_json(Path(report["artifacts_json"])).get("artifacts", [])
    report["manifest_update"] = reconcile_manifest_after_postprocess(case, report)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        from services.formal_report import generate_formal_case_report_docx

        formal_path = generate_formal_case_report_docx(case)
        report["formal_report"] = {"status": "passed", "path": str(formal_path)}
    except Exception as exc:
        report["formal_report"] = {"status": "failed", "reason": str(exc)}
    report["summary_markdown"] = write_postprocess_summary(case, report)
    # Re-write artifacts after report_json exists and has final size.
    report["artifacts_json"] = _write_artifact_manifest(case, report)
    report["artifacts"] = _read_json(Path(report["artifacts_json"])).get("artifacts", [])
    report["manifest_update"] = reconcile_manifest_after_postprocess(case, report)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  [5.10] 写入报告与 artifact manifest：完成")
    print("[5/6] 后处理与可视化：完成")
    return report
