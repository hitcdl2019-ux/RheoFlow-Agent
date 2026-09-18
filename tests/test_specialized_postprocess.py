from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.postprocess import _collect_artifacts  # noqa: E402
from services.specialized_postprocess import (  # noqa: E402
    compute_dambreak_front_metrics,
    compute_dieswell_swell_metrics,
    is_dambreak_case,
    is_dieswell_case,
    _dieswell_geometry,
)


def test_compute_dieswell_swell_metrics_for_half_domain_contour():
    points = [
        (-2.0, 1.0, 0.5),
        (0.0, 1.0, 0.5),
        (5.0, 1.15, 0.5),
        (10.0, 1.22, 0.5),
        (15.0, 1.18, 0.5),
    ]

    result = compute_dieswell_swell_metrics(
        points,
        die_exit_x=0.0,
        die_exit_half_height=1.0,
        downstream_min_x=0.0,
    )

    assert result["status"] == "passed"
    assert result["max_half_height"] == 1.22
    assert result["max_full_width"] == 2.44
    assert result["swell_ratio"] == 1.22
    assert result["max_location"] == {"x": 10.0, "y": 1.22, "z": 0.5}
    assert result["downstream_point_count"] == 4


def test_dieswell_case_detection_uses_template_import(tmp_path):
    (tmp_path / "TUTORIAL_TEMPLATE_IMPORT.json").write_text(
        '{"template_id":"rheotool_5_3_3_dieswell_oldroydb_log"}',
        encoding="utf-8",
    )

    assert is_dieswell_case(tmp_path)


def test_dieswell_artifacts_are_collected(tmp_path):
    post = tmp_path / "postprocess"
    post.mkdir()
    csv_path = post / "dieswell_free_surface_alpha05.csv"
    png_path = post / "dieswell_free_surface_swell_ratio.png"
    json_path = post / "dieswell_swell_metrics.json"
    for path in (csv_path, png_path, json_path):
        path.write_text("x", encoding="utf-8")

    artifacts = _collect_artifacts({
        "dieswell_free_surface": {
            "csv": str(csv_path),
            "plot": str(png_path),
            "metrics_json": str(json_path),
        }
    })
    kinds = {item["kind"] for item in artifacts}

    assert "dieswell_free_surface_csv" in kinds
    assert "dieswell_free_surface_plot" in kinds
    assert "dieswell_swell_metrics" in kinds


def test_compute_dambreak_front_metrics_from_free_surface_contour():
    points = [
        (0.0, 0.5, 0.0),
        (1.0, 0.4, 0.0),
        (2.5, 0.2, 0.0),
        (1.3, 0.9, 0.0),
    ]

    result = compute_dambreak_front_metrics(points)

    assert result["status"] == "passed"
    assert result["front_x"] == 2.5
    assert result["front_location"] == {"x": 2.5, "y": 0.2, "z": 0.0}
    assert result["max_height"] == 0.9
    assert result["point_count"] == 4


def test_dambreak_case_detection_uses_template_import(tmp_path):
    (tmp_path / "TUTORIAL_TEMPLATE_IMPORT.json").write_text(
        '{"template_id":"foundation_v10_interfoam_dambreak"}',
        encoding="utf-8",
    )

    assert is_dambreak_case(tmp_path)


def test_dambreak_artifacts_are_collected(tmp_path):
    post = tmp_path / "postprocess"
    post.mkdir()
    csv_path = post / "dambreak_free_surface_alpha05.csv"
    png_path = post / "dambreak_free_surface_front.png"
    json_path = post / "dambreak_front_metrics.json"
    overlay = post / "dambreak_free_surface_initial_final_overlay.png"
    history_csv = post / "dambreak_front_x_vs_time.csv"
    history_plot = post / "dambreak_front_x_vs_time.png"
    field_png = post / "dambreak_alpha_water_final.png"
    for path in (csv_path, png_path, json_path, overlay, history_csv, history_plot, field_png):
        path.write_text("x", encoding="utf-8")

    artifacts = _collect_artifacts({
        "dambreak_free_surface": {
            "csv": str(csv_path),
            "plot": str(png_path),
            "metrics_json": str(json_path),
        },
        "dambreak_enhanced_figures": {
            "free_surface_overlay": {"path": str(overlay)},
            "front_history": {"csv": str(history_csv), "plot": str(history_plot)},
            "fields": {"alpha.water:final": {"path": str(field_png)}},
        },
    })
    kinds = {item["kind"] for item in artifacts}

    assert "dambreak_free_surface_csv" in kinds
    assert "dambreak_free_surface_plot" in kinds
    assert "dambreak_front_metrics" in kinds
    assert "dambreak_free_surface_overlay" in kinds
    assert "dambreak_front_history_plot" in kinds
    assert "dambreak_field_snapshot:alpha.water:final" in kinds


def test_dieswell_geometry_prefers_manifest_metadata(tmp_path):
    (tmp_path / "manifest.json").write_text(
        """
        {
          "specialized_postprocess": {
            "dieswell": {
              "source": "user_requirement",
              "die_exit_x": 2.0,
              "die_exit_half_height": 0.5,
              "downstream_min_x": 2.0
            }
          }
        }
        """,
        encoding="utf-8",
    )

    geometry, source = _dieswell_geometry(tmp_path, "rheotool_5_3_3_dieswell_oldroydb_log")

    assert source == "user_requirement"
    assert geometry == {"die_exit_x": 2.0, "die_exit_half_height": 0.5, "downstream_min_x": 2.0}
