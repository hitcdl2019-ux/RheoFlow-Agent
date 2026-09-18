from __future__ import annotations

import os
import re
from dataclasses import dataclass

from models import CaseTarget, PhysicsSpec, ProblemIntent, RheologySpec, WorkflowPlan
from .template_families import TEMPLATE_FAMILIES, template_family_child_ids


MODEL_REQUIREMENTS = {
    "Oldroyd-B": ("etaS", "etaP", "lambda"),
    "FENE-CR": ("etaS", "etaP", "lambda", "L2"),
    "Giesekus": ("etaS", "etaP", "lambda", "alpha"),
    "PTT": ("etaS", "etaP", "lambda", "epsilon"),
    "CarreauYasuda": ("nu0", "nuInf", "k", "n", "a"),
    "HerschelBulkley": ("tau0", "k", "n"),
}

RHEOTOOL_TUTORIAL_TARGET_SOLVERS = {
    "rheotool_5_1_3_channel_oldroydb_log": "rheoFoam",
    "rheotool_5_1_4_cavity_oldroydb_log": "rheoFoam",
    "rheotool_5_1_5_contraction41_oldroydb_log": "rheoFoam",
    "rheotool_5_1_6_cylinder_oldroydb_log": "rheoFoam",
    "rheotool_5_1_7_crossslot_oldroydb_log": "rheoFoam",
    "rheotool_5_1_8_aneurysm_herschelbulkley": "rheoFoam",
    "rheotool_5_1_9_fluiddamper_carreauyasuda": "rheoFoam",
    "rheotool_5_2_2_rheotest_herschelbulkley": "rheoTestFoam",
    "rheotool_5_2_3_rheotest_fenecr": "rheoTestFoam",
    "rheotool_5_3_2_impactingdrop_oldroydb_log": "rheoInterFoam",
    "rheotool_5_3_3_dieswell_carreauyasuda": "rheoInterFoam",
    "rheotool_5_3_3_dieswell_giesekuslog": "rheoInterFoam",
    "rheotool_5_3_3_dieswell_oldroydb_log": "rheoInterFoam",
}
RHEOTOOL_TUTORIAL_FAMILIES = {
    family_id: {"children": template_family_child_ids(family_id)}
    for family_id in TEMPLATE_FAMILIES
    if family_id.startswith("rheotool_")
}
FOUNDATION_TUTORIAL_TARGET_SOLVERS = {
    "foundation_v10_icofoam_cavity": "icoFoam",
    "foundation_v10_icofoam_cavity_full_allrun": "icoFoam",
    "foundation_v10_simplefoam_pitzdaily": "simpleFoam",
    "foundation_v10_pimplefoam_ras_pitzdaily": "pimpleFoam",
    "foundation_v10_pisofoam_les_pitzdaily": "pisoFoam",
    "foundation_v10_potentialfoam_pitzdaily": "potentialFoam",
    "foundation_v10_scalartransport_pitzdaily": "scalarTransportFoam",
    "foundation_v10_potentialfoam_cylinder": "potentialFoam",
    "foundation_v10_pimplefoam_laminar_offsetcylinder": "pimpleFoam",
    "foundation_v10_interfoam_laminar_sloshingcylinder": "interFoam",
    "foundation_v10_rhocentralfoam_forwardstep": "rhoCentralFoam",
    "foundation_v10_rhopimplefoam_laminar_forwardstep": "rhoPimpleFoam",
    "foundation_v10_buoyantfoam_bernardcells": "buoyantFoam",
    "foundation_v10_pimplefoam_laminar_planarpoiseuille": "pimpleFoam",
    "foundation_v10_rhocentralfoam_obliqueshock": "rhoCentralFoam",
    "foundation_v10_rhocentralfoam_shocktube": "rhoCentralFoam",
    "foundation_v10_rhopimplefoam_laminar_shocktube": "rhoPimpleFoam",
    "foundation_v10_simplefoam_airfoil2d": "simpleFoam",
    "foundation_v10_interfoam_laminar_capillaryrise": "interFoam",
    "foundation_v10_interfoam_laminar_wave": "interFoam",
    "foundation_v10_interfoam_dambreak": "interFoam",
    "foundation_v10_interfoam_dambreak_laminar_full_allrun": "interFoam",
    "foundation_v10_interfoam_dambreak_with_obstacle": "interFoam",
    "foundation_v10_interfoam_ras_dambreak": "interFoam",
    "foundation_v10_interfoam_ras_dambreak_full_allrun": "interFoam",
    "foundation_v10_interfoam_ras_dambreak_porous_baffle": "interFoam",
}

MODEL_ALIASES = {
    "oldroyd": "Oldroyd-B",
    "fene-cr": "FENE-CR",
    "fene cr": "FENE-CR",
    "giesekus": "Giesekus",
    "ptt": "PTT",
    "carreau": "CarreauYasuda",
    "herschel": "HerschelBulkley",
}

PARAMETER_ALIASES = {
    "etaS": ("etaS", "etas", "eta_s", "eta-s", "ηs", "η_s", "ηₛ", "solvent viscosity"),
    "etaP": ("etaP", "etap", "eta_p", "eta-p", "ηp", "η_p", "ηₚ", "polymer viscosity"),
    "lambda": ("lambda", "relaxation_time", "relaxation time", "λ"),
    "L2": ("L2", "l_2", "l-2"),
    "alpha": ("alpha", "α"),
    "epsilon": ("epsilon", "eps", "ε"),
    "nu0": ("nu0", "nu_0", "eta0", "eta_0", "zero shear viscosity"),
    "nuInf": ("nuInf", "nu_inf", "etaInf", "eta_inf", "infinite shear viscosity"),
    "tau0": ("tau0", "tau_0", "τ0", "yield stress"),
    "k": ("k",),
    "n": ("n",),
    "a": ("a",),
}

