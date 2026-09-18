from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.intake import evaluate_requirement, issue_receipt, validate_receipt  # noqa: E402


def test_complete_water_pipe_requirement_is_ready(tmp_path):
    text = "水在管道中的稳态压降 geometry pipe diameter=0.01 length=1 inlet velocity=0.001 nu=1e-6 rho=1000 property source: literature_typical source reference: standard water properties at 20C user approved"
    result = evaluate_requirement(text)
    assert result["status"] == "ready"
    assert result["target_preview"]["solver"] == "simpleFoam"


def test_missing_geometry_requires_clarification():
    result = evaluate_requirement("水在管道中的稳态压降 inlet velocity=1")
    assert result["status"] == "clarify"
    assert any(item["field"] == "geometry.dimensions" for item in result["blocking_missing"])


def test_missing_flow_condition_requires_clarification():
    result = evaluate_requirement("水在管道中的稳态流动 geometry pipe diameter=0.1 length=1")
    assert result["status"] == "clarify"
    assert any(item["field"] == "flow.boundary_condition" for item in result["blocking_missing"])


def test_missing_rheology_parameters_requires_clarification():
    result = evaluate_requirement(
        "Oldroyd-B polymer solution steady flow geometry contraction die width=1 length=10 inlet velocity=0.1"
    )
    assert result["status"] == "clarify"
    assert any(item["field"] == "rheology.parameters" for item in result["blocking_missing"])


def test_typical_parameter_authorization_without_source_is_not_enough():
    result = evaluate_requirement(
        "Oldroyd-B polymer solution steady flow geometry contraction die width=1 length=10 inlet velocity=0.1 "
        "parameter source: literature_typical user approved"
    )
    assert result["status"] == "clarify"
    assert any(item["field"] == "rheology.parameters" for item in result["blocking_missing"])


def test_unsupported_physics_is_rejected():
    result = evaluate_requirement("可压缩燃烧传热模拟 geometry chamber diameter=1 inlet velocity=1")
    assert result["status"] == "reject"
    assert result["rejection_reason"]


def test_unknown_material_clarifies_instead_of_rejecting():
    result = evaluate_requirement("某种新型凝胶 稳态流动 geometry pipe diameter=0.1 length=1 inlet velocity=1")
    assert result["status"] == "clarify"
    assert result["rejection_reason"] is None
    assert any(item["field"] == "material.behavior" for item in result["blocking_missing"])


def test_explicit_model_with_complete_parameters_skips_unknown_material_card():
    result = evaluate_requirement(
        "Oldroyd-B 新型凝胶稳态流动 geometry channel width=1 length=40 inlet velocity=1 "
        "etaS=0.01 etaP=0.99 lambda=1.0 parameter source: user_provided source reference: user prompt user approved"
    )

    assert result["status"] == "ready"
    assert result["target_preview"]["solver"] == "rheoFoam"
    assert not any(item["field"] == "material.behavior" for item in result["blocking_missing"])
    assert result["material_card"]["reason"].startswith("explicit_constitutive_model")




def test_oldroyd_beta_eta0_parameters_do_not_clarify_as_missing():
    result = evaluate_requirement(
        "Fattal Kupferman 2005 Oldroyd-B lid-driven cavity benchmark "
        "geometry square cavity L=1 mesh=127x127 lid velocity U=1 "
        "beta=0.5 eta0=1 lambda=1 Re=0.01 rho=0.01 "
        "parameter source: user_provided source reference: user prompt user approved"
    )

    assert result["status"] == "ready"
    assert result["target_preview"]["solver"] == "rheoFoam"
    assert not any(item["field"] == "rheology.parameters" for item in result["blocking_missing"])


def test_oldroyd_unicode_subscript_parameters_do_not_clarify_as_missing():
    result = evaluate_requirement(
        "Oldroyd-B viscoelastic flow geometry square cavity L=1 lid velocity U=1 "
        "ηₛ=0.5 ηₚ=0.5 λ=1 parameter source: user_provided source reference: user prompt user approved"
    )

    assert result["status"] == "ready"
    assert not any(item["field"] == "rheology.parameters" for item in result["blocking_missing"])


def test_rheotool_fluiddamper_tutorial_intake_is_ready_without_lambda_or_inlet():
    result = evaluate_requirement(
        "复现 RheoTool 5.1.9 fluidDamper/CarreauYasuda 教程模板 "
        "/opt/build/rheoTool/of90/tutorials/rheoFoam/fluidDamper/CarreauYasuda/，"
        "保持原始几何、动网格、边界条件和 outputCd；"
        "几何为 5° wedge 阻尼器 x length=110mm y height=20mm，piston 振荡 f=32Hz amplitude=12mm；"
        "CarreauYasuda 广义牛顿剪切变稀模型 rho=1000 eta0=100 etaInf=0 k=0.0084033613 n=0.353 a=1.433；"
        "注意该模型无 lambda；文本中提到 controlDict application rheoInterFoam 只是教程历史字段，实际 Allrun 执行 rheoFoam。"
    )

    assert result["status"] == "ready"
    assert result["target_preview"]["solver"] == "rheoFoam"
    assert result["template_match"]["template_id"] == "rheotool_5_1_9_fluiddamper_carreauyasuda"
    assert result["blocking_missing"] == []
    assert result["clarification_questions"] == []


def test_rheotool_dieswell_family_clarifies_only_variant():
    result = evaluate_requirement(
        "请复现 RheoTool 5.3.3 planar DieSwell 教程，输出最终时间、自由液面/挤出胀大结果和主要场文件位置。"
    )

    assert result["status"] == "clarify"
    assert result["template_family_match"]["template_id"] == "rheotool_5_3_3_dieswell_family"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"tutorial.variant"}
    children = result["template_family_match"]["children"]
    assert [child["label"] for child in children] == ["Oldroyd-BLog", "GiesekusLog", "CarreauYasuda"]
    assert children[0]["recommended"] is True
    assert all(child["recommended"] is False for child in children[1:])
    assert "标准粘弹性" in children[0]["description"]
    assert "几何、网格、边界条件、参数和求解器将由所选教程模板继承" in result["blocking_missing"][0]["ask_user"]
    assert "Oldroyd-BLog（推荐）" in result["clarification_questions"][0]


def test_rheotool_dieswell_variant_intake_is_ready_without_geometry_or_parameters():
    result = evaluate_requirement(
        "请复现 RheoTool 5.3.3 DieSwell/Oldroyd-BLog 教程，输出最终时间、自由液面/挤出胀大结果和主要场文件位置。"
    )

    assert result["status"] == "ready"
    assert result["target_preview"]["solver"] == "rheoInterFoam"
    assert result["template_match"]["template_id"] == "rheotool_5_3_3_dieswell_oldroydb_log"
    assert result["blocking_missing"] == []
    assert result["clarification_questions"] == []


