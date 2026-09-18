from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from models import CaseTarget  # noqa: E402
from services.workflow_compiler import compile_workflow  # noqa: E402


@pytest.mark.parametrize(
    ("prompt", "solver"),
    [
        ("水在管道中的稳态压降", "simpleFoam"),
        ("steady incompressible pipe pressure drop", "simpleFoam"),
        ("稳态圆柱绕流", "simpleFoam"),
        ("steady external aerodynamics", "simpleFoam"),
        ("低速不可压缩风道稳态压降", "simpleFoam"),
        ("瞬态不可压缩圆柱绕流", "pimpleFoam"),
        ("transient incompressible wake", "pimpleFoam"),
        ("非稳态入口脉动流", "pimpleFoam"),
        ("transient moving boundary flow", "pimpleFoam"),
        ("瞬态入口速度变化的不可压缩尾流", "pimpleFoam"),
        ("水和空气的两相自由液面", "interFoam"),
        ("Newtonian dam break with VOF", "interFoam"),
        ("surface tension driven droplet", "interFoam"),
        ("气泡上升两相流", "interFoam"),
        ("水槽中两相液面晃动和空气夹带", "interFoam"),
        ("层流顶盖驱动空腔", "icoFoam"),
        ("laminar cavity flow", "icoFoam"),
        ("icoFoam incompressible benchmark", "icoFoam"),
        ("Oldroyd-B 聚合物流动", "rheoFoam"),
        ("Giesekus viscoelastic contraction flow", "rheoFoam"),
        ("Carreau 剪切变稀管流", "rheoFoam"),
        ("Herschel 屈服应力流体流动", "rheoFoam"),
        ("PTT 黏弹性挤出流动", "rheoFoam"),
        ("计算 FENE-CR 材料函数", "rheoTestFoam"),
        ("virtual rheometer viscosity curve", "rheoTestFoam"),
        ("振荡剪切流变仪测试", "rheoTestFoam"),
        ("测量聚合物拉伸黏度材料函数", "rheoTestFoam"),
        ("Oldroyd-B 粘弹性两相自由液面", "rheoInterFoam"),
        ("viscoelastic two-phase die swell", "rheoInterFoam"),
        ("聚合物液滴界面张力模拟", "rheoInterFoam"),
        ("Giesekus VOF impacting drop", "rheoInterFoam"),
        ("使用 rheoFoam 计算", "rheoFoam"),
        ("使用 rheoInterFoam 计算", "rheoInterFoam"),
        ("使用 simpleFoam 计算", "simpleFoam"),
        ("使用 interFoam 计算", "interFoam"),
    ],
)
def test_business_prompts_compile_to_certified_solver(prompt, solver):
    compiled = compile_workflow(prompt)
    assert compiled.plan.target is not None
    assert compiled.plan.target.solver == solver


def test_complete_constitutive_parameters_are_ready():
    compiled = compile_workflow(
        "Oldroyd-B viscoelastic flow etaS=1 etaP=2 lambda=0.5"
    )
    assert compiled.plan.ready
    assert compiled.rheology.missing_parameters == ()


def test_foundation_pitzdaily_template_routes_to_simplefoam():
    compiled = compile_workflow(
        "OpenFOAM v10 pitzDaily 模板基线，牛顿流体后向台阶稳态回流区，使用模板原始参数"
    )

    assert compiled.plan.ready
    assert compiled.intent.reproduction_target == "foundation_v10_simplefoam_pitzdaily"
    assert compiled.plan.target.solver == "simpleFoam"


def test_foundation_pitzdaily_family_remains_unresolved_until_scope_selected():
    compiled = compile_workflow(
        "请复现 OpenFOAM v10 pitzDaily 教程族，输出后向台阶回流区和速度压力场"
    )

    assert not compiled.plan.ready
    assert compiled.intent.reproduction_target == "foundation_v10_pitzdaily_family"
    assert compiled.plan.workflow_type == "foundation-tutorial-family"
    assert compiled.plan.target is None


