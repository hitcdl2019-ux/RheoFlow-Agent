from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from models import CaseTarget  # noqa: E402
from services.rheotool_templates import find_rheotool_tutorial_template, import_rheotool_tutorial_template  # noqa: E402
from services.workflow_compiler import compile_workflow  # noqa: E402


def _write_minimal_template(root: Path, relative: str, *, allrun: str = "#!/bin/sh\nrunApplication blockMesh\nrunApplication solver\n") -> Path:
    case = root / relative
    (case / "constant" / "polyMesh").mkdir(parents=True)
    (case / "system").mkdir()
    (case / "0").mkdir()
    (case / "constant" / "polyMesh" / "blockMeshDict").write_text("FoamFile{object blockMeshDict;}\n", encoding="utf-8")
    (case / "constant" / "polyMesh" / "boundary").write_text("boundary\n", encoding="utf-8")
    (case / "constant" / "constitutiveProperties").write_text("parameters{}\n", encoding="utf-8")
    (case / "system" / "controlDict").write_text("application solver;\nendTime 1;\n", encoding="utf-8")
    (case / "system" / "fvSchemes").write_text("fvSchemes\n", encoding="utf-8")
    (case / "system" / "fvSolution").write_text("fvSolution\n", encoding="utf-8")
    (case / "0" / "U").write_text("U\n", encoding="utf-8")
    (case / "0" / "p").write_text("p\n", encoding="utf-8")
    (case / "Allrun").write_text(allrun, encoding="utf-8")
    return case


@pytest.mark.parametrize(
    ("prompt", "solver", "geometry", "template_id", "relative_source"),
    [
        (
            "RheoTool 5.1.8 Aneurysm/HerschelBulkley 动脉瘤血流 ReGN=420 tau0=0.0175 k=8.9721e-3 n=0.8601",
            "rheoFoam",
            "aneurysm",
            "rheotool_5_1_8_aneurysm_herschelbulkley",
            "rheoFoam/Aneurysm/HerschelBulkley",
        ),
        (
            "RheoTool 5.1.9 fluidDamper/CarreauYasuda 阻尼器 moving mesh nu0=100 nuInf=0 lambda=0.0084033613 n=0.353 a=1.433",
            "rheoFoam",
            "fluid_damper",
            "rheotool_5_1_9_fluiddamper_carreauyasuda",
            "rheoFoam/fluidDamper/CarreauYasuda",
        ),
        (
            "rheoTestFoam/HerschelBulkley 材料函数 tau0=0.0175 k=8.9721e-3 n=0.8601",
            "rheoTestFoam",
            "rheotest_material_function",
            "rheotool_5_2_2_rheotest_herschelbulkley",
            "rheoTestFoam/HerschelBulkley",
        ),
        (
            "rheoTestFoam/FENE-CR material function etaS=0.1 etaP=0.9 lambda=1 L2=100",
            "rheoTestFoam",
            "rheotest_material_function",
            "rheotool_5_2_3_rheotest_fenecr",
            "rheoTestFoam/FENE-CR",
        ),
        (
            "rheoInterFoam ImpactingDrop/Oldroyd-BLog impacting drop Fr=2.26 Re=5 Wi=1 beta=0.1 etaS=0.1 etaP=0.9 lambda=1",
            "rheoInterFoam",
            "impacting_drop",
            "rheotool_5_3_2_impactingdrop_oldroydb_log",
            "rheoInterFoam/ImpactingDrop/Oldroyd-BLog",
        ),
        (
            "rheoInterFoam DieSwell/Oldroyd-BLog planar die swell tutorial，输出挤出胀大自由液面。",
            "rheoInterFoam",
            "die_swell",
            "rheotool_5_3_3_dieswell_oldroydb_log",
            "rheoInterFoam/DieSwell/Oldroyd-BLog",
        ),
    ],
)
def test_additional_rheotool_templates_match_explicit_reproduction_targets(tmp_path, prompt, solver, geometry, template_id, relative_source):
    _write_minimal_template(tmp_path, relative_source)
    compiled = compile_workflow(prompt)

    assert compiled.plan.target is not None
    assert compiled.plan.target.solver == solver
    assert compiled.intent.geometry_class == geometry
    assert compiled.intent.reproduction_target == template_id

    match = find_rheotool_tutorial_template(
        prompt,
        CaseTarget.for_solver(solver),
        root=tmp_path,
        compiled_workflow=compiled,
    )

    assert match is not None
    assert match["id"] == template_id
    assert match["source_dir"].endswith(relative_source)