def test_rheotool_dieswell_two_phase_template_does_not_clarify_material_behavior():
    result = evaluate_requirement(
        "请复现 RheoTool 5.3.3 DieSwell/Oldroyd-BLog 教程。"
        "material_model: Oldroyd-BLog。"
        "material_behavior: 非牛顿/粘弹性，water 相 Oldroyd-BLog 粘弹性，air 相牛顿。"
        "输出最终时间、自由液面/挤出胀大结果和主要场文件位置。"
    )

    assert result["status"] == "ready"
    assert result["template_match"]["template_id"] == "rheotool_5_3_3_dieswell_oldroydb_log"
    assert result["clarification_questions"] == []


def test_business_dieswell_request_clarifies_task_mode_first():
    result = evaluate_requirement("我想评估一种聚合物熔体从平面狭缝口模挤出后的胀大程度。")

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"task.mode"}
    question = result["clarification_questions"][0]
    assert "平台基线模板" in question
    assert "真实设备" in question
    assert "参数扫描" in question
    assert not any(item["field"] == "geometry.dimensions" for item in result["blocking_missing"])
    assert any(item["field"] == "similar_template_family" for item in result["infer_with_disclosure"])


def test_business_parallel_plate_request_clarifies_task_mode_first():
    result = evaluate_requirement("我想评估一种聚合物溶液在两块平行板之间流动时的速度分布和壁面剪切应力。")

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"task.mode"}
    question = result["clarification_questions"][0]
    assert "平台基线模板" in question
    assert "真实设备" in question
    assert "参数扫描" in question
    assert "Giesekus" not in question
    assert "PTT" not in question
    assert "本构变体" not in result["blocking_missing"][0]["ask_user"]
    assert not any(item["field"] == "constitutive_model" for item in result["blocking_missing"])
    assert not any(item["field"] == "geometry.dimensions" for item in result["blocking_missing"])
    assert any(
        item["field"] == "similar_template_family" and "5.1.3" in item["suggested"] and "Oldroyd-BLog" in item["suggested"]
        for item in result["infer_with_disclosure"]
    )


def test_business_parallel_plate_baseline_mode_clarifies_parameter_policy():
    result = evaluate_requirement(
        "我想评估一种聚合物溶液在两块平行板之间流动时的速度分布和壁面剪切应力，"
        "先使用平台已有平行板通道模板做基线评估。"
    )

    assert result["status"] == "clarify"
    assert result["template_match"]["template_id"] == "rheotool_5_1_3_channel_oldroydb_log"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_policy"}
    assert "使用模板原始参数" in result["clarification_questions"][0]
    assert "修改部分参数" in result["clarification_questions"][0]
    assert "Giesekus" not in result["clarification_questions"][0]
    assert "PTT" not in result["clarification_questions"][0]


def test_parallel_plate_real_device_giesekus_discloses_non_template_adaptation():
    result = evaluate_requirement(
        "我想用真实设备几何，Giesekus 模型，评估聚合物溶液平行板通道流。"
        "板间距1mm，长度10cm，入口速度0.01m/s，etaS=1 etaP=2 lambda=0.5 alpha=0.1。"
    )

    assert result["status"] == "ready"
    assert result.get("template_match") is None
    assert any(
        item["field"] == "generalization.constitutive_model"
        and "not a registered RheoTool 5.1.3 Case 1 template variant" in item["suggested"]
        and "Channel/Oldroyd-BLog" in item["suggested"]
        for item in result["infer_with_disclosure"]
    )


def test_parallel_plate_canonical_dimensionless_signature_clarifies_parameter_policy():
    result = evaluate_requirement(
        "基于平行板通道模板计算 Oldroyd-BLog 流动，目标 Re=0, Wi=0.99, beta=0.01。"
        "输出速度剖面、聚合物应力剖面，并与模板基线结果做对比。"
    )

    assert result["status"] == "clarify"
    assert result["template_match"]["template_id"] == "rheotool_5_1_3_channel_oldroydb_log"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_policy"}


def test_parallel_plate_noncanonical_dimensionless_signature_uses_override_review():
    result = evaluate_requirement(
        "基于平行板通道模板计算 Oldroyd-BLog 流动，目标 Re=0, Wi=1.5, beta=0.01。"
        "输出速度剖面、聚合物应力剖面，并与模板基线结果做对比。"
    )

    assert result["status"] == "clarify"
    assert result["template_match"]["template_id"] == "rheotool_5_1_3_channel_oldroydb_log"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_overrides_review"}


def test_business_parallel_plate_baseline_original_parameters_is_ready():
    result = evaluate_requirement(
        "我想评估一种聚合物溶液在两块平行板之间流动时的速度分布和壁面剪切应力，"
        "先使用平台已有平行板通道模板做基线评估，使用模板原始参数。"
    )

    assert result["status"] == "ready"
    assert result["template_match"]["template_id"] == "rheotool_5_1_3_channel_oldroydb_log"
    assert result["parameter_policy"]["mode"] == "use_template_originals"
    assert result["target_preview"]["solver"] == "rheoFoam"
    assert result["blocking_missing"] == []


def test_business_parallel_plate_lambda_override_uses_template_override_review():
    result = evaluate_requirement(
        "我想基于平台已有平行板通道模板，评估聚合物溶液流动。"
        "几何和边界条件沿用模板，但把松弛时间 lambda 改为 2.0，"
        "输出速度剖面和 tau_xy 剪切应力剖面。"
    )

    assert result["status"] == "clarify"
    assert result["template_match"]["template_id"] == "rheotool_5_1_3_channel_oldroydb_log"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_overrides_review"}
    assert not any(item["field"] == "geometry.dimensions" for item in result["blocking_missing"])
    assert not any(item["field"] == "constitutive_model" for item in result["blocking_missing"])


def test_business_parallel_plate_parameter_scan_uses_template_override_review():
    result = evaluate_requirement(
        "我想比较聚合物溶液松弛时间不同对平行板通道流动应力的影响。"
        "请基于平行板通道模板，分别计算 lambda=0.5、1.0、2.0 三组，"
        "输出 tau_xx 和 tau_xy 剖面对比。"
    )

    assert result["status"] == "clarify"
    assert result["template_match"]["template_id"] == "rheotool_5_1_3_channel_oldroydb_log"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_overrides_review"}
    assert "参数扫描" in result["clarification_questions"][0] or "部分修改" in result["clarification_questions"][0]


def test_professional_parallel_plate_inheriting_template_does_not_ask_geometry_or_flow():
    result = evaluate_requirement(
        "建立二维平行板通道 Oldroyd-BLog 黏弹性流动算例。"
        "沿用平台平行板通道模板几何和网格，设置 etaS=0.01, etaP=0.99, lambda=1.0, rho=1.0，"
        "输出中心线 Ux 和 tau_xx/tau_xy 剖面。"
    )

    assert result["status"] == "clarify"
    assert result["template_match"]["template_id"] == "rheotool_5_1_3_channel_oldroydb_log"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_overrides_review"}
    assert not any(item["field"] == "geometry.dimensions" for item in result["blocking_missing"])
    assert not any(item["field"] == "flow.boundary_condition" for item in result["blocking_missing"])


