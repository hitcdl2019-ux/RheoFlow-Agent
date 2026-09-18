from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from models import CaseTarget
from utils import read_case_foamfiles, scan_case_directory
from .rheofoam_parallel import enable_rheofoam_parallel_if_large


DEFAULT_RHEOTOOL_TUTORIAL_ROOT = Path("/opt/build/rheoTool/of90/tutorials")
RHEOTOOL_CUSTOM_BC_LIBS = {
    "navierSlip": "libBCRheoTool.so",
    "uLid": "libRheoToolTutorialBCs.so",
    "uCos": "libRheoToolTutorialBCs.so",
    "HBprofile": "libRheoToolTutorialBCs.so",
    "uShaft": "libRheoToolTutorialBCs.so",
    "ACPotential": "libRheoToolTutorialBCs.so",
    "linearExtrapolation": "libBCRheoTool.so",
}
RHEOTOOL_TUTORIAL_PPUTIL_LIBS = {
    "calcWi0": {"libpostProcessingRheoTool.so", "libRheoToolTutorialPPUtils.so"},
    "calcCd": {"libpostProcessingRheoTool.so", "libRheoToolTutorialPPUtils.so"},
    "calcKineticE": {"libpostProcessingRheoTool.so", "libRheoToolTutorialPPUtils.so"},
    "calcVortexL": {"libpostProcessingRheoTool.so", "libRheoToolTutorialPPUtils.so"},
    "calcW": {"libpostProcessingRheoTool.so", "libRheoToolTutorialPPUtils.so"},
    "calcFfl": {"libpostProcessingRheoTool.so", "libRheoToolTutorialPPUtils.so"},
}


RHEOTOOL_TEMPLATE_EXPECTATIONS: dict[str, dict[str, Any]] = {
    "rheotool_5_1_3_channel_oldroydb_log": {
        "geometry_class": "parallel_plate_channel",
        "model": "Oldroyd-B",
        "source_section": "5.1.3",
    },
    "rheotool_5_1_4_cavity_oldroydb_log": {
        "geometry_class": "lid_driven_cavity",
        "model": "Oldroyd-B",
        "source_section": "5.1.4",
    },
    "rheotool_5_1_5_contraction41_oldroydb_log": {
        "geometry_class": "contraction",
        "model": "Oldroyd-B",
        "source_section": "5.1.5",
    },
    "rheotool_5_1_6_cylinder_oldroydb_log": {
        "geometry_class": "confined_cylinder",
        "model": "Oldroyd-B",
        "source_section": "5.1.6",
    },
    "rheotool_5_1_7_crossslot_oldroydb_log": {
        "geometry_class": "cross_slot",
        "model": "Oldroyd-B",
        "source_section": "5.1.7",
    },
    "rheotool_5_1_8_aneurysm_herschelbulkley": {
        "geometry_class": "aneurysm",
        "model": "HerschelBulkley",
        "source_section": "5.1.8",
    },
    "rheotool_5_1_9_fluiddamper_carreauyasuda": {
        "geometry_class": "fluid_damper",
        "model": "CarreauYasuda",
        "source_section": "5.1.9",
    },
    "rheotool_5_2_2_rheotest_herschelbulkley": {
        "geometry_class": "rheotest_material_function",
        "model": "HerschelBulkley",
        "source_section": "5.2.2",
    },
    "rheotool_5_2_3_rheotest_fenecr": {
        "geometry_class": "rheotest_material_function",
        "model": "FENE-CR",
        "source_section": "5.2.3",
    },
    "rheotool_5_3_2_impactingdrop_oldroydb_log": {
        "geometry_class": "impacting_drop",
        "model": "Oldroyd-B",
        "source_section": "5.3.2",
    },
    "rheotool_5_3_3_dieswell_carreauyasuda": {
        "geometry_class": "die_swell",
        "model": "CarreauYasuda",
        "source_section": "5.3.3",
    },
    "rheotool_5_3_3_dieswell_giesekuslog": {
        "geometry_class": "die_swell",
        "model": "Giesekus",
        "source_section": "5.3.3",
    },
    "rheotool_5_3_3_dieswell_oldroydb_log": {
        "geometry_class": "die_swell",
        "model": "Oldroyd-B",
        "source_section": "5.3.3",
    },
}

RHEOTOOL_TEMPLATE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "rheotool_5_1_3_channel_oldroydb_log": {
        "solver": "rheoFoam", "relative_source": "rheoFoam/Channel/Oldroyd-BLog",
        "case_name": "rheotool-ob-plate-channel-wi099", "case_category": "rheotool_tutorial_channel_oldroydb_log",
        "matched_alias": "RheoTool user guide 6.0 section 5.1.3 Channel/Oldroyd-BLog",
    },
    "rheotool_5_1_4_cavity_oldroydb_log": {
        "solver": "rheoFoam", "relative_source": "rheoFoam/Cavity/Oldroyd-BLog",
        "case_name": "rheotool-cavity-oldroydb-fk2005", "case_category": "rheotool_tutorial_cavity_oldroydb_log",
        "matched_alias": "Fattal & Kupferman 2005 / RheoTool 5.1.4 Cavity/Oldroyd-BLog",
    },
    "rheotool_5_1_5_contraction41_oldroydb_log": {
        "solver": "rheoFoam", "relative_source": "rheoFoam/Contraction41/Oldroyd-BLog",
        "case_name": "rheotool-contraction41-oldroydb-log", "case_category": "rheotool_tutorial_contraction41_oldroydb_log",
        "matched_alias": "RheoTool user guide 6.0 section 5.1.5 Contraction41/Oldroyd-BLog",
    },
    "rheotool_5_1_6_cylinder_oldroydb_log": {
        "solver": "rheoFoam", "relative_source": "rheoFoam/Cylinder/Oldroyd-BLog",
        "case_name": "rheotool-cylinder-oldroydb-log", "case_category": "rheotool_tutorial_cylinder_oldroydb_log",
        "matched_alias": "RheoTool user guide 6.0 section 5.1.6 Cylinder/Oldroyd-BLog",
        "certification": {
            "status": "serial_certified",
            "validated_runtime": "foundation-v9+rheotool-of90",
            "source_port": "of90",
            "parallel_policy": "serial_certified",
            "start_policy": "clean_case_dir_start_from_0",
            "run_user_policy": "non_root_openfoam_user_required",
            "required_libs": ["libBCRheoTool.so"],
            "forbidden_libs": ["libRheoToolTutorialBCs.so"],
            "validated_outputs": ["Cd.txt", "postProcessing/sampleDict", "POSTPROCESS_REPORT.json"],
        },
    },
    "rheotool_5_1_7_crossslot_oldroydb_log": {
        "solver": "rheoFoam", "relative_source": "rheoFoam/CrossSlot/Oldroyd-BLog",
        "case_name": "rheotool-crossslot-oldroydb-log", "case_category": "rheotool_tutorial_crossslot_oldroydb_log",
        "matched_alias": "RheoTool user guide 6.0 section 5.1.7 CrossSlot/Oldroyd-BLog",
    },
    "rheotool_5_1_8_aneurysm_herschelbulkley": {
        "solver": "rheoFoam", "relative_source": "rheoFoam/Aneurysm/HerschelBulkley",
        "case_name": "rheotool-aneurysm-herschelbulkley", "case_category": "rheotool_tutorial_aneurysm_herschelbulkley",
        "matched_alias": "RheoTool user guide 6.0 section 5.1.8 Aneurysm/HerschelBulkley",
    },
    "rheotool_5_1_9_fluiddamper_carreauyasuda": {
        "solver": "rheoFoam", "relative_source": "rheoFoam/fluidDamper/CarreauYasuda",
        "case_name": "rheotool-fluiddamper-carreauyasuda", "case_category": "rheotool_tutorial_fluiddamper_carreauyasuda",
        "matched_alias": "RheoTool user guide 6.0 section 5.1.9 fluidDamper/CarreauYasuda",
    },
    "rheotool_5_2_2_rheotest_herschelbulkley": {
        "solver": "rheoTestFoam", "relative_source": "rheoTestFoam/HerschelBulkley",
        "case_name": "rheotest-herschelbulkley", "case_category": "rheotool_tutorial_rheotest_herschelbulkley",
        "matched_alias": "RheoTool user guide 6.0 section 5.2.2 rheoTestFoam/HerschelBulkley",
    },
    "rheotool_5_2_3_rheotest_fenecr": {
        "solver": "rheoTestFoam", "relative_source": "rheoTestFoam/FENE-CR",
        "case_name": "rheotest-fenecr", "case_category": "rheotool_tutorial_rheotest_fenecr",
        "matched_alias": "RheoTool user guide 6.0 section 5.2.3 rheoTestFoam/FENE-CR",
    },
    "rheotool_5_3_2_impactingdrop_oldroydb_log": {
        "solver": "rheoInterFoam", "relative_source": "rheoInterFoam/ImpactingDrop/Oldroyd-BLog",
        "case_name": "rheointerfoam-impactingdrop-oldroydb-log", "case_category": "rheotool_tutorial_impactingdrop_oldroydb_log",
        "matched_alias": "RheoTool user guide 6.0 section 5.3.2 ImpactingDrop/Oldroyd-BLog",
    },
    "rheotool_5_3_3_dieswell_carreauyasuda": {
        "solver": "rheoInterFoam", "relative_source": "rheoInterFoam/DieSwell/CarreauYasuda",
        "case_name": "rheointerfoam-dieswell-carreauyasuda", "case_category": "rheotool_tutorial_dieswell_carreauyasuda",
        "matched_alias": "RheoTool user guide 6.0 section 5.3.3 DieSwell/CarreauYasuda",
    },
    "rheotool_5_3_3_dieswell_giesekuslog": {
        "solver": "rheoInterFoam", "relative_source": "rheoInterFoam/DieSwell/GiesekusLog",
        "case_name": "rheointerfoam-dieswell-giesekuslog", "case_category": "rheotool_tutorial_dieswell_giesekuslog",
        "matched_alias": "RheoTool user guide 6.0 section 5.3.3 DieSwell/GiesekusLog",
    },
    "rheotool_5_3_3_dieswell_oldroydb_log": {
        "solver": "rheoInterFoam", "relative_source": "rheoInterFoam/DieSwell/Oldroyd-BLog",
        "case_name": "rheointerfoam-dieswell-oldroydb-log", "case_category": "rheotool_tutorial_dieswell_oldroydb_log",
        "matched_alias": "RheoTool user guide 6.0 section 5.3.3 DieSwell/Oldroyd-BLog",
    },
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").casefold()).strip()