@pytest.mark.parametrize(
    ("prompt", "template_id", "solver"),
    [
        (
            "OpenFOAM v10 pitzDaily 选择 pimpleFoam/RAS 瞬态不可压缩变体，使用模板原始参数",
            "foundation_v10_pimplefoam_ras_pitzdaily",
            "pimpleFoam",
        ),
        (
            "OpenFOAM v10 pitzDaily 选择 pisoFoam LES 变体，使用模板原始参数",
            "foundation_v10_pisofoam_les_pitzdaily",
            "pisoFoam",
        ),
        (
            "OpenFOAM v10 pitzDaily 选择 potentialFoam 势流变体，使用模板原始参数",
            "foundation_v10_potentialfoam_pitzdaily",
            "potentialFoam",
        ),
        (
            "OpenFOAM v10 pitzDaily 选择 scalarTransportFoam 标量输运变体，使用模板原始参数",
            "foundation_v10_scalartransport_pitzdaily",
            "scalarTransportFoam",
        ),
    ],
)
def test_foundation_pitzdaily_executable_variant_routes_to_template(prompt, template_id, solver):
    compiled = compile_workflow(prompt)

    assert compiled.plan.ready
    assert compiled.intent.reproduction_target == template_id
    assert compiled.plan.workflow_type == "foundation-tutorial-template"
    assert compiled.plan.target.solver == solver


def test_foundation_pitzdaily_compressible_scope_is_outside_certified_matrix():
    compiled = compile_workflow(
        "使用 OpenFOAM v10 compressible rhoPimpleFoam pitzDaily LES 模板"
    )

    assert not compiled.plan.ready
    assert compiled.intent.reproduction_target == "foundation_v10_compressible_pitzdaily_unsupported"
    assert compiled.plan.target is None
    assert "outside the current certified solver matrix" in compiled.plan.rejection_reason


def test_foundation_cylinder_family_remains_unresolved_until_scope_selected():
    compiled = compile_workflow(
        "请复现 OpenFOAM v10 cylinder 教程族，输出速度压力场"
    )

    assert not compiled.plan.ready
    assert compiled.intent.reproduction_target == "foundation_v10_cylinder_family"
    assert compiled.plan.workflow_type == "foundation-tutorial-family"
    assert compiled.plan.target is None


@pytest.mark.parametrize(
    ("prompt", "template_id", "solver"),
    [
        (
            "OpenFOAM v10 cylinder 选择 potentialFoam 势流变体，使用模板原始参数",
            "foundation_v10_potentialfoam_cylinder",
            "potentialFoam",
        ),
        (
            "OpenFOAM v10 cylinder 选择 pimpleFoam offsetCylinder 层流绕流变体，使用模板原始参数",
            "foundation_v10_pimplefoam_laminar_offsetcylinder",
            "pimpleFoam",
        ),
        (
            "OpenFOAM v10 cylinder 选择 interFoam sloshingCylinder 自由液面变体，使用模板原始参数",
            "foundation_v10_interfoam_laminar_sloshingcylinder",
            "interFoam",
        ),
    ],
)
def test_foundation_cylinder_executable_variant_routes_to_template(prompt, template_id, solver):
    compiled = compile_workflow(prompt)

    assert compiled.plan.ready
    assert compiled.intent.reproduction_target == template_id
    assert compiled.plan.workflow_type == "foundation-tutorial-template"
    assert compiled.plan.target.solver == solver


def test_foundation_cylinder_compressible_scope_is_outside_certified_matrix():
    compiled = compile_workflow(
        "OpenFOAM v10 cylinder 选择 compressibleInterFoam 可压缩圆柱教程"
    )

    assert not compiled.plan.ready
    assert compiled.intent.reproduction_target == "foundation_v10_compressible_cylinder_unsupported"
    assert compiled.plan.target is None
    assert "compressibleInterFoam" in compiled.plan.rejection_reason
    assert "outside the current certified solver matrix" in compiled.plan.rejection_reason


def test_foundation_cavity_family_remains_unresolved_until_scope_selected():
    compiled = compile_workflow(
        "请复现 OpenFOAM v10 cavity 完整教程族，包含 cavityFine、cavityHighRe 和 mapFields"
    )

    assert not compiled.plan.ready
    assert compiled.intent.reproduction_target == "foundation_v10_icofoam_cavity_family"
    assert compiled.plan.workflow_type == "foundation-tutorial-family"
    assert compiled.plan.target is None


def test_foundation_cavity_full_allrun_scope_routes_to_icofoam_template():
    compiled = compile_workflow(
        "OpenFOAM v10 cavity 选择完整官方教程族 full_allrun，运行父目录 Allrun 和 mapFields"
    )

    assert compiled.plan.ready
    assert compiled.intent.reproduction_target == "foundation_v10_icofoam_cavity_full_allrun"
    assert compiled.plan.workflow_type == "foundation-tutorial-template"
    assert compiled.plan.target.solver == "icoFoam"