def test_parallel_plate_inlet_velocity_multiplier_uses_template_override_review():
    result = evaluate_requirement(
        "使用平行板通道模板，保持 Oldroyd-BLog 本构参数不变，"
        "将入口平均速度提高到模板基线的 2 倍，比较 Ux、tau_xx 和 tau_xy 的变化。"
    )

    assert result["status"] == "clarify"
    assert result["template_match"]["template_id"] == "rheotool_5_1_3_channel_oldroydb_log"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_overrides_review"}


def test_customer_custom_boundary_condition_is_rejected_before_generic_missing_fields():
    result = evaluate_requirement(
        "我想用平行板通道模板，但入口速度边界条件需要 customerSpecialBC，"
        "自定义时间函数由我们内部模型控制。"
    )

    assert result["status"] == "reject"
    assert "customerSpecialBC" in result["rejection_reason"]
    assert "暂不支持自动编译客户自定义 BC" in result["rejection_reason"]
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"boundary_condition.custom_patch_type"}


def test_parallel_plate_high_re_turbulence_clarifies_scope_before_template_policy():
    result = evaluate_requirement(
        "我想用平行板通道模板模拟高速聚合物流动，Re 大约 20000，判断是否出现湍流影响。"
    )

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"physics.turbulence_scope"}
    assert result["blocking_missing"][0]["estimated_re"] == 20000
    assert result["blocking_missing"][0]["template_candidate"] == "rheotool_5_1_3_channel_oldroydb_log"
    assert "V10 Foundation 牛顿湍流通道" in result["blocking_missing"][0]["ask_user"]
    assert "层流模板探索" in result["blocking_missing"][0]["ask_user"]
    assert not any(item["field"] == "template.parameter_policy" for item in result["blocking_missing"])


def test_parallel_plate_high_re_turbulence_clarifies_scope_before_unknown_task_mode():
    result = evaluate_requirement(
        """
        # Foam-Agent user_requirement.txt
        ## User Goal
        我想用平行板通道模板模拟高速聚合物流动，Re 大约 20000，判断是否出现湍流影响。
        ## Task Mode
        - task_mode: unknown
        ## Geometry
        - geometry_type: parallel plates / channel template
        ## Missing / Unconfirmed Information
        - task_mode 未确认
        """
    )

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"physics.turbulence_scope"}
    assert result["blocking_missing"][0]["estimated_re"] == 20000
    assert not any(item["field"] == "task.mode" for item in result["blocking_missing"])


def test_business_cavity_request_clarifies_task_mode_first():
    result = evaluate_requirement("我想评估一种聚合物溶液在封闭方腔中被上壁拖动后形成的循环流动和应力分布。")

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"task.mode"}
    assert any(
        item["field"] == "similar_template_family" and "5.1.4" in item["suggested"]
        for item in result["infer_with_disclosure"]
    )


def test_foundation_cavity_business_request_clarifies_task_mode_first():
    result = evaluate_requirement("我想评估水在一个方形封闭腔体中，由上壁运动带动形成的主涡和速度分布。")

    assert result["status"] == "clarify"
    assert result["target_preview"]["channel"] == "v10-foundation"
    assert result["target_preview"]["solver"] == "icoFoam"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"task.mode"}
    assert any(
        item["field"] == "tutorial_template_candidate"
        and item["suggested"] == "foundation_v10_icofoam_cavity"
        for item in result["infer_with_disclosure"]
    )


def test_foundation_cavity_baseline_original_parameters_is_ready():
    result = evaluate_requirement(
        "我想评估水在顶盖驱动方腔中的主涡结构和中心线速度分布。"
        "可以先使用平台已有 OpenFOAM v10 cavity 模板做基线评估，使用模板原始参数。"
    )

    assert result["status"] == "ready"
    assert result["target_preview"]["channel"] == "v10-foundation"
    assert result["target_preview"]["solver"] == "icoFoam"
    assert result["template_match"]["template_id"] == "foundation_v10_icofoam_cavity"
    assert result["blocking_missing"] == []


def test_foundation_cavity_family_clarifies_execution_scope():
    result = evaluate_requirement(
        "请复现 OpenFOAM v10 cavity 完整教程族，包含 cavityFine、cavityHighRe 和 mapFields，"
        "输出每个子 case 的最终时间和中心线速度位置。"
    )

    assert result["status"] == "clarify"
    assert result["template_family_match"]["template_id"] == "foundation_v10_icofoam_cavity_family"
    assert result["template_family_match"]["workflow_type"] == "foundation-tutorial-family"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.scope"}
    children = result["template_family_match"]["children"]
    assert children[0]["template_id"] == "foundation_v10_icofoam_cavity"
    assert children[0]["recommended"] is True
    assert any(child["template_id"] == "foundation_v10_icofoam_cavity_full_allrun" for child in children)
    assert "基础 baseline（推荐）" in result["clarification_questions"][0]
    assert "完整官方教程族" in result["clarification_questions"][0]
    assert "mapFields" in result["blocking_missing"][0]["ask_user"]


def test_foundation_cavity_full_allrun_scope_is_ready():
    result = evaluate_requirement(
        "OpenFOAM v10 cavity 选择完整官方教程族 full_allrun，运行父目录 Allrun，"
        "包含 cavity、cavityFine、cavityGrade、cavityHighRe、cavityClipped 和 mapFields。"
    )

    assert result["status"] == "ready"
    assert result["target_preview"]["channel"] == "v10-foundation"
    assert result["target_preview"]["solver"] == "icoFoam"
    assert result["template_match"]["template_id"] == "foundation_v10_icofoam_cavity_full_allrun"
    assert result["blocking_missing"] == []


def test_foundation_pitzdaily_baseline_original_parameters_is_ready():
    result = evaluate_requirement(
        "我想使用平台已有 OpenFOAM v10 pitzDaily 模板做基线评估，"
        "模拟牛顿流体通过后向台阶/扩张通道的稳态速度场、压力场和回流区，使用模板原始参数。"
    )

    assert result["status"] == "ready"
    assert result["target_preview"]["channel"] == "v10-foundation"
    assert result["target_preview"]["solver"] == "simpleFoam"
    assert result["template_match"]["template_id"] == "foundation_v10_simplefoam_pitzdaily"
    assert result["blocking_missing"] == []


def test_foundation_pitzdaily_family_clarifies_execution_scope():
    result = evaluate_requirement(
        "请复现 OpenFOAM v10 pitzDaily 教程族，输出后向台阶回流区和速度压力场。"
    )

    assert result["status"] == "clarify"
    assert result["template_family_match"]["template_id"] == "foundation_v10_pitzdaily_family"
    assert result["template_family_match"]["workflow_type"] == "foundation-tutorial-family"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.scope"}
    children = result["template_family_match"]["children"]
    assert children[0]["template_id"] == "foundation_v10_simplefoam_pitzdaily"
    assert children[0]["recommended"] is True
    assert any(child["template_id"] == "foundation_v10_pimplefoam_ras_pitzdaily" for child in children)
    assert any(child["template_id"] == "foundation_v10_compressible_pitzdaily" for child in children)
    assert "simpleFoam baseline（推荐）" in result["clarification_questions"][0]
    assert "compressible pitzDaily" in result["clarification_questions"][0]
    assert "不会静默折叠" in result["blocking_missing"][0]["ask_user"]