def _tutorial_root() -> Path:
    return Path(os.getenv("FOAMAGENT_RHEOTOOL_TUTORIAL_ROOT", str(DEFAULT_RHEOTOOL_TUTORIAL_ROOT)))


def _template_solver_from_source(relative_source: str) -> str:
    return str(relative_source or "").split("/", 1)[0]


def _template_name(template_id: str, relative_source: str) -> str:
    section = RHEOTOOL_TEMPLATE_EXPECTATIONS.get(template_id, {}).get("source_section")
    prefix = f"RheoTool {section}" if section else "RheoTool"
    return f"{prefix} {relative_source}"


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _template_match_payload(
    *,
    template_root: Path,
    relative_source: str,
    template_id: str,
    case_name: str,
    case_category: str,
    matched_alias: str,
    score: int,
    score_reasons: list[str],
    tier: str,
) -> dict[str, Any]:
    source_dir = template_root / relative_source
    if not source_dir.is_dir():
        raise FileNotFoundError(
            "TUTORIAL_TEMPLATE_SIGNATURE_MATCH_BUT_SOURCE_MISSING: "
            f"{template_id} matched by physics signature, but source directory is missing: {source_dir}"
        )
    definition = RHEOTOOL_TEMPLATE_DEFINITIONS.get(template_id, {})
    payload = {
        "id": template_id,
        "template_name": _template_name(template_id, relative_source),
        "solver": _template_solver_from_source(relative_source),
        "source_dir": str(source_dir),
        "case_name": case_name,
        "case_domain": "rheology",
        "case_category": case_category,
        "matched_alias": matched_alias,
        "import_policy": "rheotool tutorial template import; no LLM dictionary regeneration",
        "match_score": score,
        "match_reasons": score_reasons,
        "tier": tier,
        "rag_confidence": {"A": "high", "B": "medium", "C": "low"}.get(tier, "unknown"),
    }
    if definition.get("certification"):
        payload["certification"] = definition["certification"]
    return payload


def _is_executable_openfoam_case(source_dir: Path) -> bool:
    required = (
        "Allrun",
        "system/controlDict",
        "system/fvSchemes",
        "system/fvSolution",
        "constant/constitutiveProperties",
    )
    return all((source_dir / rel_path).is_file() for rel_path in required)




def _template_payload_from_id(
    template_id: str,
    *,
    template_root: Path,
    score: int = 100,
    score_reasons: list[str] | None = None,
    tier: str = "A",
) -> dict[str, Any]:
    definition = RHEOTOOL_TEMPLATE_DEFINITIONS[template_id]
    return _template_match_payload(
        template_root=template_root,
        relative_source=definition["relative_source"],
        template_id=template_id,
        case_name=definition["case_name"],
        case_category=definition["case_category"],
        matched_alias=definition["matched_alias"],
        score=score,
        score_reasons=score_reasons or [f"reproduction_target={template_id}"],
        tier=tier,
    )


def _near(value: Any, expected: float, tol: float = 1e-9) -> bool:
    try:
        return abs(float(value) - expected) <= tol
    except (TypeError, ValueError):
        return False


def _structured_signature(compiled_workflow: Any) -> dict[str, Any]:
    if compiled_workflow is None:
        return {}
    intent = getattr(compiled_workflow, "intent", None)
    rheology = getattr(compiled_workflow, "rheology", None)
    return {
        "geometry_class": getattr(intent, "geometry_class", None),
        "reproduction_target": getattr(intent, "reproduction_target", None),
        "dimensionless_groups": getattr(intent, "dimensionless_groups", {}) or {},
        "objectives": tuple(getattr(intent, "objectives", ()) or ()),
        "selected_model": getattr(rheology, "selected_model", None),
        "parameters": getattr(rheology, "parameters", {}) or {},
    }


def _cross_slot_match_from_structured(signature: dict[str, Any]) -> tuple[int, list[str], bool, str | None]:
    if not signature:
        return 0, [], False, None
    geometry = signature.get("geometry_class")
    model = signature.get("selected_model")
    groups = signature.get("dimensionless_groups") or {}
    target = signature.get("reproduction_target")
    objectives = set(signature.get("objectives") or ())
    if geometry and geometry != "cross_slot":
        return 0, [f"geometry_conflict={geometry}"], True, None
    if model and model != "Oldroyd-B":
        return 0, [f"model_conflict={model}"], True, None

    reasons: list[str] = []
    score = 0
    if geometry == "cross_slot":
        score += 30
        reasons.append("geometry=cross-slot")
    if model == "Oldroyd-B":
        score += 25
        reasons.append("model=Oldroyd-B/Oldroyd-BLog")
    if target == "rheotool_5_1_7_crossslot_oldroydb_log":
        score += 25
        reasons.append("reproduction_target=rheotool_5_1_7")
    dimensionless_match = (
        _near(groups.get("Re"), 0.0)
        and _near(groups.get("Wi"), 0.33)
        and _near(groups.get("beta"), 0.0)
    )
    if dimensionless_match:
        score += 20
        reasons.append("dimensionless=Re0-Wi0.33-beta0")
    if _near(groups.get("Pe"), 500.0):
        score += 5
        reasons.append("dimensionless=Pe500")
    if {"local_weissenberg", "passive_scalar", "streamlines"} & objectives:
        score += 5
        reasons.append("outputs=cross-slot-diagnostics")

    if target == "rheotool_5_1_7_crossslot_oldroydb_log" or (geometry == "cross_slot" and model == "Oldroyd-B" and dimensionless_match):
        tier = "A"
    elif geometry == "cross_slot" and model == "Oldroyd-B":
        tier = "B"
    else:
        tier = None
    return score, reasons, False, tier