RHEOLOGY_TERMS = (
    "viscoelastic", "shear thinning", "yield stress", "relaxation time",
    "rheology", "polymer", "粘弹", "黏弹", "剪切变稀", "屈服应力", "松弛时间", "流变",
    "聚合物", "非牛顿",
)
MATERIAL_TEST_TERMS = (
    "material function", "rheometer", "viscosity curve", "oscillatory shear",
    "材料函数", "流变仪", "黏度曲线", "粘度曲线", "振荡剪切",
)
TWO_PHASE_TERMS = (
    "two phase", "two-phase", "multiphase", "free surface", "surface tension",
    "vof", "两相", "多相", "自由液面", "界面张力", "液滴", "气泡",
)
UNSUPPORTED_TERMS = (
    "compressible", "combustion", "conjugate heat", "heat transfer",
    "可压缩", "燃烧", "传热", "热耦合",
)
NON_CERTIFIED_SOLVERS = (
    "rhoPimpleFoam", "rhoSimpleFoam", "reactingFoam", "buoyantSimpleFoam",
    "rhoCentralFoam", "chtMultiRegionFoam", "rheoHeatFoam", "rheoEFoam", "rheoFilmFoam",
)
ESI_RUNTIME_TERMS = (
    "automatic esi", "auto esi", "esi runtime", "esi-openfoam", "esi openfoam",
    "自动 esi", "自动esi", "esi运行", "esi 运行",
)


@dataclass(frozen=True)
class CompiledWorkflow:
    intent: ProblemIntent
    physics: PhysicsSpec
    rheology: RheologySpec
    plan: WorkflowPlan

    def as_dict(self) -> dict:
        from dataclasses import asdict

        return asdict(self)