@pytest.mark.parametrize(
    ("prompt", "template_id", "solver"),
    [
        (
            "OpenFOAM v10 pitzDaily 选择 pimpleFoam/RAS 瞬态不可压缩变体，使用模板原始参数。",
            "foundation_v10_pimplefoam_ras_pitzdaily",
            "pimpleFoam",
        ),
        (
            "OpenFOAM v10 pitzDaily 选择 pisoFoam LES 变体，使用模板原始参数。",
            "foundation_v10_pisofoam_les_pitzdaily",
            "pisoFoam",
        ),
        (
            "OpenFOAM v10 pitzDaily 选择 potentialFoam 势流变体，使用模板原始参数。",
            "foundation_v10_potentialfoam_pitzdaily",
            "potentialFoam",
        ),
        (
            "OpenFOAM v10 pitzDaily 选择 scalarTransportFoam 标量输运变体，使用模板原始参数。",
            "foundation_v10_scalartransport_pitzdaily",
            "scalarTransportFoam",
        ),
    ],
)
def test_foundation_pitzdaily_executable_variants_are_ready(prompt, template_id, solver):
    result = evaluate_requirement(prompt)

    assert result["status"] == "ready"
    assert result["target_preview"]["channel"] == "v10-foundation"
    assert result["target_preview"]["solver"] == solver
    assert result["template_match"]["template_id"] == template_id
    assert result["blocking_missing"] == []


def test_foundation_pitzdaily_compressible_template_is_rejected():
    result = evaluate_requirement(
        "使用 OpenFOAM v10 compressible rhoPimpleFoam pitzDaily LES 模板。"
    )

    assert result["status"] == "reject"
    assert result["target_preview"] is None
    assert "pitzDaily compressible variants" in result["rejection_reason"]
    assert "outside the current certified solver matrix" in result["rejection_reason"]


def test_foundation_cylinder_family_clarifies_execution_scope():
    result = evaluate_requirement(
        "请复现 OpenFOAM v10 cylinder 教程族，输出速度压力场。"
    )

    assert result["status"] == "clarify"
    assert result["template_family_match"]["template_id"] == "foundation_v10_cylinder_family"
    assert result["template_family_match"]["workflow_type"] == "foundation-tutorial-family"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.scope"}
    children = result["template_family_match"]["children"]
    assert children[0]["template_id"] == "foundation_v10_potentialfoam_cylinder"
    assert children[0]["recommended"] is True
    assert any(child["template_id"] == "foundation_v10_pimplefoam_laminar_offsetcylinder" for child in children)
    assert any(child["template_id"] == "foundation_v10_interfoam_laminar_sloshingcylinder" for child in children)
    assert any(child["template_id"] == "foundation_v10_compressible_cylinder_unsupported" for child in children)
    assert "potentialFoam cylinder（推荐）" in result["clarification_questions"][0]
    assert "compressibleInterFoam cylinder" in result["clarification_questions"][0]


@pytest.mark.parametrize(
    ("prompt", "template_id", "solver"),
    [
        (
            "OpenFOAM v10 cylinder 选择 potentialFoam 势流变体，使用模板原始参数。",
            "foundation_v10_potentialfoam_cylinder",
            "potentialFoam",
        ),
        (
            "OpenFOAM v10 cylinder 选择 pimpleFoam offsetCylinder 层流绕流变体，使用模板原始参数。",
            "foundation_v10_pimplefoam_laminar_offsetcylinder",
            "pimpleFoam",
        ),
        (
            "OpenFOAM v10 cylinder 选择 interFoam sloshingCylinder 自由液面变体，使用模板原始参数。",
            "foundation_v10_interfoam_laminar_sloshingcylinder",
            "interFoam",
        ),
    ],
)
def test_foundation_cylinder_executable_variants_are_ready(prompt, template_id, solver):
    result = evaluate_requirement(prompt)

    assert result["status"] == "ready"
    assert result["target_preview"]["channel"] == "v10-foundation"
    assert result["target_preview"]["solver"] == solver
    assert result["template_match"]["template_id"] == template_id
    assert result["blocking_missing"] == []


def test_foundation_cylinder_compressible_template_is_rejected():
    result = evaluate_requirement(
        "OpenFOAM v10 cylinder 选择 compressibleInterFoam 可压缩圆柱教程。"
    )

    assert result["status"] == "reject"
    assert result["target_preview"] is None
    assert "compressibleInterFoam" in result["rejection_reason"]
    assert "outside the current certified solver matrix" in result["rejection_reason"]


def test_foundation_dambreak_baseline_original_parameters_is_ready():
    result = evaluate_requirement(
        "我想使用平台已有 OpenFOAM v10 damBreak 模板做基线评估，"
        "模拟水-空气两相破坝自由液面演化，使用模板原始参数，输出最终时间和 alpha.water 自由液面位置。"
    )

    assert result["status"] == "ready"
    assert result["target_preview"]["channel"] == "v10-foundation"
    assert result["target_preview"]["solver"] == "interFoam"
    assert result["template_match"]["template_id"] == "foundation_v10_interfoam_dambreak"
    assert result["blocking_missing"] == []


def test_foundation_dambreak_injected_ras_template_id_still_uses_laminar_baseline():
    result = evaluate_requirement(
        """
        Use the platform OpenFOAM v10 damBreak baseline template for computation.
        用户已确认参数使用方式：使用模板原始参数。
        tutorial_variant: standard damBreak tutorial
        template_id: foundation_v10_interfoam_ras_dambreak
        Requested Outputs: free_surface_evolution, water_front_advancement, pressure_field
        """
    )

    assert result["status"] == "ready"
    assert result["template_match"]["template_id"] == "foundation_v10_interfoam_dambreak"
    assert result["target_preview"]["solver"] == "interFoam"
    assert result["blocking_missing"] == []


def test_foundation_dambreak_family_clarifies_execution_scope():
    result = evaluate_requirement(
        "请复现 OpenFOAM v10 damBreak 教程族，输出自由液面和主要场文件。"
    )

    assert result["status"] == "clarify"
    assert result["template_family_match"]["template_id"] == "foundation_v10_dambreak_family"
    assert result["template_family_match"]["workflow_type"] == "foundation-tutorial-family"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.scope"}
    children = result["template_family_match"]["children"]
    assert children[0]["template_id"] == "foundation_v10_interfoam_dambreak"
    assert children[0]["recommended"] is True
    assert any(child["template_id"] == "foundation_v10_interfoam_dambreak_with_obstacle" for child in children)
    assert any(child["template_id"] == "foundation_v10_compressible_dambreak_unsupported" for child in children)
    assert "laminar interFoam baseline（推荐）" in result["clarification_questions"][0]
    assert "compressible damBreak" in result["clarification_questions"][0]