def _cylinder_match_from_structured(signature: dict[str, Any]) -> tuple[int, list[str], bool, str | None]:
    if not signature:
        return 0, [], False, None
    geometry = signature.get("geometry_class")
    model = signature.get("selected_model")
    groups = signature.get("dimensionless_groups") or {}
    target = signature.get("reproduction_target")
    objectives = set(signature.get("objectives") or ())
    if geometry and geometry != "confined_cylinder":
        return 0, [f"geometry_conflict={geometry}"], True, None
    if model and model != "Oldroyd-B":
        return 0, [f"model_conflict={model}"], True, None

    reasons: list[str] = []
    score = 0
    if geometry == "confined_cylinder":
        score += 30
        reasons.append("geometry=confined-cylinder")
    if model == "Oldroyd-B":
        score += 25
        reasons.append("model=Oldroyd-B/Oldroyd-BLog")
    if target == "rheotool_5_1_6_cylinder_oldroydb_log":
        score += 25
        reasons.append("reproduction_target=rheotool_5_1_6")
    dimensionless_match = (
        _near(groups.get("Re"), 0.0)
        and _near(groups.get("Wi"), 0.7)
        and _near(groups.get("beta"), 0.59)
    )
    if dimensionless_match:
        score += 20
        reasons.append("dimensionless=Re0-Wi0.7-beta0.59")
    if {"drag_coefficient", "normal_stress", "streamlines"} & objectives:
        score += 5
        reasons.append("outputs=cylinder-drag-stress-streamlines")

    if target == "rheotool_5_1_6_cylinder_oldroydb_log" or (geometry == "confined_cylinder" and model == "Oldroyd-B" and dimensionless_match):
        tier = "A"
    elif geometry == "confined_cylinder" and model == "Oldroyd-B":
        tier = "B"
    else:
        tier = None
    return score, reasons, False, tier


def _contraction_match_from_structured(signature: dict[str, Any]) -> tuple[int, list[str], bool, str | None]:
    if not signature:
        return 0, [], False, None
    geometry = signature.get("geometry_class")
    model = signature.get("selected_model")
    groups = signature.get("dimensionless_groups") or {}
    target = signature.get("reproduction_target")
    objectives = set(signature.get("objectives") or ())
    if geometry and geometry != "contraction":
        return 0, [f"geometry_conflict={geometry}"], True, None
    if model and model != "Oldroyd-B":
        return 0, [f"model_conflict={model}"], True, None

    reasons: list[str] = []
    score = 0
    if geometry == "contraction":
        score += 30
        reasons.append("geometry=4:1-planar-contraction")
    if model == "Oldroyd-B":
        score += 25
        reasons.append("model=Oldroyd-B/Oldroyd-BLog")
    if target == "rheotool_5_1_5_contraction41_oldroydb_log":
        score += 25
        reasons.append("reproduction_target=rheotool_5_1_5")
    dimensionless_match = (
        _near(groups.get("Re"), 0.01)
        and _near(groups.get("De"), 1.0)
        and _near(groups.get("beta"), 0.5)
    )
    if dimensionless_match:
        score += 20
        reasons.append("dimensionless=Re0.01-De1-beta0.5")
    if {"velocity_profile", "theta_profile", "kinetic_energy"} & objectives:
        score += 5
        reasons.append("outputs=contraction-profiles")

    if target == "rheotool_5_1_5_contraction41_oldroydb_log" or (geometry == "contraction" and model == "Oldroyd-B" and dimensionless_match):
        tier = "A"
    elif geometry == "contraction" and model == "Oldroyd-B":
        tier = "B"
    else:
        tier = None
    return score, reasons, False, tier


def _cavity_match_from_structured(signature: dict[str, Any]) -> tuple[int, list[str], bool, str | None]:
    if not signature:
        return 0, [], False, None
    geometry = signature.get("geometry_class")
    model = signature.get("selected_model")
    groups = signature.get("dimensionless_groups") or {}
    target = signature.get("reproduction_target")
    objectives = set(signature.get("objectives") or ())
    if geometry and geometry != "lid_driven_cavity":
        return 0, [f"geometry_conflict={geometry}"], True, None
    if model and model != "Oldroyd-B":
        return 0, [f"model_conflict={model}"], True, None

    reasons: list[str] = []
    score = 0
    if geometry == "lid_driven_cavity":
        score += 30
        reasons.append("geometry=lid-driven-cavity")
    if model == "Oldroyd-B":
        score += 25
        reasons.append("model=Oldroyd-B/Oldroyd-BLog")
    if target == "rheotool_5_1_4_cavity_oldroydb_log":
        score += 25
        reasons.append("reproduction_target=rheotool_5_1_4")
    dimensionless_match = (
        _near(groups.get("Re"), 0.01)
        and _near(groups.get("De"), 1.0)
        and _near(groups.get("beta"), 0.5)
    )
    if dimensionless_match:
        score += 20
        reasons.append("dimensionless=Re0.01-De1-beta0.5")
    if {"velocity_profile", "theta_profile", "kinetic_energy"} & objectives:
        score += 5
        reasons.append("outputs=FK-cavity-profiles")

    if target == "rheotool_5_1_4_cavity_oldroydb_log" or (geometry == "lid_driven_cavity" and model == "Oldroyd-B" and dimensionless_match):
        tier = "A"
    elif geometry == "lid_driven_cavity" and model == "Oldroyd-B":
        tier = "B"
    else:
        tier = None
    return score, reasons, False, tier


def _channel_match_from_structured(signature: dict[str, Any]) -> tuple[int, list[str], bool, str | None]:
    if not signature:
        return 0, [], False, None
    geometry = signature.get("geometry_class")
    model = signature.get("selected_model")
    groups = signature.get("dimensionless_groups") or {}
    target = signature.get("reproduction_target")
    if geometry and geometry != "parallel_plate_channel":
        return 0, [f"geometry_conflict={geometry}"], True, None
    if model and model != "Oldroyd-B":
        return 0, [f"model_conflict={model}"], True, None

    reasons: list[str] = []
    score = 0
    if geometry == "parallel_plate_channel":
        score += 30
        reasons.append("geometry=parallel-plate-channel")
    if model == "Oldroyd-B":
        score += 25
        reasons.append("model=Oldroyd-B/Oldroyd-BLog")
    if target == "rheotool_5_1_3_channel_oldroydb_log":
        score += 25
        reasons.append("reproduction_target=rheotool_5_1_3")
    dimensionless_match = _near(groups.get("Wi"), 0.99) and _near(groups.get("beta"), 0.01)
    if dimensionless_match:
        score += 20
        reasons.append("dimensionless=Wi0.99-beta0.01")

    if target == "rheotool_5_1_3_channel_oldroydb_log" or (geometry == "parallel_plate_channel" and model == "Oldroyd-B" and dimensionless_match):
        tier = "A"
    elif geometry == "parallel_plate_channel" and model == "Oldroyd-B":
        tier = "B"
    else:
        tier = None
    return score, reasons, False, tier


def _score_cross_slot_oldroydb_signature(text: str) -> tuple[int, list[str], bool]:
    hard_conflict = _has_any(
        text,
        (
            "cavity", "lid-driven", "lid driven", "方腔", "空腔", "顶盖驱动", "盖驱动",
            "contraction41", "contraction", "4:1", "4：1", "4-to-1", "4 to 1", "收缩",
            "confined cylinder", "cylinder", "受限圆柱", "圆柱绕流", "圆柱",
            "parallel plate", "parallel-plate", "平行平板", "平板通道", "giesekus",
        ),
    )
    score = 0
    reasons: list[str] = []
    if _has_any(text, ("crossslot", "cross-slot", "cross slot", "十字槽", "十字流道")):
        score += 30
        reasons.append("geometry=cross-slot")
    if "oldroyd" in text:
        score += 25
        reasons.append("model=Oldroyd-B/Oldroyd-BLog")
    if _has_any(text, ("rheotool", "rheo tool", "教程", "user guide", "5.1.7")):
        score += 15
        reasons.append("source=RheoTool-5.1.7")
    if _has_any(text, ("wi=0.33", "wi = 0.33", "re=0", "re = 0", "β=0", "beta=0", "beta = 0", "pe=500", "pe = 500")):
        score += 10
        reasons.append("dimensionless-group-match")
    if _has_any(text, ("local weissenberg", "wi0", "passive scalar", "tracer", "被动标量", "示踪", "停滞点")):
        score += 10
        reasons.append("outputs=cross-slot-diagnostics")
    return score, reasons, hard_conflict


def _score_cylinder_oldroydb_signature(text: str) -> tuple[int, list[str], bool]:
    hard_conflict = _has_any(
        text,
        (
            "cavity", "lid-driven", "lid driven", "方腔", "空腔", "顶盖驱动", "盖驱动",
            "contraction41", "contraction", "4:1", "4：1", "4-to-1", "4 to 1", "收缩",
            "crossslot", "cross-slot", "cross slot", "十字槽", "十字流道",
            "parallel plate", "parallel-plate", "平行平板", "平板通道", "giesekus",
        ),
    )
    score = 0
    reasons: list[str] = []
    if _has_any(text, ("confined cylinder", "cylinder/oldroyd", "cylinder", "受限圆柱", "圆柱绕流", "圆柱")):
        score += 30
        reasons.append("geometry=confined-cylinder")
    if "oldroyd" in text:
        score += 25
        reasons.append("model=Oldroyd-B/Oldroyd-BLog")
    if _has_any(text, ("rheotool", "rheo tool", "教程", "user guide", "5.1.6")):
        score += 15
        reasons.append("source=RheoTool-5.1.6")
    if _has_any(text, ("wi=0.7", "wi = 0.7", "re=0", "re = 0", "β=0.59", "beta=0.59", "beta = 0.59")):
        score += 10
        reasons.append("dimensionless-group-match")
    if _has_any(text, ("drag", "cd", "阻力", "第一法向", "normal stress", "n1", "streamline", "流线")):
        score += 10
        reasons.append("outputs=cylinder-drag-stress-streamlines")
    return score, reasons, hard_conflict


