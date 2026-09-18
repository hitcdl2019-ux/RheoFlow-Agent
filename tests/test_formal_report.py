from __future__ import annotations

import base64
import json
from pathlib import Path
from zipfile import ZipFile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.formal_report import generate_formal_case_report_docx  # noqa: E402


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _write_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG_1X1)


def test_generate_formal_case_report_docx_without_audit_appendix(tmp_path):
    case = tmp_path / "case"
    (case / "postprocess").mkdir(parents=True)
    manifest = {
        "solver": "rheoFoam",
        "channel": "v9-rheotool",
        "version": "v9",
        "distribution": "foundation+rheotool",
        "validation_status": "passed",
        "run_status": "passed",
        "problem_intent": {
            "application": "复现 RheoTool 平行平板通道 benchmark，Re=0 Wi=0.99 beta=0.01，参数 etaS/etaP/lambda 均为 user_provided。"
        },
        "rheology_spec": {
            "selected_model": "Oldroyd-B",
            "parameters": {"etaS": 0.01, "etaP": 0.99, "lambda": 1.0},
        },
        "physics_spec": {"phase_type": "single-phase", "transient": False},
        "workflow_plan": {
            "target": {
                "channel": "v9-rheotool",
                "version": "v9",
                "solver": "rheoFoam",
                "distribution": "foundation+rheotool",
            }
        },
    }
    (case / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    post = {
        "status": "passed",
        "samples": {"status": "present"},
        "rheotool_channel_comparison": {
            "errors": {
                "Ux": {"max_abs": 1e-3, "mean_abs": 5e-4, "rmse": 6e-4},
                "tau_xx": {"max_abs": 3e-2, "mean_abs": 6e-3, "rmse": 9e-3},
                "tau_xy": {"max_abs": 3e-2, "mean_abs": 1e-2, "rmse": 2e-2},
            }
        },
        "metrics": {
            "residuals": {
                "fields": {
                    "Ux": {"final_max": 1e-10, "count": 10},
                    "p": {"final_max": 1e-10, "count": 10},
                }
            }
        },
    }
    (case / "POSTPROCESS_REPORT.json").write_text(json.dumps(post, ensure_ascii=False), encoding="utf-8")
    for name in [
        "residuals.png",
        "lineX35_oldroydb_analytic_comparison.png",
        "visualization_U.png",
        "visualization_tau.png",
        "centerline_U.png",
        "centerline_tau.png",
    ]:
        _write_png(case / "postprocess" / name)
    (case / "POSTPROCESS_ARTIFACTS.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {"kind": "residual_plot", "path": str(case / "postprocess" / "residuals.png")},
                    {
                        "kind": "rheotool_channel_comparison_plot",
                        "path": str(case / "postprocess" / "lineX35_oldroydb_analytic_comparison.png"),
                    },
                    {"kind": "field_plot:U", "path": str(case / "postprocess" / "visualization_U.png")},
                    {"kind": "field_plot:tau", "path": str(case / "postprocess" / "visualization_tau.png")},
                    {"kind": "centerline_plot:U", "path": str(case / "postprocess" / "centerline_U.png")},
                    {"kind": "centerline_plot:tau", "path": str(case / "postprocess" / "centerline_tau.png")},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output = generate_formal_case_report_docx(case, platform_version="test-image@sha256:abc")

    assert output.is_file()
    with ZipFile(output) as archive:
        names = set(archive.namelist())
        document = archive.read("word/document.xml").decode("utf-8")
        styles = archive.read("word/styles.xml").decode("utf-8")
    assert "1. 物理问题定义与工程背景" in document
    assert "1.1 问题背景与物理模型描述" in document
    assert "1.2 数值模拟关键挑战" in document
    assert "1.3 核心技术指标与交付要求" in document
    assert "1.4 模型范围与输入约束" in document
    assert "1.1 需求背景与物理问题描述" not in document
    assert "1.2 物理场景与计算目标拆解" not in document
    assert "1.3 材料与本构" not in document
    assert "2. 数值建模方案与计算实施" in document
    assert "3. 模拟结果分析与讨论" in document
    assert "智能体针对用户问题怎么做" not in document
    assert "审计附录" not in document
    assert "微软雅黑" in styles
    assert "Arial" in styles
    assert 'w:styleId="Caption"' in styles
    assert 'w:color w:val="1F4E79"' in styles
    assert 'w:shd w:fill="1F4E79"' in document
    assert "结论摘要" in document
    assert "tblCellMar" in document
    assert len([name for name in names if name.startswith("word/media/")]) == 6


def test_generate_formal_case_report_docx_for_cavity_is_not_channel_hardcoded(tmp_path):
    case = tmp_path / "cavity"
    (case / "postprocess").mkdir(parents=True)
    (case / "system").mkdir()
    (case / "system" / "blockMeshDict").write_text(
        "blocks ( hex (0 1 2 3 4 5 6 7) (127 127 1) simpleGrading (1 1 1) );",
        encoding="utf-8",
    )
    (case / "system" / "controlDict").write_text("endTime         10;\n", encoding="utf-8")
    manifest = {
        "solver": "rheoFoam",
        "channel": "v9-rheotool",
        "version": "v9",
        "distribution": "foundation+rheotool",
        "validation_status": "passed",
        "run_status": "passed",
        "problem_intent": {
            "application": """Oldroyd-B 顶盖驱动方腔，De: lambda*U/L = 1，Re: rho*U*L/eta0 = 0.01，beta: etaS/eta0 = 0.5，end_time: 8，参数均为 user_provided。
请输出：
1. x=0.5 处的 u(y) 速度剖面；
2. y=0.75 处的 Θxy 剖面；
3. 平均动能 Ek(t) 的全程曲线。""",
            "geometry_class": "lid_driven_cavity",
            "objectives": ["velocity_profile", "theta_profile", "kinetic_energy"],
        },
        "rheology_spec": {
            "selected_model": "Oldroyd-B",
            "parameters": {"etaS": 0.5, "etaP": 0.5, "lambda": 1.0},
        },
        "physics_spec": {"phase_type": "single-phase", "transient": True, "objectives": ["velocity_profile", "theta_profile", "kinetic_energy"]},
        "workflow_plan": {
            "target": {
                "channel": "v9-rheotool",
                "version": "v9",
                "solver": "rheoFoam",
                "distribution": "foundation+rheotool",
            }
        },
    }
    (case / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    post = {
        "status": "passed",
        "latest_time": "10",
        "sampleDict": {"status": "passed"},
        "samples": {"status": "present"},
        "kinetic_energy": {"status": "passed", "rho_source": "default", "last": {"kinetic_energy_average": 0.01}},
        "benchmark_comparison": {"status": "skipped"},
        "metrics": {"residuals": {"fields": {"Ux": {"final_max": 1e-10, "count": 5}}}},
    }
    (case / "POSTPROCESS_REPORT.json").write_text(json.dumps(post, ensure_ascii=False), encoding="utf-8")
    (case / "TUTORIAL_TEMPLATE_IMPORT.json").write_text(
        json.dumps({"template_id": "rheotool_5_1_4_cavity_oldroydb_log", "tier": "A", "import_policy": "template import"}, ensure_ascii=False),
        encoding="utf-8",
    )
    for name in ["residuals.png", "kinetic_energy.png", "visualization_U.png"]:
        _write_png(case / "postprocess" / name)
    (case / "postprocess" / "kinetic_energy.csv").write_text("time,kinetic_energy_average\n0,0\n10,0.01\n", encoding="utf-8")
    for name in [
        "postProcessing/sampleDict/10/lineVert_x0.5_U.xy",
        "postProcessing/sampleDict/10/lineHorz_y0.75_tau_theta.xy",
    ]:
        path = case / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("0 0\n", encoding="utf-8")
    (case / "POSTPROCESS_ARTIFACTS.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {"kind": "residual_plot", "path": str(case / "postprocess" / "residuals.png")},
                    {"kind": "kinetic_energy_csv", "path": str(case / "postprocess" / "kinetic_energy.csv")},
                    {"kind": "kinetic_energy_plot", "path": str(case / "postprocess" / "kinetic_energy.png")},
                    {"kind": "field_plot:U", "path": str(case / "postprocess" / "visualization_U.png")},
                    {"kind": "sample", "path": str(case / "postProcessing" / "sampleDict" / "10" / "lineVert_x0.5_U.xy")},
                    {"kind": "sample", "path": str(case / "postProcessing" / "sampleDict" / "10" / "lineHorz_y0.75_tau_theta.xy")},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output = generate_formal_case_report_docx(case)

    with ZipFile(output) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    assert "顶盖驱动方腔" in document
    assert "平行平板通道" not in document
    assert "用户需求中的结束时间约为 t=8" in document
    assert "未发现本地逐点参考数据" in document
    assert "x=0.5" in document
    assert "u(y)" in document
    assert "y=0.75" in document
    assert "Θxy" in document
    assert "Ek(t)" in document
    assert "用户问题/要求" in document
    assert "x=0.5 处的 u(y) 速度剖面" in document
    assert "y=0.75 处的 Θxy 剖面" in document
    assert "平均动能 Ek(t) 的全程曲线" in document
    assert "lineVert_x0.5_U.xy" in document
    assert "lineHorz_y0.75_tau_theta.xy" in document
    assert "kinetic_energy.png" in document

def test_generate_formal_case_report_answers_dieswell_swell_ratio(tmp_path):
    case = tmp_path / "dieswell"
    (case / "postprocess").mkdir(parents=True)
    manifest = {
        "solver": "rheoInterFoam",
        "channel": "v9-rheotool",
        "version": "v9",
        "distribution": "foundation+rheotool",
        "validation_status": "passed",
        "run_status": "passed",
        "problem_intent": {
            "application": """评估一种聚合物熔体从平面狭缝口模挤出后的胀大程度。
requested_output: extrudate swell ratio (胀大比)""",
            "geometry_class": "die_swell",
            "objectives": ["free_surface"],
        },
        "physics_spec": {"phase_type": "two-phase", "transient": True, "free_surface": True, "objectives": ["free_surface"]},
        "rheology_spec": {"selected_model": "Oldroyd-B", "parameters": {"lambda": 2.0}},
        "workflow_plan": {
            "target": {
                "channel": "v9-rheotool",
                "version": "v9",
                "solver": "rheoInterFoam",
                "distribution": "foundation+rheotool",
            }
        },
    }
    (case / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    metrics = case / "postprocess" / "dieswell_swell_metrics.json"
    plot = case / "postprocess" / "dieswell_free_surface_swell_ratio.png"
    metrics.write_text('{"swell_ratio": 1.58}', encoding="utf-8")
    _write_png(plot)
    post = {
        "status": "passed",
        "latest_time": "120",
        "dieswell_free_surface": {
            "status": "passed",
            "swell_ratio": 1.58,
            "max_location": {"x": 18.3, "y": 1.58, "z": 0.0},
        },
        "metrics": {"residuals": {"fields": {"alpha.water": {"final_max": 1e-8, "count": 10}}}},
    }
    (case / "POSTPROCESS_REPORT.json").write_text(json.dumps(post, ensure_ascii=False), encoding="utf-8")
    (case / "POSTPROCESS_ARTIFACTS.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {"kind": "dieswell_swell_metrics", "path": str(metrics)},
                    {"kind": "dieswell_free_surface_plot", "path": str(plot)},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output = generate_formal_case_report_docx(case)

    with ZipFile(output) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    assert "extrudate swell ratio" in document
    assert "胀大比" in document
    assert "1.58" in document
    assert "dieswell_swell_metrics.json" in document
    assert "2.1 问题类型与计算方案" in document
    assert "2.4.1 DieSwell 控制方程与物性参数" in document
    assert "图 R3 完成态自由液面与最大胀大位置" in document
    assert "该指标是本案例的核心定量交付结果" in document
    assert "用途：直接回答" not in document
    assert "读图方法：" not in document
    assert "说明结论：" not in document


def test_generate_formal_case_report_docx_for_dambreak_uses_common_skeleton_and_plugin(tmp_path):
    case = tmp_path / "dambreak"
    (case / "postprocess").mkdir(parents=True)
    manifest = {
        "solver": "interFoam",
        "channel": "v10-foundation",
        "version": "v10",
        "distribution": "foundation",
        "validation_status": "passed",
        "run_status": "passed",
        "problem_intent": {
            "application": """# Foam-Agent user_requirement.txt

## User Goal
Simulate the sudden collapse of a water column and its impact on the downstream region, capturing free-surface evolution, water-front advancement, and pressure distribution. Use the platform OpenFOAM v10 damBreak baseline template for computation. Produce a formal report containing free-surface evolution, velocity field, pressure field, final time, and main result file locations.

## User Confirmation
用户已确认参数使用方式：使用模板原始参数（推荐）。

## Task Mode
- task_mode: platform_baseline_template
- tutorial_family: OpenFOAM v10 damBreak
- tutorial_variant: standard damBreak tutorial
- parameter_policy: 使用模板原始参数（推荐）
- template_id: foundation_v10_interfoam_ras_dambreak
""",
            "geometry_class": "dam_break",
            "reproduction_target": "foundation_v10_interfoam_dambreak",
            "objectives": ["free_surface"],
        },
        "physics_spec": {"phase_type": "two-phase", "transient": True, "free_surface": True, "objectives": ["free_surface"]},
        "rheology_spec": {"selected_model": None, "parameters": {}},
        "workflow_plan": {
            "target": {
                "channel": "v10-foundation",
                "version": "v10",
                "solver": "interFoam",
                "distribution": "foundation",
            }
        },
    }
    (case / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    post = {
        "status": "passed",
        "latest_time": "1",
        "dambreak_free_surface": {
            "status": "passed",
            "front_x": 2.5,
            "max_height": 0.9,
            "front_location": {"x": 2.5, "y": 0.2, "z": 0.0},
        },
        "metrics": {"residuals": {"fields": {"alpha.water": {"final_max": 1e-8, "count": 3}}}},
    }
    (case / "POSTPROCESS_REPORT.json").write_text(json.dumps(post, ensure_ascii=False), encoding="utf-8")
    (case / "TUTORIAL_TEMPLATE_IMPORT.json").write_text(
        json.dumps({"template_id": "foundation_v10_interfoam_dambreak", "tier": "A"}, ensure_ascii=False),
        encoding="utf-8",
    )
    for name in [
        "dambreak_free_surface_initial_final_overlay.png",
        "dambreak_free_surface_front.png",
        "dambreak_front_x_vs_time.png",
        "dambreak_alpha_water_initial.png",
        "dambreak_alpha_water_final.png",
        "dambreak_U_initial.png",
        "dambreak_U_final.png",
        "dambreak_p_rgh_initial.png",
        "dambreak_p_rgh_final.png",
    ]:
        _write_png(case / "postprocess" / name)
    (case / "POSTPROCESS_ARTIFACTS.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "kind": "dambreak_free_surface_overlay",
                        "path": str(case / "postprocess" / "dambreak_free_surface_initial_final_overlay.png"),
                    },
                    {"kind": "dambreak_free_surface_plot", "path": str(case / "postprocess" / "dambreak_free_surface_front.png")},
                    {"kind": "dambreak_front_history_plot", "path": str(case / "postprocess" / "dambreak_front_x_vs_time.png")},
                    {"kind": "dambreak_field_snapshot:alpha.water:initial", "path": str(case / "postprocess" / "dambreak_alpha_water_initial.png")},
                    {"kind": "dambreak_field_snapshot:alpha.water:final", "path": str(case / "postprocess" / "dambreak_alpha_water_final.png")},
                    {"kind": "dambreak_field_snapshot:U:initial", "path": str(case / "postprocess" / "dambreak_U_initial.png")},
                    {"kind": "dambreak_field_snapshot:U:final", "path": str(case / "postprocess" / "dambreak_U_final.png")},
                    {"kind": "dambreak_field_snapshot:p_rgh:initial", "path": str(case / "postprocess" / "dambreak_p_rgh_initial.png")},
                    {"kind": "dambreak_field_snapshot:p_rgh:final", "path": str(case / "postprocess" / "dambreak_p_rgh_final.png")},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output = generate_formal_case_report_docx(case)

    with ZipFile(output) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    assert "1. 物理问题定义与工程背景" in document
    assert "1.1 问题背景与物理模型描述" in document
    assert "# Foam-Agent user_requirement.txt" not in document
    assert "## Task Mode" not in document
    assert "task_mode: platform_baseline_template" not in document
    assert "foundation_v10_interfoam_ras_dambreak" not in document
    assert "Simulate the sudden collapse of a water column" in document
    assert "本案例关注水柱突然坍塌后的两相自由液面流动" in document
    assert "1.2 数值模拟关键挑战" in document
    assert "1.3 核心技术指标与交付要求" in document
    assert "1.4 模型范围与输入约束" in document
    assert "1.1 需求背景与物理问题描述" not in document
    assert "1.2 物理场景与计算目标拆解" not in document
    assert "1.3 材料与本构" not in document
    assert "2. 数值建模方案与计算实施" in document
    assert "3. 模拟结果分析与讨论" in document
    assert "溃坝自由液面流动" in document
    assert "2.4.1 damBreak 自由液面模型说明" in document
    assert "3.2.1 自由液面与水体前沿" in document
    assert "图 R1 自由液面初始态—中间态—完成态叠加" in document
    assert "图 R2 完成态 alpha.water=0.5 自由液面与水体前沿" in document
    assert "front_x≈2.5" in document
    assert "图 R3 水体前沿位置随时间变化" in document
    assert "图 R4 alpha.water 相分数场" in document
    assert "图 R5 速度场 |U|" in document
    assert "图 R6 压力场" in document


def test_formal_report_never_marks_requested_output_as_generic_summary(tmp_path):
    case = tmp_path / "unknown_output"
    case.mkdir()
    manifest = {
        "solver": "simpleFoam",
        "channel": "v10-foundation",
        "version": "v10",
        "distribution": "foundation",
        "validation_status": "passed",
        "run_status": "passed",
        "problem_intent": {
            "application": "水在管道中的稳态压降\nrequested_output: custom_business_metric",
            "objectives": [],
        },
        "physics_spec": {"phase_type": "single-phase", "transient": False, "objectives": []},
        "rheology_spec": {"selected_model": None, "parameters": {}},
        "workflow_plan": {
            "target": {
                "channel": "v10-foundation",
                "version": "v10",
                "solver": "simpleFoam",
                "distribution": "foundation",
            }
        },
    }
    (case / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (case / "POSTPROCESS_REPORT.json").write_text(json.dumps({"status": "passed", "latest_time": "1", "metrics": {}}, ensure_ascii=False), encoding="utf-8")
    (case / "POSTPROCESS_ARTIFACTS.json").write_text(json.dumps({"artifacts": []}), encoding="utf-8")

    output = generate_formal_case_report_docx(case)

    with ZipFile(output) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    assert "custom_business_metric" in document
    assert "未生成明确答案" in document
    assert "custom_business_metric</w:t></w:r></w:p></w:tc><w:tc><w:tcPr><w:tcW w:w=\"0\" w:type=\"auto\"/></w:tcPr><w:p><w:r><w:t>已汇总" not in document