@pytest.mark.parametrize(
    ("prompt", "template_id"),
    [
        (
            "OpenFOAM v10 damBreak 选择 laminar full_allrun 完整教程族，使用模板原始参数。",
            "foundation_v10_interfoam_dambreak_laminar_full_allrun",
        ),
        (
            "OpenFOAM v10 damBreak 选择 with obstacle 障碍物变体，使用模板原始参数。",
            "foundation_v10_interfoam_dambreak_with_obstacle",
        ),
        (
            "OpenFOAM v10 damBreak 选择 RAS 湍流 baseline，使用模板原始参数。",
            "foundation_v10_interfoam_ras_dambreak",
        ),
        (
            "OpenFOAM v10 damBreak 选择 RAS full_allrun 完整教程族，使用模板原始参数。",
            "foundation_v10_interfoam_ras_dambreak_full_allrun",
        ),
        (
            "OpenFOAM v10 damBreak 选择 porous baffle 多孔挡板变体，使用模板原始参数。",
            "foundation_v10_interfoam_ras_dambreak_porous_baffle",
        ),
    ],
)
def test_foundation_dambreak_executable_variants_are_ready(prompt, template_id):
    result = evaluate_requirement(prompt)

    assert result["status"] == "ready"
    assert result["target_preview"]["channel"] == "v10-foundation"
    assert result["target_preview"]["solver"] == "interFoam"
    assert result["template_match"]["template_id"] == template_id
    assert result["blocking_missing"] == []


@pytest.mark.parametrize(
    ("prompt", "expected_reason"),
    [
        (
            "OpenFOAM v10 damBreak 选择 interMixingFoam 三相混合破坝教程。",
            "interMixingFoam",
        ),
        (
            "OpenFOAM v10 damBreak 选择 compressibleInterFoam 可压缩破坝教程。",
            "compressibleInterFoam",
        ),
    ],
)
def test_foundation_dambreak_unsupported_variants_are_rejected(prompt, expected_reason):
    result = evaluate_requirement(prompt)

    assert result["status"] == "reject"
    assert result["target_preview"] is None
    assert expected_reason in result["rejection_reason"]
    assert "outside the current certified solver matrix" in result["rejection_reason"]


def test_foundation_forwardstep_family_clarifies_execution_scope():
    result = evaluate_requirement(
        "请复现 OpenFOAM v10 forwardStep 可压缩教程族，输出压力、温度和速度场。"
    )

    assert result["status"] == "clarify"
    assert result["template_family_match"]["template_id"] == "foundation_v10_forwardstep_family"
    assert result["template_family_match"]["workflow_type"] == "foundation-tutorial-family"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.scope"}
    children = result["template_family_match"]["children"]
    assert children[0]["template_id"] == "foundation_v10_rhocentralfoam_forwardstep"
    assert children[0]["recommended"] is True
    assert any(child["template_id"] == "foundation_v10_rhopimplefoam_laminar_forwardstep" for child in children)
    assert "rhoCentralFoam forwardStep（推荐）" in result["clarification_questions"][0]
    assert "rhoPimpleFoam laminar forwardStep" in result["clarification_questions"][0]


@pytest.mark.parametrize(
    ("prompt", "template_id", "solver"),
    [
        (
            "OpenFOAM v10 forwardStep 选择 rhoCentralFoam 高速可压缩变体，使用模板原始参数。",
            "foundation_v10_rhocentralfoam_forwardstep",
            "rhoCentralFoam",
        ),
        (
            "OpenFOAM v10 forwardStep 选择 rhoPimpleFoam laminar 层流瞬态可压缩变体，使用模板原始参数。",
            "foundation_v10_rhopimplefoam_laminar_forwardstep",
            "rhoPimpleFoam",
        ),
    ],
)
def test_foundation_forwardstep_executable_variants_are_ready(prompt, template_id, solver):
    result = evaluate_requirement(prompt)

    assert result["status"] == "ready"
    assert result["target_preview"]["channel"] == "v10-foundation"
    assert result["target_preview"]["solver"] == solver
    assert result["template_match"]["template_id"] == template_id
    assert result["blocking_missing"] == []


def test_foundation_bernardcells_template_is_ready():
    result = evaluate_requirement(
        "请复现 OpenFOAM v10 Rayleigh-Benard / BernardCells buoyantFoam 教程，"
        "使用模板原始参数，输出温度场和速度场。"
    )

    assert result["status"] == "ready"
    assert result["target_preview"]["channel"] == "v10-foundation"
    assert result["target_preview"]["solver"] == "buoyantFoam"
    assert result["template_match"]["template_id"] == "foundation_v10_buoyantfoam_bernardcells"
    assert result["blocking_missing"] == []


@pytest.mark.parametrize(
    ("prompt", "template_id", "solver"),
    [
        (
            "请复现 OpenFOAM v10 pimpleFoam planarPoiseuille 平面泊肃叶流教程，使用模板原始参数。",
            "foundation_v10_pimplefoam_laminar_planarpoiseuille",
            "pimpleFoam",
        ),
        (
            "请复现 OpenFOAM v10 rhoCentralFoam obliqueShock 斜激波教程，使用模板原始参数。",
            "foundation_v10_rhocentralfoam_obliqueshock",
            "rhoCentralFoam",
        ),
        (
            "请复现 OpenFOAM v10 rhoCentralFoam shockTube 激波管教程，使用模板原始参数。",
            "foundation_v10_rhocentralfoam_shocktube",
            "rhoCentralFoam",
        ),
        (
            "请复现 OpenFOAM v10 rhoPimpleFoam laminar shockTube 激波管教程，使用模板原始参数。",
            "foundation_v10_rhopimplefoam_laminar_shocktube",
            "rhoPimpleFoam",
        ),
        (
            "请复现 OpenFOAM v10 simpleFoam airFoil2D 翼型教程，使用模板原始参数。",
            "foundation_v10_simplefoam_airfoil2d",
            "simpleFoam",
        ),
        (
            "请复现 OpenFOAM v10 interFoam capillaryRise 毛细上升教程，使用模板原始参数。",
            "foundation_v10_interfoam_laminar_capillaryrise",
            "interFoam",
        ),
        (
            "请复现 OpenFOAM v10 interFoam wave 波浪教程，使用模板原始参数。",
            "foundation_v10_interfoam_laminar_wave",
            "interFoam",
        ),
    ],
)
def test_additional_foundation_v10_templates_are_ready(prompt, template_id, solver):
    result = evaluate_requirement(prompt)

    assert result["status"] == "ready"
    assert result["target_preview"]["channel"] == "v10-foundation"
    assert result["target_preview"]["solver"] == solver
    assert result["template_match"]["template_id"] == template_id
    assert result["blocking_missing"] == []