@pytest.mark.parametrize(
    ("prompt", "template_id", "relative_source"),
    [
        (
            "请复现 RheoTool 5.3.3 DieSwell/CarreauYasuda 教程",
            "rheotool_5_3_3_dieswell_carreauyasuda",
            "rheoInterFoam/DieSwell/CarreauYasuda",
        ),
        (
            "请复现 RheoTool 5.3.3 DieSwell/GiesekusLog 教程",
            "rheotool_5_3_3_dieswell_giesekuslog",
            "rheoInterFoam/DieSwell/GiesekusLog",
        ),
        (
            "请复现 RheoTool 5.3.3 DieSwell/Oldroyd-BLog 教程",
            "rheotool_5_3_3_dieswell_oldroydb_log",
            "rheoInterFoam/DieSwell/Oldroyd-BLog",
        ),
    ],
)
def test_dieswell_variants_are_executable_templates(tmp_path, prompt, template_id, relative_source):
    _write_minimal_template(tmp_path, relative_source)
    compiled = compile_workflow(prompt)

    assert compiled.intent.reproduction_target == template_id
    assert compiled.plan.target is not None
    assert compiled.plan.target.solver == "rheoInterFoam"

    match = find_rheotool_tutorial_template(
        prompt,
        CaseTarget.for_solver("rheoInterFoam"),
        root=tmp_path,
        compiled_workflow=compiled,
    )

    assert match["id"] == template_id
    assert match["source_dir"].endswith(relative_source)


def test_dieswell_family_is_not_executable_template(tmp_path):
    family = tmp_path / "rheoInterFoam" / "DieSwell"
    family.mkdir(parents=True)
    _write_minimal_template(tmp_path, "rheoInterFoam/DieSwell/Oldroyd-BLog")
    compiled = compile_workflow("请复现 RheoTool 5.3.3 planar DieSwell 教程")

    assert compiled.intent.reproduction_target == "rheotool_5_3_3_dieswell_family"
    assert compiled.plan.workflow_type == "rheotool-tutorial-family"
    assert compiled.plan.target is None

    match = find_rheotool_tutorial_template(
        "请复现 RheoTool 5.3.3 planar DieSwell 教程",
        CaseTarget.for_solver("rheoInterFoam"),
        root=tmp_path,
        compiled_workflow=compiled,
    )

    assert match is None


def test_import_rejects_non_executable_tutorial_family(tmp_path):
    family = tmp_path / "templates" / "rheoInterFoam" / "DieSwell"
    family.mkdir(parents=True)
    match = {
        "id": "rheotool_5_3_3_dieswell_oldroydb_log",
        "source_dir": str(family),
        "matched_alias": "RheoTool 5.3.3 DieSwell/Oldroyd-BLog",
        "import_policy": "rheotool tutorial template import; no LLM dictionary regeneration",
        "tier": "A",
        "rag_confidence": "high",
    }

    with pytest.raises(ValueError, match="TUTORIAL_TEMPLATE_NOT_EXECUTABLE"):
        import_rheotool_tutorial_template(str(tmp_path / "case"), match)


def test_dieswell_oldroyd_import_ignores_negated_or_alternative_variant_mentions(tmp_path):
    source = _write_minimal_template(tmp_path / "templates", "rheoInterFoam/DieSwell/Oldroyd-BLog")
    match = {
        "id": "rheotool_5_3_3_dieswell_oldroydb_log",
        "source_dir": str(source),
        "matched_alias": "RheoTool 5.3.3 DieSwell/Oldroyd-BLog",
        "import_policy": "rheotool tutorial template import; no LLM dictionary regeneration",
        "tier": "A",
        "rag_confidence": "high",
    }
    requirement = (
        "Reproduce RheoTool 5.3.3 DieSwell / Oldroyd-BLog. "
        "constitutive_model: Oldroyd-BLog. "
        "No Giesekus / PTT / other constitutive model is requested. "
        "同目录另有 GiesekusLog、CarreauYasuda 可选，但本次采用 Oldroyd-BLog。"
    )

    result = import_rheotool_tutorial_template(str(tmp_path / "case"), match, user_requirement=requirement)

    assert result["tutorial_template_import"]["template_id"] == "rheotool_5_3_3_dieswell_oldroydb_log"