def test_foundation_dambreak_template_routes_to_interfoam():
    compiled = compile_workflow(
        "OpenFOAM v10 damBreak 模板基线，水-空气两相破坝自由液面，使用模板原始参数"
    )

    assert compiled.plan.ready
    assert compiled.intent.reproduction_target == "foundation_v10_interfoam_dambreak"
    assert compiled.plan.target.solver == "interFoam"


def test_foundation_dambreak_kuiba_alias_routes_to_laminar_baseline():
    compiled = compile_workflow(
        "我想使用平台已有 OpenFOAM v10 溃坝流模板做基线评估，使用模板原始参数。"
    )

    assert compiled.plan.ready
    assert compiled.intent.reproduction_target == "foundation_v10_interfoam_dambreak"
    assert compiled.plan.target.solver == "interFoam"


def test_foundation_dambreak_injected_ras_template_id_does_not_override_standard_baseline():
    compiled = compile_workflow(
        """
        Use the platform OpenFOAM v10 damBreak baseline template for computation.
        用户已确认参数使用方式：使用模板原始参数。
        tutorial_variant: standard damBreak tutorial
        template_id: foundation_v10_interfoam_ras_dambreak
        Requested Outputs: free_surface_evolution, water_front_advancement, pressure_field
        """
    )

    assert compiled.plan.ready
    assert compiled.intent.reproduction_target == "foundation_v10_interfoam_dambreak"
    assert compiled.plan.target.solver == "interFoam"


def test_foundation_dambreak_family_remains_unresolved_until_scope_selected():
    compiled = compile_workflow(
        "请复现 OpenFOAM v10 damBreak 教程族，输出自由液面和主要场文件"
    )

    assert not compiled.plan.ready
    assert compiled.intent.reproduction_target == "foundation_v10_dambreak_family"
    assert compiled.plan.workflow_type == "foundation-tutorial-family"
    assert compiled.plan.target is None


@pytest.mark.parametrize(
    ("prompt", "template_id"),
    [
        (
            "OpenFOAM v10 damBreak 选择 laminar full_allrun 完整教程族，使用模板原始参数",
            "foundation_v10_interfoam_dambreak_laminar_full_allrun",
        ),
        (
            "OpenFOAM v10 damBreak 选择 with obstacle 障碍物变体，使用模板原始参数",
            "foundation_v10_interfoam_dambreak_with_obstacle",
        ),
        (
            "OpenFOAM v10 damBreak 选择 RAS 湍流 baseline，使用模板原始参数",
            "foundation_v10_interfoam_ras_dambreak",
        ),
        (
            "OpenFOAM v10 damBreak 选择 RAS full_allrun 完整教程族，使用模板原始参数",
            "foundation_v10_interfoam_ras_dambreak_full_allrun",
        ),
        (
            "OpenFOAM v10 damBreak 选择 porous baffle 多孔挡板变体，使用模板原始参数",
            "foundation_v10_interfoam_ras_dambreak_porous_baffle",
        ),
    ],
)
def test_foundation_dambreak_executable_variant_routes_to_interfoam(prompt, template_id):
    compiled = compile_workflow(prompt)

    assert compiled.plan.ready
    assert compiled.intent.reproduction_target == template_id
    assert compiled.plan.workflow_type == "foundation-tutorial-template"
    assert compiled.plan.target.solver == "interFoam"


@pytest.mark.parametrize(
    ("prompt", "expected_reason"),
    [
        (
            "OpenFOAM v10 damBreak 选择 interMixingFoam 三相混合破坝教程",
            "interMixingFoam",
        ),
        (
            "OpenFOAM v10 damBreak 选择 compressibleInterFoam 可压缩破坝教程",
            "compressibleInterFoam",
        ),
    ],
)
def test_foundation_dambreak_unsupported_variants_are_outside_certified_matrix(prompt, expected_reason):
    compiled = compile_workflow(prompt)

    assert not compiled.plan.ready
    assert compiled.plan.target is None
    assert expected_reason in compiled.plan.rejection_reason


def test_foundation_forwardstep_family_remains_unresolved_until_scope_selected():
    compiled = compile_workflow(
        "请复现 OpenFOAM v10 forwardStep 可压缩教程族，输出压力温度和速度场"
    )

    assert not compiled.plan.ready
    assert compiled.intent.reproduction_target == "foundation_v10_forwardstep_family"
    assert compiled.plan.workflow_type == "foundation-tutorial-family"
    assert compiled.plan.target is None