def test_foundation_cavity_benchmark_clarifies_parameter_policy():
    result = evaluate_requirement(
        "OpenFOAM v10 lid-driven cavity benchmark，Newtonian incompressible laminar flow，"
        "Re=100，top lid moving wall，输出主涡位置和中心线速度。"
    )

    assert result["status"] == "clarify"
    assert result["target_preview"]["channel"] == "v10-foundation"
    assert result["target_preview"]["solver"] == "icoFoam"
    assert result["template_match"]["template_id"] == "foundation_v10_icofoam_cavity"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_policy"}


def test_foundation_cavity_real_geometry_complete_is_ready_without_task_mode():
    result = evaluate_requirement(
        "模拟一个真实二维方腔：边长 0.2 m，水的运动黏度 nu=1e-6 m2/s，"
        "密度 rho=1000 kg/m3，顶盖速度 0.02 m/s，其余壁面 noSlip，"
        "输出最终速度场、压力场、主涡位置和中心线速度剖面。"
    )

    assert result["status"] == "ready"
    assert result["target_preview"]["channel"] == "v10-foundation"
    assert result["target_preview"]["solver"] == "icoFoam"
    assert "template_match" not in result
    assert result["blocking_missing"] == []


def test_business_cavity_baseline_original_parameters_is_ready():
    result = evaluate_requirement(
        "我想评估聚合物溶液在顶盖驱动方腔中的速度剖面、应力分布和平均动能变化。"
        "可以先使用平台已有方腔模板做基线评估，使用模板原始参数。"
    )

    assert result["status"] == "ready"
    assert result["template_match"]["template_id"] == "rheotool_5_1_4_cavity_oldroydb_log"
    assert result["parameter_policy"]["mode"] == "use_template_originals"
    assert result["target_preview"]["solver"] == "rheoFoam"
    assert result["blocking_missing"] == []


def test_business_cavity_lambda_override_uses_template_override_review():
    result = evaluate_requirement(
        "我想基于平台已有顶盖驱动方腔模板评估聚合物溶液流动。"
        "几何、网格和边界条件沿用模板，但把松弛时间 lambda 改为 2.0，"
        "输出速度剖面、tau_xy 剖面和平均动能曲线。"
    )

    assert result["status"] == "clarify"
    assert result["template_match"]["template_id"] == "rheotool_5_1_4_cavity_oldroydb_log"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_overrides_review"}


def test_cavity_real_geometry_side_length_is_ready():
    result = evaluate_requirement(
        "我要模拟边长 10 mm 的二维顶盖驱动方腔，材料使用 Oldroyd-BLog，"
        "etaS=0.2, etaP=0.8, lambda=0.5, rho=1000，顶盖速度 0.01 m/s，"
        "输出主涡位置、中心线速度剖面和壁面剪切应力。"
    )

    assert result["status"] == "ready"
    assert result["target_preview"]["solver"] == "rheoFoam"
    assert "template_match" not in result
    assert result["blocking_missing"] == []


def test_cavity_high_re_turbulence_clarifies_scope_before_template_policy():
    result = evaluate_requirement(
        "我想用顶盖驱动方腔模板模拟高速聚合物流动，Re 大约 10000，判断是否出现湍流或不稳定流动。"
    )

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"physics.turbulence_scope"}
    assert result["blocking_missing"][0]["estimated_re"] == 10000
    assert result["blocking_missing"][0]["template_candidate"] == "rheotool_5_1_4_cavity_oldroydb_log"
    assert "顶盖驱动方腔" in result["blocking_missing"][0]["ask_user"]


def test_business_contraction_request_clarifies_task_mode_first():
    result = evaluate_requirement("我想评估一种聚合物溶液通过收缩流道时的压力损失和收缩口附近应力集中。")

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"task.mode"}
    assert any(
        item["field"] == "similar_template_family" and "5.1.5" in item["suggested"]
        for item in result["infer_with_disclosure"]
    )


def test_business_contraction_baseline_original_parameters_is_ready():
    result = evaluate_requirement(
        "我想评估聚合物溶液通过 4:1 平面收缩流道时的压降、速度剖面和收缩口应力集中。"
        "可以先使用平台已有 4:1 收缩流道模板做基线评估，使用模板原始参数。"
    )

    assert result["status"] == "ready"
    assert result["template_match"]["template_id"] == "rheotool_5_1_5_contraction41_oldroydb_log"
    assert result["parameter_policy"]["mode"] == "use_template_originals"
    assert result["target_preview"]["solver"] == "rheoFoam"
    assert result["blocking_missing"] == []


def test_business_contraction_lambda_override_uses_template_override_review():
    result = evaluate_requirement(
        "我想基于平台已有 4:1 收缩流道模板评估聚合物溶液流动。"
        "几何、网格和边界条件沿用模板，但把松弛时间 lambda 改为 2.0，"
        "输出入口压降、收缩口 tau_xx/tau_xy 和下游速度剖面。"
    )

    assert result["status"] == "clarify"
    assert result["template_match"]["template_id"] == "rheotool_5_1_5_contraction41_oldroydb_log"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_overrides_review"}


def test_contraction_ratio_mismatch_clarifies_before_template_use():
    result = evaluate_requirement("我想模拟聚合物溶液通过 2:1 平面收缩流道时的压力损失和应力集中。")

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"geometry.contraction_ratio"}
    assert result["blocking_missing"][0]["requested_ratio"] == 2
    assert result["blocking_missing"][0]["available_template_ratio"] == 4.0


def test_contraction_high_re_turbulence_clarifies_scope_before_template_policy():
    result = evaluate_requirement(
        "我想用 4:1 收缩流道模板模拟高速聚合物流动，Re 大约 10000，判断收缩口附近是否出现湍流或不稳定流动。"
    )

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"physics.turbulence_scope"}
    assert result["blocking_missing"][0]["estimated_re"] == 10000
    assert result["blocking_missing"][0]["template_candidate"] == "rheotool_5_1_5_contraction41_oldroydb_log"
    assert "收缩流道" in result["blocking_missing"][0]["ask_user"]


def test_business_cylinder_request_clarifies_task_mode_first():
    result = evaluate_requirement("我想评估一种聚合物溶液流过受限圆柱时的阻力和尾迹应力分布。")

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"task.mode"}
    assert any(
        item["field"] == "similar_template_family" and "5.1.6" in item["suggested"]
        for item in result["infer_with_disclosure"]
    )


def test_business_cylinder_baseline_original_parameters_is_ready():
    result = evaluate_requirement(
        "我想评估聚合物溶液流过受限圆柱时的阻力系数、尾迹速度和应力分布。"
        "可以先使用平台已有受限圆柱绕流模板做基线评估，使用模板原始参数。"
    )

    assert result["status"] == "ready"
    assert result["template_match"]["template_id"] == "rheotool_5_1_6_cylinder_oldroydb_log"
    assert result["parameter_policy"]["mode"] == "use_template_originals"
    assert result["target_preview"]["solver"] == "rheoFoam"
    assert result["blocking_missing"] == []