def _score_contraction_oldroydb_signature(text: str) -> tuple[int, list[str], bool]:
    hard_conflict = _has_any(
        text,
        (
            "cavity", "lid-driven", "lid driven", "方腔", "空腔", "顶盖驱动", "盖驱动",
            "parallel plate", "parallel-plate", "平行平板", "平板通道",
            "confined cylinder", "cylinder", "受限圆柱", "圆柱绕流", "圆柱",
            "crossslot", "cross-slot", "cross slot", "十字槽", "十字流道", "giesekus",
        ),
    )
    score = 0
    reasons: list[str] = []
    if _has_any(text, ("contraction41", "contraction", "4:1", "4：1", "4-to-1", "4 to 1", "收缩")):
        score += 30
        reasons.append("geometry=4:1-planar-contraction")
    if "oldroyd" in text:
        score += 25
        reasons.append("model=Oldroyd-B/Oldroyd-BLog")
    if _has_any(text, ("rheotool", "rheo tool", "教程", "user guide", "5.1.5")):
        score += 15
        reasons.append("source=RheoTool-5.1.5")
    if _has_any(text, ("de=1", "de = 1", "re=0.01", "re = 0.01", "β=0.5", "beta=0.5", "beta = 0.5")):
        score += 10
        reasons.append("dimensionless-group-match")
    if _has_any(text, ("theta_xy", "θxy", "thetax y", "streamline", "流线", "动能", "ek(t)", "ek")):
        score += 10
        reasons.append("outputs=contraction-profiles")
    return score, reasons, hard_conflict


def _score_cavity_oldroydb_signature(text: str) -> tuple[int, list[str], bool]:
    hard_conflict = _has_any(
        text,
        (
            "giesekus", "4:1", "4：1", "contraction", "收缩", "cylinder", "圆柱",
            "crossslot", "cross-slot", "cross slot", "十字", "十字槽", "aneurysm", "动脉瘤",
        ),
    )
    score = 0
    reasons: list[str] = []
    if _has_any(text, ("cavity", "lid-driven", "lid driven", "方腔", "空腔", "顶盖驱动", "盖驱动")):
        score += 30
        reasons.append("geometry=lid-driven-cavity")
    if "oldroyd" in text:
        score += 25
        reasons.append("model=Oldroyd-B/Oldroyd-BLog")
    if _has_any(text, ("fattal", "kupferman")):
        score += 20
        reasons.append("reference=Fattal-Kupferman-2005")
    if _has_any(text, ("rheotool", "rheo tool", "教程", "user guide", "5.1.4")):
        score += 15
        reasons.append("source=RheoTool-5.1.4")
    if _has_any(text, ("de=1", "de = 1", "re=0.01", "re = 0.01", "β=0.5", "beta=0.5", "beta = 0.5")):
        score += 10
        reasons.append("dimensionless-group-match")
    if _has_any(text, ("127×127", "127 x 127", "127x127")):
        score += 10
        reasons.append("mesh=127x127")
    if _has_any(text, ("theta_xy", "θxy", "thetax y", "kinetic energy", "动能", "ek(t)", "ek")):
        score += 10
        reasons.append("outputs=FK-cavity-profiles")
    return score, reasons, hard_conflict


def _score_channel_oldroydb_signature(text: str) -> tuple[int, list[str], bool]:
    hard_conflict = _has_any(
        text,
        (
            "cavity", "lid-driven", "lid driven", "方腔", "空腔", "顶盖驱动", "盖驱动",
            "giesekus", "contraction41", "contraction", "4:1", "4：1", "4-to-1",
            "4 to 1", "收缩", "re-entrant", "lip vortex", "corner vortex", "5.1.5",
            "confined cylinder", "cylinder", "受限圆柱", "圆柱绕流", "圆柱", "5.1.6",
            "crossslot", "cross-slot", "cross slot", "十字槽", "十字流道", "5.1.7",
        ),
    )
    score = 0
    reasons: list[str] = []
    if _has_any(text, ("channel", "parallel plate", "parallel-plate", "平行", "平板", "通道")):
        score += 30
        reasons.append("geometry=parallel-plate-channel")
    if "oldroyd" in text:
        score += 25
        reasons.append("model=Oldroyd-B/Oldroyd-BLog")
    if _has_any(text, ("rheotool", "rheo tool", "教程", "user guide", "5.1.3")):
        score += 15
        reasons.append("source=RheoTool-5.1.3")
    if _has_any(text, ("benchmark", "wi=0.99", "wi = 0.99", "β=0.01", "beta=0.01", "beta = 0.01")):
        score += 15
        reasons.append("dimensionless-group-match")
    if _has_any(text, ("50x60", "50 x 60", "x=35", "linex35")):
        score += 10
        reasons.append("mesh-or-sample-line-match")
    return score, reasons, hard_conflict