@pytest.mark.parametrize(
    ("prompt", "template_id", "solver"),
    [
        (
            "OpenFOAM v10 forwardStep 选择 rhoCentralFoam 高速可压缩变体，使用模板原始参数",
            "foundation_v10_rhocentralfoam_forwardstep",
            "rhoCentralFoam",
        ),
        (
            "OpenFOAM v10 forwardStep 选择 rhoPimpleFoam laminar 层流瞬态可压缩变体，使用模板原始参数",
            "foundation_v10_rhopimplefoam_laminar_forwardstep",
            "rhoPimpleFoam",
        ),
    ],
)
def test_foundation_forwardstep_executable_variant_routes_to_template(prompt, template_id, solver):
    compiled = compile_workflow(prompt)

    assert compiled.plan.ready
    assert compiled.intent.reproduction_target == template_id
    assert compiled.plan.workflow_type == "foundation-tutorial-template"
    assert compiled.plan.target.solver == solver


def test_foundation_bernardcells_template_routes_to_buoyantfoam():
    compiled = compile_workflow(
        "请复现 OpenFOAM v10 Rayleigh-Benard / BernardCells buoyantFoam 教程，"
        "使用模板原始参数，输出温度场和速度场"
    )

    assert compiled.plan.ready
    assert compiled.intent.reproduction_target == "foundation_v10_buoyantfoam_bernardcells"
    assert compiled.plan.workflow_type == "foundation-tutorial-template"
    assert compiled.plan.target.solver == "buoyantFoam"


@pytest.mark.parametrize(
    ("prompt", "template_id", "solver"),
    [
        (
            "请复现 OpenFOAM v10 pimpleFoam planarPoiseuille 平面泊肃叶流教程，使用模板原始参数",
            "foundation_v10_pimplefoam_laminar_planarpoiseuille",
            "pimpleFoam",
        ),
        (
            "请复现 OpenFOAM v10 rhoCentralFoam obliqueShock 斜激波教程，使用模板原始参数",
            "foundation_v10_rhocentralfoam_obliqueshock",
            "rhoCentralFoam",
        ),
        (
            "请复现 OpenFOAM v10 rhoCentralFoam shockTube 激波管教程，使用模板原始参数",
            "foundation_v10_rhocentralfoam_shocktube",
            "rhoCentralFoam",
        ),
        (
            "请复现 OpenFOAM v10 rhoPimpleFoam laminar shockTube 激波管教程，使用模板原始参数",
            "foundation_v10_rhopimplefoam_laminar_shocktube",
            "rhoPimpleFoam",
        ),
        (
            "请复现 OpenFOAM v10 simpleFoam airFoil2D 翼型教程，使用模板原始参数",
            "foundation_v10_simplefoam_airfoil2d",
            "simpleFoam",
        ),
        (
            "请复现 OpenFOAM v10 interFoam capillaryRise 毛细上升教程，使用模板原始参数",
            "foundation_v10_interfoam_laminar_capillaryrise",
            "interFoam",
        ),
        (
            "请复现 OpenFOAM v10 interFoam wave 波浪教程，使用模板原始参数",
            "foundation_v10_interfoam_laminar_wave",
            "interFoam",
        ),
    ],
)
def test_additional_foundation_v10_templates_route_to_expected_solver(prompt, template_id, solver):
    compiled = compile_workflow(prompt)

    assert compiled.plan.ready
    assert compiled.intent.reproduction_target == template_id
    assert compiled.plan.workflow_type == "foundation-tutorial-template"
    assert compiled.plan.target.solver == solver


def test_carreau_yasuda_uses_k_not_relaxation_lambda():
    compiled = compile_workflow(
        "RheoTool 5.1.9 fluidDamper/CarreauYasuda 广义牛顿剪切变稀阻尼器 "
        "eta0=100 etaInf=0 k=0.0084033613 n=0.353 a=1.433"
    )

    assert compiled.plan.target is not None
    assert compiled.plan.target.solver == "rheoFoam"
    assert compiled.intent.reproduction_target == "rheotool_5_1_9_fluiddamper_carreauyasuda"
    assert compiled.rheology.behavior == "generalized-newtonian"
    assert compiled.rheology.missing_parameters == ()
    assert "newtonian_and_rheological" not in compiled.intent.contradictions