def test_business_cylinder_lambda_override_uses_template_override_review():
    result = evaluate_requirement(
        "我想基于平台已有受限圆柱绕流模板评估聚合物溶液流动。"
        "几何、网格和边界条件沿用模板，但把松弛时间 lambda 改为 1.5，"
        "输出圆柱阻力、尾迹速度和 tau_xx/tau_xy 应力分布。"
    )

    assert result["status"] == "clarify"
    assert result["template_match"]["template_id"] == "rheotool_5_1_6_cylinder_oldroydb_log"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_overrides_review"}


def test_cylinder_obstacle_shape_mismatch_clarifies_before_task_mode():
    result = evaluate_requirement("我想模拟聚合物溶液绕过通道中的方形障碍物流动，输出阻力和尾迹应力分布。")

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"geometry.obstacle_shape"}
    assert result["blocking_missing"][0]["requested_shape"] == "square_or_rectangular_obstacle"
    assert result["blocking_missing"][0]["available_template_shape"] == "circular_cylinder"


def test_cylinder_high_re_turbulence_clarifies_scope_before_template_policy():
    result = evaluate_requirement(
        "我想用受限圆柱绕流模板模拟高速聚合物流动，Re 大约 10000，判断圆柱后方是否出现湍流或不稳定尾迹。"
    )

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"physics.turbulence_scope"}
    assert result["blocking_missing"][0]["estimated_re"] == 10000
    assert result["blocking_missing"][0]["template_candidate"] == "rheotool_5_1_6_cylinder_oldroydb_log"
    assert "受限圆柱绕流" in result["blocking_missing"][0]["ask_user"]


def test_business_crossslot_request_clarifies_task_mode_first():
    result = evaluate_requirement("我想评估一种聚合物溶液在二维十字槽流道中是否会发生不对称分岔，并查看中心停滞点附近的速度和应力分布。")

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"task.mode"}
    assert any(
        item["field"] == "similar_template_family" and "5.1.7" in item["suggested"]
        for item in result["infer_with_disclosure"]
    )


def test_business_crossslot_baseline_original_parameters_is_ready():
    result = evaluate_requirement(
        "我想评估聚合物溶液在二维 cross-slot 十字流道中的弹性分岔行为。"
        "可以先使用平台已有 CrossSlot 模板做基线评估，使用模板原始参数，"
        "输出中心停滞点附近速度、应力和被动标量分布。"
    )

    assert result["status"] == "ready"
    assert result["template_match"]["template_id"] == "rheotool_5_1_7_crossslot_oldroydb_log"
    assert result["parameter_policy"]["mode"] == "use_template_originals"
    assert result["target_preview"]["solver"] == "rheoFoam"
    assert result["blocking_missing"] == []


def test_business_crossslot_lambda_override_uses_template_override_review():
    result = evaluate_requirement(
        "我想基于平台已有 CrossSlot 十字槽模板评估聚合物溶液弹性分岔。"
        "几何、网格和边界条件沿用模板，但把松弛时间 lambda 改为 0.5，"
        "输出中心线速度、tau_xx/tau_xy 和出口不对称程度。"
    )

    assert result["status"] == "clarify"
    assert result["template_match"]["template_id"] == "rheotool_5_1_7_crossslot_oldroydb_log"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_overrides_review"}


def test_crossslot_dimensionless_benchmark_clarifies_parameter_policy():
    result = evaluate_requirement(
        "RheoTool 5.1.7 cross-slot benchmark，Oldroyd-BLog，Re=0，Wi=0.33，"
        "beta=0，Pe=500，关注二维十字槽中心停滞点附近的 elastic bifurcation 和 asymmetric flow。"
    )

    assert result["status"] == "clarify"
    assert result["template_match"]["template_id"] == "rheotool_5_1_7_crossslot_oldroydb_log"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_policy"}


def test_crossslot_t_junction_topology_mismatch_clarifies_before_generic_missing_fields():
    result = evaluate_requirement("我想模拟聚合物溶液在 T 型微流道中的汇合与分流，判断支路出口流量是否均匀。")

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"geometry.topology"}
    assert result["blocking_missing"][0]["requested_topology"] == "t_junction"
    assert result["blocking_missing"][0]["available_template_topology"] == "four_arm_cross_slot"


def test_crossslot_high_re_turbulence_clarifies_scope_before_template_policy():
    result = evaluate_requirement(
        "我想用 cross-slot 十字槽模板模拟高速聚合物流动，Re 大约 10000，判断中心区域是否出现湍流和不稳定分岔。"
    )

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"physics.turbulence_scope"}
    assert result["blocking_missing"][0]["estimated_re"] == 10000
    assert result["blocking_missing"][0]["template_candidate"] == "rheotool_5_1_7_crossslot_oldroydb_log"
    assert "CrossSlot" in result["blocking_missing"][0]["ask_user"]


def test_business_dieswell_unknown_task_mode_is_not_polluted_by_option_words():
    result = evaluate_requirement(
        """
        ## User Goal
        评估一种聚合物熔体从平面狭缝口模挤出后的胀大程度（extrudate swell / die swell）。

        ## Task Mode
        - task_mode: unknown
          （待用户确认：平台已有相似案例/教程模板基线、真实设备/真实几何、参数扫描）

        ## Missing / Unconfirmed Information
        - task_mode 未确认（教程基线 / 真实设备 / 参数扫描）
        """
    )

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"task.mode"}
    assert "平台基线模板" in result["clarification_questions"][0]


def test_business_dieswell_baseline_mode_then_clarifies_template_variant():
    result = evaluate_requirement(
        "我想评估一种聚合物熔体从平面狭缝口模挤出后的胀大程度，先使用平台已有相似案例/教程模板做基线评估。"
    )

    assert result["status"] == "clarify"
    assert result["template_family_match"]["template_id"] == "rheotool_5_3_3_dieswell_family"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"tutorial.variant"}
    assert "Oldroyd-BLog（推荐）" in result["clarification_questions"][0]


def test_business_dieswell_structured_unknown_variant_options_do_not_select_oldroyd():
    result = evaluate_requirement(
        """
        ## User Goal
        Evaluate the degree of die swell for a polymer melt extruded from a planar slit die.

        ## Task Mode
        - task_mode: template_baseline
        - user_selected: platform baseline template (RheoTool 5.3.3 DieSwell tutorial family)

        ## Rheology
        - material: polymer_melt
        - tutorial_family: RheoTool 5.3.3 DieSwell
        - tutorial_variant: unknown
        - constitutive_model: unknown
        - parameter_policy: unknown

        ## Missing / Unconfirmed Information
        - tutorial_variant: unknown (Oldroyd-BLog, GiesekusLog, or CarreauYasuda)
        - parameter_policy: unknown (use template defaults or modify)
        """
    )

    assert result["status"] == "clarify"
    assert result["template_family_match"]["template_id"] == "rheotool_5_3_3_dieswell_family"
    assert result.get("template_match") is None
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"tutorial.variant"}
    assert "Oldroyd-BLog（推荐）" in result["clarification_questions"][0]


