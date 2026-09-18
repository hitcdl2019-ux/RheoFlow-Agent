from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.material_cards import match_material_card, unknown_material_questions
from services.workflow_compiler import (
    FOUNDATION_TUTORIAL_TARGET_SOLVERS,
    MODEL_REQUIREMENTS,
    NUMBER_PATTERN,
    PARAMETER_ALIASES,
    _parameter_name_pattern,
    compile_workflow,
)
from services.template_families import (
    TEMPLATE_FAMILIES,
    template_family_clarification,
    template_family_match_payload,
)

INTAKE_VERSION = "1"
POLICY_VERSION = "dual-channel-mvp-v1"
RECEIPT_SUFFIX = ".intake.json"

GEOMETRY_TERMS = (
    "geometry", "dimension", "diameter", "length", "width", "height", "radius",
    "pipe", "channel", "cavity", "die", "mesh", "几何", "尺寸", "直径", "长度", "宽度",
    "高度", "半径", "边长", "管", "通道", "方腔", "空腔", "腔体", "模具", "网格",
)
FLOW_TERMS = (
    "inlet", "velocity", "flow rate", "flowrate", "pressure", "re=", "入口", "速度",
    "流量", "压差", "压降", "压力", "脉动",
)
MATERIAL_HINT_TERMS = (
    "polymer", "melt", "solution", "toothpaste", "blood", "slurry",
    "gel", "聚合物", "熔体", "溶液", "牙膏", "血液", "浆料", "凝胶",
)
BENCHMARK_TERMS = ("benchmark", "cavity", "dam break", "方腔", "空腔", "破坝")
MATERIAL_TEST_TERMS = ("rheometer", "material function", "流变仪", "材料函数")
PARAMETER_SOURCE_TERMS = ("parameter source", "参数来源")
APPROVAL_TERMS = ("user approved", "user confirmation", "用户授权", "用户确认")
SOURCE_TERMS = ("source reference", "doi", "来源", "文献")
BASELINE_MODE_TERMS = (
    "template baseline", "baseline template", "similar case", "use template",
    "模板基线", "基线模板", "相似案例", "已有案例", "已有模板", "教程模板", "先用模板", "用模板",
    "基线评估", "模板做基线", "做基线评估", "平行板通道模板", "通道模板", "沿用模板", "沿用平台",
    "方腔模板", "顶盖驱动方腔模板", "cavity template", "lid-driven cavity template",
    "4:1 收缩流道模板", "4：1 收缩流道模板", "收缩流道模板", "contraction41 模板",
    "contraction41 template", "planar contraction template", "contraction template",
    "受限圆柱绕流模板", "圆柱绕流模板", "cylinder/oldroyd-blog 模板",
    "cylinder/oldroyd-b 模板", "confined cylinder template", "cylinder template",
    "crossslot 模板", "cross-slot 模板", "cross slot 模板", "十字槽模板",
    "十字流道模板", "crossslot template", "cross-slot template", "cross slot template",
    "基于平台已有", "基于模板",
)
REAL_DEVICE_MODE_TERMS = (
    "real device", "actual device", "real geometry", "actual geometry",
    "真实设备", "实际设备", "真实几何", "实际几何", "真实口模", "实际口模", "我的口模",
)
PARAMETER_SCAN_MODE_TERMS = (
    "parameter scan", "parametric", "sensitivity", "参数扫描", "参数研究", "敏感性分析",
    "分别计算", "多组", "多工况", "扫描", "对比不同",
)
TEMPLATE_ORIGINAL_PARAMETER_TERMS = (
    "use template original parameters", "template original parameters", "use all template parameters",
    "no parameter changes", "without parameter changes",
    "使用模板原始参数", "使用模板全部原始参数", "使用模板全部默认参数", "模板原始参数",
    "全部默认参数", "全部原始参数", "不修改参数", "无需修改参数", "保持原始参数", "保持模板参数",
)
TEMPLATE_PARTIAL_OVERRIDE_TERMS = (
    "modify template parameters", "partial parameter override", "with user overrides",
    "override parameters", "修改部分参数", "部分修改", "参数覆盖", "覆盖参数", "基于模板修改",
    "在模板原始参数基础上修改", "改为", "改成", "修改为", "提高到", "降低到", "倍",
)
TASK_MODE_FIRST_TEMPLATE_GEOMETRIES = {
    "die_swell": {
        "suggested": "RheoTool 5.3.3 DieSwell tutorial family can be used as a baseline after the user confirms task.mode=template_baseline.",
        "source": "RheoTool tutorial registry",
    },
    "parallel_plate_channel": {
        "suggested": "RheoTool 5.1.3 parallel-plates/channel template can be used as a baseline after the user confirms task.mode=template_baseline.",
        "source": "RheoTool tutorial registry",
    },
    "lid_driven_cavity": {
        "suggested": "RheoTool 5.1.4 lid-driven cavity template can be used as a baseline after the user confirms task.mode=template_baseline.",
        "source": "RheoTool tutorial registry",
    },
    "contraction": {
        "suggested": "RheoTool 5.1.5 4:1 planar contraction template can be used as a baseline after the user confirms task.mode=template_baseline.",
        "source": "RheoTool tutorial registry",
    },
    "confined_cylinder": {
        "suggested": "RheoTool 5.1.6 confined cylinder template can be used as a baseline after the user confirms task.mode=template_baseline.",
        "source": "RheoTool tutorial registry",
    },
    "cross_slot": {
        "suggested": "RheoTool 5.1.7 2D CrossSlot template can be used as a baseline after the user confirms task.mode=template_baseline.",
        "source": "RheoTool tutorial registry",
    },
}
FOUNDATION_SOLVERS = {
    "icoFoam", "simpleFoam", "pimpleFoam", "interFoam",
    "pisoFoam", "potentialFoam", "scalarTransportFoam",
}
REYNOLDS_THRESHOLD = 2300.0
CANONICAL_TEMPLATE_DIMENSIONLESS = {
    "rheotool_5_1_3_channel_oldroydb_log": {
        "Re": 0.0,
        "Wi": 0.99,
        "beta": 0.01,
    },
    "rheotool_5_1_7_crossslot_oldroydb_log": {
        "Re": 0.0,
        "Wi": 0.33,
        "beta": 0.0,
        "Pe": 500.0,
    },
}


def requirement_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def receipt_path_for(requirement_path: str | Path) -> Path:
    path = Path(requirement_path)
    return path.with_suffix(path.suffix + RECEIPT_SUFFIX)


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _has_number(text: str) -> bool:
    return any(ch.isdigit() for ch in text)



