from __future__ import annotations

from typing import Any


TEMPLATE_FAMILIES: dict[str, dict[str, Any]] = {
    "rheotool_5_3_3_dieswell_family": {
        "workflow_type": "rheotool-tutorial-family",
        "blocking_field": "tutorial.variant",
        "reason": "Matched a RheoTool tutorial family with multiple executable constitutive variants.",
        "question_prefix": "请选择要复现的 DieSwell 教程本构变体",
        "ask_suffix": "几何、网格、边界条件、参数和求解器将由所选教程模板继承。",
        "disclosure": (
            "Matched a RheoTool tutorial family. Select one constitutive variant; "
            "geometry, mesh, boundary conditions, parameters, solver, and numerics "
            "will be inherited from the selected child template."
        ),
        "infer_field": "rheotool_tutorial_family",
        "infer_suggested": (
            "Select a constitutive variant instead of restating template-owned geometry, "
            "flow conditions, or constitutive parameters."
        ),
        "source": "RheoTool tutorial registry",
        "children": (
            {
                "template_id": "rheotool_5_3_3_dieswell_oldroydb_log",
                "label": "Oldroyd-BLog",
                "recommended": True,
                "description": "推荐：标准粘弹性 DieSwell 教程变体，log-conformation Oldroyd-B，适合一般复现。",
            },
            {
                "template_id": "rheotool_5_3_3_dieswell_giesekuslog",
                "label": "GiesekusLog",
                "recommended": False,
                "description": "Giesekus 非线性粘弹性变体，适合复现该本构模型下的自由液面胀大。",
            },
            {
                "template_id": "rheotool_5_3_3_dieswell_carreauyasuda",
                "label": "CarreauYasuda",
                "recommended": False,
                "description": "广义牛顿剪切变稀变体，适合关注剪切变稀黏度而非弹性应力的教程复现。",
            },
        ),
    },
    "foundation_v10_icofoam_cavity_family": {
        "workflow_type": "foundation-tutorial-family",
        "blocking_field": "template.scope",
        "reason": "Matched a Foundation tutorial family with multiple cavity variants/execution scopes.",
        "question_prefix": "请选择要运行的 OpenFOAM v10 cavity 教程范围",
        "ask_suffix": "所选范围决定是否只跑基础 baseline、是否包含高 Re、网格变体或 mapFields 完整教程链路。",
        "disclosure": (
            "Matched an OpenFOAM Foundation tutorial family. Select an execution scope; "
            "the selected child template or tutorial-chain owns geometry, mesh, boundary "
            "conditions, physical parameters, solver, and numerics."
        ),
        "infer_field": "foundation_tutorial_family",
        "infer_suggested": (
            "Select a cavity tutorial scope/variant before executing; do not silently collapse "
            "a family request into the base cavity case."
        ),
        "source": "Foundation v10 tutorial registry",
        "children": (
            {
                "template_id": "foundation_v10_icofoam_cavity",
                "label": "基础 baseline",
                "recommended": True,
                "description": "只运行官方 icoFoam/cavity/cavity 基础子模板，适合快速查看主涡和中心线速度。",
            },
            {
                "template_id": "foundation_v10_icofoam_cavity_fine",
                "label": "细网格",
                "recommended": False,
                "description": "运行 cavityFine，用于更细网格下的结果对比；需要后续登记执行模板。",
            },
            {
                "template_id": "foundation_v10_icofoam_cavity_grade",
                "label": "渐变网格",
                "recommended": False,
                "description": "运行 cavityGrade，用于评估 graded mesh 对结果的影响；需要后续登记执行模板。",
            },
            {
                "template_id": "foundation_v10_icofoam_cavity_highre",
                "label": "高 Re 变体",
                "recommended": False,
                "description": "运行 cavityHighRe，用于观察高 Re/二级涡；可能依赖基础结果映射。",
            },
            {
                "template_id": "foundation_v10_icofoam_cavity_clipped",
                "label": "clipped/mapFields",
                "recommended": False,
                "description": "运行 cavityClipped，用于几何裁剪和 mapFields 演示；需要教程链路支持。",
            },
            {
                "template_id": "foundation_v10_icofoam_cavity_full_allrun",
                "label": "完整官方教程族",
                "recommended": False,
                "description": "执行父目录 Allrun，包含多个子 case 和 mapFields；属于多 case 教程链路。",
            },
        ),
    },
    "foundation_v10_pitzdaily_family": {
        "workflow_type": "foundation-tutorial-family",
        "blocking_field": "template.scope",
        "reason": "Matched a Foundation pitzDaily/backward-facing-step tutorial family with multiple solver/physics scopes.",
        "question_prefix": "请选择要运行的 OpenFOAM v10 pitzDaily / backward-facing step 教程变体",
        "ask_suffix": "所选变体决定使用稳态不可压缩、瞬态/RAS、LES、势流、标量输运或可压缩教程；不会静默折叠为基础 simpleFoam case。",
        "disclosure": (
            "Matched an OpenFOAM Foundation pitzDaily tutorial family. Select a solver/physics "
            "scope before execution; only registered executable child templates may run automatically."
        ),
        "infer_field": "foundation_tutorial_family",
        "infer_suggested": (
            "Select a pitzDaily solver/physics scope before executing; do not silently collapse "
            "the tutorial family into the steady simpleFoam baseline."
        ),
        "source": "Foundation v10 tutorial registry",
        "children": (
            {
                "template_id": "foundation_v10_simplefoam_pitzdaily",
                "label": "steady incompressible simpleFoam baseline",
                "recommended": True,
                "description": "推荐：已登记并验证的稳态不可压缩 simpleFoam/pitzDaily 后向台阶 baseline。",
            },
            {
                "template_id": "foundation_v10_pimplefoam_ras_pitzdaily",
                "label": "transient incompressible pimpleFoam/RAS",
                "recommended": False,
                "description": "瞬态不可压缩 RAS 变体；已登记 Foundation v10 pimpleFoam/pitzDaily 执行模板。",
            },
            {
                "template_id": "foundation_v10_pisofoam_les_pitzdaily",
                "label": "LES/pisoFoam",
                "recommended": False,
                "description": "LES 教程变体；已登记 Foundation v10 pisoFoam/LES/pitzDaily 执行模板，真实运行耗时明显长于 baseline。",
            },
            {
                "template_id": "foundation_v10_potentialfoam_pitzdaily",
                "label": "potentialFoam",
                "recommended": False,
                "description": "势流基础教程变体；已登记 Foundation v10 potentialFoam/pitzDaily 执行模板，但物理上不能替代黏性后向台阶求解。",
            },
            {
                "template_id": "foundation_v10_scalartransport_pitzdaily",
                "label": "scalarTransportFoam",
                "recommended": False,
                "description": "标量输运教程变体；已登记 Foundation v10 scalarTransportFoam/pitzDaily 执行模板。",
            },
            {
                "template_id": "foundation_v10_compressible_pitzdaily",
                "label": "compressible pitzDaily",
                "recommended": False,
                "description": "可压缩 pitzDaily 变体；当前 Foundation 可压缩求解器不在认证矩阵内，选择后应明确能力边界。",
            },
        ),
    },
    "foundation_v10_dambreak_family": {
        "workflow_type": "foundation-tutorial-family",
        "blocking_field": "template.scope",
        "reason": "Matched a Foundation damBreak tutorial family with multiple free-surface variants/execution scopes.",
        "question_prefix": "请选择要运行的 OpenFOAM v10 damBreak / 破坝/溃坝教程变体",
        "ask_suffix": "所选变体决定使用基础层流、完整 fine 网格链路、障碍物、RAS 湍流、porous baffle 或多相/可压缩能力边界。",
        "disclosure": (
            "Matched an OpenFOAM Foundation damBreak tutorial family. Select a free-surface "
            "variant before execution; only registered interFoam child templates may run automatically."
        ),
        "infer_field": "foundation_tutorial_family",
        "infer_suggested": (
            "Select a damBreak variant/scope before executing; do not silently collapse "
            "the family into the laminar interFoam baseline."
        ),
        "source": "Foundation v10 tutorial registry",
        "children": (
            {
                "template_id": "foundation_v10_interfoam_dambreak",
                "label": "laminar interFoam baseline",
                "recommended": True,
                "description": "推荐：已登记并验证的两相层流 interFoam/damBreak baseline。",
            },
            {
                "template_id": "foundation_v10_interfoam_dambreak_laminar_full_allrun",
                "label": "laminar full_allrun",
                "recommended": False,
                "description": "运行官方父目录 Allrun，包含 damBreak 与克隆生成的 damBreakFine fine 网格链路。",
            },
            {
                "template_id": "foundation_v10_interfoam_dambreak_with_obstacle",
                "label": "laminar with obstacle",
                "recommended": False,
                "description": "层流破坝带障碍物变体，执行 blockMesh、topoSet、subsetMesh、setFields 和 interFoam；含动态/自适应网格，真实运行耗时较长。",
            },
            {
                "template_id": "foundation_v10_interfoam_ras_dambreak",
                "label": "RAS interFoam baseline",
                "recommended": False,
                "description": "RAS 湍流 interFoam/damBreak baseline，适合比较湍流自由液面设置。",
            },
            {
                "template_id": "foundation_v10_interfoam_ras_dambreak_full_allrun",
                "label": "RAS full_allrun",
                "recommended": False,
                "description": "运行 RAS 父目录 Allrun，包含 damBreak 与 damBreakFine 并行重构链路。",
            },
            {
                "template_id": "foundation_v10_interfoam_ras_dambreak_porous_baffle",
                "label": "RAS porous baffle",
                "recommended": False,
                "description": "RAS 破坝 porous baffle 变体，执行 createBaffles 后运行 interFoam。",
            },
            {
                "template_id": "foundation_v10_intermixingfoam_dambreak_unsupported",
                "label": "interMixingFoam multi-liquid",
                "recommended": False,
                "description": "三相混合破坝教程；interMixingFoam 当前不在认证矩阵内，选择后应明确能力边界。",
            },
            {
                "template_id": "foundation_v10_multiphase_dambreak4phase_unsupported",
                "label": "4-phase multiphase",
                "recommended": False,
                "description": "四相 multiphaseInterFoam/multiphaseEulerFoam 教程；当前不在认证矩阵内。",
            },
            {
                "template_id": "foundation_v10_compressible_dambreak_unsupported",
                "label": "compressible damBreak",
                "recommended": False,
                "description": "可压缩 damBreak 变体；当前 Foundation 可压缩求解器不在认证矩阵内。",
            },
        ),
    },
    "foundation_v10_cylinder_family": {
        "workflow_type": "foundation-tutorial-family",
        "blocking_field": "template.scope",
        "reason": "Matched a Foundation cylinder tutorial family with multiple solver/physics scopes.",
        "question_prefix": "请选择要运行的 OpenFOAM v10 cylinder / 圆柱教程变体",
        "ask_suffix": "所选变体决定使用势流圆柱、不可压缩 offsetCylinder、自由液面 sloshingCylinder 或可压缩能力边界。",
        "disclosure": (
            "Matched an OpenFOAM Foundation cylinder tutorial family. Select a cylinder "
            "variant before execution; only registered potentialFoam/pimpleFoam/interFoam "
            "child templates may run automatically."
        ),
        "infer_field": "foundation_tutorial_family",
        "infer_suggested": (
            "Select a cylinder tutorial variant before executing; do not silently collapse "
            "the family into a generic cylinder flow case."
        ),
        "source": "Foundation v10 tutorial registry",
        "children": (
            {
                "template_id": "foundation_v10_potentialfoam_cylinder",
                "label": "potentialFoam cylinder（推荐）",
                "recommended": True,
                "description": "推荐：基础势流圆柱教程，运行 blockMesh、potentialFoam 和 streamFunction 后处理。",
            },
            {
                "template_id": "foundation_v10_pimplefoam_laminar_offsetcylinder",
                "label": "pimpleFoam laminar offsetCylinder",
                "recommended": False,
                "description": "不可压缩瞬态层流 offsetCylinder 变体，适合圆柱绕流/尾迹类基础测试。",
            },
            {
                "template_id": "foundation_v10_interfoam_laminar_sloshingcylinder",
                "label": "interFoam sloshingCylinder",
                "recommended": False,
                "description": "两相自由液面 sloshingCylinder 变体，执行 snappyHexMesh、setFields 和 interFoam。",
            },
            {
                "template_id": "foundation_v10_compressible_cylinder_unsupported",
                "label": "compressibleInterFoam cylinder",
                "recommended": False,
                "description": "可压缩/喷雾/燃烧相关 cylinder 教程；当前 Foundation 可压缩求解器不在认证矩阵内。",
            },
        ),
    },
    "foundation_v10_forwardstep_family": {
        "workflow_type": "foundation-tutorial-family",
        "blocking_field": "template.scope",
        "reason": "Matched a Foundation forwardStep tutorial family with multiple compressible solver scopes.",
        "question_prefix": "请选择要运行的 OpenFOAM v10 forwardStep / 前向台阶可压缩教程变体",
        "ask_suffix": "所选变体决定使用 rhoCentralFoam 高速可压缩显式教程，或 rhoPimpleFoam 层流瞬态可压缩教程。",
        "disclosure": (
            "Matched an OpenFOAM Foundation compressible forwardStep tutorial family. "
            "Select a solver scope before execution; registered child templates inherit "
            "the official geometry, mesh, thermophysical properties, boundary conditions, and numerics."
        ),
        "infer_field": "foundation_tutorial_family",
        "infer_suggested": (
            "Select a forwardStep compressible solver scope before executing; do not silently "
            "collapse the family into another incompressible step-flow template."
        ),
        "source": "Foundation v10 tutorial registry",
        "children": (
            {
                "template_id": "foundation_v10_rhocentralfoam_forwardstep",
                "label": "rhoCentralFoam forwardStep（推荐）",
                "recommended": True,
                "description": "推荐：官方高速可压缩 forwardStep 教程，适合测试激波/膨胀波类基础能力。",
            },
            {
                "template_id": "foundation_v10_rhopimplefoam_laminar_forwardstep",
                "label": "rhoPimpleFoam laminar forwardStep",
                "recommended": False,
                "description": "层流瞬态可压缩 forwardStep 教程，适合测试 PIMPLE 型可压缩瞬态流程。",
            },
        ),
    },
}


