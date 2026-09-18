from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from models import CaseTarget


IMMUTABLE_TARGET_FIELDS = ("channel", "version", "solver", "distribution")
DIESWELL_TEMPLATE_IDS = {
    "rheotool_5_3_3_dieswell_oldroydb_log",
    "rheotool_5_3_3_dieswell_giesekuslog",
    "rheotool_5_3_3_dieswell_carreauyasuda",
}


def _asdict_or_empty(value: Any) -> dict[str, Any]:
    return asdict(value) if value is not None else {}


def _text_from_problem_intent(problem_intent: Any) -> str:
    if problem_intent is None:
        return ""
    if isinstance(problem_intent, dict):
        return str(problem_intent.get("application") or "")
    return str(getattr(problem_intent, "application", "") or "")


def _intent_field(problem_intent: Any, field: str) -> Any:
    if problem_intent is None:
        return None
    if isinstance(problem_intent, dict):
        return problem_intent.get(field)
    return getattr(problem_intent, field, None)


def _extract_named_float(text: str, names: tuple[str, ...]) -> float | None:
    number = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
    for name in names:
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(name)}\s*(?:=|:|：|为)\s*{number}"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _extract_symmetry(text: str) -> str | None:
    match = re.search(r"symmetry[_\s-]*plane\s*(?:=|:|：|为)\s*([A-Za-z][A-Za-z0-9_+\-=.]*)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    if "对称面 y=0" in text or "symmetry y=0" in text.lower():
        return "y=0"
    if "无对称" in text or "full domain" in text.lower():
        return "none"
    return None


def _dieswell_template_geometry(template_id: str | None) -> dict[str, Any] | None:
    if template_id not in DIESWELL_TEMPLATE_IDS:
        return None
    return {
        "schema_version": 1,
        "geometry_class": "die_swell",
        "source": "template_metadata",
        "template_id": template_id,
        "die_exit_x": 0.0,
        "die_exit_half_height": 1.0,
        "die_exit_full_width": 2.0,
        "downstream_min_x": 0.0,
        "symmetry_plane": "y=0",
        "notes": [
            "RheoTool 5.3.3 DieSwell template: die exit x=0, symmetry plane y=0, die half-height=1."
        ],
    }


def dieswell_geometry_metadata_from_intent(problem_intent: Any) -> dict[str, Any] | None:
    """Extract DieSwell specialized-postprocess geometry metadata.

    The metadata is only emitted when it is either a known template geometry or
    the user supplied enough real-geometry values to define the swell ratio.  It
    intentionally does not invent dimensions for real customer geometries.
    """
    geometry_class = _intent_field(problem_intent, "geometry_class")
    reproduction_target = _intent_field(problem_intent, "reproduction_target")
    template_geometry = _dieswell_template_geometry(str(reproduction_target) if reproduction_target else None)
    if template_geometry:
        return template_geometry
    if geometry_class != "die_swell":
        return None

    text = _text_from_problem_intent(problem_intent)
    die_exit_x = _extract_named_float(text, ("die_exit_x", "die exit x", "出口x", "口模出口x"))
    half_height = _extract_named_float(
        text,
        ("die_exit_half_height", "die half height", "half_height", "口模半高", "出口半高"),
    )
    full_width = _extract_named_float(
        text,
        ("die_exit_width", "die exit width", "die_width", "出口宽度", "口模出口宽度", "狭缝高度"),
    )
    if half_height is None and full_width is not None:
        half_height = 0.5 * full_width
    if full_width is None and half_height is not None:
        full_width = 2.0 * half_height
    downstream_min_x = _extract_named_float(text, ("downstream_min_x", "downstream min x", "下游起点x"))
    if downstream_min_x is None and die_exit_x is not None:
        downstream_min_x = die_exit_x
    symmetry = _extract_symmetry(text)

    if die_exit_x is None or half_height is None:
        return None
    return {
        "schema_version": 1,
        "geometry_class": "die_swell",
        "source": "user_requirement",
        "die_exit_x": float(die_exit_x),
        "die_exit_half_height": float(half_height),
        "die_exit_full_width": float(full_width),
        "downstream_min_x": float(downstream_min_x if downstream_min_x is not None else die_exit_x),
        "symmetry_plane": symmetry or "unknown",
        "required_for": ["free_surface_contour", "swell_ratio"],
    }


def read_dieswell_geometry_metadata(case_dir: str | Path) -> dict[str, Any] | None:
    path = Path(case_dir) / "manifest.json"
    if not path.is_file():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    metadata = (manifest.get("specialized_postprocess") or {}).get("dieswell")
    return metadata if isinstance(metadata, dict) else None


def case_target_from_manifest(case_dir: str | Path) -> CaseTarget:
    path = Path(case_dir) / "manifest.json"
    if not path.is_file():
        raise ValueError("MANIFEST_MISSING: manifest.json is required")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return CaseTarget(**{field: manifest.get(field) for field in IMMUTABLE_TARGET_FIELDS})


def create_case_manifest(
    case_dir: str | Path,
    target: CaseTarget,
    *,
    problem_intent: Any = None,
    physics_spec: Any = None,
    rheology_spec: Any = None,
    workflow_plan: Any = None,
) -> Path:
    path = Path(case_dir) / "manifest.json"
    specialized_postprocess: dict[str, Any] = {}
    dieswell_metadata = dieswell_geometry_metadata_from_intent(problem_intent)
    if dieswell_metadata:
        specialized_postprocess["dieswell"] = dieswell_metadata

    manifest: dict[str, Any] = {
        "schema_version": 2,
        **target.as_dict(),
        "validation_status": "pending",
        "run_status": "pending",
        "artifacts": [],
        "problem_intent": _asdict_or_empty(problem_intent),
        "physics_spec": _asdict_or_empty(physics_spec),
        "rheology_spec": _asdict_or_empty(rheology_spec),
        "workflow_plan": _asdict_or_empty(workflow_plan),
        "specialized_postprocess": specialized_postprocess,
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def validate_case_manifest(case_dir: str | Path, target: CaseTarget) -> dict[str, Any]:
    path = Path(case_dir) / "manifest.json"
    if not path.is_file():
        raise ValueError("MANIFEST_MISSING: manifest.json is required")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 2:
        raise ValueError("MANIFEST_SCHEMA_MISMATCH: expected schema_version 2")
    expected = target.as_dict()
    mismatches = [
        field
        for field in IMMUTABLE_TARGET_FIELDS
        if manifest.get(field) != expected[field]
    ]
    if mismatches:
        raise ValueError(
            "MANIFEST_TARGET_MISMATCH: immutable fields differ: "
            + ", ".join(mismatches)
        )
    return manifest


def update_case_manifest_status(
    case_dir: str | Path,
    target: CaseTarget,
    *,
    validation_status: str | None = None,
    run_status: str | None = None,
) -> None:
    path = Path(case_dir) / "manifest.json"
    manifest = validate_case_manifest(case_dir, target)
    if validation_status is not None:
        manifest["validation_status"] = validation_status
    if run_status is not None:
        manifest["run_status"] = run_status
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