def _has_material_hint(text: str) -> bool:
    lowered = text.lower()
    for term in MATERIAL_HINT_TERMS:
        if term.isascii():
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", lowered):
                return True
        elif term in lowered:
            return True
    return False


def _has_foundation_hint(text: str) -> bool:
    lowered = text.lower()
    return any(
        term in lowered
        for term in (
            "water", "air", "newtonian", "openfoam v10", "v10", "foundation", "icofoam",
            "水", "空气", "牛顿",
        )
    )


def _template_candidates(text: str, compiled) -> list[dict[str, Any]]:
    """Return platform template candidates independent of the final selected template.

    This is intentionally small and explicit.  Intake task-mode ordering should depend on
    whether the platform has a plausible baseline candidate, not on per-case hard-coded
    clarification branches.
    """
    geometry = compiled.intent.geometry_class
    candidates: list[dict[str, Any]] = []
    if geometry == "parallel_plate_channel" and _has_material_hint(text):
        candidates.append({
            "field": "template_candidate",
            "template_id": "rheotool_5_1_3_channel_oldroydb_log",
            "suggested": "RheoTool 5.1.3 parallel-plates/channel baseline is the single certified Channel/Oldroyd-BLog template; non-Oldroyd-B models are generalization/adaptation cases, not registered template variants.",
            "source": "RheoTool tutorial registry",
            "channel": "v9-rheotool",
        })
    elif geometry == "lid_driven_cavity":
        if _has_material_hint(text) or compiled.rheology.selected_model is not None:
            candidates.append({
                "field": "template_candidate",
                "template_id": "rheotool_5_1_4_cavity_oldroydb_log",
                "suggested": "RheoTool 5.1.4 lid-driven cavity template can be used as a baseline after task.mode is confirmed.",
                "source": "RheoTool tutorial registry",
                "channel": "v9-rheotool",
            })
        elif _has_foundation_hint(text):
            candidates.append({
                "field": "template_candidate",
                "template_id": "foundation_v10_icofoam_cavity",
                "suggested": "OpenFOAM v10 icoFoam lid-driven cavity template can be used as a baseline after task.mode is confirmed.",
                "source": "Foundation v10 tutorial registry",
                "channel": "v10-foundation",
            })
    elif geometry == "contraction" and _has_material_hint(text):
        candidates.append({
            "field": "template_candidate",
            "template_id": "rheotool_5_1_5_contraction41_oldroydb_log",
            "suggested": "RheoTool 5.1.5 4:1 planar contraction template can be used as a baseline after task.mode is confirmed.",
            "source": "RheoTool tutorial registry",
            "channel": "v9-rheotool",
        })
    elif geometry == "confined_cylinder" and _has_material_hint(text):
        candidates.append({
            "field": "template_candidate",
            "template_id": "rheotool_5_1_6_cylinder_oldroydb_log",
            "suggested": "RheoTool 5.1.6 confined cylinder template can be used as a baseline after task.mode is confirmed.",
            "source": "RheoTool tutorial registry",
            "channel": "v9-rheotool",
        })
    elif geometry == "cross_slot" and _has_material_hint(text):
        candidates.append({
            "field": "template_candidate",
            "template_id": "rheotool_5_1_7_crossslot_oldroydb_log",
            "suggested": "RheoTool 5.1.7 2D CrossSlot template can be used as a baseline after task.mode is confirmed.",
            "source": "RheoTool tutorial registry",
            "channel": "v9-rheotool",
        })
    elif geometry == "die_swell" and _has_material_hint(text):
        candidates.append({
            "field": "template_candidate",
            "template_id": "rheotool_5_3_3_dieswell_family",
            "suggested": "RheoTool 5.3.3 DieSwell tutorial family can be used as a baseline after task.mode is confirmed.",
            "source": "RheoTool tutorial registry",
            "channel": "v9-rheotool",
        })
    return candidates


def _target_preview(compiled) -> dict[str, str] | None:
    return compiled.plan.target.as_dict() if compiled.plan.target is not None else None


def _template_family_match(target_id: str | None) -> dict[str, Any] | None:
    if not target_id:
        return None
    return template_family_match_payload(target_id)


def _task_mode(text: str) -> str | None:
    lowered = text.lower()
    if _has_any(lowered, PARAMETER_SCAN_MODE_TERMS):
        return "parameter_scan"
    if re.search(r"(?:比较|评估).{0,20}(?:不同|多组|多个|若干).{0,40}(?:影响|变化|对比)", lowered):
        return "parameter_scan"
    if _has_any(lowered, BASELINE_MODE_TERMS) or re.search(r"(?:基于|使用|沿用).{0,20}模板", lowered):
        return "template_baseline"
    if _has_any(lowered, REAL_DEVICE_MODE_TERMS):
        return "real_device"
    return None


def _template_parameter_policy(text: str) -> str | None:
    lowered = text.lower()
    if _has_any(lowered, TEMPLATE_PARTIAL_OVERRIDE_TERMS):
        return "template_with_user_overrides"
    if _has_any(lowered, TEMPLATE_ORIGINAL_PARAMETER_TERMS):
        return "use_template_originals"
    return None


def _template_baseline_requested(text: str) -> bool:
    lowered = text.lower()
    explicit_task_mode = re.search(
        r"task[_\s-]*mode\s*[:=：]\s*(?:template_baseline|baseline|模板基线|基线模板)",
        lowered,
    )
    if explicit_task_mode:
        return True
    if _template_parameter_policy(lowered) is not None:
        return True
    if any(term in lowered for term in ("复现", "reproduce tutorial", "tutorial reproduction")):
        return False
    return _task_mode(lowered) == "template_baseline"


def _has_template_override_values(text: str) -> bool:
    lowered = text.lower()
    if re.search(r"\b(?:etaS|etas|etaP|etap|lambda|alpha|epsilon|nu0|nuInf|eta0|etaInf|tau0|k|n|a|rho|U|velocity|flowrate|flow rate|endTime|Wi|Re|Pe|De|beta|D)\b\s*[:=：]\s*[-+]?\d", text, re.IGNORECASE):
        return True
    return bool(re.search(r"(?:改为|改成|修改为|提高到|降低到|override).{0,20}[-+]?\d|[-+]?\d+(?:\.\d+)?\s*倍", lowered))


