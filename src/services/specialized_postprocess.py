from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .case_manifest import read_dieswell_geometry_metadata
from .visualization import ensure_foam_file


DIESWELL_TEMPLATE_IDS = {
    "rheotool_5_3_3_dieswell_oldroydb_log",
    "rheotool_5_3_3_dieswell_giesekuslog",
    "rheotool_5_3_3_dieswell_carreauyasuda",
}

DAMBREAK_TEMPLATE_IDS = {
    "foundation_v10_interfoam_dambreak",
    "foundation_v10_interfoam_dambreak_laminar_full_allrun",
    "foundation_v10_interfoam_dambreak_with_obstacle",
    "foundation_v10_interfoam_ras_dambreak",
    "foundation_v10_interfoam_ras_dambreak_full_allrun",
    "foundation_v10_interfoam_ras_dambreak_porous_baffle",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _template_id(case_dir: Path) -> str | None:
    note = _read_json(case_dir / "TUTORIAL_TEMPLATE_IMPORT.json")
    value = note.get("template_id")
    return str(value) if value else None


def is_dieswell_case(case_dir: str | Path, *, user_requirement: str = "") -> bool:
    case = Path(case_dir)
    template_id = _template_id(case)
    if template_id in DIESWELL_TEMPLATE_IDS:
        return True
    lowered = str(user_requirement or "").lower()
    return any(term in lowered for term in ("dieswell", "die swell", "die-swell", "挤出胀大", "模口胀大"))


def is_dambreak_case(case_dir: str | Path, *, user_requirement: str = "") -> bool:
    case = Path(case_dir)
    template_id = _template_id(case)
    if template_id in DAMBREAK_TEMPLATE_IDS:
        return True
    lowered = str(user_requirement or "").lower()
    return any(term in lowered for term in ("dambreak", "dam break", "破坝", "溃坝", "水柱坍塌"))


def _dieswell_template_geometry(template_id: str | None) -> dict[str, float] | None:
    if template_id in DIESWELL_TEMPLATE_IDS:
        # RheoTool 5.3.3 DieSwell tutorials use a symmetry plane at y=0,
        # die exit at x=0, and die half-height y=1 in blockMeshDict.
        return {
            "die_exit_x": 0.0,
            "die_exit_half_height": 1.0,
            "downstream_min_x": 0.0,
        }
    return None


def _dieswell_geometry(case: Path, template_id: str | None) -> tuple[dict[str, float] | None, str]:
    metadata = read_dieswell_geometry_metadata(case)
    if metadata:
        try:
            return {
                "die_exit_x": float(metadata["die_exit_x"]),
                "die_exit_half_height": float(metadata["die_exit_half_height"]),
                "downstream_min_x": float(metadata.get("downstream_min_x", metadata["die_exit_x"])),
            }, str(metadata.get("source") or "manifest")
        except (KeyError, TypeError, ValueError):
            return None, "invalid_manifest"
    template_geometry = _dieswell_template_geometry(template_id)
    return template_geometry, "template_fallback" if template_geometry else "missing"


def compute_dieswell_swell_metrics(
    points: Iterable[Iterable[float]],
    *,
    die_exit_x: float = 0.0,
    die_exit_half_height: float = 1.0,
    downstream_min_x: float | None = None,
    x_tolerance: float = 1e-9,
) -> dict[str, Any]:
    """Compute planar die-swell metrics from alpha=0.5 free-surface points.

    The metric is reported as half-height ratio because RheoTool DieSwell is a
    half-domain with a symmetry plane at y=0. For a symmetric full die, the full
    width ratio is identical to max_half_height / die_exit_half_height.
    """
    rows: list[tuple[float, float, float]] = []
    for point in points:
        values = list(point)
        if len(values) < 2:
            continue
        x = float(values[0])
        y = float(values[1])
        z = float(values[2]) if len(values) > 2 else 0.0
        rows.append((x, y, z))

    if not rows:
        return {"status": "skipped", "reason": "free-surface contour has no points"}
    if die_exit_half_height <= 0:
        return {"status": "failed", "reason": "die_exit_half_height must be positive"}

    min_x = downstream_min_x if downstream_min_x is not None else die_exit_x
    downstream = [row for row in rows if row[0] >= min_x - x_tolerance and row[1] >= 0]
    if not downstream:
        return {
            "status": "skipped",
            "reason": "no free-surface contour points found downstream of die exit",
            "die_exit_x": die_exit_x,
            "downstream_min_x": min_x,
            "point_count": len(rows),
        }

    max_point = max(downstream, key=lambda row: row[1])
    max_half_height = float(max_point[1])
    swell_ratio = max_half_height / die_exit_half_height
    return {
        "status": "passed",
        "definition": "planar half-domain swell_ratio = max_free_surface_y_downstream / die_exit_half_height; full-width ratio is identical for symmetric cases",
        "die_exit_x": float(die_exit_x),
        "downstream_min_x": float(min_x),
        "die_exit_half_height": float(die_exit_half_height),
        "die_exit_full_width": float(2.0 * die_exit_half_height),
        "max_half_height": max_half_height,
        "max_full_width": float(2.0 * max_half_height),
        "swell_ratio": float(swell_ratio),
        "max_location": {"x": float(max_point[0]), "y": float(max_point[1]), "z": float(max_point[2])},
        "point_count": len(rows),
        "downstream_point_count": len(downstream),
    }


def compute_dambreak_front_metrics(points: Iterable[Iterable[float]]) -> dict[str, Any]:
    """Compute damBreak free-surface/front metrics from alpha=0.5 contour points."""
    rows: list[tuple[float, float, float]] = []
    for point in points:
        values = list(point)
        if len(values) < 2:
            continue
        x = float(values[0])
        y = float(values[1])
        z = float(values[2]) if len(values) > 2 else 0.0
        rows.append((x, y, z))

    if not rows:
        return {"status": "skipped", "reason": "free-surface contour has no points"}

    front = max(rows, key=lambda row: row[0])
    highest = max(rows, key=lambda row: row[1])
    lowest = min(rows, key=lambda row: row[1])
    return {
        "status": "passed",
        "definition": "damBreak water-front metrics from alpha.water=0.5 contour; front_x = max contour x",
        "front_x": float(front[0]),
        "front_location": {"x": float(front[0]), "y": float(front[1]), "z": float(front[2])},
        "max_height": float(highest[1]),
        "max_height_location": {"x": float(highest[0]), "y": float(highest[1]), "z": float(highest[2])},
        "min_height": float(lowest[1]),
        "point_count": len(rows),
    }


def _combined_openfoam_mesh(case: Path, time_name: str) -> Any:
    import pyvista as pv

    foam_file = ensure_foam_file(str(case))
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
    try:
        mesh = mesh.cell_data_to_point_data(pass_cell_data=True)
    except Exception:
        pass
    return mesh


def _find_alpha_field(mesh: Any) -> str | None:
    names: list[str] = []
    for container_name in ("point_data", "cell_data"):
        try:
            names.extend(list(getattr(mesh, container_name, {}).keys()))
        except Exception:
            pass
    for preferred in ("alpha.water", "alpha"):
        if preferred in names:
            return preferred
    for name in names:
        if str(name).startswith("alpha."):
            return str(name)
    return None


def _free_surface_points(mesh: Any, alpha_field: str) -> list[tuple[float, float, float]]:
    contour = mesh.contour(isosurfaces=[0.5], scalars=alpha_field)
    points = getattr(contour, "points", [])
    return [(float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0) for p in points]


def _numeric_time_dirs(case: Path) -> list[str]:
    times: list[tuple[float, str]] = []
    for child in case.iterdir():
        if not child.is_dir():
            continue
        try:
            value = float(child.name)
        except ValueError:
            continue
        times.append((value, child.name))
    return [name for _, name in sorted(times)]


def _plotter(output: Path, *, title: str):
    import pyvista as pv

    try:
        pv.OFF_SCREEN = True
        pv.start_xvfb()
    except Exception:
        pass
    plotter = pv.Plotter(off_screen=True, window_size=(1400, 720))
    plotter.set_background("white")
    plotter.add_text(title, font_size=11, color="black")
    return plotter


def _clip_to_bounds(mesh: Any, bounds: tuple[float, float, float, float, float, float] | None) -> Any:
    if bounds is None:
        return mesh
    try:
        clipped = mesh.clip_box(bounds=bounds, invert=False)
        if getattr(clipped, "n_cells", 0) > 0:
            return clipped
    except Exception:
        pass
    return mesh


def _view_xy_and_save(plotter: Any, output: Path) -> str:
    plotter.view_xy()
    try:
        plotter.enable_parallel_projection()
    except Exception:
        pass
    plotter.reset_camera()
    plotter.screenshot(str(output))
    plotter.close()
    return str(output)


def _mesh_array(mesh: Any, field: str) -> tuple[str, Any, str] | None:
    import numpy as np

    if field == "N1.water":
        for location, container in (("point", getattr(mesh, "point_data", {})), ("cell", getattr(mesh, "cell_data", {}))):
            if "tau.water" not in container:
                continue
            values = np.asarray(container["tau.water"])
            # OpenFOAM symmTensor order is (xx xy xz yy yz zz).
            if values.ndim == 2 and values.shape[1] >= 4:
                return "N1=tau_xx-tau_yy", values[:, 0] - values[:, 3], location
        return None

    for location, container in (("point", getattr(mesh, "point_data", {})), ("cell", getattr(mesh, "cell_data", {}))):
        if field not in container:
            continue
        values = np.asarray(container[field])
        if values.ndim == 1 or (values.ndim == 2 and values.shape[1] == 1):
            return field, values.reshape(-1), location
        if field == "U":
            name = "|U|"
        elif field.startswith("tau"):
            name = f"|{field}|"
        else:
            name = f"|{field}|"
        return name, np.linalg.norm(values, axis=1), location
    return None


def _field_stats(mesh: Any, values: Any, location: str) -> dict[str, Any]:
    import numpy as np

    stats = {
        "min": float(np.nanmin(values)),
        "max": float(np.nanmax(values)),
        "mean": float(np.nanmean(values)),
    }
    try:
        if location == "point" and len(values) == len(mesh.points):
            point = mesh.points[int(np.nanargmax(values))]
        else:
            centers = mesh.cell_centers().points
            point = centers[int(np.nanargmax(values))]
        stats["max_location"] = {"x": float(point[0]), "y": float(point[1]), "z": float(point[2]) if len(point) > 2 else 0.0}
    except Exception:
        pass
    return stats


def _plot_mesh_overview(
    case: Path,
    *,
    time_name: str,
    output: Path,
    view_bounds: tuple[float, float, float, float, float, float] | None = None,
    title_prefix: str = "DieSwell",
) -> dict[str, Any]:
    try:
        mesh = _combined_openfoam_mesh(case, time_name)
        mesh = _clip_to_bounds(mesh, view_bounds)
        title = f"{title_prefix} mesh overview, t={time_name}"
        if view_bounds is not None:
            title = f"{title_prefix} mesh zoom, t={time_name}"
        plotter = _plotter(output, title=title)
        plotter.add_mesh(mesh, style="wireframe", color="black", line_width=0.25)
        plotter.add_axes()
        _view_xy_and_save(plotter, output)
        result = {"status": "passed", "path": str(output), "time": time_name}
        if view_bounds is not None:
            result["view_bounds"] = list(view_bounds)
        return result
    except Exception as exc:
        return {"status": "failed", "reason": str(exc), "path": str(output), "time": time_name}


def _plot_field_snapshot(
    case: Path,
    *,
    time_name: str,
    field: str,
    output: Path,
    view_bounds: tuple[float, float, float, float, float, float] | None = None,
) -> dict[str, Any]:
    try:
        mesh = _combined_openfoam_mesh(case, time_name)
        mesh = _clip_to_bounds(mesh, view_bounds)
        array = _mesh_array(mesh, field)
        if array is None:
            return {"status": "skipped", "reason": f"field {field} not found", "field": field, "time": time_name}
        scalar_name, values, location = array
        mesh = mesh.copy()
        if location == "point":
            mesh.point_data[scalar_name] = values
        else:
            mesh.cell_data[scalar_name] = values
        title = f"{scalar_name} field, t={time_name}"
        if view_bounds is not None:
            title = f"{scalar_name} die-lip zoom, t={time_name}"
        plotter = _plotter(output, title=title)
        plotter.add_mesh(mesh, scalars=scalar_name, cmap="viridis", show_scalar_bar=True)
        plotter.add_mesh(mesh.outline(), color="black", line_width=1.0)
        _view_xy_and_save(plotter, output)
        result = {
            "status": "passed",
            "path": str(output),
            "field": field,
            "plotted_scalar": scalar_name,
            "time": time_name,
            "stats": _field_stats(mesh, values, location),
        }
        if view_bounds is not None:
            result["view_bounds"] = list(view_bounds)
        return result
    except Exception as exc:
        return {"status": "failed", "reason": str(exc), "field": field, "time": time_name, "path": str(output)}


def _plot_free_surface_overlay(
    case: Path,
    *,
    time_names: list[str],
    geometry: dict[str, float],
    output: Path,
) -> dict[str, Any]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plotted = 0
        plt.figure(figsize=(8, 4.8), dpi=160)
        for time_name in time_names:
            mesh = _combined_openfoam_mesh(case, time_name)
            alpha_field = _find_alpha_field(mesh)
            if not alpha_field:
                continue
            points = _free_surface_points(mesh, alpha_field)
            if not points:
                continue
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            plt.scatter(xs, ys, s=3 if time_name == time_names[-1] else 2, alpha=0.75, label=f"t={time_name}")
            plotted += 1
        if plotted == 0:
            plt.close()
            return {"status": "skipped", "reason": "no alpha=0.5 contours extracted"}
        plt.axvline(geometry["die_exit_x"], color="black", linestyle="--", linewidth=1, label="die exit")
        plt.axhline(geometry["die_exit_half_height"], color="gray", linestyle=":", linewidth=1, label="die half-height")
        plt.xlabel("x")
        plt.ylabel("y (half-domain)")
        plt.title("DieSwell free-surface evolution")
        plt.grid(True, alpha=0.25)
        plt.legend(loc="best", fontsize=8)
        plt.tight_layout()
        plt.savefig(output)
        plt.close()
        return {"status": "passed", "path": str(output), "times": time_names, "contours": plotted}
    except Exception as exc:
        return {"status": "failed", "reason": str(exc), "path": str(output)}


def _plot_swell_ratio_history(
    case: Path,
    *,
    time_names: list[str],
    geometry: dict[str, float],
    csv_path: Path,
    output: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for time_name in time_names:
        try:
            mesh = _combined_openfoam_mesh(case, time_name)
            alpha_field = _find_alpha_field(mesh)
            if not alpha_field:
                rows.append({"time": time_name, "status": "skipped", "reason": "alpha field missing"})
                continue
            points = _free_surface_points(mesh, alpha_field)
            metrics = compute_dieswell_swell_metrics(points, **geometry)
            rows.append({"time": time_name, **metrics})
        except Exception as exc:
            rows.append({"time": time_name, "status": "failed", "reason": str(exc)})

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time", "status", "swell_ratio", "max_half_height", "max_x", "max_y", "point_count", "reason"])
        for row in rows:
            loc = row.get("max_location") or {}
            writer.writerow([
                row.get("time"),
                row.get("status"),
                row.get("swell_ratio"),
                row.get("max_half_height"),
                loc.get("x"),
                loc.get("y"),
                row.get("point_count"),
                row.get("reason", ""),
            ])

    passed = [row for row in rows if row.get("status") == "passed"]
    if not passed:
        return {"status": "skipped", "reason": "no passed time-step swell metrics", "csv": str(csv_path)}
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        xs = [float(row["time"]) for row in passed]
        ys = [float(row["swell_ratio"]) for row in passed]
        plt.figure(figsize=(7.2, 4.2), dpi=160)
        plt.plot(xs, ys, marker="o", linewidth=1.5)
        plt.xlabel("time")
        plt.ylabel("swell ratio")
        plt.title("DieSwell swell ratio evolution")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output)
        plt.close()
        return {
            "status": "passed",
            "csv": str(csv_path),
            "plot": str(output),
            "rows": len(rows),
            "passed_rows": len(passed),
            "final_swell_ratio": ys[-1],
        }
    except Exception as exc:
        return {"status": "failed", "reason": str(exc), "csv": str(csv_path), "plot": str(output)}


def _plot_dambreak_free_surface_overlay(
    case: Path,
    *,
    time_names: list[str],
    output: Path,
) -> dict[str, Any]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plotted = 0
        plt.figure(figsize=(8, 4.8), dpi=160)
        for time_name in time_names:
            mesh = _combined_openfoam_mesh(case, time_name)
            alpha_field = _find_alpha_field(mesh)
            if not alpha_field:
                continue
            points = _free_surface_points(mesh, alpha_field)
            if not points:
                continue
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            plt.scatter(xs, ys, s=3 if time_name == time_names[-1] else 2, alpha=0.75, label=f"t={time_name}")
            plotted += 1
        if plotted == 0:
            plt.close()
            return {"status": "skipped", "reason": "no alpha=0.5 contours extracted"}
        plt.xlabel("x")
        plt.ylabel("y")
        plt.title("damBreak free-surface evolution")
        plt.grid(True, alpha=0.25)
        plt.legend(loc="best", fontsize=8)
        plt.tight_layout()
        plt.savefig(output)
        plt.close()
        return {"status": "passed", "path": str(output), "times": time_names, "contours": plotted}
    except Exception as exc:
        return {"status": "failed", "reason": str(exc), "path": str(output)}


def _plot_dambreak_front_history(
    case: Path,
    *,
    time_names: list[str],
    csv_path: Path,
    output: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for time_name in time_names:
        try:
            mesh = _combined_openfoam_mesh(case, time_name)
            alpha_field = _find_alpha_field(mesh)
            if not alpha_field:
                rows.append({"time": time_name, "status": "skipped", "reason": "alpha field missing"})
                continue
            points = _free_surface_points(mesh, alpha_field)
            rows.append({"time": time_name, **compute_dambreak_front_metrics(points)})
        except Exception as exc:
            rows.append({"time": time_name, "status": "failed", "reason": str(exc)})

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time", "status", "front_x", "front_y", "max_height", "point_count", "reason"])
        for row in rows:
            loc = row.get("front_location") or {}
            writer.writerow([
                row.get("time"),
                row.get("status"),
                row.get("front_x"),
                loc.get("y"),
                row.get("max_height"),
                row.get("point_count"),
                row.get("reason", ""),
            ])

    passed = [row for row in rows if row.get("status") == "passed"]
    if not passed:
        return {"status": "skipped", "reason": "no passed time-step front metrics", "csv": str(csv_path)}
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        xs = [float(row["time"]) for row in passed]
        ys = [float(row["front_x"]) for row in passed]
        plt.figure(figsize=(7.2, 4.2), dpi=160)
        plt.plot(xs, ys, marker="o", linewidth=1.5)
        plt.xlabel("time")
        plt.ylabel("water-front x")
        plt.title("damBreak water-front advancement")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output)
        plt.close()
        return {
            "status": "passed",
            "csv": str(csv_path),
            "plot": str(output),
            "rows": len(rows),
            "passed_rows": len(passed),
            "final_front_x": ys[-1],
        }
    except Exception as exc:
        return {"status": "failed", "reason": str(exc), "csv": str(csv_path), "plot": str(output)}


def generate_dieswell_enhanced_figures(
    case_dir: str | Path,
    *,
    latest_time: str,
    user_requirement: str = "",
) -> dict[str, Any]:
    """Generate customer-facing DieSwell figures without rerunning the solver."""
    case = Path(case_dir)
    if not is_dieswell_case(case, user_requirement=user_requirement):
        return {"status": "skipped", "reason": "not a DieSwell case"}

    template_id = _template_id(case)
    geometry, geometry_source = _dieswell_geometry(case, template_id)
    if geometry is None:
        return {"status": "skipped", "reason": "DieSwell geometry metadata unavailable", "template_id": template_id}

    post_dir = case / "postprocess"
    post_dir.mkdir(exist_ok=True)
    times = _numeric_time_dirs(case)
    initial_time = times[0] if times else "0"
    final_time = latest_time
    overlay_times = [time for time in [initial_time, final_time] if time is not None]
    if initial_time != final_time and len(times) > 2:
        mid = times[len(times) // 2]
        overlay_times = [initial_time, mid, final_time]

    die_lip_bounds = (-5.0, 10.0, 0.0, 2.2, -0.05, 1.05)

    mesh = _plot_mesh_overview(case, time_name=final_time, output=post_dir / "dieswell_mesh_overview.png")
    mesh_zoom = _plot_mesh_overview(
        case,
        time_name=final_time,
        output=post_dir / "dieswell_mesh_die_lip_zoom.png",
        view_bounds=die_lip_bounds,
    )
    fields: dict[str, Any] = {}
    zoom_fields: dict[str, Any] = {}
    for field in ("U", "p_rgh", "tau.water", "alpha.water"):
        safe = field.replace(".", "_")
        initial = _plot_field_snapshot(
            case,
            time_name=initial_time,
            field=field,
            output=post_dir / f"dieswell_{safe}_initial.png",
        )
        if initial.get("status") != "passed":
            for fallback_time in times[1:]:
                initial = _plot_field_snapshot(
                    case,
                    time_name=fallback_time,
                    field=field,
                    output=post_dir / f"dieswell_{safe}_initial.png",
                )
                if initial.get("status") == "passed":
                    initial["requested_time"] = initial_time
                    initial["time_role"] = "initial_available"
                    initial["note"] = (
                        f"Requested initial time {initial_time} was not readable for {field}; "
                        f"using first available written time {fallback_time}."
                    )
                    break
        fields[f"{field}:initial"] = initial
        fields[f"{field}:final"] = _plot_field_snapshot(
            case,
            time_name=final_time,
            field=field,
            output=post_dir / f"dieswell_{safe}_final.png",
        )

    for field in ("U", "p_rgh", "tau.water", "N1.water", "alpha.water"):
        safe = field.replace(".", "_")
        initial = _plot_field_snapshot(
            case,
            time_name=initial_time,
            field=field,
            output=post_dir / f"dieswell_{safe}_zoom_initial.png",
            view_bounds=die_lip_bounds,
        )
        if initial.get("status") != "passed":
            for fallback_time in times[1:]:
                initial = _plot_field_snapshot(
                    case,
                    time_name=fallback_time,
                    field=field,
                    output=post_dir / f"dieswell_{safe}_zoom_initial.png",
                    view_bounds=die_lip_bounds,
                )
                if initial.get("status") == "passed":
                    initial["requested_time"] = initial_time
                    initial["time_role"] = "initial_available"
                    initial["note"] = (
                        f"Requested initial time {initial_time} was not readable for {field}; "
                        f"using first available written time {fallback_time}."
                    )
                    break
        zoom_fields[f"{field}:initial"] = initial
        zoom_fields[f"{field}:final"] = _plot_field_snapshot(
            case,
            time_name=final_time,
            field=field,
            output=post_dir / f"dieswell_{safe}_zoom_final.png",
            view_bounds=die_lip_bounds,
        )

    overlay = _plot_free_surface_overlay(
        case,
        time_names=overlay_times,
        geometry=geometry,
        output=post_dir / "dieswell_free_surface_initial_final_overlay.png",
    )
    history = _plot_swell_ratio_history(
        case,
        time_names=times,
        geometry=geometry,
        csv_path=post_dir / "dieswell_swell_ratio_vs_time.csv",
        output=post_dir / "dieswell_swell_ratio_vs_time.png",
    )
    passed = [item for item in [mesh, overlay, history, *fields.values()] if item.get("status") == "passed"]
    return {
        "status": "passed" if passed else "failed",
        "template_id": template_id,
        "geometry_source": geometry_source,
        "initial_time": initial_time,
        "final_time": final_time,
        "mesh": mesh,
        "mesh_zoom": mesh_zoom,
        "fields": fields,
        "zoom_fields": zoom_fields,
        "zoom_bounds": list(die_lip_bounds),
        "free_surface_overlay": overlay,
        "swell_ratio_history": history,
    }


def generate_dieswell_free_surface_postprocess(
    case_dir: str | Path,
    *,
    time_name: str,
    user_requirement: str = "",
) -> dict[str, Any]:
    """Generate DieSwell free-surface contour, swell metrics, CSV, and PNG."""
    case = Path(case_dir)
    if not is_dieswell_case(case, user_requirement=user_requirement):
        return {"status": "skipped", "reason": "not a DieSwell case"}

    template_id = _template_id(case)
    geometry, geometry_source = _dieswell_geometry(case, template_id)
    if geometry is None:
        return {
            "status": "skipped",
            "reason": "DieSwell geometry metadata is unavailable or invalid; provide die_exit_x and die_exit_half_height/die_exit_width in manifest or user_requirement",
            "template_id": template_id,
            "geometry_source": geometry_source,
        }

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        return {"status": "skipped", "reason": f"plotting dependencies unavailable: {exc}"}

    try:
        mesh = _combined_openfoam_mesh(case, time_name)
        alpha_field = _find_alpha_field(mesh)
        if not alpha_field:
            return {"status": "skipped", "reason": "alpha.water field not found", "template_id": template_id}
        points = _free_surface_points(mesh, alpha_field)
    except Exception as exc:
        return {"status": "failed", "reason": f"failed to extract alpha=0.5 free surface: {exc}", "template_id": template_id}

    metrics = compute_dieswell_swell_metrics(points, **geometry)
    post_dir = case / "postprocess"
    post_dir.mkdir(exist_ok=True)
    csv_path = post_dir / "dieswell_free_surface_alpha05.csv"
    png_path = post_dir / "dieswell_free_surface_swell_ratio.png"
    json_path = post_dir / "dieswell_swell_metrics.json"

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["x", "y", "z"])
        for point in sorted(points, key=lambda row: (row[0], row[1], row[2])):
            writer.writerow([point[0], point[1], point[2]])

    if metrics.get("status") == "passed":
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        plt.figure(figsize=(8, 4.8), dpi=160)
        plt.scatter(xs, ys, s=3, alpha=0.65, label="alpha.water=0.5")
        plt.axvline(metrics["die_exit_x"], color="black", linestyle="--", linewidth=1, label="die exit")
        plt.axhline(metrics["die_exit_half_height"], color="gray", linestyle=":", linewidth=1, label="die half-height")
        max_loc = metrics["max_location"]
        plt.scatter([max_loc["x"]], [max_loc["y"]], color="red", s=30, label="max swell")
        plt.annotate(
            f"B={metrics['swell_ratio']:.4g}",
            xy=(max_loc["x"], max_loc["y"]),
            xytext=(8, 8),
            textcoords="offset points",
            color="red",
        )
        plt.xlabel("x")
        plt.ylabel("y (half-domain)")
        plt.title(f"DieSwell free surface and swell ratio, t={time_name}")
        plt.grid(True, alpha=0.25)
        plt.legend(loc="best")
        plt.tight_layout()
        plt.savefig(png_path)
        plt.close()
    else:
        # Still produce a diagnostic point cloud plot if contour extraction worked.
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        plt.figure(figsize=(8, 4.8), dpi=160)
        plt.scatter(xs, ys, s=3, alpha=0.65)
        plt.xlabel("x")
        plt.ylabel("y")
        plt.title(f"DieSwell alpha.water=0.5 contour, t={time_name}")
        plt.grid(True, alpha=0.25)
        plt.tight_layout()
        plt.savefig(png_path)
        plt.close()

    result = {
        **metrics,
        "template_id": template_id,
        "time": time_name,
        "alpha_field": "alpha.water",
        "contour_level": 0.5,
        "geometry_source": geometry_source,
        "csv": str(csv_path),
        "plot": str(png_path),
        "metrics_json": str(json_path),
        "assumptions": [
            "RheoTool 5.3.3 DieSwell template geometry: die exit x=0, symmetry plane y=0, die half-height=1.",
            "Free surface is approximated by alpha.water=0.5 contour.",
        ],
    }
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def generate_dambreak_free_surface_postprocess(
    case_dir: str | Path,
    *,
    time_name: str,
    user_requirement: str = "",
) -> dict[str, Any]:
    """Generate damBreak free-surface contour, water-front metrics, CSV, and PNG."""
    case = Path(case_dir)
    if not is_dambreak_case(case, user_requirement=user_requirement):
        return {"status": "skipped", "reason": "not a damBreak case"}

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        return {"status": "skipped", "reason": f"plotting dependencies unavailable: {exc}"}

    try:
        mesh = _combined_openfoam_mesh(case, time_name)
        alpha_field = _find_alpha_field(mesh)
        if not alpha_field:
            return {"status": "skipped", "reason": "alpha.water field not found"}
        points = _free_surface_points(mesh, alpha_field)
    except Exception as exc:
        return {"status": "failed", "reason": f"failed to extract alpha=0.5 free surface: {exc}"}

    metrics = compute_dambreak_front_metrics(points)
    post_dir = case / "postprocess"
    post_dir.mkdir(exist_ok=True)
    csv_path = post_dir / "dambreak_free_surface_alpha05.csv"
    png_path = post_dir / "dambreak_free_surface_front.png"
    json_path = post_dir / "dambreak_front_metrics.json"

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["x", "y", "z"])
        for point in sorted(points, key=lambda row: (row[0], row[1], row[2])):
            writer.writerow([point[0], point[1], point[2]])

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    plt.figure(figsize=(8, 4.8), dpi=160)
    plt.scatter(xs, ys, s=3, alpha=0.65, label="alpha.water=0.5")
    if metrics.get("status") == "passed":
        front = metrics["front_location"]
        plt.scatter([front["x"]], [front["y"]], color="red", s=32, label="water front")
        plt.annotate(
            f"x_front={metrics['front_x']:.4g}",
            xy=(front["x"], front["y"]),
            xytext=(8, 8),
            textcoords="offset points",
            color="red",
        )
    plt.xlabel("x")
    plt.ylabel("y")
    plt.title(f"damBreak free surface and water front, t={time_name}")
    plt.grid(True, alpha=0.25)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(png_path)
    plt.close()

    result = {
        **metrics,
        "time": time_name,
        "alpha_field": "alpha.water",
        "contour_level": 0.5,
        "csv": str(csv_path),
        "plot": str(png_path),
        "metrics_json": str(json_path),
        "assumptions": [
            "Free surface is approximated by alpha.water=0.5 contour.",
            "Water-front location is approximated by the maximum x coordinate on the alpha.water=0.5 contour.",
        ],
    }
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def generate_dambreak_enhanced_figures(
    case_dir: str | Path,
    *,
    latest_time: str,
    user_requirement: str = "",
) -> dict[str, Any]:
    """Generate customer-facing damBreak figures without rerunning the solver."""
    case = Path(case_dir)
    if not is_dambreak_case(case, user_requirement=user_requirement):
        return {"status": "skipped", "reason": "not a damBreak case"}

    post_dir = case / "postprocess"
    post_dir.mkdir(exist_ok=True)
    times = _numeric_time_dirs(case)
    initial_time = times[0] if times else "0"
    final_time = latest_time
    overlay_times = [time for time in [initial_time, final_time] if time is not None]
    if initial_time != final_time and len(times) > 2:
        mid = times[len(times) // 2]
        overlay_times = [initial_time, mid, final_time]

    mesh = _plot_mesh_overview(
        case,
        time_name=final_time,
        output=post_dir / "dambreak_mesh_overview.png",
        title_prefix="damBreak",
    )

    fields: dict[str, Any] = {}
    for field in ("alpha.water", "U", "p_rgh", "p"):
        safe = field.replace(".", "_")
        initial = _plot_field_snapshot(
            case,
            time_name=initial_time,
            field=field,
            output=post_dir / f"dambreak_{safe}_initial.png",
        )
        if initial.get("status") != "passed":
            for fallback_time in times[1:]:
                initial = _plot_field_snapshot(
                    case,
                    time_name=fallback_time,
                    field=field,
                    output=post_dir / f"dambreak_{safe}_initial.png",
                )
                if initial.get("status") == "passed":
                    initial["requested_time"] = initial_time
                    initial["time_role"] = "initial_available"
                    initial["note"] = (
                        f"Requested initial time {initial_time} was not readable for {field}; "
                        f"using first available written time {fallback_time}."
                    )
                    break
        fields[f"{field}:initial"] = initial
        fields[f"{field}:final"] = _plot_field_snapshot(
            case,
            time_name=final_time,
            field=field,
            output=post_dir / f"dambreak_{safe}_final.png",
        )

    overlay = _plot_dambreak_free_surface_overlay(
        case,
        time_names=overlay_times,
        output=post_dir / "dambreak_free_surface_initial_final_overlay.png",
    )
    history = _plot_dambreak_front_history(
        case,
        time_names=times,
        csv_path=post_dir / "dambreak_front_x_vs_time.csv",
        output=post_dir / "dambreak_front_x_vs_time.png",
    )
    passed = [item for item in [mesh, overlay, history, *fields.values()] if item.get("status") == "passed"]
    return {
        "status": "passed" if passed else "failed",
        "template_id": _template_id(case),
        "initial_time": initial_time,
        "final_time": final_time,
        "mesh": mesh,
        "fields": fields,
        "free_surface_overlay": overlay,
        "front_history": history,
    }