def test_additional_template_source_missing_does_not_fallback_to_existing_template(tmp_path):
    _write_minimal_template(tmp_path, "rheoFoam/Channel/Oldroyd-BLog")
    prompt = "RheoTool 5.1.8 Aneurysm/HerschelBulkley 动脉瘤血流 tau0=0.0175 k=8.9721e-3 n=0.8601"
    compiled = compile_workflow(prompt)

    with pytest.raises(FileNotFoundError, match="rheotool_5_1_8_aneurysm_herschelbulkley"):
        find_rheotool_tutorial_template(
            prompt,
            CaseTarget.for_solver("rheoFoam"),
            root=tmp_path,
            compiled_workflow=compiled,
        )


def test_additional_template_import_consistency_rejects_wrong_template(tmp_path):
    source = _write_minimal_template(tmp_path / "templates", "rheoFoam/Channel/Oldroyd-BLog")
    match = {
        "id": "rheotool_5_1_3_channel_oldroydb_log",
        "source_dir": str(source),
        "matched_alias": "RheoTool 5.1.3 Channel/Oldroyd-BLog",
        "import_policy": "rheotool tutorial template import; no LLM dictionary regeneration",
        "tier": "A",
        "rag_confidence": "high",
    }

    with pytest.raises(ValueError, match="TEMPLATE_IMPORT_CONFLICT"):
        import_rheotool_tutorial_template(
            str(tmp_path / "case"),
            match,
            user_requirement="RheoTool 5.1.9 fluidDamper/CarreauYasuda 阻尼器",
        )


def test_fluiddamper_import_normalizes_control_dict_solver(tmp_path):
    source = _write_minimal_template(
        tmp_path / "templates",
        "rheoFoam/fluidDamper/CarreauYasuda",
        allrun="#!/bin/sh\nrunApplication blockMesh\nrunApplication rheoFoam\n",
    )
    (source / "system" / "controlDict").write_text(
        "application     rheoInterFoam;\n"
        "libs\n"
        "(\n"
        "    \"libBCRheoTool.so\"\n"
        ");\n",
        encoding="utf-8",
    )
    (source / "0" / "U").write_text(
        "boundaryField\n{\n"
        "    piston { type navierSlip; model nonLinearNavierSlip; }\n"
        "    shaft { type codedFixedValue; value uniform (0 0 0); }\n"
        "}\n",
        encoding="utf-8",
    )
    (source / "0" / "pointMotionUx").write_text(
        "boundaryField\n{\n"
        "    piston { type codedFixedValue; value uniform 0; }\n"
        "}\n",
        encoding="utf-8",
    )
    prompt = "复现 RheoTool 5.1.9 fluidDamper/CarreauYasuda 教程"
    compiled = compile_workflow(prompt)
    match = find_rheotool_tutorial_template(
        prompt,
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path / "templates",
        compiled_workflow=compiled,
    )

    result = import_rheotool_tutorial_template(str(tmp_path / "case"), match, user_requirement=prompt)

    control_dict = (tmp_path / "case" / "system" / "controlDict").read_text(encoding="utf-8")
    assert "application     rheoFoam;" in control_dict
    assert "rheoInterFoam" not in control_dict
    assert result["tutorial_template_import"]["template_id"] == "rheotool_5_1_9_fluiddamper_carreauyasuda"


def test_rheointerfoam_impacting_drop_import_preserves_setfields_sequence(tmp_path):
    _write_minimal_template(
        tmp_path / "templates",
        "rheoInterFoam/ImpactingDrop/Oldroyd-BLog",
        allrun="#!/bin/sh\nrunApplication blockMesh\ncp 0/alpha1.org 0/alpha1\ncp 0/U.org 0/U\nrunApplication setFields\nrunApplication rheoInterFoam\n",
    )
    prompt = "rheoInterFoam ImpactingDrop/Oldroyd-BLog impacting drop etaS=0.1 etaP=0.9 lambda=1 Re=5 Wi=1 beta=0.1"
    compiled = compile_workflow(prompt)
    match = find_rheotool_tutorial_template(prompt, CaseTarget.for_solver("rheoInterFoam"), root=tmp_path / "templates", compiled_workflow=compiled)

    result = import_rheotool_tutorial_template(str(tmp_path / "case"), match, user_requirement=prompt)

    allrun = (tmp_path / "case" / "Allrun").read_text(encoding="utf-8")
    assert "cp 0/alpha1.org 0/alpha1" in allrun
    assert "runApplication setFields" in allrun
    assert result["tutorial_template_import"]["template_id"] == "rheotool_5_3_2_impactingdrop_oldroydb_log"