def _has_template_override_values_for_template(text: str, template_id: str | None, compiled) -> bool:
    lowered = text.lower()
    if re.search(r"\b(?:etaS|etas|etaP|etap|lambda|alpha|epsilon|nu0|nuInf|eta0|etaInf|tau0|k|n|a|rho|U|velocity|flowrate|flow rate|endTime)\b\s*[:=：]\s*[-+]?\d", text, re.IGNORECASE):
        return True
    if re.search(r"(?:改为|改成|修改为|提高到|降低到|override).{0,20}[-+]?\d|[-+]?\d+(?:\.\d+)?\s*倍", lowered):
        return True

    groups = compiled.intent.dimensionless_groups or {}
    explicit_dimensionless = any(name in groups for name in ("Re", "Wi", "Pe", "De", "beta"))
    if not explicit_dimensionless:
        return bool(re.search(r"\bD\b\s*[:=：]\s*[-+]?\d", text, re.IGNORECASE))

    canonical = CANONICAL_TEMPLATE_DIMENSIONLESS.get(template_id or "")
    if not canonical:
        return True
    for name, value in groups.items():
        if name not in canonical:
            return True
        if abs(float(value) - float(canonical[name])) > 1e-9:
            return True
    return False


def _has_canonical_dimensionless_signature(template_id: str | None, compiled) -> bool:
    canonical = CANONICAL_TEMPLATE_DIMENSIONLESS.get(template_id or "")
    if not canonical:
        return False
    groups = compiled.intent.dimensionless_groups or {}
    if set(groups) != set(canonical):
        return False
    return all(abs(float(groups[name]) - float(value)) <= 1e-9 for name, value in canonical.items())


def _unknown_custom_boundary_condition(text: str) -> str | None:
    candidates = re.findall(r"(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_]*BC)(?![A-Za-z0-9_])", text)
    for name in candidates:
        lowered = name.lower()
        if lowered.startswith(("customer", "custom")):
            return name
    if "自定义" in text and re.search(r"边界条件|boundary condition|\\bbc\\b", text, re.IGNORECASE):
        return "custom boundary condition"
    return None


def _explicit_contraction_ratio(text: str) -> float | None:
    lowered = text.lower()
    patterns = (
        r"(?<!\d)(\d+(?:\.\d+)?)\s*[:：]\s*1(?!\d)",
        r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:to|-to-)\s*1(?!\d)",
    )
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
    return None


def _contraction_ratio_mismatch(text: str, compiled) -> dict[str, Any] | None:
    if compiled.intent.geometry_class != "contraction":
        return None
    ratio = _explicit_contraction_ratio(text)
    if ratio is None or abs(ratio - 4.0) < 1e-9:
        return None
    return {
        "field": "geometry.contraction_ratio",
        "reason": (
            f"Detected a {ratio:g}:1 contraction request, while the available RheoTool Contraction41 template is 4:1. "
            "Foam-Agent must not silently approximate this with the 4:1 template."
        ),
        "ask_user": (
            f"检测到你请求的是 {ratio:g}:1 平面收缩流道，但平台已登记模板是 4:1 Contraction41。"
            "请确认：1）改用 4:1 模板做基线近似；2）按真实 2:1/非 4:1 几何生成新 case；"
            "3）提供已有的对应收缩比认证模板。"
        ),
        "requested_ratio": ratio,
        "available_template_ratio": 4.0,
        "template_candidate": "rheotool_5_1_5_contraction41_oldroydb_log",
    }


def _obstacle_shape_mismatch(text: str, compiled) -> dict[str, Any] | None:
    lowered = text.lower()
    square_obstacle = (
        ("方形" in lowered or "矩形" in lowered or "square" in lowered or "rectangular" in lowered)
        and ("障碍物" in lowered or "obstacle" in lowered or "柱" in lowered)
    )
    if not square_obstacle:
        return None
    return {
        "field": "geometry.obstacle_shape",
        "reason": (
            "Detected a non-cylindrical obstacle request, while the available RheoTool confined-cylinder template uses a circular cylinder. "
            "Foam-Agent must not silently approximate a square/rectangular obstacle with the cylinder template."
        ),
        "ask_user": (
            "检测到你请求的是方形/矩形障碍物，但平台已登记的受限绕流模板是圆柱障碍物。"
            "请确认：1）改用圆柱模板做基线近似；2）按真实方形障碍物几何生成新 case；"
            "3）提供已有的方形障碍物认证模板。"
        ),
        "requested_shape": "square_or_rectangular_obstacle",
        "available_template_shape": "circular_cylinder",
        "template_candidate": "rheotool_5_1_6_cylinder_oldroydb_log",
    }



def _cross_slot_topology_mismatch(text: str, compiled) -> dict[str, Any] | None:
    lowered = text.lower()
    t_junction = (
        "t 型" in lowered
        or "t型" in lowered
        or "t-junction" in lowered
        or "t junction" in lowered
        or "t形" in lowered
    )
    if not t_junction:
        return None
    return {
        "field": "geometry.topology",
        "reason": (
            "Detected a T-junction topology request, while the available RheoTool CrossSlot template is a four-arm cross-slot. "
            "Foam-Agent must not silently approximate a T-junction with the CrossSlot template."
        ),
        "ask_user": (
            "检测到你请求的是 T 型流道，但平台已登记的 CrossSlot 模板是四臂十字槽拓扑。"
            "请确认：1）改用 CrossSlot 模板做基线近似；2）按真实 T 型几何生成新 case；"
            "3）提供已有的 T 型流道认证模板。"
        ),
        "requested_topology": "t_junction",
        "available_template_topology": "four_arm_cross_slot",
        "template_candidate": "rheotool_5_1_7_crossslot_oldroydb_log",
    }