def find_rheotool_tutorial_template(
    user_requirement: str,
    target: CaseTarget,
    *,
    root: Path | None = None,
    compiled_workflow: Any = None,
    minimum_tier: str = "A",
) -> dict[str, Any] | None:
    """Return a deterministic rheoTool tutorial template match.

    This matcher is used for execution decisions, not merely RAG context. It
    therefore combines semantic/physics-signature scoring with hard-conflict
    filters, and refuses to silently fall back to LLM dictionary generation
    when a high-confidence template signature is found but the local source tree
    is missing.
    """
    if target.channel != "v9-rheotool" or target.solver not in {"rheoFoam", "rheoTestFoam", "rheoInterFoam"}:
        return None

    text = _normalize(user_requirement)
    template_root = root or _tutorial_root()
    min_rank = {"A": 3, "B": 2, "C": 1}.get(minimum_tier, 3)

    signature = _structured_signature(compiled_workflow)
    explicit_target = signature.get("reproduction_target") if signature else None
    explicit_only_targets = {
        "rheotool_5_1_8_aneurysm_herschelbulkley",
        "rheotool_5_1_9_fluiddamper_carreauyasuda",
        "rheotool_5_2_2_rheotest_herschelbulkley",
        "rheotool_5_2_3_rheotest_fenecr",
        "rheotool_5_3_2_impactingdrop_oldroydb_log",
        "rheotool_5_3_3_dieswell_carreauyasuda",
        "rheotool_5_3_3_dieswell_giesekuslog",
        "rheotool_5_3_3_dieswell_oldroydb_log",
    }
    if explicit_target in explicit_only_targets:
        definition = RHEOTOOL_TEMPLATE_DEFINITIONS[explicit_target]
        if definition.get("solver") == target.solver and min_rank <= 3:
            return _template_payload_from_id(
                explicit_target,
                template_root=template_root,
                score=100,
                score_reasons=[f"reproduction_target={explicit_target}"],
                tier="A",
            )
    cross_slot_score, cross_slot_reasons, cross_slot_conflict, cross_slot_tier = _cross_slot_match_from_structured(signature)
    cylinder_score, cylinder_reasons, cylinder_conflict, cylinder_tier = _cylinder_match_from_structured(signature)
    contraction_score, contraction_reasons, contraction_conflict, contraction_tier = _contraction_match_from_structured(signature)
    cavity_score, cavity_reasons, cavity_conflict, cavity_tier = _cavity_match_from_structured(signature)
    channel_score, channel_reasons, channel_conflict, channel_tier = _channel_match_from_structured(signature)

    # Compatibility fallback for direct unit tests or legacy callers that have
    # not supplied compiled_workflow yet. This path is secondary; plan.py passes
    # structured intake/compiler output.
    if not signature:
        raw_cross_slot_score, raw_cross_slot_reasons, cross_slot_conflict = _score_cross_slot_oldroydb_signature(text)
        raw_cylinder_score, raw_cylinder_reasons, cylinder_conflict = _score_cylinder_oldroydb_signature(text)
        raw_contraction_score, raw_contraction_reasons, contraction_conflict = _score_contraction_oldroydb_signature(text)
        raw_cavity_score, raw_cavity_reasons, cavity_conflict = _score_cavity_oldroydb_signature(text)
        raw_channel_score, raw_channel_reasons, channel_conflict = _score_channel_oldroydb_signature(text)
        cross_slot_score, cross_slot_reasons = raw_cross_slot_score, raw_cross_slot_reasons
        cylinder_score, cylinder_reasons = raw_cylinder_score, raw_cylinder_reasons
        contraction_score, contraction_reasons = raw_contraction_score, raw_contraction_reasons
        cavity_score, cavity_reasons = raw_cavity_score, raw_cavity_reasons
        channel_score, channel_reasons = raw_channel_score, raw_channel_reasons
        cross_slot_tier = "A" if cross_slot_score >= 70 and not cross_slot_conflict else None
        cylinder_tier = "A" if cylinder_score >= 70 and not cylinder_conflict else None
        contraction_tier = "A" if contraction_score >= 70 and not contraction_conflict else None
        cavity_tier = "A" if cavity_score >= 70 and not cavity_conflict else None
        channel_tier = "A" if channel_score >= 70 and not channel_conflict else None

    def tier_allowed(tier: str | None) -> bool:
        return tier is not None and {"A": 3, "B": 2, "C": 1}.get(tier, 0) >= min_rank

    if (
        not cross_slot_conflict
        and tier_allowed(cross_slot_tier)
        and cross_slot_score >= cylinder_score
        and cross_slot_score >= contraction_score
        and cross_slot_score >= cavity_score
        and cross_slot_score >= channel_score
    ):
        return _template_match_payload(
            template_root=template_root,
            relative_source="rheoFoam/CrossSlot/Oldroyd-BLog",
            template_id="rheotool_5_1_7_crossslot_oldroydb_log",
            case_name="rheotool-crossslot-oldroydb-log",
            case_category="rheotool_tutorial_crossslot_oldroydb_log",
            matched_alias="RheoTool user guide 6.0 section 5.1.7 CrossSlot/Oldroyd-BLog",
            score=cross_slot_score,
            score_reasons=cross_slot_reasons,
            tier=cross_slot_tier or "C",
        )

    if (
        not cylinder_conflict
        and tier_allowed(cylinder_tier)
        and cylinder_score >= contraction_score
        and cylinder_score >= cavity_score
        and cylinder_score >= channel_score
        and cylinder_score >= cross_slot_score
    ):
        return _template_match_payload(
            template_root=template_root,
            relative_source="rheoFoam/Cylinder/Oldroyd-BLog",
            template_id="rheotool_5_1_6_cylinder_oldroydb_log",
            case_name="rheotool-cylinder-oldroydb-log",
            case_category="rheotool_tutorial_cylinder_oldroydb_log",
            matched_alias="RheoTool user guide 6.0 section 5.1.6 Cylinder/Oldroyd-BLog",
            score=cylinder_score,
            score_reasons=cylinder_reasons,
            tier=cylinder_tier or "C",
        )

    if (
        not contraction_conflict
        and tier_allowed(contraction_tier)
        and contraction_score >= cavity_score
        and contraction_score >= channel_score
        and contraction_score >= cylinder_score
        and contraction_score >= cross_slot_score
    ):
        return _template_match_payload(
            template_root=template_root,
            relative_source="rheoFoam/Contraction41/Oldroyd-BLog",
            template_id="rheotool_5_1_5_contraction41_oldroydb_log",
            case_name="rheotool-contraction41-oldroydb-log",
            case_category="rheotool_tutorial_contraction41_oldroydb_log",
            matched_alias="RheoTool user guide 6.0 section 5.1.5 Contraction41/Oldroyd-BLog",
            score=contraction_score,
            score_reasons=contraction_reasons,
            tier=contraction_tier or "C",
        )

    if (
        not cavity_conflict
        and tier_allowed(cavity_tier)
        and cavity_score >= channel_score
        and cavity_score >= contraction_score
        and cavity_score >= cylinder_score
        and cavity_score >= cross_slot_score
    ):
        return _template_match_payload(
            template_root=template_root,
            relative_source="rheoFoam/Cavity/Oldroyd-BLog",
            template_id="rheotool_5_1_4_cavity_oldroydb_log",
            case_name="rheotool-cavity-oldroydb-fk2005",
            case_category="rheotool_tutorial_cavity_oldroydb_log",
            matched_alias="Fattal & Kupferman 2005 / RheoTool 5.1.4 Cavity/Oldroyd-BLog",
            score=cavity_score,
            score_reasons=cavity_reasons,
            tier=cavity_tier or "C",
        )

    if (
        not channel_conflict
        and tier_allowed(channel_tier)
        and channel_score > cavity_score
        and channel_score > contraction_score
        and channel_score > cylinder_score
        and channel_score > cross_slot_score
    ):
        return _template_match_payload(
            template_root=template_root,
            relative_source="rheoFoam/Channel/Oldroyd-BLog",
            template_id="rheotool_5_1_3_channel_oldroydb_log",
            case_name="rheotool-ob-plate-channel-wi099",
            case_category="rheotool_tutorial_channel_oldroydb_log",
            matched_alias="RheoTool user guide 6.0 section 5.1.3 Channel/Oldroyd-BLog",
            score=channel_score,
            score_reasons=channel_reasons,
            tier=channel_tier or "C",
        )

    return None


def tutorial_template_subtasks(template_match: dict[str, Any]) -> list[dict[str, str]]:
    source_dir = Path(template_match["source_dir"])
    subtasks: list[dict[str, str]] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_dir)
        if len(rel.parts) == 1:
            folder_name = ""
            file_name = rel.parts[0]
        else:
            folder_name = str(Path(*rel.parts[:-1]))
            file_name = rel.parts[-1]
        subtasks.append({"folder_name": folder_name, "file_name": file_name})
    return subtasks


def _copy_case_tree(source_dir: Path, destination_dir: Path) -> None:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"rheoTool tutorial template not found: {source_dir}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    for item in source_dir.iterdir():
        destination = destination_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def _detect_rheotool_custom_bc_libs(case_dir: Path) -> set[str]:
    libs: set[str] = set()
    for path in (case_dir / "0").glob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for bc_type, lib_name in RHEOTOOL_CUSTOM_BC_LIBS.items():
            if re.search(rf"\btype\s+{re.escape(bc_type)}\s*;", text):
                libs.add(lib_name)
    return libs


def _detect_rheotool_pputil_libs(case_dir: Path) -> set[str]:
    libs: set[str] = set()
    fv_solution = case_dir / "system" / "fvSolution"
    if not fv_solution.is_file():
        return libs
    text = fv_solution.read_text(encoding="utf-8", errors="ignore")
    for pputil_type, lib_names in RHEOTOOL_TUTORIAL_PPUTIL_LIBS.items():
        if re.search(rf"\bfuncType\s+{re.escape(pputil_type)}\s*;", text):
            libs.update(lib_names)
    return libs


def _ensure_control_dict_libs(case_dir: Path, required_libs: set[str]) -> None:
    if not required_libs:
        return
    control_dict = case_dir / "system" / "controlDict"
    if not control_dict.is_file():
        return

    text = control_dict.read_text(encoding="utf-8", errors="ignore")
    missing = sorted(lib for lib in required_libs if lib not in text)
    if not missing:
        return

    entries = "".join(f'    "{lib}"\n' for lib in missing)
    libs_block = re.search(r"(?s)\blibs\s*\(.*?\)\s*;", text)
    if libs_block:
        block = libs_block.group(0)
        updated = re.sub(r"\)\s*;\s*$", entries + ");", block, count=1)
        text = text[:libs_block.start()] + updated + text[libs_block.end():]
    else:
        block = "libs\n(\n" + entries + ");\n"
        text = re.sub(
            r"(?m)^(\s*application\s+[^;]+;\s*)$",
            r"\1\n" + block,
            text,
            count=1,
        )
        if any(lib not in text for lib in missing):
            text = block + "\n" + text

    control_dict.write_text(text, encoding="utf-8")


def _set_control_dict_application(case_dir: Path, application: str) -> None:
    control_dict = case_dir / "system" / "controlDict"
    if not control_dict.is_file():
        return
    text = control_dict.read_text(encoding="utf-8", errors="ignore")
    updated = re.sub(
        r"(?m)^(\s*application\s+)[^;]+;",
        rf"\g<1>{application};",
        text,
        count=1,
    )
    if updated == text:
        updated = re.sub(
            r"(?m)^(\s*FoamFile\s*\{)",
            f"application     {application};\n\n\\1",
            text,
            count=1,
        )
    control_dict.write_text(updated, encoding="utf-8")