def test_carreau_yasuda_legacy_lambda_alias_maps_to_k():
    compiled = compile_workflow(
        "RheoTool 5.1.9 fluidDamper/CarreauYasuda moving mesh "
        "nu0=100 nuInf=0 lambda=0.0084033613 n=0.353 a=1.433"
    )

    assert compiled.plan.target is not None
    assert compiled.plan.target.solver == "rheoFoam"
    assert compiled.rheology.parameters["k"] == 0.0084033613
    assert compiled.rheology.missing_parameters == ()


def test_constitutive_parameter_aliases_are_parsed():
    compiled = compile_workflow(
        "Oldroyd-B viscoelastic channel flow ηs=0.01 ηp=0.99 λ=1.0"
    )
    assert compiled.plan.ready
    assert compiled.rheology.parameters == {
        "etaS": 0.01,
        "etaP": 0.99,
        "lambda": 1.0,
    }
    assert compiled.rheology.missing_parameters == ()




def test_oldroyd_parameters_are_derived_from_beta_and_eta0():
    compiled = compile_workflow(
        "Oldroyd-B lid-driven cavity beta=0.5 eta0=1 lambda=1 geometry square L=1 inlet velocity=1"
    )

    assert compiled.rheology.parameters["etaS"] == 0.5
    assert compiled.rheology.parameters["etaP"] == 0.5
    assert compiled.rheology.parameters["lambda"] == 1.0
    assert compiled.rheology.missing_parameters == ()


@pytest.mark.parametrize(
    "beta_text",
    [
        "beta = etaS/eta0: 0.5",
        "beta = eta_s / eta0 : 0.5",
        "β = ηs / η0 : 0.5",
        "beta (etaS/eta0) = 0.5",
        "beta: 0.5",
    ],
)
def test_dimensionless_beta_definition_variants_are_parsed(beta_text):
    compiled = compile_workflow(
        "Oldroyd-B 顶盖驱动方腔 "
        f"{beta_text} De=1 Re=0.01 etaS=0.5 etaP=0.5 lambda=1"
    )

    assert compiled.intent.dimensionless_groups["beta"] == 0.5
    assert compiled.intent.reproduction_target == "rheotool_5_1_4_cavity_oldroydb_log"


def test_dimensionless_beta_is_inferred_from_user_viscosities():
    compiled = compile_workflow(
        "Oldroyd-B 顶盖驱动方腔 De=1 Re=0.01 etaS=0.5 etaP=0.5 lambda=1"
    )

    assert compiled.intent.dimensionless_groups["beta"] == 0.5
    assert compiled.intent.reproduction_target == "rheotool_5_1_4_cavity_oldroydb_log"


def test_dimensionless_formula_assignment_variants_are_parsed():
    compiled = compile_workflow(
        """
        Oldroyd-B 顶盖驱动方腔。
        beta: etaS/eta0 = 0.5
        De: lambda*U/L = 1
        Re: rho*U*L/eta0 = 0.01
        etaS=0.5 etaP=0.5 lambda=1
        """
    )

    assert compiled.intent.dimensionless_groups == {"beta": 0.5, "De": 1.0, "Re": 0.01}
    assert compiled.intent.reproduction_target == "rheotool_5_1_4_cavity_oldroydb_log"


def test_llm_dimensionless_extractor_supplements_only_grounded_fields(monkeypatch):
    from services import requirement_structured_extractor as extractor

    def fake_extract(_text):
        return extractor.RequirementStructuredExtraction(
            dimensionless_groups={
                "De": extractor.ExtractedScalar(value=1.0, evidence="Deborah number is one"),
                "Re": extractor.ExtractedScalar(value=0.01, evidence="Reynolds number is 0.01"),
                "Wi": extractor.ExtractedScalar(value=99.0, evidence="not copied from the prompt"),
            }
        )

    monkeypatch.setenv("FOAMAGENT_ENABLE_LLM_STRUCTURED_EXTRACTOR", "1")
    monkeypatch.setattr(extractor, "extract_requirement_with_llm", fake_extract)

    compiled = compile_workflow(
        "Oldroyd-B 顶盖驱动方腔 beta=0.5 etaS=0.5 etaP=0.5 lambda=1; "
        "Deborah number is one; Reynolds number is 0.01."
    )

    assert compiled.intent.dimensionless_groups == {"beta": 0.5, "De": 1.0, "Re": 0.01}
    assert "Wi" not in compiled.intent.dimensionless_groups
    assert compiled.intent.reproduction_target == "rheotool_5_1_4_cavity_oldroydb_log"