def _hits(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(term for term in terms if term in text)


def _strip_negated_two_phase_terms(text: str) -> str:
    cleaned = text
    negative_values = r"(?:no|false|none|not applicable|n/a|unresolved|否|无|不适用|没有)"
    for field in (
        r"free[ _-]?surface",
        r"two[ _-]?phase",
        r"multi[ _-]?phase",
        r"surface[ _-]?tension",
        r"vof",
    ):
        cleaned = re.sub(rf"{field}\s*[:=]\s*{negative_values}", " ", cleaned)
    cleaned = re.sub(r"(?:不考虑|没有|无)(?:自由液面|两相|多相|界面张力|液滴|气泡)", " ", cleaned)
    cleaned = re.sub(
        r"(?:water-air|water and air|水和空气|水/空气)\s*(?:material card|材料卡)[^,，.;；]*(?:not applicable|不适用)",
        " ",
        cleaned,
    )
    return cleaned


def _two_phase_hits(text: str) -> tuple[str, ...]:
    return _hits(_strip_negated_two_phase_terms(text), TWO_PHASE_TERMS)


NUMBER_PATTERN = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?"
ASSIGNMENT_SEPARATORS = r"[:=：]"


def _parameter_name_pattern(name: str) -> str:
    return re.escape(name).replace(r"\ ", r"\s+")


def _extract_scalar_alias(text: str, aliases: tuple[str, ...]) -> float | None:
    for alias in aliases:
        pattern = _parameter_name_pattern(alias)
        direct = re.search(
            rf"(?<![A-Za-z0-9_]){pattern}\s*(?:{ASSIGNMENT_SEPARATORS}|\s)\s*({NUMBER_PATTERN})",
            text,
            re.IGNORECASE,
        )
        if direct:
            return float(direct.group(1))
        definition = re.search(
            rf"(?<![A-Za-z0-9_]){pattern}\s*{ASSIGNMENT_SEPARATORS}\s*[^,，;；\n]*?(?:=|:|：)\s*({NUMBER_PATTERN})",
            text,
            re.IGNORECASE,
        )
        if definition:
            return float(definition.group(1))
        parenthesized_definition = re.search(
            rf"(?<![A-Za-z0-9_]){pattern}\s*\([^)]*\)\s*{ASSIGNMENT_SEPARATORS}\s*({NUMBER_PATTERN})",
            text,
            re.IGNORECASE,
        )
        if parenthesized_definition:
            return float(parenthesized_definition.group(1))
    return None


def _infer_beta_from_viscosities(text: str) -> float | None:
    eta_s = _extract_scalar_alias(text, PARAMETER_ALIASES["etaS"])
    if eta_s is None:
        return None
    eta0 = _extract_scalar_alias(text, ("eta0", "eta_0", "eta-0", "η0", "η_0", "η₀"))
    if eta0 is not None and eta0 != 0:
        return eta_s / eta0
    eta_p = _extract_scalar_alias(text, PARAMETER_ALIASES["etaP"])
    if eta_p is not None and eta_s + eta_p != 0:
        return eta_s / (eta_s + eta_p)
    return None


def _extract_parameters(text: str) -> dict[str, float]:
    parameters: dict[str, float] = {}
    names = {name for required in MODEL_REQUIREMENTS.values() for name in required}
    for name in names:
        value = _extract_scalar_alias(text, PARAMETER_ALIASES.get(name, (name,)))
        if value is not None:
            parameters[name] = value
    return parameters


def _complete_oldroyd_parameters_from_beta(text: str, parameters: dict[str, float]) -> dict[str, float]:
    """Infer etaS/etaP from the common beta=etaS/eta0 definition.

    This only normalizes user-provided dimensionless data; it does not add
    typical or estimated material values.
    """
    completed = dict(parameters)
    eta0 = _extract_scalar_alias(text, ("eta0", "eta_0", "eta-0", "η0", "η_0", "η₀"))
    beta = _extract_scalar_alias(text, ("beta", "β"))
    if eta0 is not None and beta is not None:
        completed.setdefault("etaS", beta * eta0)
        completed.setdefault("etaP", (1.0 - beta) * eta0)
    elif eta0 is not None and "etaS" in completed and "etaP" not in completed:
        completed["etaP"] = eta0 - completed["etaS"]
    elif eta0 is not None and "etaP" in completed and "etaS" not in completed:
        completed["etaS"] = eta0 - completed["etaP"]
    return completed

def _strip_unconfirmed_model_options(text: str) -> str:
    """Remove model names that appear only as choices for an unknown field.

    CodeBuddy requirement drafts often include lines like
    ``tutorial_variant: unknown (Oldroyd-BLog, GiesekusLog, or CarreauYasuda)``.
    Those option labels are not user selections and must not drive template
    routing to the first alias (Oldroyd-B).
    """
    option_terms = r"oldroyd|giesekus|carreau|ptt|fene"
    cleaned = re.sub(
        rf"(?:unknown|未知|未确认|待确认)\s*\([^)]*(?:{option_terms})[^)]*\)",
        "unknown",
        text,
        flags=re.IGNORECASE,
    )
    return cleaned


def _selected_model(text: str) -> str | None:
    text = _strip_unconfirmed_model_options(text)
    for alias, model in MODEL_ALIASES.items():
        if alias in text:
            return model
    return None


def _unsupported_hits(text: str) -> tuple[str, ...]:
    hits = _hits(text, UNSUPPORTED_TERMS)
    if "incompressible" in text:
        hits = tuple(hit for hit in hits if hit != "compressible")
    if "不可压缩" in text:
        hits = tuple(hit for hit in hits if hit != "可压缩")

    lower_solver_names = {solver.lower(): solver for solver in NON_CERTIFIED_SOLVERS}
    unsupported_solvers = tuple(
        solver for lowered, solver in lower_solver_names.items() if lowered in text
    )
    esi_runtime = _hits(text, ESI_RUNTIME_TERMS)
    return hits + unsupported_solvers + esi_runtime



def _has_newtonian_evidence(text: str) -> bool:
    """Return True only for positive Newtonian evidence.

    Avoid substring false positives such as ``non-Newtonian``, ``NOT Newtonian``,
    ``generalized-Newtonian`` and Chinese ``非牛顿``.
    """
    normalized = str(text or "").lower()
    for match in re.finditer(r"\bnewtonian\b", normalized):
        prefix = normalized[max(0, match.start() - 24):match.start()]
        if re.search(r"(?:non[-\s]?|not\s+|no\s+|not\s+a\s+|not\s+an\s+|generalized[-\s]?)$", prefix):
            continue
        return True

    for match in re.finditer("牛顿", normalized):
        prefix = normalized[max(0, match.start() - 8):match.start()]
        if re.search(r"(?:非|广义[\s-]*)$", prefix):
            continue
        return True
    return False




def _geometry_class(text: str) -> str | None:
    if any(term in text for term in ("cavity", "lid-driven", "lid driven", "方腔", "空腔", "腔体", "顶盖驱动", "盖驱动", "上壁运动")):
        return "lid_driven_cavity"
    # RheoTool tutorial geometries may contain generic channel wording.  Detect
    # the more specific benchmark geometries before generic channel terms.
    if any(term in text for term in ("aneurysm", "aneurysm/herschel", "动脉瘤")):
        return "aneurysm"
    if any(term in text for term in ("fluiddamper", "fluid damper", "viscous fluid damper", "damper", "阻尼器")):
        return "fluid_damper"
    if any(term in text for term in ("impactingdrop", "impacting drop", "impactingdrop/oldroyd", "drop impact", "液滴撞击", "撞击液滴")):
        return "impacting_drop"
    if any(term in text for term in ("dieswell", "die swell", "die-swell", "挤出胀大", "模口胀大")):
        return "die_swell"
    if "胀大" in text and any(term in text for term in ("挤出", "口模", "狭缝")):
        return "die_swell"
    if any(term in text for term in ("rheotestfoam/herschel", "rheotestfoam/fene", "rheotestfoam", "virtual rheometer", "材料函数")):
        return "rheotest_material_function"
    if any(term in text for term in ("crossslot", "cross-slot", "cross slot", "十字槽", "十字流道")):
        return "cross_slot"
    if any(term in text for term in ("confined cylinder", "cylinder/oldroyd", "cylinder", "受限圆柱", "圆柱绕流", "圆柱")):
        return "confined_cylinder"
    if any(term in text for term in ("contraction41", "contraction", "4:1", "4：1", "4-to-1", "4 to 1", "收缩")):
        return "contraction"
    if any(term in text for term in ("channel", "parallel plate", "parallel-plate", "平行", "平板", "通道")):
        return "parallel_plate_channel"
    return None


def _should_try_llm_extractor(text: str, groups: dict[str, float]) -> bool:
    if not os.getenv("FOAMAGENT_ENABLE_LLM_STRUCTURED_EXTRACTOR", "").strip():
        return False
    if {"beta", "De", "Wi", "Re"}.issubset(groups):
        return False
    return any(
        token in text
        for token in (
            "de",
            "deborah",
            "re",
            "reynolds",
            "wi",
            "weissenberg",
            "beta",
            "β",
            "德博拉",
            "雷诺",
            "魏森伯格",
        )
    )


def _extract_dimensionless_groups(
    text: str,
    *,
    raw_user_requirement: str = "",
    use_llm_extractor: bool | None = None,
) -> dict[str, float]:
    groups: dict[str, float] = {}
    aliases = {
        "beta": ("beta", "β"),
        "De": ("de", "deborah", "deborah_number", "deborah number"),
        "Wi": ("wi", "weissenberg", "weissenberg_number", "weissenberg number"),
        "Re": ("re", "reynolds", "reynolds_number", "reynolds number"),
        "Pe": ("pe", "peclet", "péclet", "peclet_number", "peclet number"),
    }
    for name, names in aliases.items():
        value = _extract_scalar_alias(text, names)
        if value is not None:
            groups[name] = value
    if "beta" not in groups:
        beta = _infer_beta_from_viscosities(text)
        if beta is not None:
            groups["beta"] = beta
    should_try_llm = _should_try_llm_extractor(text, groups) if use_llm_extractor is None else use_llm_extractor
    if should_try_llm:
        try:
            from services.requirement_structured_extractor import (
                extract_requirement_with_llm,
                merge_llm_dimensionless_groups,
            )

            extraction = extract_requirement_with_llm(raw_user_requirement or text)
            if extraction is not None:
                groups, _audit = merge_llm_dimensionless_groups(raw_user_requirement or text, groups, extraction)
        except Exception:
            # LLM extraction is a non-authoritative supplement.  Intake must not
            # fail merely because the optional extractor is unavailable.
            pass
    return groups


def _reproduction_target(text: str, geometry: str | None, model: str | None, groups: dict[str, float]) -> str | None:
    template_intent_terms = (
        "模板基线", "基线模板", "相似案例", "已有案例", "已有模板",
        "基线评估", "模板做基线", "做基线评估", "沿用模板",
        "沿用平台", "基于平台已有", "基于模板",
        "template baseline", "baseline template", "similar case", "use template",
    )
    parallel_plate_template_intent = any(
        term in text
        for term in (
            "5.1.3", "rheotool", "rheo tool", "教程", "user guide",
            "平行板通道模板", "通道模板", *template_intent_terms,
        )
    )
    cavity_template_intent = any(
        term in text
        for term in (
            "5.1.4", "rheotool", "rheo tool", "教程", "user guide",
            "方腔模板", "顶盖驱动方腔模板", "cavity template",
            "lid-driven cavity template", "lid driven cavity template", *template_intent_terms,
        )
    )
    contraction_template_intent = any(
        term in text
        for term in (
            "5.1.5", "rheotool", "rheo tool", "教程", "user guide",
            "contraction41", "4:1 收缩流道模板", "4：1 收缩流道模板",
            "收缩流道模板", "contraction41 模板", "contraction41 template",
            "planar contraction template", "contraction template", *template_intent_terms,
        )
    )
    cylinder_template_intent = any(
        term in text
        for term in (
            "5.1.6", "rheotool", "rheo tool", "教程", "user guide",
            "confined cylinder", "cylinder/oldroyd", "受限圆柱绕流模板",
            "圆柱绕流模板", "cylinder/oldroyd-blog 模板", "cylinder/oldroyd-b 模板",
            "confined cylinder template", "cylinder template", *template_intent_terms,
        )
    )
    cross_slot_template_intent = (
        any(
            term in text
            for term in (
                "5.1.7", "rheotool", "rheo tool", "教程", "user guide", "benchmark",
                "crossslot 模板", "cross-slot 模板", "cross slot 模板", "十字槽模板", "十字流道模板",
                "crossslot template", "cross-slot template", "cross slot template", *template_intent_terms,
            )
        )
        or (geometry == "cross_slot" and "模板" in text)
    )
    foundation_cavity_template_intent = (
        geometry == "lid_driven_cavity"
        and any(
            term in text
            for term in (
                "openfoam v10", "v10", "foundation", "icofoam", "newtonian", "牛顿", "水",
                "water", "cavity 模板", "openfoam v10 cavity", "foundation cavity",
            )
        )
        and any(term in text for term in ("模板", "template", "benchmark", "基线", "已有"))
    )
    foundation_cavity_family_intent = (
        geometry == "lid_driven_cavity"
        and any(term in text for term in ("openfoam v10", "v10", "foundation", "icofoam", "cavity"))
        and any(
            term in text
            for term in (
                "教程族", "完整教程", "完整官方", "full allrun", "allrun", "mapfields",
                "cavityfine", "cavitygrade", "cavityhighre", "cavityclipped",
                "细网格", "渐变网格", "高 re", "高re", "二级涡", "网格对比", "网格无关",
                "多个子", "多变体", "full tutorial", "tutorial family",
            )
        )
    )
    foundation_cavity_full_allrun_selected = (
        foundation_cavity_family_intent
        and any(term in text for term in ("选择完整官方教程族", "完整官方教程族", "full_allrun", "full allrun", "父目录 allrun"))
    )
    foundation_pitzdaily_intent = (
        any(term in text for term in ("pitzdaily", "pitz daily"))
        and any(term in text for term in ("openfoam v10", "v10", "foundation", "simplefoam", "pimplefoam", "pisofoam", "potentialfoam", "scalartransportfoam", "牛顿", "水", "water", "模板", "template", "benchmark", "基线", "已有", "教程"))
    )
    foundation_pitzdaily_simplefoam_selected = (
        foundation_pitzdaily_intent
        and any(
            term in text
            for term in (
                "simplefoam", "simple foam", "steady incompressible", "稳态不可压缩",
                "模板基线", "基线模板", "基线评估", "baseline", "使用模板原始参数",
            )
        )
    )
    foundation_pitzdaily_pimple_ras_selected = (
        foundation_pitzdaily_intent
        and (
            any(term in text for term in ("pimplefoam", "pimple foam", "瞬态不可压缩"))
            or re.search(r"(?<![a-z0-9_])r(?:a|n)s(?![a-z0-9_])", text) is not None
        )
    )
    foundation_pitzdaily_piso_les_selected = (
        foundation_pitzdaily_intent
        and any(term in text for term in ("pisofoam", "piso foam", "les"))
    )
    foundation_pitzdaily_potential_selected = (
        foundation_pitzdaily_intent
        and any(term in text for term in ("potentialfoam", "potential foam", "势流"))
    )
    foundation_pitzdaily_scalar_selected = (
        foundation_pitzdaily_intent
        and any(term in text for term in ("scalartransportfoam", "scalar transport", "标量输运"))
    )
    foundation_pitzdaily_compressible_selected = (
        foundation_pitzdaily_intent
        and (
            "rhopimplefoam" in text
            or "rhocentralfoam" in text
            or ("compressible" in text and "incompressible" not in text)
            or ("可压缩" in text and "不可压缩" not in text)
        )
    )
    foundation_cylinder_intent = (
        any(term in text for term in ("cylinder", "offsetcylinder", "offset cylinder", "sloshingcylinder", "sloshing cylinder", "圆柱"))
        and any(term in text for term in ("openfoam v10", "v10", "foundation", "potentialfoam", "pimplefoam", "interfoam", "模板", "template", "benchmark", "基线", "已有", "教程"))
        and not any(term in text for term in ("rheotool", "oldroyd", "受限圆柱", "confined cylinder"))
    )
    foundation_cylinder_potential_selected = (
        foundation_cylinder_intent
        and any(term in text for term in ("potentialfoam", "potential foam", "势流", "模板基线", "基线模板", "基线评估", "baseline", "使用模板原始参数"))
    )
    foundation_cylinder_offset_selected = (
        foundation_cylinder_intent
        and any(term in text for term in ("offsetcylinder", "offset cylinder", "pimplefoam", "pimple foam", "瞬态不可压缩", "层流绕流"))
    )
    foundation_cylinder_sloshing_selected = (
        foundation_cylinder_intent
        and any(term in text for term in ("sloshingcylinder", "sloshing cylinder", "sloshing", "interfoam", "自由液面", "晃荡", "两相"))
    )
    foundation_cylinder_compressible_selected = (
        foundation_cylinder_intent
        and (
            "compressibleinterfoam" in text
            or ("compressible" in text and "incompressible" not in text)
            or ("可压缩" in text and "不可压缩" not in text)
        )
    )
    dambreak_routing_text = re.sub(r"\btemplate_id\s*[:=：]\s*\S+", " ", text)
    foundation_dambreak_intent = (
        any(term in text for term in ("dambreak", "dam break", "破坝", "溃坝"))
        and any(term in text for term in ("openfoam v10", "v10", "foundation", "interfoam", "模板", "template", "benchmark", "基线", "已有", "教程"))
    )
    foundation_dambreak_laminar_full_selected = (
        foundation_dambreak_intent
        and any(term in dambreak_routing_text for term in ("laminar full", "层流 full", "完整教程族", "full_allrun", "full allrun", "dambreakfine", "fine 网格", "细网格"))
        and "ras" not in dambreak_routing_text
    )
    foundation_dambreak_obstacle_selected = (
        foundation_dambreak_intent
        and any(term in dambreak_routing_text for term in ("obstacle", "with obstacle", "障碍物"))
    )
    foundation_dambreak_ras_full_selected = (
        foundation_dambreak_intent
        and any(term in dambreak_routing_text for term in ("ras full", "ras 完整", "ras full_allrun", "ras full allrun"))
    )
    foundation_dambreak_porous_selected = (
        foundation_dambreak_intent
        and any(term in dambreak_routing_text for term in ("porous", "baffle", "porous baffle", "多孔", "挡板"))
    )
    foundation_dambreak_ras_selected = (
        foundation_dambreak_intent
        and (
            re.search(r"(?<![a-z0-9_])r(?:a|n)s(?![a-z0-9_])", dambreak_routing_text) is not None
            or "湍流" in dambreak_routing_text
            or "turbulent" in dambreak_routing_text
        )
    )
    foundation_dambreak_unsupported_multiphase_selected = (
        foundation_dambreak_intent
        and any(term in dambreak_routing_text for term in ("intermixingfoam", "multiphaseinterfoam", "multiphaseeulerfoam", "4phase", "4 phase", "四相", "三相"))
    )
    foundation_dambreak_compressible_selected = (
        foundation_dambreak_intent
        and (
            "compressibleinterfoam" in dambreak_routing_text
            or "compressiblemultiphaseinterfoam" in dambreak_routing_text
            or ("compressible" in dambreak_routing_text and "incompressible" not in dambreak_routing_text)
            or ("可压缩" in dambreak_routing_text and "不可压缩" not in dambreak_routing_text)
        )
    )
    foundation_dambreak_baseline_selected = (
        foundation_dambreak_intent
        and any(term in dambreak_routing_text for term in ("模板基线", "基线模板", "基线评估", "baseline", "使用模板原始参数", "laminar baseline", "层流 baseline"))
    )
    foundation_forwardstep_intent = (
        any(term in text for term in ("forwardstep", "forward step", "前向台阶"))
        and any(term in text for term in ("openfoam v10", "v10", "foundation", "模板", "template", "benchmark", "基线", "已有"))
    )
    foundation_forwardstep_rhocentral_selected = (
        foundation_forwardstep_intent
        and any(term in text for term in ("rhocentralfoam", "rho central", "rho-central", "central", "高速可压缩"))
    )
    foundation_forwardstep_rhopimple_selected = (
        foundation_forwardstep_intent
        and any(term in text for term in ("rhopimplefoam", "rho pimple", "rho-pimple", "层流瞬态", "laminar"))
    )
    foundation_bernardcells_intent = (
        any(
            term in text
            for term in (
                "bernardcells", "bernard cells", "benardcells", "benard cells",
                "bénard", "benard", "rayleigh-benard", "rayleigh bénard",
                "rayleigh-bénard", "rayleigh benard", "rayleigh 对流", "瑞利", "自然对流",
            )
        )
        and any(term in text for term in ("openfoam v10", "v10", "foundation", "buoyantfoam", "模板", "template", "benchmark", "基线", "已有", "教程"))
    )
    foundation_planarpoiseuille_intent = (
        any(term in text for term in ("planarpoiseuille", "planar poiseuille", "平面泊肃叶", "泊肃叶"))
        and any(term in text for term in ("openfoam v10", "v10", "foundation", "pimplefoam", "模板", "template", "benchmark", "基线", "已有", "教程"))
    )
    foundation_obliqueshock_intent = (
        any(term in text for term in ("obliqueshock", "oblique shock", "斜激波"))
        and any(term in text for term in ("openfoam v10", "v10", "foundation", "rhocentralfoam", "模板", "template", "benchmark", "基线", "已有", "教程"))
    )
    foundation_rhocentral_shocktube_intent = (
        any(term in text for term in ("shocktube", "shock tube", "激波管"))
        and any(term in text for term in ("rhocentralfoam", "rho central", "rho-central"))
        and any(term in text for term in ("openfoam v10", "v10", "foundation", "模板", "template", "benchmark", "基线", "已有", "教程"))
    )
    foundation_rhopimple_shocktube_intent = (
        any(term in text for term in ("shocktube", "shock tube", "激波管"))
        and any(term in text for term in ("rhopimplefoam", "rho pimple", "rho-pimple"))
        and any(term in text for term in ("openfoam v10", "v10", "foundation", "模板", "template", "benchmark", "基线", "已有", "教程"))
    )
    foundation_airfoil2d_intent = (
        any(term in text for term in ("airfoil2d", "airfoil 2d", "airfoil", "air foil", "翼型"))
        and any(term in text for term in ("openfoam v10", "v10", "foundation", "simplefoam", "模板", "template", "benchmark", "基线", "已有", "教程"))
    )
    foundation_capillaryrise_intent = (
        any(term in text for term in ("capillaryrise", "capillary rise", "毛细上升"))
        and any(term in text for term in ("openfoam v10", "v10", "foundation", "interfoam", "模板", "template", "benchmark", "基线", "已有", "教程"))
    )
    foundation_wave_intent = (
        any(term in text for term in ("interfoam wave", " wave ", "wave 教程", "wave 波", "波浪"))
        and any(term in text for term in ("openfoam v10", "v10", "foundation", "interfoam", "模板", "template", "benchmark", "基线", "已有", "教程"))
    )
    if foundation_pitzdaily_compressible_selected:
        return "foundation_v10_compressible_pitzdaily_unsupported"
    if foundation_pitzdaily_pimple_ras_selected:
        return "foundation_v10_pimplefoam_ras_pitzdaily"
    if foundation_pitzdaily_piso_les_selected:
        return "foundation_v10_pisofoam_les_pitzdaily"
    if foundation_pitzdaily_potential_selected:
        return "foundation_v10_potentialfoam_pitzdaily"
    if foundation_pitzdaily_scalar_selected:
        return "foundation_v10_scalartransport_pitzdaily"
    if foundation_pitzdaily_simplefoam_selected:
        return "foundation_v10_simplefoam_pitzdaily"
    if foundation_pitzdaily_intent:
        return "foundation_v10_pitzdaily_family"
    if foundation_cylinder_compressible_selected:
        return "foundation_v10_compressible_cylinder_unsupported"
    if foundation_cylinder_sloshing_selected:
        return "foundation_v10_interfoam_laminar_sloshingcylinder"
    if foundation_cylinder_offset_selected:
        return "foundation_v10_pimplefoam_laminar_offsetcylinder"
    if foundation_cylinder_potential_selected:
        return "foundation_v10_potentialfoam_cylinder"
    if foundation_cylinder_intent:
        return "foundation_v10_cylinder_family"
    if foundation_dambreak_compressible_selected:
        return "foundation_v10_compressible_dambreak_unsupported"
    if foundation_dambreak_unsupported_multiphase_selected:
        return "foundation_v10_multiphase_dambreak_unsupported"
    if foundation_dambreak_porous_selected:
        return "foundation_v10_interfoam_ras_dambreak_porous_baffle"
    if foundation_dambreak_ras_full_selected:
        return "foundation_v10_interfoam_ras_dambreak_full_allrun"
    if foundation_dambreak_ras_selected:
        return "foundation_v10_interfoam_ras_dambreak"
    if foundation_dambreak_obstacle_selected:
        return "foundation_v10_interfoam_dambreak_with_obstacle"
    if foundation_dambreak_laminar_full_selected:
        return "foundation_v10_interfoam_dambreak_laminar_full_allrun"
    if foundation_dambreak_baseline_selected:
        return "foundation_v10_interfoam_dambreak"
    if foundation_dambreak_intent:
        return "foundation_v10_dambreak_family"
    if foundation_forwardstep_rhocentral_selected:
        return "foundation_v10_rhocentralfoam_forwardstep"
    if foundation_forwardstep_rhopimple_selected:
        return "foundation_v10_rhopimplefoam_laminar_forwardstep"
    if foundation_forwardstep_intent:
        return "foundation_v10_forwardstep_family"
    if foundation_bernardcells_intent:
        return "foundation_v10_buoyantfoam_bernardcells"
    if foundation_planarpoiseuille_intent:
        return "foundation_v10_pimplefoam_laminar_planarpoiseuille"
    if foundation_obliqueshock_intent:
        return "foundation_v10_rhocentralfoam_obliqueshock"
    if foundation_rhocentral_shocktube_intent:
        return "foundation_v10_rhocentralfoam_shocktube"
    if foundation_rhopimple_shocktube_intent:
        return "foundation_v10_rhopimplefoam_laminar_shocktube"
    if foundation_airfoil2d_intent:
        return "foundation_v10_simplefoam_airfoil2d"
    if foundation_capillaryrise_intent:
        return "foundation_v10_interfoam_laminar_capillaryrise"
    if foundation_wave_intent:
        return "foundation_v10_interfoam_laminar_wave"
    if geometry == "aneurysm" and model == "HerschelBulkley":
        if any(term in text for term in ("5.1.8", "aneurysm/herschel", "aneurysm", "动脉瘤", "rheotool", "教程", "user guide")):
            return "rheotool_5_1_8_aneurysm_herschelbulkley"
    if geometry == "fluid_damper" and model == "CarreauYasuda":
        if any(term in text for term in ("5.1.9", "fluiddamper", "fluid damper", "damper", "阻尼器", "rheotool", "教程", "user guide")):
            return "rheotool_5_1_9_fluiddamper_carreauyasuda"
    if geometry == "rheotest_material_function" and model == "HerschelBulkley":
        if any(term in text for term in ("5.2.2", "rheotestfoam/herschel", "rheotestfoam", "材料函数", "rheotool", "教程", "user guide")):
            return "rheotool_5_2_2_rheotest_herschelbulkley"
    if geometry == "rheotest_material_function" and model == "FENE-CR":
        if any(term in text for term in ("5.2.3", "rheotestfoam/fene", "rheotestfoam", "material function", "rheotool", "教程", "user guide")):
            return "rheotool_5_2_3_rheotest_fenecr"
    if geometry == "impacting_drop" and model == "Oldroyd-B":
        if any(term in text for term in ("5.3.2", "impactingdrop", "impacting drop", "rheointerfoam", "rheotool", "教程", "user guide")):
            return "rheotool_5_3_2_impactingdrop_oldroydb_log"
    if geometry == "die_swell":
        if any(term in text for term in ("5.3.3", "rheointerfoam", "rheotool", "教程", "user guide", "模板基线", "基线模板", "相似案例", "已有案例", "已有模板", "template baseline")):
            if model == "CarreauYasuda":
                return "rheotool_5_3_3_dieswell_carreauyasuda"
            if model == "Giesekus":
                return "rheotool_5_3_3_dieswell_giesekuslog"
            if model == "Oldroyd-B":
                return "rheotool_5_3_3_dieswell_oldroydb_log"
            return "rheotool_5_3_3_dieswell_family"
    if geometry == "cross_slot" and model == "Oldroyd-B":
        if cross_slot_template_intent:
            return "rheotool_5_1_7_crossslot_oldroydb_log"
        if groups.get("Re") == 0.0 and groups.get("Wi") == 0.33 and groups.get("beta") == 0.0:
            return "rheotool_5_1_7_crossslot_oldroydb_log"
    if geometry == "cross_slot" and model is None:
        if cross_slot_template_intent:
            return "rheotool_5_1_7_crossslot_oldroydb_log"
    if geometry == "confined_cylinder" and model == "Oldroyd-B":
        if cylinder_template_intent:
            return "rheotool_5_1_6_cylinder_oldroydb_log"
        if groups.get("Re") == 0.0 and groups.get("Wi") == 0.7 and groups.get("beta") == 0.59:
            return "rheotool_5_1_6_cylinder_oldroydb_log"
    if geometry == "confined_cylinder" and model is None:
        if cylinder_template_intent:
            return "rheotool_5_1_6_cylinder_oldroydb_log"
    if geometry == "contraction" and model == "Oldroyd-B":
        if contraction_template_intent:
            return "rheotool_5_1_5_contraction41_oldroydb_log"
        if groups.get("Re") == 0.01 and groups.get("De") == 1.0 and groups.get("beta") == 0.5:
            return "rheotool_5_1_5_contraction41_oldroydb_log"
    if geometry == "contraction" and model is None:
        if contraction_template_intent:
            return "rheotool_5_1_5_contraction41_oldroydb_log"
    if geometry == "lid_driven_cavity" and model == "Oldroyd-B":
        if cavity_template_intent:
            return "rheotool_5_1_4_cavity_oldroydb_log"
        if any(term in text for term in ("fattal", "kupferman")):
            return "rheotool_5_1_4_cavity_oldroydb_log"
        if groups.get("Re") == 0.01 and groups.get("De") == 1.0 and groups.get("beta") == 0.5:
            return "rheotool_5_1_4_cavity_oldroydb_log"
    if foundation_cavity_full_allrun_selected:
        return "foundation_v10_icofoam_cavity_full_allrun"
    if foundation_cavity_family_intent:
        return "foundation_v10_icofoam_cavity_family"
    if foundation_cavity_template_intent:
        return "foundation_v10_icofoam_cavity"
    if geometry == "lid_driven_cavity" and model is None:
        if cavity_template_intent:
            return "rheotool_5_1_4_cavity_oldroydb_log"
    if geometry == "parallel_plate_channel" and model == "Oldroyd-B":
        if parallel_plate_template_intent:
            return "rheotool_5_1_3_channel_oldroydb_log"
        if groups.get("Wi") == 0.99 and groups.get("beta") == 0.01:
            return "rheotool_5_1_3_channel_oldroydb_log"
    if geometry == "parallel_plate_channel" and model is None:
        if parallel_plate_template_intent:
            return "rheotool_5_1_3_channel_oldroydb_log"
    return None


def _certified_benchmark_alias_match(text: str) -> dict | None:
    """Return local certified benchmark metadata only for a signature-safe match."""
    try:
        from services.benchmarks import find_certified_benchmark_alias_match
    except Exception:
        return None
    return find_certified_benchmark_alias_match(text)

def compile_workflow(user_requirement: str, *, use_llm_extractor: bool | None = None) -> CompiledWorkflow:
    text = " ".join((user_requirement or "").lower().split())
    benchmark_alias_match = _certified_benchmark_alias_match(text)
    evidence_text = text.replace("steady_or_transient", "flow_state")
    evidence_text = evidence_text.replace("## rheology", "## constitutive_model_section")
    rheology_evidence = _hits(evidence_text, RHEOLOGY_TERMS) + tuple(
        alias for alias in MODEL_ALIASES if alias in evidence_text
    )
    if benchmark_alias_match:
        physics_meta = benchmark_alias_match["metadata"].get("physics") or {}
        if physics_meta.get("constitutive_family") or physics_meta.get("model"):
            rheology_evidence = rheology_evidence + ("certified_benchmark",)
        model = physics_meta.get("model")
        if model and str(model).lower() in {"giesekus", "oldroyd-b", "ptt", "fen-ecr"}:
            evidence_text += " " + str(model).lower()
    two_phase_evidence = _two_phase_hits(evidence_text)
    two_phase = bool(two_phase_evidence)
    material_test = bool(_hits(evidence_text, MATERIAL_TEST_TERMS))
    steady = "steady" in evidence_text or ("稳态" in evidence_text and "非稳态" not in evidence_text)
    transient = "transient" in evidence_text or "瞬态" in evidence_text or "非稳态" in evidence_text
    contradictions = []
    if steady and transient:
        contradictions.append("steady_and_transient")
    if rheology_evidence and _has_newtonian_evidence(evidence_text):
        contradictions.append("newtonian_and_rheological")
    selected_model = _selected_model(evidence_text)
    parameters = _extract_parameters(evidence_text)
    if selected_model == "Oldroyd-B":
        parameters = _complete_oldroyd_parameters_from_beta(evidence_text, parameters)
    if selected_model == "CarreauYasuda" and "k" not in parameters and "lambda" in parameters:
        # Older/user shorthand often calls the Carreau-Yasuda time constant
        # "lambda"; RheoTool's dictionary key is k and the model has no
        # viscoelastic relaxation-time parameter to require separately.
        parameters["k"] = parameters["lambda"]
    if benchmark_alias_match:
        benchmark_model = (benchmark_alias_match["metadata"].get("physics") or {}).get("model")
        if benchmark_model:
            selected_model = str(benchmark_model)
        benchmark_parameters = benchmark_alias_match["metadata"].get("parameters") or {}
        for key, value in benchmark_parameters.items():
            if isinstance(value, (int, float)):
                parameters[str(key)] = float(value)
    unsupported = _unsupported_hits(evidence_text)

    behavior = "newtonian"
    if selected_model in {"CarreauYasuda", "HerschelBulkley"} or "剪切变稀" in evidence_text or "yield stress" in evidence_text:
        behavior = "generalized-newtonian"
    elif rheology_evidence:
        behavior = "viscoelastic"

    missing_parameters = tuple(
        name for name in MODEL_REQUIREMENTS.get(selected_model or "", ()) if name not in parameters
    )
    missing_fields = ()
    if rheology_evidence and not selected_model:
        missing_fields = ("constitutive_model",)
    if benchmark_alias_match:
        missing_parameters = ()
        missing_fields = ()

    objectives = tuple(
        name for name, terms in {
            "pressure_drop": ("pressure drop", "压降"),
            "material_functions": MATERIAL_TEST_TERMS,
            "velocity_profile": ("u(y)", "速度剖面", "velocity profile"),
            "theta_profile": ("theta_xy", "θxy", "θ_xy", "thetaxy"),
            "kinetic_energy": ("kinetic energy", "动能", "ek(t)", "ek"),
        }.items() if _hits(evidence_text, terms)
    )
    if two_phase_evidence:
        objectives = objectives + ("free_surface",)
    geometry = _geometry_class(evidence_text)
    dimensionless_groups = _extract_dimensionless_groups(
        evidence_text,
        raw_user_requirement=user_requirement,
        use_llm_extractor=use_llm_extractor,
    )
    reproduction_target = _reproduction_target(evidence_text, geometry, selected_model, dimensionless_groups)
    if reproduction_target in RHEOTOOL_TUTORIAL_TARGET_SOLVERS or reproduction_target in TEMPLATE_FAMILIES:
        # RheoTool tutorial templates own the full material setup.  Two-phase
        # tutorials commonly mention a viscoelastic liquid phase and a
        # Newtonian air phase; that should not trigger the generic
        # "Newtonian vs rheological" user clarification.
        contradictions = tuple(item for item in contradictions if item != "newtonian_and_rheological")
    if reproduction_target in RHEOTOOL_TUTORIAL_TARGET_SOLVERS or reproduction_target in FOUNDATION_TUTORIAL_TARGET_SOLVERS:
        missing_parameters = ()
        missing_fields = ()
    intent = ProblemIntent(
        application=user_requirement.strip(),
        phases=("fluid", "gas") if two_phase else ("fluid",),
        objectives=objectives,
        rheology_evidence=rheology_evidence,
        newtonian_evidence=("newtonian",) if _has_newtonian_evidence(evidence_text) else (),
        steady_or_transient="steady" if steady else "transient" if transient else None,
        free_surface=two_phase,
        known_parameters=parameters,
        missing_critical_fields=missing_fields,
        contradictions=tuple(contradictions),
        geometry_class=geometry,
        dimensionless_groups=dimensionless_groups,
        reproduction_target=reproduction_target,
    )
    physics = PhysicsSpec(
        phase_type="two-phase" if two_phase else "single-phase",
        incompressible=not bool(unsupported),
        transient=True if transient or two_phase else False if steady else None,
        free_surface=two_phase,
        objectives=objectives,
    )
    rheology = RheologySpec(
        behavior=behavior,
        selected_model=selected_model,
        parameters=parameters,
        missing_parameters=missing_parameters,
    )

    rejection_reason = None
    target = None
    workflow_type = "unresolved"
    explicit_solver = next(
        (solver for solver in (
            "rheoTestFoam", "rheoInterFoam", "rheoFoam", "simpleFoam",
            "pimpleFoam", "interFoam", "icoFoam", "pisoFoam",
            "potentialFoam", "scalarTransportFoam", "buoyantFoam",
        ) if solver.lower() in evidence_text),
        None,
    )
    if benchmark_alias_match:
        target_meta = benchmark_alias_match["metadata"].get("target") or {}
        solver = target_meta.get("solver")
        if solver:
            target = CaseTarget.for_solver(str(solver))
            workflow_type = "certified-benchmark"
    if reproduction_target == "foundation_v10_compressible_pitzdaily_unsupported":
        rejection_reason = (
            "OpenFOAM v10 pitzDaily compressible variants use compressible solvers "
            "(for example rhoPimpleFoam/rhoCentralFoam), which are outside the current "
            "certified solver matrix."
        )
    elif reproduction_target == "foundation_v10_compressible_dambreak_unsupported":
        rejection_reason = (
            "OpenFOAM v10 damBreak compressible variants use compressible solvers "
            "(for example compressibleInterFoam/compressibleMultiphaseInterFoam), "
            "which are outside the current certified solver matrix."
        )
    elif reproduction_target == "foundation_v10_multiphase_dambreak_unsupported":
        rejection_reason = (
            "OpenFOAM v10 damBreak multi-phase variants use solvers such as "
            "interMixingFoam, multiphaseInterFoam, or multiphaseEulerFoam, which are "
            "outside the current certified solver matrix."
        )
    elif reproduction_target == "foundation_v10_compressible_cylinder_unsupported":
        rejection_reason = (
            "OpenFOAM v10 cylinder compressible variants use compressible solvers "
            "(for example compressibleInterFoam), which are outside the current "
            "certified solver matrix."
        )
    elif reproduction_target in FOUNDATION_TUTORIAL_TARGET_SOLVERS:
        target = CaseTarget.for_solver(FOUNDATION_TUTORIAL_TARGET_SOLVERS[reproduction_target])
        workflow_type = "foundation-tutorial-template"
    elif reproduction_target in TEMPLATE_FAMILIES:
        workflow_type = str(TEMPLATE_FAMILIES[reproduction_target]["workflow_type"])
    elif unsupported and target is None:
        rejection_reason = f"Physics is outside the certified capability matrix: {', '.join(unsupported)}"
    elif target is not None:
        pass
    elif reproduction_target == "foundation_v10_forwardstep_unsupported":
        rejection_reason = (
            "OpenFOAM v10 forwardStep tutorial in the installed Foundation tree uses "
            "compressible solvers (rhoCentralFoam/rhoPimpleFoam), which are outside the "
            "current certified solver matrix."
        )
    elif reproduction_target in RHEOTOOL_TUTORIAL_TARGET_SOLVERS:
        target = CaseTarget.for_solver(RHEOTOOL_TUTORIAL_TARGET_SOLVERS[reproduction_target])
        workflow_type = "rheotool-tutorial-template"
    elif explicit_solver:
        target = CaseTarget.for_solver(explicit_solver)
        workflow_type = "explicit-certified-solver"
    elif material_test:
        target = CaseTarget.for_solver("rheoTestFoam")
        workflow_type = "material-characterization"
    elif rheology_evidence and two_phase:
        target = CaseTarget.for_solver("rheoInterFoam")
        workflow_type = "rheological-two-phase"
    elif rheology_evidence:
        target = CaseTarget.for_solver("rheoFoam")
        workflow_type = "rheological-single-phase"
    elif two_phase:
        target = CaseTarget.for_solver("interFoam")
        workflow_type = "newtonian-two-phase"
    elif steady:
        target = CaseTarget.for_solver("simpleFoam")
        workflow_type = "newtonian-steady"
    elif transient:
        target = CaseTarget.for_solver("pimpleFoam")
        workflow_type = "newtonian-transient"
    elif (
        "cavity" in evidence_text
        or "空腔" in evidence_text
        or "方腔" in evidence_text
        or "腔体" in evidence_text
        or "顶盖驱动" in evidence_text
        or "上壁运动" in evidence_text
    ):
        target = CaseTarget.for_solver("icoFoam")
        workflow_type = "newtonian-laminar-transient"

    questions = []
    if "steady_and_transient" in contradictions:
        questions.append("请确认该工况是稳态还是瞬态。")
    if "newtonian_and_rheological" in contradictions:
        questions.append("请确认材料是牛顿流体还是具有非牛顿/粘弹性行为。")
    if missing_fields:
        questions.append("请提供或选择经过验证的本构模型。")
    if missing_parameters:
        questions.append("请提供本构参数：" + ", ".join(missing_parameters) + "。")
    if target is None and rejection_reason is None:
        questions.append("请说明工况是稳态、瞬态还是包含自由液面。")

    ready = target is not None and not rejection_reason and not questions
    plan = WorkflowPlan(
        workflow_type=workflow_type,
        stages=("mesh", "generate", "validate", "run", "postprocess"),
        required_inputs=tuple(missing_fields) + missing_parameters,
        expected_outputs=objectives or ("flow_field",),
        target=target,
        ready=ready,
        clarification_questions=tuple(questions),
        rejection_reason=rejection_reason,
    )
    return CompiledWorkflow(intent, physics, rheology, plan)