def _sync_control_dict_managed_libs(case_dir: Path, required_libs: set[str], managed_libs: set[str]) -> None:
    control_dict = case_dir / "system" / "controlDict"
    if not control_dict.is_file():
        return

    text = control_dict.read_text(encoding="utf-8", errors="ignore")
    stale_libs = managed_libs - required_libs
    for lib in sorted(stale_libs):
        text = re.sub(rf'(?m)^\s*"{re.escape(lib)}"\s*;?\s*\n?', "", text)
        text = re.sub(rf"(?m)^\s*{re.escape(lib)}\s*;?\s*\n?", "", text)
    control_dict.write_text(text, encoding="utf-8")
    _ensure_control_dict_libs(case_dir, required_libs)


def _normalize_foundation_v9_layout(case_dir: Path, *, enable_parallel: bool = True) -> None:
    """Adapt shipped foam-extend-style rheoTool templates for Foundation v9."""
    system_dir = case_dir / "system"
    poly_mesh_dir = case_dir / "constant" / "polyMesh"
    legacy_block_mesh = poly_mesh_dir / "blockMeshDict"
    system_block_mesh = system_dir / "blockMeshDict"

    if legacy_block_mesh.is_file():
        system_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_block_mesh, system_block_mesh)
        shutil.rmtree(poly_mesh_dir, ignore_errors=True)

    sample_dict = system_dir / "sampleDict"
    if sample_dict.is_file():
        text = sample_dict.read_text(encoding="utf-8", errors="ignore")
        text = text.replace("type        face;", "type        lineFace;")
        if not re.search(r"(?m)^\s*type\s+sets\s*;", text):
            header = 'type            sets;\nlibs            ("libsampling.so");\n\n'
            if "setFormat raw;" in text:
                text = text.replace("setFormat raw;", header + "setFormat raw;", 1)
            else:
                text = header + text
        elif not re.search(r'(?m)^\s*libs\s+\("libsampling\.so"\)\s*;', text):
            text = re.sub(r"(?m)^(\s*type\s+sets\s*;\s*)$", '\\1\nlibs            ("libsampling.so");', text, count=1)
        sample_dict.write_text(text, encoding="utf-8")

    allrun = case_dir / "Allrun"
    if allrun.is_file():
        text = allrun.read_text(encoding="utf-8", errors="ignore")
        text = re.sub(
            r"(?m)^\s*runApplication\s+sample\s*$",
            "if command -v sample >/dev/null 2>&1; then\n"
            "    runApplication sample\n"
            "else\n"
            "    runApplication postProcess -func sampleDict -latestTime\n"
            "fi",
            text,
        )
        if enable_parallel:
            text = enable_rheofoam_parallel_if_large(case_dir, CaseTarget.for_solver("rheoFoam"), text)
        allrun.write_text(text, encoding="utf-8")

    _sync_control_dict_managed_libs(
        case_dir,
        _detect_rheotool_custom_bc_libs(case_dir) | _detect_rheotool_pputil_libs(case_dir),
        set(RHEOTOOL_CUSTOM_BC_LIBS.values()) | {lib for libs in RHEOTOOL_TUTORIAL_PPUTIL_LIBS.values() for lib in libs},
    )


def _remove_top_level_named_blocks(text: str, name: str) -> str:
    """Remove Foam dictionary blocks named ``name`` using brace balancing."""
    pattern = re.compile(rf"(?m)^\s*{re.escape(name)}\s*\{{")
    out: list[str] = []
    pos = 0
    for match in pattern.finditer(text):
        out.append(text[pos:match.start()])
        depth = 0
        end = match.end()
        for idx in range(match.end() - 1, len(text)):
            char = text[idx]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = idx + 1
                    while end < len(text) and text[end] in " \t\r\n":
                        end += 1
                    break
        pos = end
    out.append(text[pos:])
    return "".join(out)


def _disable_rheofoam_parallel_for_serial_pputil(case_dir: Path) -> None:
    allrun = case_dir / "Allrun"
    if not allrun.is_file():
        return
    text = allrun.read_text(encoding="utf-8", errors="ignore")
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if (
            stripped == "rm -rf processor*"
            or stripped.startswith("runApplication decomposePar")
            or stripped.startswith("export OMPI_ALLOW_RUN_AS_ROOT=")
            or stripped.startswith("export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=")
            or stripped.startswith("runApplication reconstructPar")
        ):
            continue
        parallel_match = re.match(r"runParallel\s+-np\s+\d+\s+(\S+)", stripped)
        if parallel_match:
            indent = line[: len(line) - len(line.lstrip())]
            lines.append(f"{indent}runApplication {parallel_match.group(1)}")
            continue
        legacy_parallel = re.match(r"runParallel\s+(\S+)\s+\d+", stripped)
        if legacy_parallel:
            indent = line[: len(line) - len(line.lstrip())]
            lines.append(f"{indent}runApplication {legacy_parallel.group(1)}")
            continue
        lines.append(line)
    allrun.write_text("\n".join(lines) + "\n", encoding="utf-8")
    decompose = case_dir / "system" / "decomposeParDict"
    if decompose.is_file():
        decompose.unlink()


def _normalize_contraction41_template(case_dir: Path) -> None:
    _normalize_foundation_v9_layout(case_dir)

    sample_dict = case_dir / "system" / "sampleDict"
    if sample_dict.is_file():
        text = sample_dict.read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r"\btype\s+midPoint\s*;", "type        lineCell;", text)
        sample_dict.write_text(text, encoding="utf-8")

    fv_solution = case_dir / "system" / "fvSolution"
    if fv_solution.is_file():
        text = fv_solution.read_text(encoding="utf-8", errors="ignore")
        has_calc_vortex_l = "calcVortexL" in text
        text = re.sub(r"\bsolver\s+BiCGStab\s*;", "solver          PBiCGStab;", text)
        text = re.sub(
            r"preconditioner\s*\{\s*preconditioner\s+(?:ILU0|DILU)\s*;\s*\}",
            "preconditioner  DILU;",
            text,
            flags=re.DOTALL,
        )
        text = re.sub(r"\bpreconditioner\s+ILU0\s*;", "preconditioner  DILU;", text)
        fv_solution.write_text(text, encoding="utf-8")
        if has_calc_vortex_l:
            _ensure_control_dict_libs(
                case_dir,
                {"libpostProcessingRheoTool.so", "libRheoToolTutorialPPUtils.so"},
            )
            _disable_rheofoam_parallel_for_serial_pputil(case_dir)


def _normalize_channel_template(case_dir: Path) -> None:
    _normalize_foundation_v9_layout(case_dir)
    sample_dict = case_dir / "system" / "sampleDict"
    if not sample_dict.is_file():
        return
    text = sample_dict.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"start\s+\(\s*30\s+-?1(?:\.2)?\s+0\s*\)\s*;", "start       ( 35 -1.2 0 );", text)
    text = re.sub(r"end\s+\(\s*30\s+-?1(?:\.2)?\s+0\s*\)\s*;", "end         ( 35 1.2 0 );", text)
    text = text.replace("lineVert", "lineX35")
    sample_dict.write_text(text, encoding="utf-8")


def _normalize_cavity_template(case_dir: Path) -> None:
    _normalize_foundation_v9_layout(case_dir)
    fv_solution = case_dir / "system" / "fvSolution"
    if fv_solution.is_file():
        text = fv_solution.read_text(encoding="utf-8", errors="ignore")
        text = re.sub(
            r"preconditioner\s*\{\s*preconditioner\s+DILU\s*;\s*\}",
            "preconditioner   DILU;",
            text,
            flags=re.DOTALL,
        )
        fv_solution.write_text(text, encoding="utf-8")


def _make_cylinder_mirror_mesh_idempotent(case_dir: Path) -> None:
    allrun = case_dir / "Allrun"
    if not allrun.is_file():
        return
    text = allrun.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(
        r"(?m)^(\s*runApplication\s+mirrorMesh[^\n]*\n)\s*cp\s+-fr\s+0/polyMesh/\s+constant/\s*\n\s*rm\s+-rf\s+0/polyMesh/\s*$",
        r"\1if [ -d 0/polyMesh ]; then\n"
        r"    cp -fr 0/polyMesh/ constant/\n"
        r"    rm -rf 0/polyMesh/\n"
        r"fi",
        text,
        count=1,
    )
    allrun.write_text(text, encoding="utf-8")


def _normalize_cylinder_template(case_dir: Path) -> None:
    _normalize_foundation_v9_layout(case_dir, enable_parallel=False)
    _make_cylinder_mirror_mesh_idempotent(case_dir)
    _disable_rheofoam_parallel_for_serial_pputil(case_dir)


