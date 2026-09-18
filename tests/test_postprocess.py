from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.postprocess import run_standard_postprocess  # noqa: E402
from nodes import visualization_node as viz_node  # noqa: E402


def _write_pressure_field(path: Path) -> None:
    path.write_text(
        """
FoamFile{}
dimensions      [0 2 -2 0 0 0 0];
internalField   nonuniform List<scalar>
3
(
3.2
2.0
0.1
)
;
boundaryField
{
    inlet
    {
        type fixedValue;
        value uniform 3.2;
    }
    outlet
    {
        type fixedValue;
        value uniform 0.1;
    }
}
// ************************************************************************* //
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_u_field(path: Path, internal_field: str) -> None:
    path.write_text(
        f"""
FoamFile{{}}
dimensions      [0 1 -1 0 0 0 0];
internalField   {internal_field}
boundaryField{{}}
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_xy(path: Path) -> None:
    path.write_text(
        "0.0 1.0 0.0 0.0\n"
        "0.5 0.7 -0.1 0.0\n"
        "1.0 0.1 -0.2 0.0\n",
        encoding="utf-8",
    )


def _write_minimal_sample_case(case_dir: Path) -> None:
    (case_dir / "10").mkdir(parents=True)
    (case_dir / "10" / "U").write_text("FoamFile{}\n", encoding="utf-8")
    _write_pressure_field(case_dir / "10" / "p")
    (case_dir / "system").mkdir()
    (case_dir / "system" / "sampleDict").write_text("FoamFile{}\n", encoding="utf-8")
    sample = case_dir / "postProcessing" / "sampleDict" / "10"
    sample.mkdir(parents=True)
    _write_xy(sample / "lBeforex0_U.xy")
    _write_xy(sample / "lAfterx0_U.xy")
    (case_dir / "manifest.json").write_text(
        json.dumps(
            {
                "channel": "v9-rheotool",
                "version": "v9",
                "solver": "rheoFoam",
                "run_status": "failed",
            }
        ),
        encoding="utf-8",
    )
    (case_dir / "log.rheoFoam").write_text(
        "Solving for Ux, Initial residual = 0.1, Final residual = 1e-06, No Iterations 2\n"
        "Solving for p, Initial residual = 0.2, Final residual = 2e-05, No Iterations 3\n"
        "End\n",
        encoding="utf-8",
    )


def _write_rheotool_channel_sample_case(case_dir: Path) -> None:
    (case_dir / "30").mkdir(parents=True)
    (case_dir / "30" / "U").write_text("FoamFile{}\n", encoding="utf-8")
    (case_dir / "system").mkdir()
    (case_dir / "system" / "sampleDict").write_text("FoamFile{}\n", encoding="utf-8")
    (case_dir / "constant").mkdir()
    (case_dir / "constant" / "constitutiveProperties").write_text(
        "parameters\n{\n    etaP 0.99;\n    lambda 1;\n}\n",
        encoding="utf-8",
    )
    sample = case_dir / "postProcessing" / "sampleDict" / "30"
    sample.mkdir(parents=True)
    sample.joinpath("lineX35_U.xy").write_text(
        "-1 0 0 0\n"
        "0 1.5 0 0\n"
        "1 0 0 0\n",
        encoding="utf-8",
    )
    sample.joinpath("lineX35_tau.xy").write_text(
        "-1 17.82 3 0 0 0 0\n"
        "0 0 0 0 0 0 0\n"
        "1 17.82 -3 0 0 0 0\n",
        encoding="utf-8",
    )
    (case_dir / "manifest.json").write_text(
        json.dumps({"channel": "v9-rheotool", "version": "v9", "solver": "rheoFoam", "run_status": "passed"}),
        encoding="utf-8",
    )


def test_standard_postprocess_writes_report_and_rude_line_plot(tmp_path):
    case_dir = tmp_path / "rude-postprocess"
    _write_minimal_sample_case(case_dir)

    report = run_standard_postprocess(
        case_dir,
        user_requirement="复现 RUDE 图 4 曲线并输出后处理报告",
        fields=(),
        run_openfoam_sample=False,
    )

    assert report["status"] == "passed"
    assert report["latest_time"] == "10"
    assert report["postprocess_plan"]["metrics"] == [
        "pressure",
        "residuals",
        "kinetic_energy",
        "generic_centerline_pressure_drop_if_available",
    ]
    assert report["metrics"]["pressure"]["pressure_drop"] == 3.1
    assert report["metrics"]["residuals"]["fields"]["p"]["final_max"] == 2e-05
    assert report["residual_plot"]["status"] == "passed"
    assert report["line_plot"]["status"] == "passed"
    assert (case_dir / "postprocess" / "fig4_Ux_curve.png").is_file()
    assert (case_dir / "postprocess" / "residuals.png").is_file()
    assert (case_dir / "postprocess" / "residuals.csv").is_file()
    assert (case_dir / "POSTPROCESS_REPORT.json").is_file()
    assert (case_dir / "POSTPROCESS_SUMMARY.md").is_file()
    assert (case_dir / "POSTPROCESS_ARTIFACTS.json").is_file()
    assert (case_dir / "FINAL_REPORT.docx").is_file()
    assert report["formal_report"]["status"] == "passed"

    manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["postprocess_status"] == "passed"
    assert manifest["run_status"] == "passed"
    assert manifest["artifacts"]
    assert any(item["kind"] == "formal_report" for item in manifest["artifacts"])


def test_standard_postprocess_generates_rheotool_channel_analytic_comparison(tmp_path):
    case_dir = tmp_path / "rheotool-channel"
    _write_rheotool_channel_sample_case(case_dir)

    report = run_standard_postprocess(
        case_dir,
        user_requirement="RheoTool Channel Oldroyd-BLog lineX35 analytic comparison",
        fields=(),
        run_openfoam_sample=False,
    )

    comparison = report["rheotool_channel_comparison"]
    assert comparison["status"] == "passed"
    assert Path(comparison["plot"]).is_file()
    assert Path(comparison["csv"]).is_file()
    assert comparison["errors"]["Ux"]["max_abs"] == 0.0
    assert comparison["errors"]["tau_xy"]["max_abs"] == 0.0
    assert comparison["errors"]["tau_xx"]["max_abs"] == 0.0
    artifacts = json.loads((case_dir / "POSTPROCESS_ARTIFACTS.json").read_text(encoding="utf-8"))["artifacts"]
    kinds = {item["kind"] for item in artifacts}
    assert "rheotool_channel_comparison_plot" in kinds
    assert "rheotool_channel_comparison_csv" in kinds


def test_standard_postprocess_generates_kinetic_energy_history(tmp_path):
    case_dir = tmp_path / "kinetic-energy"
    (case_dir / "0").mkdir(parents=True)
    (case_dir / "1").mkdir()
    (case_dir / "2").mkdir()
    _write_u_field(case_dir / "0" / "U", "uniform (0 0 0);")
    _write_u_field(case_dir / "1" / "U", "uniform (2 0 0);")
    _write_u_field(
        case_dir / "2" / "U",
        "nonuniform List<vector>\n2\n(\n(1 0 0)\n(3 0 0)\n)\n;",
    )

    report = run_standard_postprocess(
        case_dir,
        user_requirement="rho=0.01",
        fields=(),
        run_openfoam_sample=False,
    )

    kinetic = report["kinetic_energy"]
    assert kinetic["status"] == "passed"
    assert kinetic["rho"] == 0.01
    assert kinetic["rho_source"] == "user_requirement"
    assert kinetic["rows"] == 3
    assert kinetic["first"]["kinetic_energy_average"] == 0.0
    assert kinetic["last"]["kinetic_energy_average"] == 0.025
    assert Path(kinetic["csv"]).is_file()
    assert Path(kinetic["plot"]).is_file()

    artifacts = json.loads((case_dir / "POSTPROCESS_ARTIFACTS.json").read_text(encoding="utf-8"))["artifacts"]
    kinds = {item["kind"] for item in artifacts}
    assert "kinetic_energy_csv" in kinds
    assert "kinetic_energy_plot" in kinds


def test_visualization_node_prefers_standard_postprocess(monkeypatch, tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()

    def fake_postprocess(case_dir_arg, **kwargs):
        out = Path(case_dir_arg) / "postprocess" / "visualization_U.png"
        out.parent.mkdir(exist_ok=True)
        out.write_bytes(b"png")
        return {
            "report_json": str(Path(case_dir_arg) / "POSTPROCESS_REPORT.json"),
            "summary_markdown": str(Path(case_dir_arg) / "POSTPROCESS_SUMMARY.md"),
            "line_plot": {"status": "skipped"},
            "field_visualizations": {
                "status": "passed",
                "fields": {"U": {"status": "passed", "output": str(out)}},
            },
        }

    monkeypatch.setattr(viz_node, "run_standard_postprocess", fake_postprocess)

    result = viz_node.visualization_node({"case_dir": str(case_dir), "user_requirement": "可视化速度场", "config": None})

    assert result["visualization_summary"]["used"] == "standard_postprocess"
    assert result["plot_outputs"] == [str(case_dir / "postprocess" / "visualization_U.png")]
    assert result["postprocess_result"]["field_visualizations"]["status"] == "passed"
