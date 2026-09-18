import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from models import CaseTarget  # noqa: E402
from services.case_manifest import (  # noqa: E402
    create_case_manifest,
    read_dieswell_geometry_metadata,
    update_case_manifest_status,
    validate_case_manifest,
)
from services.workflow_compiler import compile_workflow  # noqa: E402


def test_manifest_preserves_case_target_and_updates_only_status(tmp_path):
    target = CaseTarget.for_solver("rheoFoam")
    create_case_manifest(tmp_path, target)
    update_case_manifest_status(
        tmp_path, target, validation_status="passed", run_status="passed"
    )

    manifest = validate_case_manifest(tmp_path, target)
    assert manifest["schema_version"] == 2
    assert manifest["validation_status"] == "passed"
    assert manifest["run_status"] == "passed"
    assert {key: manifest[key] for key in target.as_dict()} == target.as_dict()


def test_manifest_rejects_target_mutation(tmp_path):
    target = CaseTarget.for_solver("rheoFoam")
    path = create_case_manifest(tmp_path, target)
    manifest = json.loads(path.read_text())
    manifest["version"] = "v10"
    path.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="MANIFEST_TARGET_MISMATCH"):
        validate_case_manifest(tmp_path, target)


def test_manifest_records_compiled_physics_workflow(tmp_path):
    compiled = compile_workflow("水在管道中的稳态压降")
    target = compiled.plan.target
    create_case_manifest(
        tmp_path,
        target,
        problem_intent=compiled.intent,
        physics_spec=compiled.physics,
        rheology_spec=compiled.rheology,
        workflow_plan=compiled.plan,
    )

    manifest = validate_case_manifest(tmp_path, target)
    assert manifest["physics_spec"]["phase_type"] == "single-phase"
    assert manifest["workflow_plan"]["target"]["solver"] == "simpleFoam"


def test_manifest_records_dieswell_template_geometry_metadata(tmp_path):
    compiled = compile_workflow("请复现 RheoTool 5.3.3 DieSwell/Oldroyd-BLog 教程，使用模板原始参数。")
    target = compiled.plan.target
    create_case_manifest(
        tmp_path,
        target,
        problem_intent=compiled.intent,
        physics_spec=compiled.physics,
        rheology_spec=compiled.rheology,
        workflow_plan=compiled.plan,
    )

    metadata = read_dieswell_geometry_metadata(tmp_path)
    assert metadata["source"] == "template_metadata"
    assert metadata["template_id"] == "rheotool_5_3_3_dieswell_oldroydb_log"
    assert metadata["die_exit_x"] == 0.0
    assert metadata["die_exit_half_height"] == 1.0
    assert metadata["downstream_min_x"] == 0.0


def test_manifest_records_user_provided_dieswell_geometry_metadata(tmp_path):
    compiled = compile_workflow(
        "真实设备平面狭缝口模挤出胀大，die_exit_x=0，die_exit_width=0.004，"
        "downstream_min_x=0，symmetry_plane=y=0，聚合物熔体。"
    )
    target = CaseTarget.for_solver("rheoInterFoam")
    create_case_manifest(tmp_path, target, problem_intent=compiled.intent)

    metadata = read_dieswell_geometry_metadata(tmp_path)
    assert metadata["source"] == "user_requirement"
    assert metadata["die_exit_x"] == 0.0
    assert metadata["die_exit_half_height"] == 0.002
    assert metadata["die_exit_full_width"] == 0.004
    assert metadata["downstream_min_x"] == 0.0
    assert metadata["symmetry_plane"] == "y=0"


def test_manifest_does_not_invent_dieswell_geometry_for_real_case(tmp_path):
    compiled = compile_workflow("真实设备平面狭缝口模挤出胀大，聚合物熔体。")
    target = CaseTarget.for_solver("rheoInterFoam")
    create_case_manifest(tmp_path, target, problem_intent=compiled.intent)

    manifest = validate_case_manifest(tmp_path, target)
    assert manifest["specialized_postprocess"] == {}
    assert read_dieswell_geometry_metadata(tmp_path) is None