def _copy_zero_org_field(case_dir: Path, source_name: str, destination_name: str, object_name: str | None = None) -> None:
    source = case_dir / "0" / source_name
    destination = case_dir / "0" / destination_name
    if not source.is_file() or destination.exists():
        return
    text = source.read_text(encoding="utf-8", errors="ignore")
    if object_name:
        text = re.sub(r"(?m)^(\s*object\s+)[^;]+;", rf"\g<1>{object_name};", text, count=1)
    destination.write_text(text, encoding="utf-8")


def _normalize_crossslot_template(case_dir: Path) -> None:
    _normalize_foundation_v9_layout(case_dir)
    _copy_zero_org_field(case_dir, "C.org", "C", "C")


def _normalize_fluiddamper_template(case_dir: Path) -> None:
    # The of90 tutorial's controlDict still says rheoInterFoam, while Allrun
    # executes rheoFoam.  Keep the tutorial dictionaries, but make the
    # preflight-visible application match the certified execution target.
    _normalize_foundation_v9_layout(case_dir, enable_parallel=False)
    _set_control_dict_application(case_dir, "rheoFoam")


def _normalize_rheointer_template(case_dir: Path) -> None:
    _normalize_foundation_v9_layout(case_dir)
    _copy_zero_org_field(case_dir, "U.org", "U", "U")
    _copy_zero_org_field(case_dir, "pd", "p_rgh", "p_rgh")
    _copy_zero_org_field(case_dir, "alpha1.org", "alpha", "alpha")
    _copy_zero_org_field(case_dir, "alpha1.org", "alpha1", "alpha1")