def template_family_child_ids(family_id: str) -> tuple[str, ...]:
    family = TEMPLATE_FAMILIES.get(family_id)
    if not family:
        return ()
    return tuple(str(child["template_id"]) for child in family["children"])


def template_family_match_payload(family_id: str) -> dict[str, Any] | None:
    family = TEMPLATE_FAMILIES.get(family_id)
    if not family:
        return None
    children = [dict(child) for child in family["children"]]
    return {
        "workflow_type": family["workflow_type"],
        "template_id": family_id,
        "children": children,
        "disclosure": family["disclosure"],
    }


def template_family_clarification(family_id: str) -> dict[str, Any] | None:
    family = TEMPLATE_FAMILIES.get(family_id)
    if not family:
        return None
    children = [dict(child) for child in family["children"]]
    variants = " / ".join(
        f"{child['label']}（推荐）" if child.get("recommended") else child["label"]
        for child in children
    )
    return {
        "blocking_field": family["blocking_field"],
        "reason": family["reason"],
        "ask_user": f"{family['question_prefix']}：{variants}。{family['ask_suffix']}",
        "question": f"{family['question_prefix']}：{variants}。",
        "children": children,
        "infer_field": family["infer_field"],
        "infer_suggested": family["infer_suggested"],
        "source": family["source"],
    }