def test_business_dieswell_baseline_variant_then_clarifies_parameter_policy():
    result = evaluate_requirement(
        "我想评估一种聚合物熔体从平面狭缝口模挤出后的胀大程度，"
        "先使用平台已有相似案例/教程模板做基线评估，采用 Oldroyd-BLog 变体。"
    )

    assert result["status"] == "clarify"
    assert result["template_match"]["template_id"] == "rheotool_5_3_3_dieswell_oldroydb_log"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_policy"}
    assert "使用模板原始参数" in result["clarification_questions"][0]
    assert "修改部分参数" in result["clarification_questions"][0]


def test_business_dieswell_baseline_variant_original_parameters_is_ready():
    result = evaluate_requirement(
        "我想评估一种聚合物熔体从平面狭缝口模挤出后的胀大程度，"
        "先使用平台已有相似案例/教程模板做基线评估，采用 Oldroyd-BLog 变体，使用模板原始参数。"
    )

    assert result["status"] == "ready"
    assert result["template_match"]["template_id"] == "rheotool_5_3_3_dieswell_oldroydb_log"
    assert result["parameter_policy"]["mode"] == "use_template_originals"
    assert result["blocking_missing"] == []


def test_business_dieswell_baseline_variant_partial_modify_requires_override_values():
    result = evaluate_requirement(
        "我想评估一种聚合物熔体从平面狭缝口模挤出后的胀大程度，"
        "先使用平台已有相似案例/教程模板做基线评估，采用 Oldroyd-BLog 变体，修改部分参数。"
    )

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_overrides"}
    assert "参数和值" in result["clarification_questions"][0]


def test_business_dieswell_baseline_variant_partial_modify_with_values_needs_override_review():
    result = evaluate_requirement(
        "我想评估一种聚合物熔体从平面狭缝口模挤出后的胀大程度，"
        "先使用平台已有相似案例/教程模板做基线评估，采用 Oldroyd-BLog 变体，"
        "在模板原始参数基础上修改部分参数：lambda=1.5。"
    )

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"template.parameter_overrides_review"}
    assert "白名单" in result["clarification_questions"][0]


def test_business_dieswell_real_device_mode_clarifies_geometry_before_flow_or_material():
    result = evaluate_requirement("我想评估一种聚合物熔体从平面狭缝口模挤出后的胀大程度，按真实设备/真实几何模拟。")

    assert result["status"] == "clarify"
    fields = {item["field"] for item in result["blocking_missing"]}
    assert fields == {"geometry.dimensions"}
    assert "真实几何" in result["blocking_missing"][0]["ask_user"]


def test_invalid_rheology_parameter_format_is_not_reported_as_missing():
    result = evaluate_requirement(
        "Oldroyd-B viscoelastic steady flow geometry channel width=1 length=40 inlet velocity=1 "
        "etaS=low etaP=0.99 lambda=1.0 parameter source: user_provided source reference: user prompt user approved"
    )

    assert result["status"] == "clarify"
    assert any(item["field"] == "rheology.parameters_format" for item in result["blocking_missing"])
    assert not any(item["field"] == "rheology.parameters" for item in result["blocking_missing"])


def test_ready_requirement_can_issue_and_validate_receipt(tmp_path):
    req = tmp_path / "user_requirement.txt"
    req.write_text("水在管道中的稳态压降 geometry pipe diameter=0.01 length=1 inlet velocity=0.001 nu=1e-6 rho=1000 property source: literature_typical source reference: standard water properties at 20C user approved", encoding="utf-8")
    receipt = issue_receipt(req)
    validated = validate_receipt(req)
    assert validated["requirement_sha256"] == receipt["requirement_sha256"]
    assert validated["target_preview"]["solver"] == "simpleFoam"


def test_receipt_hash_mismatch_fails(tmp_path):
    req = tmp_path / "user_requirement.txt"
    req.write_text("水在管道中的稳态压降 geometry pipe diameter=0.01 length=1 inlet velocity=0.001 nu=1e-6 rho=1000 property source: literature_typical source reference: standard water properties at 20C user approved", encoding="utf-8")
    issue_receipt(req)
    req.write_text("水在管道中的稳态压降 geometry pipe diameter=0.02 length=1 inlet velocity=0.001 nu=1e-6 rho=1000 property source: literature_typical source reference: standard water properties at 20C user approved", encoding="utf-8")
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        validate_receipt(req)


def test_newtonian_none_required_parameters_are_rejected_by_intake():
    result = evaluate_requirement(
        """
        # Foam-Agent User Requirement
        ## Business Problem
        Calculate steady water pipe pressure drop.
        ## Geometry
        - geometry type: pipe
        - dimensions: diameter=0.01 m, length=1 m
        ## Flow Conditions
        - steady_or_transient: steady
        - inlet: velocity=0.001 m/s
        ## Rheology
        - behavior: Newtonian
        - model: Newtonian
        - parameters: none required
        - parameter source: user_provided
        """
    )

    assert result["status"] == "clarify"
    assert any(item["field"] == "fluid.properties" for item in result["blocking_missing"])


def test_high_reynolds_number_without_turbulence_treatment_requires_clarification():
    result = evaluate_requirement(
        """
        水在管道中的稳态压降
        geometry pipe diameter=0.1 length=10
        inlet velocity=1
        model: Newtonian
        parameters: nu=1e-6 rho=1000
        property source: literature_typical
        source reference: standard water properties at 20C
        user approved
        """
    )

    assert result["status"] == "clarify"
    assert any(item["field"] == "physics.reynolds_number" for item in result["blocking_missing"])


def test_high_reynolds_number_with_steady_or_transient_field_does_not_imply_rans():
    result = evaluate_requirement(
        """
        # Foam-Agent User Requirement
        ## Flow Conditions
        - steady_or_transient: steady
        - turbulence: unresolved
        水在管道中的稳态压降
        geometry pipe diameter=0.1 length=10
        inlet velocity=1
        model: Newtonian
        parameters: nu=1e-6 rho=1000
        property source: literature_typical
        source reference: standard water properties at 20C
        user approved
        """
    )

    assert result["status"] == "clarify"
    assert result["target_preview"]["solver"] == "simpleFoam"
    assert any(item["field"] == "physics.reynolds_number" for item in result["blocking_missing"])


def test_low_reynolds_number_with_newtonian_properties_is_ready():
    result = evaluate_requirement(
        """
        水在微管中的稳态压降
        geometry pipe diameter=0.001 length=0.1
        inlet velocity=0.001
        model: Newtonian
        parameters: nu=1e-6 rho=1000
        property source: literature_typical
        source reference: standard water properties at 20C
        user approved
        """
    )

    assert result["status"] == "ready"
    assert result["target_preview"]["solver"] == "simpleFoam"