def _format_foam_scalar(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _extract_requested_end_time(user_requirement: str) -> float | None:
    """Extract an explicitly requested simulation end time without parsing formula internals."""
    text = str(user_requirement or "")
    number = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
    patterns = (
        rf"\bend[_\s-]*time\b\s*(?:=|:|为|到|至)?\s*{number}",
        rf"\bendTime\b\s*(?:=|:|为|到|至)?\s*{number}",
        rf"(?:计算|算|运行|跑|求解|积分)\s*(?:到|至)\s*t\s*=\s*{number}",
        rf"(?:计算|算|运行|跑|求解|积分)\s*(?:到|至)\s*(?:time|时间)\s*(?:=|为|:)?\s*{number}",
        rf"\b(?:run|compute|solve|simulate|integrate)\s+(?:to|until)\s+t\s*=\s*{number}",
        rf"\b(?:run|compute|solve|simulate|integrate)\s+(?:to|until)\s+(?:time\s*)?{number}",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if value > 0:
            return value
    return None


def _override_control_dict_end_time(case_dir: Path, end_time: float | None) -> dict[str, Any] | None:
    if end_time is None:
        return None
    control_dict = case_dir / "system" / "controlDict"
    if not control_dict.is_file():
        return None

    text = control_dict.read_text(encoding="utf-8", errors="ignore")
    value = _format_foam_scalar(end_time)
    replacement = f"endTime         {value};"
    if re.search(r"(?m)^\s*endTime\s+[^;]+;", text):
        updated = re.sub(r"(?m)^\s*endTime\s+[^;]+;", replacement, text, count=1)
    elif re.search(r"(?m)^\s*startTime\s+[^;]+;", text):
        updated = re.sub(r"(?m)^(\s*startTime\s+[^;]+;)", r"\1\n" + replacement, text, count=1)
    elif re.search(r"(?m)^\s*application\s+[^;]+;", text):
        updated = re.sub(r"(?m)^(\s*application\s+[^;]+;)", r"\1\n" + replacement, text, count=1)
    else:
        updated = replacement + "\n" + text
    control_dict.write_text(updated, encoding="utf-8")
    return {"field": "endTime", "value": end_time, "source": "user_requirement"}


def _explicit_template_targets_from_text(text: str) -> set[str]:
    targets: set[str] = set()
    if _has_any(text, ("5.1.3", "channel/oldroyd-blog", "channel/oldroydb-log", "平行平板通道")):
        targets.add("rheotool_5_1_3_channel_oldroydb_log")
    if _has_any(text, ("5.1.4", "cavity/oldroyd-blog", "cavity/oldroydb-log", "fattal", "kupferman", "顶盖驱动", "盖驱动方腔")):
        targets.add("rheotool_5_1_4_cavity_oldroydb_log")
    if _has_any(text, ("5.1.5", "contraction41", "contraction41/oldroyd-blog", "contraction41/oldroydb-log", "4:1", "4：1", "收缩")):
        targets.add("rheotool_5_1_5_contraction41_oldroydb_log")
    if _has_any(text, ("5.1.6", "cylinder/oldroyd-blog", "cylinder/oldroydb-log", "confined cylinder", "cylinder", "受限圆柱", "圆柱绕流", "圆柱")):
        targets.add("rheotool_5_1_6_cylinder_oldroydb_log")
    if _has_any(text, ("5.1.7", "crossslot", "cross-slot", "cross slot", "crossslot/oldroyd-blog", "crossslot/oldroydb-log", "十字槽", "十字流道")):
        targets.add("rheotool_5_1_7_crossslot_oldroydb_log")
    if _has_any(text, ("5.1.8", "aneurysm/herschel", "aneurysm", "动脉瘤")):
        targets.add("rheotool_5_1_8_aneurysm_herschelbulkley")
    if _has_any(text, ("5.1.9", "fluiddamper", "fluid damper", "damper", "阻尼器")):
        targets.add("rheotool_5_1_9_fluiddamper_carreauyasuda")
    if _has_any(text, ("5.2.2", "rheotestfoam/herschel", "herschelbulkley/")):
        targets.add("rheotool_5_2_2_rheotest_herschelbulkley")
    if _has_any(text, ("5.2.3", "rheotestfoam/fene", "fene-cr/")):
        targets.add("rheotool_5_2_3_rheotest_fenecr")
    if _has_any(text, ("5.3.2", "impactingdrop", "impacting drop", "impactingdrop/oldroyd")):
        targets.add("rheotool_5_3_2_impactingdrop_oldroydb_log")
    if _has_any(text, ("5.3.3", "dieswell", "die swell", "die-swell", "挤出胀大", "模口胀大")):
        targets.update(_explicit_dieswell_variant_targets(text))
        if not targets.intersection({
            "rheotool_5_3_3_dieswell_carreauyasuda",
            "rheotool_5_3_3_dieswell_giesekuslog",
            "rheotool_5_3_3_dieswell_oldroydb_log",
        }):
            targets.add("rheotool_5_3_3_dieswell_family")
    return targets


def _explicit_dieswell_variant_targets(text: str) -> set[str]:
    variants = (
        (
            "rheotool_5_3_3_dieswell_oldroydb_log",
            ("oldroyd-blog", "oldroydb-log", "oldroyd-b log", "oldroyd blog", "oldroyd"),
        ),
        (
            "rheotool_5_3_3_dieswell_giesekuslog",
            ("giesekuslog", "giesekus-log", "giesekus log", "giesekus"),
        ),
        (
            "rheotool_5_3_3_dieswell_carreauyasuda",
            ("carreauyasuda", "carreau-yasuda", "carreau yasuda", "carreau"),
        ),
    )

    positive: set[str] = set()
    fallback: set[str] = set()
    for target_id, terms in variants:
        for term in terms:
            for match in re.finditer(re.escape(term), text):
                before = text[max(0, match.start() - 80):match.start()]
                after = text[match.end():match.end() + 80]
                context = before + term + after
                local_context = before[-30:] + term + after[:30]
                if re.search(r"\b(no|not|without|instead of)\b|不使用|不是|无需|另有|可选|other|其它|其他", local_context):
                    continue
                fallback.add(target_id)
                if (
                    re.search(r"dieswell\s*/\s*$", before)
                    or re.search(r"die\s+swell\s*/\s*$", before)
                    or _has_any(
                        context,
                        (
                            "source_tutorial",
                            "source_template_path",
                            "constitutive_model",
                            "constitutive_variant",
                            "material_model",
                            "using the",
                            "using",
                            "采用",
                            "使用",
                        ),
                    )
                ):
                    positive.add(target_id)

    if positive:
        return positive
    if len(fallback) == 1:
        return fallback
    return set()


def _explicit_geometry_from_text(text: str) -> str | None:
    if _has_any(text, ("aneurysm", "aneurysm/herschel", "动脉瘤")):
        return "aneurysm"
    if _has_any(text, ("fluiddamper", "fluid damper", "viscous fluid damper", "damper", "阻尼器")):
        return "fluid_damper"
    if _has_any(text, ("impactingdrop", "impacting drop", "impactingdrop/oldroyd", "drop impact", "液滴撞击", "撞击液滴")):
        return "impacting_drop"
    if _has_any(text, ("dieswell", "die swell", "die-swell", "挤出胀大", "模口胀大")):
        return "die_swell"
    if _has_any(text, ("rheotestfoam/herschel", "rheotestfoam/fene", "rheotestfoam", "virtual rheometer", "材料函数")):
        return "rheotest_material_function"
    if _has_any(text, ("crossslot", "cross-slot", "cross slot", "十字槽", "十字流道")):
        return "cross_slot"
    if _has_any(text, ("confined cylinder", "cylinder/oldroyd", "cylinder", "受限圆柱", "圆柱绕流", "圆柱")):
        return "confined_cylinder"
    if _has_any(text, ("contraction41", "contraction", "4:1", "4：1", "4-to-1", "4 to 1", "收缩")):
        return "contraction"
    if _has_any(text, ("cavity", "lid-driven", "lid driven", "方腔", "空腔", "顶盖驱动", "盖驱动")):
        return "lid_driven_cavity"
    if _has_any(text, ("channel", "parallel plate", "parallel-plate", "平行", "平板", "通道")):
        return "parallel_plate_channel"
    return None


def _explicit_model_from_text(text: str) -> str | None:
    if "herschel" in text:
        return "HerschelBulkley"
    if "carreau" in text:
        return "CarreauYasuda"
    if "fene-cr" in text or "fene cr" in text:
        return "FENE-CR"
    if "oldroyd" in text:
        return "Oldroyd-B"
    if "giesekus" in text:
        return "Giesekus"
    return None


def validate_tutorial_template_import_consistency(user_requirement: str, template_match: dict[str, Any]) -> None:
    """Block deterministic template imports that contradict explicit user intent.

    RAG/manual snippets can describe many cases, but importing a tutorial case is
    an executable decision.  This guard is intentionally generic for all
    registered rheoTool tutorial templates so a wrong match cannot proceed to
    OpenFOAM simply because the case is syntactically valid.
    """
    text = _normalize(user_requirement)
    if not text:
        return
    selected_id = str(template_match.get("id") or template_match.get("template_id") or "")
    expected = RHEOTOOL_TEMPLATE_EXPECTATIONS.get(selected_id)
    if not expected:
        return

    explicit_targets = _explicit_template_targets_from_text(text)
    if explicit_targets and selected_id not in explicit_targets:
        raise ValueError(
            "TEMPLATE_IMPORT_CONFLICT: explicit RheoTool tutorial target does not match selected template; "
            f"expected_one_of={sorted(explicit_targets)} actual={selected_id}"
        )

    explicit_geometry = _explicit_geometry_from_text(text)
    expected_geometry = expected.get("geometry_class")
    if explicit_geometry and expected_geometry and explicit_geometry != expected_geometry:
        raise ValueError(
            "TEMPLATE_IMPORT_CONFLICT: explicit geometry does not match selected template; "
            f"expected_geometry={explicit_geometry} actual_template_geometry={expected_geometry} actual={selected_id}"
        )

    if selected_id.startswith("rheotool_5_3_3_dieswell_"):
        return

    explicit_model = _explicit_model_from_text(text)
    expected_model = expected.get("model")
    if explicit_model and expected_model and explicit_model != expected_model:
        raise ValueError(
            "TEMPLATE_IMPORT_CONFLICT: explicit constitutive model does not match selected template; "
            f"expected_model={explicit_model} actual_template_model={expected_model} actual={selected_id}"
        )



def normalize_imported_rheotool_tutorial_case(case_dir: str | Path, template_id: str) -> None:
    """Apply deterministic Foundation-v9 compatibility normalization to an existing imported tutorial case."""
    destination_dir = Path(case_dir)
    if template_id == "rheotool_5_1_3_channel_oldroydb_log":
        _normalize_channel_template(destination_dir)
    elif template_id == "rheotool_5_1_4_cavity_oldroydb_log":
        _normalize_cavity_template(destination_dir)
    elif template_id == "rheotool_5_1_5_contraction41_oldroydb_log":
        _normalize_contraction41_template(destination_dir)
    elif template_id == "rheotool_5_1_6_cylinder_oldroydb_log":
        _normalize_cylinder_template(destination_dir)
    elif template_id == "rheotool_5_1_7_crossslot_oldroydb_log":
        _normalize_crossslot_template(destination_dir)
    elif template_id == "rheotool_5_1_9_fluiddamper_carreauyasuda":
        _normalize_fluiddamper_template(destination_dir)
    elif template_id in {
        "rheotool_5_3_2_impactingdrop_oldroydb_log",
        "rheotool_5_3_3_dieswell_carreauyasuda",
        "rheotool_5_3_3_dieswell_giesekuslog",
        "rheotool_5_3_3_dieswell_oldroydb_log",
    }:
        _normalize_rheointer_template(destination_dir)
    else:
        _normalize_foundation_v9_layout(destination_dir)

def import_rheotool_tutorial_template(
    case_dir: str,
    template_match: dict[str, Any],
    user_requirement: str = "",
) -> dict[str, Any]:
    validate_tutorial_template_import_consistency(user_requirement, template_match)

    source_dir = Path(template_match["source_dir"])
    destination_dir = Path(case_dir)
    if not _is_executable_openfoam_case(source_dir):
        raise ValueError(
            "TUTORIAL_TEMPLATE_NOT_EXECUTABLE: "
            f"{template_match.get('id')} source directory is a tutorial family or incomplete case, not a runnable OpenFOAM case: {source_dir}"
        )

    _copy_case_tree(source_dir, destination_dir)
    if template_match.get("id") == "rheotool_5_1_3_channel_oldroydb_log":
        _normalize_channel_template(destination_dir)
    elif template_match.get("id") == "rheotool_5_1_4_cavity_oldroydb_log":
        _normalize_cavity_template(destination_dir)
    elif template_match.get("id") == "rheotool_5_1_5_contraction41_oldroydb_log":
        _normalize_contraction41_template(destination_dir)
    elif template_match.get("id") == "rheotool_5_1_6_cylinder_oldroydb_log":
        _normalize_cylinder_template(destination_dir)
    elif template_match.get("id") == "rheotool_5_1_7_crossslot_oldroydb_log":
        _normalize_crossslot_template(destination_dir)
    elif template_match.get("id") == "rheotool_5_1_9_fluiddamper_carreauyasuda":
        _normalize_fluiddamper_template(destination_dir)
    elif template_match.get("id") in {
        "rheotool_5_1_8_aneurysm_herschelbulkley",
        "rheotool_5_2_2_rheotest_herschelbulkley",
        "rheotool_5_2_3_rheotest_fenecr",
    }:
        _normalize_foundation_v9_layout(destination_dir)
    elif template_match.get("id") in {
        "rheotool_5_3_2_impactingdrop_oldroydb_log",
        "rheotool_5_3_3_dieswell_carreauyasuda",
        "rheotool_5_3_3_dieswell_giesekuslog",
        "rheotool_5_3_3_dieswell_oldroydb_log",
    }:
        _normalize_rheointer_template(destination_dir)

    end_time_override = _override_control_dict_end_time(
        destination_dir,
        _extract_requested_end_time(user_requirement),
    )
    note = {
        "template_id": template_match["id"],
        "template_name": template_match.get("template_name"),
        "solver": template_match.get("solver"),
        "source_directory": str(source_dir),
        "matched_alias": template_match.get("matched_alias"),
        "import_policy": template_match.get("import_policy"),
        "tier": template_match.get("tier"),
        "rag_confidence": template_match.get("rag_confidence"),
        "match_score": template_match.get("match_score"),
        "match_reasons": template_match.get("match_reasons"),
    }
    if template_match.get("certification"):
        note["certification"] = template_match.get("certification")
        certification = template_match["certification"]
        for key in ("parallel_policy", "start_policy", "run_user_policy"):
            if certification.get(key):
                note[key] = certification[key]
    if end_time_override:
        note["overrides"] = [end_time_override]
    (destination_dir / "TUTORIAL_TEMPLATE_IMPORT.json").write_text(
        json.dumps(note, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    dir_structure = scan_case_directory(str(destination_dir))
    foamfiles = read_case_foamfiles(str(destination_dir), dir_structure)
    return {
        "dir_structure": dir_structure,
        "foamfiles": foamfiles,
        "tutorial_template_import": note,
    }