def _explicit_reynolds_number(text: str, compiled) -> float | None:
    value = (compiled.intent.dimensionless_groups or {}).get("Re")
    if isinstance(value, (int, float)):
        return float(value)
    patterns = (
        r"(?<![A-Za-z0-9_])re\s*(?:=|:|：|约|大约|around|about)?\s*([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)",
        r"雷诺数\s*(?:=|:|：|约|大约)?\s*([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
    return None


def _needs_turbulence_scope_clarification(text: str, compiled, *, rheotool_tutorial: bool) -> dict[str, Any] | None:
    if not rheotool_tutorial:
        return None
    supported_geometry_labels = {
        "parallel_plate_channel": "平行板通道",
        "lid_driven_cavity": "顶盖驱动方腔",
        "contraction": "4:1 收缩流道",
        "confined_cylinder": "受限圆柱绕流",
        "cross_slot": "二维 CrossSlot 十字槽",
    }
    geometry_label = supported_geometry_labels.get(compiled.intent.geometry_class)
    if geometry_label is None:
        return None
    lowered = text.lower()
    reynolds = _explicit_reynolds_number(text, compiled)
    turbulence_terms = ("turbulence", "turbulent", "rans", "les", "湍流", "湍流影响", "高速")
    has_turbulence_intent = any(term in lowered for term in turbulence_terms)
    high_re = reynolds is not None and reynolds > REYNOLDS_THRESHOLD
    if not (high_re or (has_turbulence_intent and reynolds is not None)):
        return None
    reason = (
        f"The request combines the RheoTool {compiled.intent.geometry_class} viscoelastic template with a high-Re/turbulence assessment. "
        "The template is a laminar/low-Re viscoelastic baseline and must not be used directly to judge turbulent effects."
    )
    if reynolds is not None:
        reason += f" Detected Re≈{reynolds:g}."
    return {
        "field": "physics.turbulence_scope",
        "reason": reason,
        "ask_user": (
            f"检测到 Re 较高或湍流影响诉求。当前{geometry_label} RheoTool 模板是低 Re/层流黏弹性基线，"
            "不能直接用于判断真实湍流影响。请确认：1）保留黏弹性但降级为层流模板探索；"
            "2）忽略黏弹性，转为 V10 Foundation 牛顿湍流通道；3）提供已认证的黏弹性湍流模型/模板；"
            "4）重新提供几何、速度和黏度以复核 Re。"
        ),
        "estimated_re": reynolds,
        "template_candidate": compiled.intent.reproduction_target,
        "options": [
            {
                "id": "rheotool_laminar_exploratory",
                "label": "层流模板探索",
                "description": f"使用 v9-rheotool/rheoFoam {geometry_label}模板，但报告声明不判断真实湍流影响。",
            },
            {
                "id": "v10_newtonian_turbulence",
                "label": "牛顿湍流近似",
                "description": "忽略黏弹性，转为 V10 Foundation 湍流通道问题；需补充牛顿物性和湍流模型。",
            },
            {
                "id": "unsupported_viscoelastic_turbulence",
                "label": "黏弹性湍流",
                "description": "若必须同时考虑黏弹性和湍流，需要已认证模型/模板；当前不自动生成。",
            },
            {
                "id": "recheck_reynolds_number",
                "label": "复核 Re",
                "description": "提供几何、速度、密度和黏度，重新判断是否真的高 Re。",
            },
        ],
    }


def _has_unknown_task_mode(text: str) -> bool:
    lowered = text.lower()
    return bool(
        re.search(r"task[_\s-]*mode\s*[:=：]\s*unknown\b", lowered)
        or re.search(r"任务模式\s*[:=：]\s*(?:unknown|未知|未确认)", lowered)
    )


def _should_clarify_task_mode_first(text: str, compiled) -> bool:
    lowered = text.lower()
    candidates = _template_candidates(lowered, compiled)
    if _has_unknown_task_mode(lowered):
        return bool(candidates)
    if _task_mode(lowered):
        return False
    if str(compiled.intent.reproduction_target or "").startswith("rheotool_"):
        return False
    if compiled.plan.workflow_type in {"certified-benchmark", "rheotool-tutorial-template", "rheotool-tutorial-family"}:
        return False
    if any(term in lowered for term in ("复现", "教程", "tutorial", "benchmark", "rheotool", "user guide")):
        return False
    has_geometry = _has_any(lowered, GEOMETRY_TERMS) and _has_geometry_dimensions(lowered)
    has_flow = _has_any(lowered, FLOW_TERMS)
    has_rheology = (
        compiled.rheology.selected_model is not None
        and not compiled.rheology.missing_parameters
        and not compiled.intent.missing_critical_fields
    )
    nu, rho = _extract_newtonian_properties(text)
    has_complete_newtonian_case = (
        _has_foundation_hint(lowered)
        and has_geometry
        and has_flow
        and nu is not None
        and rho is not None
    )
    if (has_geometry and has_flow and has_rheology) or has_complete_newtonian_case:
        return False
    if has_geometry and has_flow and _has_material_hint(lowered):
        return False
    if compiled.rheology.selected_model is not None:
        return False
    return bool(candidates)


def _task_mode_clarification(compiled, text: str) -> dict[str, Any]:
    suggestions = []
    for candidate in _template_candidates(text, compiled):
        suggestions.append({
            "field": "similar_template_family",
            "suggested": candidate["suggested"],
            "source": candidate["source"],
            "requires_user_confirmation": True,
        })
        suggestions.append({
            "field": "tutorial_template_candidate",
            "suggested": candidate["template_id"],
            "source": candidate["source"],
            "requires_user_confirmation": True,
        })
    return {
        "field": "task.mode",
        "reason": "This is a business-level evaluation request. Foam-Agent must first know whether to inherit a platform baseline, model the user's real device, or run a parameter study.",
        "ask_user": (
            "请先确认任务模式：1）使用平台已有相似案例/教程模板做基线评估（推荐用于快速看趋势）；"
            "2）模拟你的真实设备/真实几何；3）做参数扫描。确认后我再按所选模式处理："
            "平台基线继承已登记模板，真实设备按几何→工况→材料参数澄清，参数扫描先确定基线和覆盖项。"
        ),
        "options": [
            {
                "id": "template_baseline",
                "label": "平台基线模板（推荐）",
                "description": "优先继承已登记模板的几何、网格、边界和参数，用于快速评估趋势。",
            },
            {
                "id": "real_device",
                "label": "真实设备/真实几何",
                "description": "需要继续补充口模尺寸、工况和材料参数，用于更贴近实际设计。",
            },
            {
                "id": "parameter_scan",
                "label": "参数扫描",
                "description": "先确定一个基线，再扫描几何、流量或材料参数对结果的影响。",
            },
        ],
        "infer_with_disclosure": suggestions,
    }


def _parallel_plate_non_template_model_disclosure(compiled) -> dict[str, Any] | None:
    model = compiled.rheology.selected_model
    if compiled.intent.geometry_class != "parallel_plate_channel" or model in {None, "Oldroyd-B"}:
        return None
    return {
        "field": "generalization.constitutive_model",
        "suggested": (
            f"{model} parallel-plate channel is not a registered RheoTool 5.1.3 Case 1 template variant. "
            "The certified Case 1 baseline is Channel/Oldroyd-BLog; using another constitutive model "
            "is a real-geometry/generalization case that must be generated and validated separately."
        ),
        "source": "RheoTool tutorial registry + user_requirement",
        "requires_user_confirmation": False,
    }


def _template_parameter_policy_clarification(template_id: str | None) -> dict[str, Any]:
    return {
        "field": "template.parameter_policy",
        "reason": "A baseline template variant has been selected. Foam-Agent must know whether to keep template-owned physical parameters unchanged or collect user overrides before execution.",
        "ask_user": "请选择参数使用方式：1）使用模板原始参数（推荐，几何/网格/边界/本构参数/工况均继承模板）；2）基于模板原始参数修改部分参数。",
        "template_id": template_id,
        "options": [
            {
                "id": "use_template_originals",
                "label": "使用模板原始参数（推荐）",
                "description": "完整继承模板的几何、网格、边界、工况和本构参数，最快得到可复现基线。",
            },
            {
                "id": "template_with_user_overrides",
                "label": "修改部分参数",
                "description": "先继承模板，再收集你要覆盖的参数和值；覆盖项会在报告中单独披露。",
            },
        ],
    }


def _template_parameter_overrides_clarification(template_id: str | None) -> dict[str, Any]:
    return {
        "field": "template.parameter_overrides",
        "reason": "The user selected partial modification of template parameters, but no concrete override values were provided.",
        "ask_user": "请列出要在模板原始参数基础上修改的参数和值，例如 lambda=1.5、入口平均速度=0.02 m/s、endTime=60。不要修改 solver、patch 名或自定义边界条件。",
        "template_id": template_id,
    }


def _template_parameter_overrides_review(template_id: str | None) -> dict[str, Any]:
    return {
        "field": "template.parameter_overrides_review",
        "reason": "Concrete template parameter overrides were provided. They must be mapped to a supported override whitelist before OpenFOAM dictionaries are modified.",
        "ask_user": "已收到部分参数修改意图。下一步需要由 Foam-Agent 按白名单确认这些覆盖项可安全写入模板字典；当前不会静默执行，以避免参数被忽略或破坏模板一致性。",
        "template_id": template_id,
    }


def _return_single_clarification(result: dict[str, Any], item: dict[str, Any], question: str) -> dict[str, Any]:
    result["status"] = "clarify"
    result["blocking_missing"].append(item)
    result["clarification_questions"].append(question)
    result["defaults_available"].extend([
        {
            "field": "mesh.base_resolution",
            "default": "coarse certified benchmark mesh",
            "disclosure": "初始网格可默认，但发布结论前需要网格无关性检查。",
        },
        {
            "field": "time_control.output_interval",
            "default": "solver-specific tutorial baseline",
            "disclosure": "输出间隔可使用认证基线默认值。",
        },
    ])
    return result


def _extract_named_number(text: str, names: tuple[str, ...]) -> float | None:
    for name in names:
        pattern = rf"(?<![A-Za-z0-9_]){name}\s*[:=]\s*([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _extract_newtonian_properties(text: str) -> tuple[float | None, float | None]:
    nu = _extract_named_number(text, ("nu", "kinematic_viscosity", "kinematic viscosity"))
    rho = _extract_named_number(text, ("rho", "density"))
    return nu, rho


def _extract_velocity(text: str) -> float | None:
    return _extract_named_number(text, ("inlet velocity", "velocity", "U"))


def _extract_characteristic_length(text: str) -> float | None:
    diameter = _extract_named_number(text, ("diameter", "D"))
    if diameter is not None:
        return diameter
    width = _extract_named_number(text, ("width",))
    if width is not None:
        return width
    height = _extract_named_number(text, ("height",))
    if height is not None:
        return height
    radius = _extract_named_number(text, ("radius",))
    if radius is not None:
        return 2.0 * radius
    return None


def _turbulence_treatment(text: str) -> str | None:
    lowered = text.lower()
    turbulent_patterns = (
        r"(?<![a-z0-9_])k[-_ ]?omega(?:[-_ ]?sst)?(?![a-z0-9_])",
        r"(?<![a-z0-9_])k[-_ ]?epsilon(?![a-z0-9_])",
        r"(?<![a-z0-9_])rans(?![a-z0-9_])",
        r"(?<![a-z0-9_])les(?![a-z0-9_])",
    )
    if any(re.search(pattern, lowered) for pattern in turbulent_patterns) or "湍流" in lowered:
        return "turbulent"
    if any(term in lowered for term in ("laminar", "层流")):
        return "laminar"
    if "turbulence" in lowered:
        return "specified"
    return None


def _has_none_required_parameters(text: str) -> bool:
    return bool(re.search(
        r"(?im)^\s*-?\s*parameters\s*:\s*(none required|not required|无需参数|不需要参数)\b",
        text,
    ))


def _is_foundation_newtonian_target(target_preview: dict[str, str] | None) -> bool:
    return bool(target_preview and target_preview.get("solver") in FOUNDATION_SOLVERS)


def _has_geometry_dimensions(text: str) -> bool:
    lowered = text.lower()
    if _has_any(lowered, BENCHMARK_TERMS):
        return True
    dimension_patterns = (
        "diameter", "length", "width", "height", "radius",
        "直径", "长度", "宽度", "高度", "半径",
        "边长", "inlet_width", "outlet_width", "side length",
    )
    return _has_any(lowered, dimension_patterns) and _has_number(lowered)


def _source_authorized(text: str) -> bool:
    lowered = text.lower()
    return (
        _has_any(lowered, PARAMETER_SOURCE_TERMS)
        and _has_any(lowered, SOURCE_TERMS)
        and _has_any(lowered, APPROVAL_TERMS)
    )


def _invalid_rheology_parameter_assignments(text: str, selected_model: str | None) -> tuple[str, ...]:
    if not selected_model:
        return ()
    invalid = []
    for name in MODEL_REQUIREMENTS.get(selected_model, ()):
        for alias in PARAMETER_ALIASES.get(name, (name,)):
            match = re.search(
                rf"(?<![A-Za-z0-9_]){_parameter_name_pattern(alias)}\s*[:=]\s*([^\s,，;；)]+)",
                text,
                re.IGNORECASE,
            )
            if match:
                value = match.group(1)
                if not re.match(rf"^{NUMBER_PATTERN}", value, re.IGNORECASE):
                    invalid.append(name)
                break
    return tuple(dict.fromkeys(invalid))


def evaluate_requirement(requirement_text: str) -> dict[str, Any]:
    compiled = compile_workflow(requirement_text)
    target_preview = _target_preview(compiled)
    text = requirement_text or ""
    result: dict[str, Any] = {
        "status": "ready",
        "intake_version": INTAKE_VERSION,
        "policy_version": POLICY_VERSION,
        "target_preview": target_preview,
        "blocking_missing": [],
        "infer_with_disclosure": [],
        "defaults_available": [],
        "clarification_questions": [],
        "rejection_reason": None,
    }

    unknown_bc = _unknown_custom_boundary_condition(text)
    if unknown_bc:
        result["status"] = "reject"
        result["rejection_reason"] = (
            f"检测到未知边界条件 {unknown_bc}。当前运行环境未注册该 patchField type，"
            "且产品暂不支持自动编译客户自定义 BC。请提供已编译的动态库并由维护者加入运行环境，"
            "或改用当前支持的标准/已内置边界条件。"
        )
        result["blocking_missing"].append({
            "field": "boundary_condition.custom_patch_type",
            "reason": "Unknown customer custom boundary condition is outside the automatic generation/compilation capability.",
            "ask_user": result["rejection_reason"],
            "patch_type": unknown_bc,
        })
        return result

    if compiled.plan.rejection_reason:
        result["status"] = "reject"
        result["rejection_reason"] = compiled.plan.rejection_reason
        return result

    certified_benchmark = compiled.plan.workflow_type == "certified-benchmark"
    family_match = _template_family_match(compiled.intent.reproduction_target)
    rheotool_tutorial = (
        str(compiled.intent.reproduction_target or "").startswith("rheotool_")
        and family_match is None
    )
    foundation_tutorial = compiled.intent.reproduction_target in FOUNDATION_TUTORIAL_TARGET_SOLVERS
    tutorial_template = rheotool_tutorial or foundation_tutorial

    obstacle_mismatch = _obstacle_shape_mismatch(text, compiled)
    if obstacle_mismatch:
        result["infer_with_disclosure"].append({
            "field": "rheotool_tutorial_template_candidate",
            "suggested": "rheotool_5_1_6_cylinder_oldroydb_log",
            "source": "RheoTool tutorial registry",
            "requires_user_confirmation": True,
        })
        return _return_single_clarification(
            result,
            obstacle_mismatch,
            "检测到障碍物形状与已登记圆柱绕流模板不一致；请确认用圆柱模板近似、生成真实几何，或提供对应模板。",
        )

    topology_mismatch = _cross_slot_topology_mismatch(text, compiled)
    if topology_mismatch:
        result["infer_with_disclosure"].append({
            "field": "rheotool_tutorial_template_candidate",
            "suggested": "rheotool_5_1_7_crossslot_oldroydb_log",
            "source": "RheoTool tutorial registry",
            "requires_user_confirmation": True,
        })
        return _return_single_clarification(
            result,
            topology_mismatch,
            "检测到流道拓扑与已登记 CrossSlot 模板不一致；请确认用 CrossSlot 模板近似、生成真实几何，或提供对应模板。",
        )

    ratio_mismatch = _contraction_ratio_mismatch(text, compiled)
    if ratio_mismatch:
        result["infer_with_disclosure"].append({
            "field": "rheotool_tutorial_template_candidate",
            "suggested": "rheotool_5_1_5_contraction41_oldroydb_log",
            "source": "RheoTool tutorial registry",
            "requires_user_confirmation": True,
        })
        return _return_single_clarification(
            result,
            ratio_mismatch,
            "检测到收缩比与已登记 4:1 Contraction41 模板不一致；请确认用 4:1 模板近似、生成真实几何，或提供对应模板。",
        )

    turbulence_scope = _needs_turbulence_scope_clarification(text, compiled, rheotool_tutorial=rheotool_tutorial)
    if turbulence_scope:
        result["infer_with_disclosure"].append({
            "field": "rheotool_tutorial_template_candidate",
            "suggested": compiled.intent.reproduction_target,
            "source": "RheoTool tutorial registry",
            "requires_user_confirmation": True,
        })
        return _return_single_clarification(
            result,
            turbulence_scope,
            "检测到高 Re / 湍流影响诉求；请先确认是否按层流模板探索、转牛顿湍流近似、提供黏弹性湍流模板，或复核 Re。",
        )

    if _should_clarify_task_mode_first(text, compiled):
        item = _task_mode_clarification(compiled, text)
        result["infer_with_disclosure"].extend(item.pop("infer_with_disclosure", []))
        return _return_single_clarification(
            result,
            item,
            "请先确认任务模式：平台基线模板、真实设备/真实几何，还是参数扫描？",
        )

    if certified_benchmark:
        result["benchmark_match"] = {
            "workflow_type": "certified-benchmark",
            "target": target_preview,
            "disclosure": "Matched a local certified benchmark from knowledge/benchmarks; geometry, flow conditions, constitutive parameters, and numerics are supplied by the benchmark metadata/case files.",
        }
        result["infer_with_disclosure"].append({
            "field": "certified_benchmark",
            "suggested": "Use local certified benchmark case files instead of browsing the web or regenerating dictionaries from scratch.",
            "source": "knowledge/benchmarks",
            "requires_user_confirmation": False,
        })
    if tutorial_template:
        result["template_match"] = {
            "workflow_type": compiled.plan.workflow_type,
            "template_id": compiled.intent.reproduction_target,
            "target": target_preview,
            "disclosure": "Matched an explicit tutorial/template target; geometry, boundary conditions, physical parameters, solver, and numerics are supplied by the template files.",
        }
        result["infer_with_disclosure"].append({
            "field": "tutorial_template",
            "suggested": "Use local tutorial/template case files instead of asking the user to restate template-owned OpenFOAM dictionaries.",
            "source": compiled.intent.reproduction_target,
            "requires_user_confirmation": False,
        })
        if _task_mode(text) == "parameter_scan":
            result["parameter_policy"] = {
                "mode": "template_with_user_overrides",
                "template_id": compiled.intent.reproduction_target,
            }
            if not _has_template_override_values_for_template(text, compiled.intent.reproduction_target, compiled):
                return _return_single_clarification(
                    result,
                    _template_parameter_overrides_clarification(compiled.intent.reproduction_target),
                    "请列出要在模板原始参数基础上扫描/修改的参数和值。",
                )
            return _return_single_clarification(
                result,
                _template_parameter_overrides_review(compiled.intent.reproduction_target),
                "已收到参数扫描/部分修改意图；需要先确认覆盖项在模板参数白名单内，避免被忽略或破坏模板一致性。",
            )
        if _template_baseline_requested(text):
            parameter_policy = _template_parameter_policy(text)
            if parameter_policy is None and _has_template_override_values_for_template(text, compiled.intent.reproduction_target, compiled):
                parameter_policy = "template_with_user_overrides"
            result["parameter_policy"] = {
                "mode": parameter_policy or "unknown",
                "template_id": compiled.intent.reproduction_target,
            }
            if parameter_policy is None:
                return _return_single_clarification(
                    result,
                    _template_parameter_policy_clarification(compiled.intent.reproduction_target),
                    "请选择参数使用方式：使用模板原始参数，还是基于模板原始参数修改部分参数？",
                )
            if parameter_policy == "template_with_user_overrides" and not _has_template_override_values_for_template(text, compiled.intent.reproduction_target, compiled):
                return _return_single_clarification(
                    result,
                    _template_parameter_overrides_clarification(compiled.intent.reproduction_target),
                    "请列出要在模板原始参数基础上修改的参数和值。",
                )
            if parameter_policy == "template_with_user_overrides":
                return _return_single_clarification(
                    result,
                    _template_parameter_overrides_review(compiled.intent.reproduction_target),
                    "已收到部分参数修改意图；需要先确认覆盖项在模板参数白名单内，避免被忽略或破坏模板一致性。",
                )
            result["infer_with_disclosure"].append({
                "field": "template.parameter_policy",
                "suggested": parameter_policy,
                "source": "user_requirement",
                "requires_user_confirmation": False,
            })
        if (
            compiled.intent.reproduction_target == "rheotool_5_1_7_crossslot_oldroydb_log"
            and "parameter_policy" not in result
        ):
            lowered = text.lower()
            result["parameter_policy"] = {
                "mode": "unknown",
                "template_id": compiled.intent.reproduction_target,
            }
            explicit_tutorial_section = any(
                term in lowered
                for term in ("tutorial", "user guide", "section", "教程")
            )
            if explicit_tutorial_section and _has_canonical_dimensionless_signature(compiled.intent.reproduction_target, compiled):
                result["parameter_policy"]["mode"] = "use_template_originals"
                result["infer_with_disclosure"].append({
                    "field": "template.parameter_policy",
                    "suggested": "use_template_originals",
                    "source": "canonical_dimensionless_signature",
                    "requires_user_confirmation": False,
                })
                return result
            if any(term in lowered for term in ("rheotool", "5.1.7", "benchmark", "教程", "user guide")):
                return _return_single_clarification(
                    result,
                    _template_parameter_policy_clarification(compiled.intent.reproduction_target),
                    "请选择参数使用方式：使用模板原始参数，还是基于模板原始参数修改部分参数？",
                )
            if _has_template_override_values_for_template(text, compiled.intent.reproduction_target, compiled):
                result["parameter_policy"]["mode"] = "template_with_user_overrides"
                return _return_single_clarification(
                    result,
                    _template_parameter_overrides_review(compiled.intent.reproduction_target),
                    "已收到部分参数修改意图；需要先确认覆盖项在模板参数白名单内，避免被忽略或破坏模板一致性。",
                )
            return _return_single_clarification(
                result,
                _template_parameter_policy_clarification(compiled.intent.reproduction_target),
                "请选择参数使用方式：使用模板原始参数，还是基于模板原始参数修改部分参数？",
            )
        if foundation_tutorial and "parameter_policy" not in result:
            result["parameter_policy"] = {
                "mode": "use_template_originals" if str(compiled.intent.reproduction_target or "").endswith("_full_allrun") else "unknown",
                "template_id": compiled.intent.reproduction_target,
            }
            if result["parameter_policy"]["mode"] == "use_template_originals":
                result["infer_with_disclosure"].append({
                    "field": "template.parameter_policy",
                    "suggested": "use_template_originals",
                    "source": "official_full_allrun_scope",
                    "requires_user_confirmation": False,
                })
                return result
            return _return_single_clarification(
                result,
                _template_parameter_policy_clarification(compiled.intent.reproduction_target),
                "请选择参数使用方式：使用模板原始参数，还是基于模板原始参数修改部分参数？",
            )
    if family_match:
        result["status"] = "clarify"
        result["template_family_match"] = family_match
        clarification = template_family_clarification(compiled.intent.reproduction_target)
        if clarification is None:
            return result
        result["blocking_missing"].append({
            "field": clarification["blocking_field"],
            "reason": clarification["reason"],
            "ask_user": clarification["ask_user"],
            "children": clarification["children"],
        })
        result["clarification_questions"].append(clarification["question"])
        result["infer_with_disclosure"].append({
            "field": clarification["infer_field"],
            "suggested": clarification["infer_suggested"],
            "source": clarification["source"],
            "requires_user_confirmation": True,
        })
        result["defaults_available"].extend([
            {
                "field": "mesh.base_resolution",
                "default": "solver-specific tutorial baseline",
                "disclosure": "子模板选定后继承教程网格；发布结论前需要网格无关性检查。",
            },
            {
                "field": "time_control.output_interval",
                "default": "solver-specific tutorial baseline",
                "disclosure": "子模板选定后继承教程输出间隔。",
            },
        ])
        return result

    mode = _task_mode(text)
    if mode == "real_device" and not certified_benchmark and not tutorial_template:
        if not (_has_any(text, GEOMETRY_TERMS) and _has_geometry_dimensions(text)):
            return _return_single_clarification(
                result,
                {
                    "field": "geometry.dimensions",
                    "reason": "The user selected real-device modeling; real geometry must be fixed before flow and material parameters are actionable.",
                    "ask_user": "请先提供真实几何的关键尺寸（例如口模狭缝高度/宽度、出口后计算长度、对称/二维假设）。",
                },
                "请先提供真实几何的关键尺寸。",
            )
        material_test = _has_any(text, MATERIAL_TEST_TERMS)
        if not material_test and not _has_any(text, FLOW_TERMS):
            return _return_single_clarification(
                result,
                {
                    "field": "flow.boundary_condition",
                    "reason": "Real geometry is available; the next critical input is the operating condition.",
                    "ask_user": "请提供入口速度、体积流量、质量流量、压差/压降或等效工况之一。",
                },
                "请提供入口速度、流量、压差/压降或等效工况。",
            )

    non_template_model = _parallel_plate_non_template_model_disclosure(compiled)
    if non_template_model and not certified_benchmark and not tutorial_template:
        result["infer_with_disclosure"].append(non_template_model)

    explicit_constitutive_model = compiled.rheology.selected_model is not None
    invalid_rheology_parameters = _invalid_rheology_parameter_assignments(
        text,
        compiled.rheology.selected_model,
    )
    if explicit_constitutive_model:
        result["material_card"] = {
            "material": None,
            "source": None,
            "reason": "explicit_constitutive_model; material-card lookup not required for model-fluid/benchmark input.",
        }
    else:
        material_card = match_material_card(text)
        if material_card:
            result["material_card"] = {
                "material": material_card.get("material"),
                "source": material_card.get("_path"),
            }
            if material_card.get("likely_behavior"):
                result["infer_with_disclosure"].append({
                    "field": "rheology.behavior",
                    "suggested": material_card.get("likely_behavior"),
                    "source": material_card.get("_path"),
                    "requires_user_confirmation": True,
                })
        elif _has_material_hint(text):
            result["status"] = "clarify"
            result["blocking_missing"].append({
                "field": "material.behavior",
                "reason": "Material is not covered by the current material card library.",
                "ask_user": "请从流动现象角度补充该材料是否牛顿、剪切变稀、屈服、回弹或拉丝。",
            })
            result["clarification_questions"].extend(unknown_material_questions())

    if invalid_rheology_parameters:
        result["status"] = "clarify"
        result["blocking_missing"].append({
            "field": "rheology.parameters_format",
            "reason": "Constitutive parameter assignments were found but their values are not numeric.",
            "ask_user": "请用数值格式提供本构参数，例如 etaS=0.01 etaP=0.99 lambda=1.0。",
            "invalid": list(invalid_rheology_parameters),
        })

    if not certified_benchmark and not tutorial_template and not (_has_any(text, GEOMETRY_TERMS) and _has_geometry_dimensions(text)):
        result["status"] = "clarify"
        result["blocking_missing"].append({
            "field": "geometry.dimensions",
            "reason": "Geometry dimensions or an explicit certified benchmark geometry are required before running OpenFOAM.",
            "ask_user": "请提供几何类型和关键尺寸；如果要用认证基准几何，请明确说明。",
        })

    material_test = _has_any(text, MATERIAL_TEST_TERMS)
    if not certified_benchmark and not tutorial_template and not material_test and not _has_any(text, FLOW_TERMS):
        result["status"] = "clarify"
        result["blocking_missing"].append({
            "field": "flow.boundary_condition",
            "reason": "A runnable flow case needs inlet velocity, flow rate, pressure drop, or equivalent operating condition.",
            "ask_user": "请提供入口速度、流量、压差/压降或等效工况。",
        })

    if _has_none_required_parameters(text):
        result["status"] = "clarify"
        result["blocking_missing"].append({
            "field": "fluid.properties",
            "reason": "Newtonian fluids still require physical properties; 'parameters: none required' is not allowed.",
            "ask_user": "请提供 nu 和 rho，并标注来源；例如水在 20°C 的标准物性需标为 literature_typical 或经用户确认。",
        })

    if _is_foundation_newtonian_target(target_preview) and not foundation_tutorial:
        nu, rho = _extract_newtonian_properties(text)
        if nu is None or rho is None:
            result["status"] = "clarify"
            result["blocking_missing"].append({
                "field": "fluid.properties",
                "reason": "Foundation-channel Newtonian workflows require kinematic viscosity nu and density rho.",
                "ask_user": "请提供运动黏度 nu 和密度 rho，并说明是用户提供、文献典型值还是经用户授权的估计值。",
                "missing": [name for name, value in (("nu", nu), ("rho", rho)) if value is None],
            })
        velocity = _extract_velocity(text)
        length = _extract_characteristic_length(text)
        if nu and velocity is not None and length is not None:
            reynolds = velocity * length / nu
            treatment = _turbulence_treatment(text)
            if reynolds > REYNOLDS_THRESHOLD and treatment != "turbulent":
                result["status"] = "clarify"
                result["blocking_missing"].append({
                    "field": "physics.reynolds_number",
                    "reason": f"Estimated Re={reynolds:.3g} exceeds the laminar pipe/channel threshold {REYNOLDS_THRESHOLD:.0f}.",
                    "ask_user": "该工况可能为湍流；请确认是否采用已认证的湍流处理，或调整速度/尺寸/物性使其处于层流范围。",
                    "estimated_re": reynolds,
                })

    missing_rheology_parameters = tuple(
        name for name in compiled.rheology.missing_parameters
        if name not in invalid_rheology_parameters
    )
    if not certified_benchmark and not tutorial_template and missing_rheology_parameters and not _source_authorized(text):
        result["status"] = "clarify"
        result["blocking_missing"].append({
            "field": "rheology.parameters",
            "reason": "Constitutive parameters are required unless typical values are explicitly authorized and sourced.",
            "ask_user": "请提供本构参数，或明确授权使用有来源的典型值。",
            "missing": list(missing_rheology_parameters),
        })

    for field in compiled.intent.missing_critical_fields:
        result["status"] = "clarify"
        result["blocking_missing"].append({
            "field": field,
            "reason": "Foam-Agent needs this field to compile a certified workflow.",
            "ask_user": "请用业务语言补充该信息；不需要直接选择 OpenFOAM solver。",
        })

    for question in compiled.plan.clarification_questions:
        if invalid_rheology_parameters and question.startswith("请提供本构参数"):
            continue
        if question not in result["clarification_questions"]:
            result["clarification_questions"].append(question)

    result["defaults_available"].extend([
        {
            "field": "mesh.base_resolution",
            "default": "coarse certified benchmark mesh",
            "disclosure": "初始网格可默认，但发布结论前需要网格无关性检查。",
        },
        {
            "field": "time_control.output_interval",
            "default": "solver-specific tutorial baseline",
            "disclosure": "输出间隔可使用认证基线默认值。",
        },
    ])

    if result["blocking_missing"] or result["clarification_questions"]:
        result["status"] = "clarify"
    elif target_preview is None:
        result["status"] = "clarify"
        result["clarification_questions"].append("请补充该问题是稳态、瞬态还是自由液面/两相。")

    return result


def issue_receipt(requirement_path: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(requirement_path)
    text = path.read_text(encoding="utf-8")
    evaluation = evaluate_requirement(text)
    if evaluation["status"] != "ready":
        raise ValueError("INTAKE_NOT_READY: cannot issue receipt unless status is ready")
    receipt = {
        "status": "ready",
        "requirement_sha256": requirement_hash(text),
        "target_preview": evaluation["target_preview"],
        "intake_version": INTAKE_VERSION,
        "policy_version": POLICY_VERSION,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "unstamped_override": False,
    }
    out = Path(output_path) if output_path else receipt_path_for(path)
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    receipt["receipt_path"] = str(out)
    return receipt


def validate_receipt(requirement_path: str | Path, receipt_path: str | Path | None = None) -> dict[str, Any]:
    req_path = Path(requirement_path)
    rcpt_path = Path(receipt_path) if receipt_path else receipt_path_for(req_path)
    if not rcpt_path.is_file():
        raise ValueError(
            "INTAKE_RECEIPT_MISSING: run scripts/foamagent_intake.py --write-receipt before src/main.py"
        )
    text = req_path.read_text(encoding="utf-8")
    receipt = json.loads(rcpt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "ready":
        raise ValueError("INTAKE_RECEIPT_NOT_READY: receipt status must be ready")
    if receipt.get("requirement_sha256") != requirement_hash(text):
        raise ValueError("INTAKE_RECEIPT_HASH_MISMATCH: user_requirement.txt changed after intake")
    compiled = compile_workflow(text)
    target = _target_preview(compiled)
    if receipt.get("target_preview") != target:
        raise ValueError("INTAKE_RECEIPT_TARGET_MISMATCH: receipt target differs from current compile_workflow target")
    return receipt


def allow_unstamped_override() -> bool:
    return bool(os.environ.get("FOAMAGENT_DEV_ALLOW_UNSTAMPED"))