def test_oldroyd_parameters_parse_unicode_subscripts_and_whitespace_assignments():
    compiled = compile_workflow(
        "Oldroyd-B viscoelastic flow ηₛ 0.5 ηₚ 0.5 λ 1"
    )

    assert compiled.rheology.parameters == {"etaS": 0.5, "etaP": 0.5, "lambda": 1.0}
    assert compiled.rheology.missing_parameters == ()

def test_missing_constitutive_parameters_require_clarification_without_fabrication():
    compiled = compile_workflow("Oldroyd-B viscoelastic flow")
    assert not compiled.plan.ready
    assert compiled.rheology.parameters == {}
    assert compiled.rheology.missing_parameters == ("etaS", "etaP", "lambda")
    assert "etaS" in compiled.plan.clarification_questions[0]


def test_generic_rheology_requires_a_constitutive_model():
    compiled = compile_workflow("聚合物粘弹性流动")
    assert compiled.plan.target.solver == "rheoFoam"
    assert not compiled.plan.ready
    assert compiled.intent.missing_critical_fields == ("constitutive_model",)


def test_conflicting_physics_requires_clarification():
    compiled = compile_workflow("稳态和瞬态牛顿粘弹性流动")
    assert not compiled.plan.ready
    assert len(compiled.intent.contradictions) == 2


def test_unsupported_physics_is_rejected():
    compiled = compile_workflow("可压缩燃烧传热模拟")
    assert compiled.plan.target is None
    assert compiled.plan.rejection_reason


def test_ambiguous_standard_flow_requires_business_clarification():
    compiled = compile_workflow("模拟普通不可压缩管流")
    assert compiled.plan.target is None
    assert not compiled.plan.ready
    assert compiled.plan.clarification_questions


def test_negated_two_phase_fields_do_not_route_single_phase_water_to_interfoam():
    compiled = compile_workflow(
        """
        水在微管中的稳态压降
        geometry pipe diameter=0.001 length=0.1 inlet velocity=0.001
        model: Newtonian parameters: nu=1e-6 rho=1000
        free surface: no
        surface tension: not applicable
        water-air material card: not applicable; single phase water only
        """
    )

    assert compiled.physics.phase_type == "single-phase"
    assert compiled.physics.free_surface is False
    assert compiled.plan.target is not None
    assert compiled.plan.target.solver == "simpleFoam"


def test_case_target_accepts_certified_buoyantfoam_solver():
    target = CaseTarget.for_solver("buoyantFoam")

    assert target.channel == "v10-foundation"
    assert target.solver == "buoyantFoam"


def test_negated_newtonian_terms_do_not_conflict_with_explicit_viscoelastic_model():
    prompts = [
        "Oldroyd-B non-Newtonian viscoelastic flow etaS=0.5 etaP=0.5 lambda=1",
        "Oldroyd-B NOT Newtonian viscoelastic flow etaS=0.5 etaP=0.5 lambda=1",
        "Oldroyd-B 非牛顿 粘弹性流动 etaS=0.5 etaP=0.5 lambda=1",
    ]
    for prompt in prompts:
        compiled = compile_workflow(prompt)
        assert compiled.plan.ready
        assert "newtonian_and_rheological" not in compiled.intent.contradictions
        assert compiled.intent.newtonian_evidence == ()
        assert compiled.plan.target.solver == "rheoFoam"


def test_positive_newtonian_still_conflicts_with_viscoelastic_claim():
    compiled = compile_workflow("牛顿粘弹性聚合物流动 etaS=0.5 etaP=0.5 lambda=1")
    assert not compiled.plan.ready
    assert "newtonian_and_rheological" in compiled.intent.contradictions



def test_rude_class_text_does_not_force_certified_benchmark_when_physics_conflicts():
    compiled = compile_workflow(
        "Oldroyd-B RUDE-class lid-driven cavity flow etaS=0.5 etaP=0.5 lambda=1 "
        "Fattal Kupferman 2005 benchmark"
    )

    assert compiled.plan.target is not None
    assert compiled.plan.target.solver == "rheoFoam"
    assert compiled.plan.workflow_type != "certified-benchmark"
    assert compiled.rheology.selected_model == "Oldroyd-B"
