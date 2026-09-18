from pathlib import Path
import re
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from models import CaseTarget  # noqa: E402
from services.rheotool_templates import (  # noqa: E402
    find_rheotool_tutorial_template,
    import_rheotool_tutorial_template,
)
from services.plan import generate_simulation_plan  # noqa: E402
from services.workflow_compiler import compile_workflow  # noqa: E402


def _write_minimal_channel_template(root: Path) -> Path:
    case = root / "rheoFoam" / "Channel" / "Oldroyd-BLog"
    (case / "constant" / "polyMesh").mkdir(parents=True)
    (case / "system").mkdir()
    (case / "0").mkdir()

    (case / "constant" / "polyMesh" / "blockMeshDict").write_text(
        "FoamFile{object blockMeshDict;}\nblocks ((50 30 1) (50 30 1));\n",
        encoding="utf-8",
    )
    (case / "constant" / "polyMesh" / "boundary").write_text("legacy boundary\n", encoding="utf-8")
    (case / "constant" / "constitutiveProperties").write_text(
        "parameters\n{\n    type Oldroyd-BLog;\n    etaS 0.01;\n    etaP 0.99;\n    lambda 1.;\n}\n",
        encoding="utf-8",
    )
    (case / "system" / "fvSchemes").write_text(
        "ddtSchemes\n{\n    default         Euler;\n}\n"
        "divSchemes\n{\n    div(phi,theta)            GaussDefCmpw cubista;\n"
        "    div(phi,tau)             GaussDefCmpw cubista;\n}\n",
        encoding="utf-8",
    )
    (case / "system" / "fvSolution").write_text(
        "SIMPLE\n{\n    nInIter         1;\n}\nrelaxationFactors\n{\n    equations { theta 1; }\n}\n",
        encoding="utf-8",
    )
    (case / "system" / "controlDict").write_text(
        "application     rheoFoam;\nstartTime       0;\nendTime         1;\n",
        encoding="utf-8",
    )
    (case / "system" / "sampleDict").write_text(
        "sets\n(\n    lineVert\n    {\n        start       ( 30 -1.2 0 );\n"
        "        end         ( 30 1.2 0 );\n        type        face;\n    }\n);\nfields ( U tau );\n",
        encoding="utf-8",
    )
    (case / "0" / "theta").write_text(
        "boundaryField\n{\n    inlet { type fixedValue; value uniform (0 0 0 0 0 0); }\n"
        "    walls { type zeroGradient; }\n}\n",
        encoding="utf-8",
    )
    (case / "0" / "tau").write_text(
        "boundaryField\n{\n    inlet { type fixedValue; value uniform (0 0 0 0 0 0); }\n"
        "    walls { type linearExtrapolation; value uniform (0 0 0 0 0 0); }\n}\n",
        encoding="utf-8",
    )
    (case / "0" / "U").write_text("U\n", encoding="utf-8")
    (case / "0" / "p").write_text("p\n", encoding="utf-8")
    (case / "Allrun").write_text(
        "#!/bin/sh\nrunApplication blockMesh\nrunApplication rheoFoam\nrunApplication sample\n",
        encoding="utf-8",
    )
    return case


def _write_minimal_cavity_template(root: Path) -> Path:
    case = root / "rheoFoam" / "Cavity" / "Oldroyd-BLog"
    (case / "constant" / "polyMesh").mkdir(parents=True)
    (case / "system").mkdir()
    (case / "0").mkdir()

    (case / "constant" / "polyMesh" / "blockMeshDict").write_text(
        "FoamFile{object blockMeshDict;}\nblocks\n(\n    hex (0 1 2 3 4 5 6 7) (127 127 1) simpleGrading (1 1 1)\n);\n",
        encoding="utf-8",
    )
    (case / "constant" / "polyMesh" / "boundary").write_text("legacy boundary\n", encoding="utf-8")
    (case / "constant" / "constitutiveProperties").write_text(
        "parameters\n{\n    type Oldroyd-BLog;\n    etaS 0.5;\n    etaP 0.5;\n    lambda 1.;\n}\n",
        encoding="utf-8",
    )
    (case / "system" / "fvSchemes").write_text("divSchemes { div(phi,theta) GaussDefCmpw cubista; }\n", encoding="utf-8")
    (case / "system" / "fvSolution").write_text(
        "solvers\n{\n"
        "    \"(theta|tau|U)\"\n    {\n        solver PBiCG;\n"
        "        preconditioner\n        {\n            preconditioner DILU;\n        }\n"
        "    }\n}\n"
        "PostProcessing\n{\n    functions\n    (\n        kineticE\n"
        "        {\n            funcType calcKineticE;\n            enabled true;\n        }\n    );\n}\n",
        encoding="utf-8",
    )
    (case / "system" / "controlDict").write_text(
        "application     rheoFoam;\nstartTime       0;\nendTime         10;\n",
        encoding="utf-8",
    )
    (case / "system" / "sampleDict").write_text(
        "setFormat raw;\nfields ( U tau theta );\nsets\n(\n"
        "    lineVert_x0.5\n    {\n        type        face;\n        axis        y;\n"
        "        start       ( 0.5 -0.1 0.);\n        end         ( 0.5 1.1 0. );\n    }\n"
        "    lineHorz_y0.75\n    {\n        type        face;\n        axis        x;\n"
        "        start       ( -0.1 0.75 0.);\n        end         ( 1.1 0.75 0. );\n    }\n);\n",
        encoding="utf-8",
    )
    (case / "0" / "theta").write_text("theta\n", encoding="utf-8")
    (case / "0" / "tau").write_text(
        "boundaryField\n{\n    cylinder\n    {\n        type linearExtrapolation;\n        value uniform (0 0 0 0 0 0);\n    }\n}\n",
        encoding="utf-8",
    )
    (case / "0" / "U").write_text(
        "boundaryField\n{\n"
        "    movingLid\n    {\n        type uLid;\n        value uniform (0 0 0);\n    }\n"
        "}\n",
        encoding="utf-8",
    )
    (case / "0" / "p").write_text("p\n", encoding="utf-8")
    (case / "Allrun").write_text(
        "#!/bin/sh\nrunApplication blockMesh\nrunApplication rheoFoam\nrunApplication sample\n",
        encoding="utf-8",
    )
    return case


def _write_minimal_contraction_template(root: Path) -> Path:
    case = root / "rheoFoam" / "Contraction41" / "Oldroyd-BLog"
    (case / "constant" / "polyMesh").mkdir(parents=True)
    (case / "system").mkdir()
    (case / "0").mkdir()

    (case / "constant" / "polyMesh" / "blockMeshDict").write_text(
        "FoamFile{object blockMeshDict;}\n"
        "vertices ((-100 -4 0) (0 -4 0) (100 -1 0) (100 1 0) (0 4 0) (-100 4 0));\n"
        "blocks (hex (0 1 2 3 4 5 5 5) (200 80 1) simpleGrading (1 1 1));\n",
        encoding="utf-8",
    )
    (case / "constant" / "polyMesh" / "boundary").write_text("inlet outlet wall_liptop wall_lipdown walls\n", encoding="utf-8")
    (case / "constant" / "constitutiveProperties").write_text(
        "parameters\n{\n    type Oldroyd-BLog;\n    rho 0.01;\n    etaS 0.5;\n    etaP 0.5;\n    lambda 1.;\n}\n",
        encoding="utf-8",
    )
    (case / "system" / "controlDict").write_text("application rheoFoam;\nendTime 8;\n", encoding="utf-8")
    (case / "system" / "fvSchemes").write_text("divSchemes { div(phi,theta) GaussDefCmpw cubista; }\n", encoding="utf-8")
    (case / "system" / "fvSolution").write_text(
        "solvers\n{\n"
        "    U\n    {\n        solver BiCGStab;\n        preconditioner\n        {\n            preconditioner ILU0;\n        }\n    }\n"
        "    \\\"(theta|tau)\\\"\n    {\n        solver PBiCG;\n        preconditioner\n        {\n            preconditioner ILU0;\n        }\n    }\n"
        "}\n"
        "PostProcessing\n{\n    functions\n    (\n        vortexL\n        {\n            funcType calcVortexL;\n        }\n    );\n}\n"
        "PostProcessing\n{\n    funcType calcVortexL;\n}\n"
        "SIMPLE { nInIter 1; }\n",
        encoding="utf-8",
    )
    (case / "system" / "sampleDict").write_text(
        "setFormat raw;\nfields ( U tau theta );\nsets ( lBeforex0 { type midPoint; } lAfterx0 { type midPoint; } );\n",
        encoding="utf-8",
    )
    (case / "0" / "U").write_text(
        "boundaryField { inlet { type uCos; tlim 1.; fac 8.; uav (0.25 0 0); dirN (1 0 0); value uniform (0 0 0); } }\n",
        encoding="utf-8",
    )
    (case / "0" / "p").write_text("p\n", encoding="utf-8")
    (case / "0" / "theta").write_text("theta\n", encoding="utf-8")
    (case / "0" / "tau").write_text(
        "boundaryField\n{\n    \\\"(wall.*)\\\"\n    {\n        type linearExtrapolation;\n        value uniform (0 0 0 0 0 0);\n    }\n}\n",
        encoding="utf-8",
    )
    (case / "Allrun").write_text("#!/bin/sh\nrunApplication blockMesh\nrunApplication rheoFoam\nrunApplication sample\n", encoding="utf-8")
    return case

def test_find_rheotool_channel_oldroyd_template(tmp_path):
    _write_minimal_channel_template(tmp_path)
    prompt = (
        "请复现 rheoTool 教程的平行平板通道 benchmark: "
        "Oldroyd-B 流体, Wi=0.99, beta=0.01"
    )

    match = find_rheotool_tutorial_template(
        prompt,
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path,
    )

    assert match is not None
    assert match["id"] == "rheotool_5_1_3_channel_oldroydb_log"


def test_import_rheotool_channel_template_normalizes_foundation_v9_layout(tmp_path):
    _write_minimal_channel_template(tmp_path / "templates")
    match = find_rheotool_tutorial_template(
        "rheoTool 教程 平行平板通道 Oldroyd-B benchmark Wi=0.99 beta=0.01",
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path / "templates",
    )
    case_dir = tmp_path / "case"

    result = import_rheotool_tutorial_template(str(case_dir), match)

    assert (case_dir / "TUTORIAL_TEMPLATE_IMPORT.json").is_file()
    assert (case_dir / "system" / "blockMeshDict").is_file()
    assert not (case_dir / "constant" / "polyMesh").exists()
    assert "default         Euler" in (case_dir / "system" / "fvSchemes").read_text(encoding="utf-8")
    assert "GaussDefCmpw cubista" in (case_dir / "system" / "fvSchemes").read_text(encoding="utf-8")
    allrun = (case_dir / "Allrun").read_text(encoding="utf-8")
    assert "command -v sample" in allrun
    assert "runApplication postProcess -func sampleDict -latestTime" in allrun

    sample = (case_dir / "system" / "sampleDict").read_text(encoding="utf-8")
    assert "lineX35" in sample
    assert "start       ( 35 -1.2 0 );" in sample
    assert "end         ( 35 1.2 0 );" in sample
    assert "type            sets;" in sample
    assert 'libs            ("libsampling.so");' in sample
    assert "type        lineFace;" in sample

    theta = (case_dir / "0" / "theta").read_text(encoding="utf-8")
    assert "fixedValue" in theta
    assert "zeroGradient" in theta
    assert result["tutorial_template_import"]["template_id"] == "rheotool_5_1_3_channel_oldroydb_log"


def test_plan_uses_rheotool_template_for_channel_benchmark(tmp_path, monkeypatch):
    _write_minimal_channel_template(tmp_path / "templates")
    monkeypatch.setenv("FOAMAGENT_RHEOTOOL_TUTORIAL_ROOT", str(tmp_path / "templates"))

    plan = generate_simulation_plan(
        user_requirement=(
            "请复现 rheoTool 教程的平行平板通道 benchmark: "
            "Oldroyd-B 流体, Wi=0.99, beta=0.01, etaS=0.01 etaP=0.99 lambda=1"
        ),
        case_stats={},
        case_dir=str(tmp_path / "out"),
    )

    assert plan["case_solver"] == "rheoFoam"
    assert plan["tutorial_template_match"]["id"] == "rheotool_5_1_3_channel_oldroydb_log"
    assert plan["benchmark_match"] is None
    assert any(item["file_name"] == "fvSchemes" for item in plan["subtasks"])


def test_find_rheotool_cavity_oldroyd_template(tmp_path):
    _write_minimal_cavity_template(tmp_path)
    prompt = (
        "盖驱动方腔 benchmark: Oldroyd-B 流体, beta=0.5, "
        "De=1, Re=0.01; 数值配置整体沿用教程原 case, "
        "与 Fattal & Kupferman 2005 对比"
    )

    match = find_rheotool_tutorial_template(
        prompt,
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path,
    )

    assert match is not None
    assert match["id"] == "rheotool_5_1_4_cavity_oldroydb_log"
    assert match["source_dir"].endswith("rheoFoam/Cavity/Oldroyd-BLog")


def test_find_rheotool_cavity_oldroyd_template_by_physics_signature_without_tutorial_words(tmp_path):
    _write_minimal_cavity_template(tmp_path)
    prompt = (
        "请复现 Fattal & Kupferman 2005 的 Oldroyd-B 顶盖驱动方腔算例。"
        "二维正方腔 L=1，127×127 均匀网格，Re=0.01，De=1，beta=0.5，"
        "输出 x=0.5 的 u(y)、y=0.75 的 Theta_xy 和平均动能 Ek(t)。"
    )

    match = find_rheotool_tutorial_template(
        prompt,
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path,
    )

    assert match is not None
    assert match["id"] == "rheotool_5_1_4_cavity_oldroydb_log"
    assert match["match_score"] >= 70
    assert "geometry=lid-driven-cavity" in match["match_reasons"]
    assert "reference=Fattal-Kupferman-2005" in match["match_reasons"]


def test_rheotool_cavity_signature_does_not_silently_fallback_when_template_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="TUTORIAL_TEMPLATE_SIGNATURE_MATCH_BUT_SOURCE_MISSING"):
        find_rheotool_tutorial_template(
            "Fattal Kupferman 2005 Oldroyd-B lid-driven cavity Re=0.01 De=1 beta=0.5 127x127",
            CaseTarget.for_solver("rheoFoam"),
            root=tmp_path,
        )




def test_find_cavity_template_uses_structured_fields_and_formula_groups(tmp_path):
    _write_minimal_cavity_template(tmp_path)
    prompt = (
        "顶盖驱动方腔算例。二维正方腔 L=1。流体为 Oldroyd-B 黏弹性流体，"
        "β=ηs/η0=0.5，De=λU/L=1，Re=ρUL/η0=0.01。"
        "使用无量纲制 L=1、U=1、η0=1、λ=1，因此 ηs=0.5、ηp=0.5、ρ=0.01。"
    )
    compiled = compile_workflow(prompt)

    assert compiled.intent.geometry_class == "lid_driven_cavity"
    assert compiled.intent.dimensionless_groups == {"beta": 0.5, "De": 1.0, "Re": 0.01}
    assert compiled.intent.reproduction_target == "rheotool_5_1_4_cavity_oldroydb_log"

    match = find_rheotool_tutorial_template(
        prompt,
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path,
        compiled_workflow=compiled,
    )

    assert match is not None
    assert match["id"] == "rheotool_5_1_4_cavity_oldroydb_log"
    assert match["tier"] == "A"
    assert match["rag_confidence"] == "high"
    assert "dimensionless=Re0.01-De1-beta0.5" in match["match_reasons"]


def _write_minimal_cylinder_template(root: Path) -> Path:
    case = root / "rheoFoam" / "Cylinder" / "Oldroyd-BLog"
    (case / "constant" / "polyMesh").mkdir(parents=True)
    (case / "system").mkdir()
    (case / "0").mkdir()

    (case / "constant" / "polyMesh" / "blockMeshDict").write_text(
        "FoamFile{object blockMeshDict;}\n"
        "vertices ((-20 -2 0) (0 -1 0) (60 -2 0) (60 2 0) (0 1 0) (-20 2 0));\n"
        "blocks (hex (0 1 2 3 4 5 5 5) (200 80 1) simpleGrading (1 1 1));\n",
        encoding="utf-8",
    )
    (case / "constant" / "polyMesh" / "boundary").write_text("inlet outlet walls cylinder\n", encoding="utf-8")
    (case / "constant" / "constitutiveProperties").write_text(
        "parameters\n{\n    type Oldroyd-BLog;\n    rho 1;\n    etaS 0.59;\n    etaP 0.41;\n    lambda 0.7;\n}\n",
        encoding="utf-8",
    )
    (case / "system" / "controlDict").write_text("application rheoFoam;\nendTime 15;\n", encoding="utf-8")
    (case / "system" / "fvSchemes").write_text("divSchemes { div(phi,theta) GaussDefCmpw cubista; }\n", encoding="utf-8")
    (case / "system" / "fvSolution").write_text("SIMPLE { nInIter 1; }\n", encoding="utf-8")
    (case / "system" / "sampleDict").write_text("fields ( U tau theta );\n", encoding="utf-8")
    (case / "0" / "U").write_text("inlet uniform (1 0 0); cylinder fixedValue;\n", encoding="utf-8")
    (case / "0" / "p").write_text("p\n", encoding="utf-8")
    (case / "0" / "theta").write_text("theta\n", encoding="utf-8")
    (case / "0" / "tau").write_text(
        "boundaryField\n{\n    cylinder\n    {\n        type linearExtrapolation;\n        value uniform (0 0 0 0 0 0);\n    }\n}\n",
        encoding="utf-8",
    )
    (case / "Allrun").write_text(
        "#!/bin/sh\n"
        "runApplication blockMesh\n"
        "runApplication mirrorMesh -noFunctionObjects\n"
        "cp -fr 0/polyMesh/ constant/\n"
        "rm -rf 0/polyMesh/\n"
        "runApplication rheoFoam\n"
        "runApplication sample\n",
        encoding="utf-8",
    )
    return case


def test_find_rheotool_contraction41_oldroyd_template_from_structured_signature(tmp_path):
    _write_minimal_contraction_template(tmp_path)
    prompt = (
        "请复现 RheoTool 手册 5.1.5 Case 3：4:1 平面收缩流道 Oldroyd-BLog 教程算例。"
        "Re=0.01，De=1，beta=0.5，etaS=0.5 etaP=0.5 lambda=1，输出速度/应力剖面。"
    )
    compiled = compile_workflow(prompt)

    assert compiled.intent.geometry_class == "contraction"
    assert compiled.intent.reproduction_target == "rheotool_5_1_5_contraction41_oldroydb_log"

    match = find_rheotool_tutorial_template(
        prompt,
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path,
        compiled_workflow=compiled,
    )

    assert match is not None
    assert match["id"] == "rheotool_5_1_5_contraction41_oldroydb_log"
    assert match["tier"] == "A"
    assert match["source_dir"].endswith("rheoFoam/Contraction41/Oldroyd-BLog")


def test_contraction41_request_never_falls_back_to_channel_when_source_missing(tmp_path):
    _write_minimal_channel_template(tmp_path)
    prompt = (
        "请复现 RheoTool 5.1.5 Case 3：4:1 planar contraction Oldroyd-BLog，"
        "Re=0.01 De=1 beta=0.5 etaS=0.5 etaP=0.5 lambda=1。"
    )
    compiled = compile_workflow(prompt)

    with pytest.raises(FileNotFoundError, match="rheotool_5_1_5_contraction41_oldroydb_log"):
        find_rheotool_tutorial_template(
            prompt,
            CaseTarget.for_solver("rheoFoam"),
            root=tmp_path,
            compiled_workflow=compiled,
        )


def test_import_contraction41_template_loads_compatible_ucos_library(tmp_path):
    _write_minimal_contraction_template(tmp_path / "templates")
    match = find_rheotool_tutorial_template(
        "RheoTool 5.1.5 4:1 planar contraction Oldroyd-BLog",
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path / "templates",
    )

    result = import_rheotool_tutorial_template(str(tmp_path / "case"), match)

    control_dict = (tmp_path / "case" / "system" / "controlDict").read_text(encoding="utf-8")
    assert '"libRheoToolTutorialBCs.so"' in control_dict
    assert '"libBCRheoTool.so"' in control_dict
    assert result["tutorial_template_import"]["template_id"] == "rheotool_5_1_5_contraction41_oldroydb_log"


def test_import_cylinder_template_uses_bcrheotool_for_linear_extrapolation(tmp_path):
    _write_minimal_cylinder_template(tmp_path / "templates")
    match = find_rheotool_tutorial_template(
        "RheoTool 5.1.6 confined cylinder Oldroyd-BLog",
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path / "templates",
    )

    import_rheotool_tutorial_template(str(tmp_path / "case"), match)

    control_dict = (tmp_path / "case" / "system" / "controlDict").read_text(encoding="utf-8")
    assert '"libBCRheoTool.so"' in control_dict
    assert '"libRheoToolTutorialBCs.so"' not in control_dict


def test_normalize_cylinder_template_removes_stale_tutorial_bc_library(tmp_path):
    _write_minimal_cylinder_template(tmp_path / "templates")
    match = find_rheotool_tutorial_template(
        "RheoTool 5.1.6 confined cylinder Oldroyd-BLog",
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path / "templates",
    )
    case_dir = tmp_path / "case"
    import_rheotool_tutorial_template(str(case_dir), match)
    (case_dir / "system" / "controlDict").write_text(
        'application rheoFoam;\nlibs\n(\n    "libRheoToolTutorialBCs.so"\n);\nendTime 15;\n',
        encoding="utf-8",
    )

    from services.rheotool_templates import normalize_imported_rheotool_tutorial_case

    normalize_imported_rheotool_tutorial_case(case_dir, "rheotool_5_1_6_cylinder_oldroydb_log")

    control_dict = (case_dir / "system" / "controlDict").read_text(encoding="utf-8")
    assert '"libBCRheoTool.so"' in control_dict
    assert '"libRheoToolTutorialBCs.so"' not in control_dict


def test_import_contraction41_template_applies_foundation_v9_compatibility_normalization(tmp_path):
    _write_minimal_contraction_template(tmp_path / "templates")
    match = find_rheotool_tutorial_template(
        "RheoTool 5.1.5 4:1 planar contraction Oldroyd-BLog",
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path / "templates",
    )

    import_rheotool_tutorial_template(str(tmp_path / "case"), match)

    tau = (tmp_path / "case" / "0" / "tau").read_text(encoding="utf-8")
    fv_solution = (tmp_path / "case" / "system" / "fvSolution").read_text(encoding="utf-8")
    sample_dict = (tmp_path / "case" / "system" / "sampleDict").read_text(encoding="utf-8")

    assert "linearExtrapolation" in tau
    assert "zeroGradient" not in tau
    assert "calcVortexL" in fv_solution
    assert "PostProcessing" in fv_solution
    assert "solver          PBiCGStab;" in fv_solution
    assert "ILU0" not in fv_solution
    assert "preconditioner  DILU;" in fv_solution
    assert "midPoint" not in sample_dict
    assert "lineCell" in sample_dict
    control_dict = (tmp_path / "case" / "system" / "controlDict").read_text(encoding="utf-8")
    allrun = (tmp_path / "case" / "Allrun").read_text(encoding="utf-8")
    assert '"libpostProcessingRheoTool.so"' in control_dict
    assert '"libRheoToolTutorialPPUtils.so"' in control_dict
    assert "runParallel" not in allrun
    assert not (tmp_path / "case" / "system" / "decomposeParDict").exists()


def test_normalize_imported_contraction41_reuse_case_repairs_known_template_issues(tmp_path):
    from services.rheotool_templates import normalize_imported_rheotool_tutorial_case

    case = _write_minimal_contraction_template(tmp_path / "reuse" / "templates")

    normalize_imported_rheotool_tutorial_case(
        case,
        "rheotool_5_1_5_contraction41_oldroydb_log",
    )

    tau = (case / "0" / "tau").read_text(encoding="utf-8")
    fv_solution = (case / "system" / "fvSolution").read_text(encoding="utf-8")
    sample_dict = (case / "system" / "sampleDict").read_text(encoding="utf-8")

    assert "linearExtrapolation" in tau
    assert "zeroGradient" not in tau
    assert "calcVortexL" in fv_solution
    assert not re.search(r"\bsolver\s+BiCGStab\s*;", fv_solution)
    assert "PBiCGStab" in fv_solution
    assert "ILU0" not in fv_solution
    assert "DILU" in fv_solution
    assert "midPoint" not in sample_dict
    assert "lineCell" in sample_dict


def test_template_import_consistency_rejects_wrong_geometry_before_copy(tmp_path):
    source = _write_minimal_channel_template(tmp_path / "templates")
    match = {
        "id": "rheotool_5_1_3_channel_oldroydb_log",
        "source_dir": str(source),
        "matched_alias": "RheoTool 5.1.3 Channel/Oldroyd-BLog",
        "import_policy": "rheotool tutorial template import; no LLM dictionary regeneration",
        "tier": "A",
        "rag_confidence": "high",
    }
    case_dir = tmp_path / "case"

    with pytest.raises(ValueError, match="TEMPLATE_IMPORT_CONFLICT"):
        import_rheotool_tutorial_template(
            str(case_dir),
            match,
            user_requirement="RheoTool 5.1.5 4:1 平面收缩流道 Oldroyd-BLog",
        )

    assert not case_dir.exists()


def test_plan_uses_rheotool_template_for_contraction41_benchmark(tmp_path, monkeypatch):
    _write_minimal_contraction_template(tmp_path / "templates")
    monkeypatch.setenv("FOAMAGENT_RHEOTOOL_TUTORIAL_ROOT", str(tmp_path / "templates"))

    plan = generate_simulation_plan(
        user_requirement=(
            "请复现 RheoTool 手册 5.1.5 Case 3：4:1 平面收缩流道 Oldroyd-BLog 教程算例。"
            "Re=0.01，De=1，beta=0.5，etaS=0.5 etaP=0.5 lambda=1，"
            "输出 t=8 的速度/应力剖面、Theta 等值线和流线图。"
        ),
        case_stats={},
        case_dir=str(tmp_path / "out"),
    )

    assert plan["case_solver"] == "rheoFoam"
    assert plan["tutorial_template_match"]["id"] == "rheotool_5_1_5_contraction41_oldroydb_log"
    assert plan["benchmark_match"] is None
    assert any(item["file_name"] == "fvSchemes" for item in plan["subtasks"])


def _write_minimal_crossslot_template(root: Path) -> Path:
    case = root / "rheoFoam" / "CrossSlot" / "Oldroyd-BLog"
    (case / "constant" / "polyMesh").mkdir(parents=True)
    (case / "system").mkdir()
    (case / "0").mkdir()

    (case / "constant" / "polyMesh" / "blockMeshDict").write_text(
        "FoamFile{object blockMeshDict;}\n"
        "vertices ((-10 -0.5 0) (-0.5 -0.5 0) (0.5 -0.5 0) (10 -0.5 0) "
        "(-0.5 0.5 0) (0.5 0.5 0) (-0.5 -10 0) (0.5 -10 0) (-0.5 10 0) (0.5 10 0));\n"
        "blocks (hex (0 1 4 4 0 1 4 4) (60 51 1) simpleGrading (1 1 1));\n",
        encoding="utf-8",
    )
    (case / "constant" / "polyMesh" / "boundary").write_text("inlet_north inlet_south outlet_west outlet_east walls\n", encoding="utf-8")
    (case / "constant" / "constitutiveProperties").write_text(
        "parameters\n{\n    type Oldroyd-BLog;\n    rho 1;\n    etaS 0;\n    etaP 1;\n    lambda 0.33;\n}\n",
        encoding="utf-8",
    )
    (case / "system" / "controlDict").write_text("application rheoFoam;\nendTime 100;\n", encoding="utf-8")
    (case / "system" / "fvSchemes").write_text("divSchemes { div(phi,theta) GaussDefCmpw cubista; div(phi,C) Gauss upwind; }\n", encoding="utf-8")
    (case / "system" / "fvSolution").write_text("SIMPLE { nInIter 1; }\n", encoding="utf-8")
    (case / "system" / "setFieldsDict").write_text("regions ( boxToCell { fieldValues ( volScalarFieldValue C 1 ); } );\n", encoding="utf-8")
    (case / "0" / "C.org").write_text("C passive scalar\n", encoding="utf-8")
    (case / "0" / "U").write_text("inlet_north uniform (0 -1 0); inlet_south uniform (0 1 0);\n", encoding="utf-8")
    (case / "0" / "p").write_text("p\n", encoding="utf-8")
    (case / "0" / "theta").write_text("theta\n", encoding="utf-8")
    (case / "0" / "tau").write_text("tau\n", encoding="utf-8")
    (case / "Allrun").write_text(
        "#!/bin/sh\nrunApplication blockMesh\ncp 0/C.org 0/C\nrunApplication setFields\nrunApplication rheoFoam\n",
        encoding="utf-8",
    )
    return case


def test_find_rheotool_cylinder_oldroyd_template_from_structured_signature(tmp_path):
    _write_minimal_cylinder_template(tmp_path)
    prompt = (
        "请复现 RheoTool 手册 5.1.6 Case 4：受限圆柱绕流 Oldroyd-BLog 教程算例。"
        "Re=0，Wi=0.7，beta=0.59，rho=1 etaS=0.59 etaP=0.41 lambda=0.7，"
        "输出阻力系数和第一法向应力差。"
    )
    compiled = compile_workflow(prompt)

    assert compiled.intent.geometry_class == "confined_cylinder"
    assert compiled.intent.reproduction_target == "rheotool_5_1_6_cylinder_oldroydb_log"

    match = find_rheotool_tutorial_template(
        prompt,
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path,
        compiled_workflow=compiled,
    )

    assert match is not None
    assert match["id"] == "rheotool_5_1_6_cylinder_oldroydb_log"
    assert match["tier"] == "A"
    assert match["source_dir"].endswith("rheoFoam/Cylinder/Oldroyd-BLog")


def test_cylinder_request_never_falls_back_to_channel_when_source_missing(tmp_path):
    _write_minimal_channel_template(tmp_path)
    prompt = (
        "RheoTool 5.1.6 Oldroyd-BLog confined cylinder benchmark "
        "Re=0 Wi=0.7 beta=0.59 etaS=0.59 etaP=0.41 lambda=0.7。"
    )
    compiled = compile_workflow(prompt)

    with pytest.raises(FileNotFoundError, match="rheotool_5_1_6_cylinder_oldroydb_log"):
        find_rheotool_tutorial_template(
            prompt,
            CaseTarget.for_solver("rheoFoam"),
            root=tmp_path,
            compiled_workflow=compiled,
        )


def test_import_rheotool_cylinder_template_preserves_mirror_mesh(tmp_path):
    _write_minimal_cylinder_template(tmp_path / "templates")
    match = find_rheotool_tutorial_template(
        "RheoTool 5.1.6 confined cylinder Oldroyd-BLog Re=0 Wi=0.7 beta=0.59",
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path / "templates",
    )
    case_dir = tmp_path / "case"

    result = import_rheotool_tutorial_template(str(case_dir), match)

    assert (case_dir / "TUTORIAL_TEMPLATE_IMPORT.json").is_file()
    assert (case_dir / "system" / "blockMeshDict").is_file()
    assert not (case_dir / "constant" / "polyMesh").exists()
    allrun = (case_dir / "Allrun").read_text(encoding="utf-8")
    assert "runApplication mirrorMesh -noFunctionObjects" in allrun
    assert "if [ -d 0/polyMesh ]; then" in allrun
    assert "cp -fr 0/polyMesh/ constant/" in allrun
    assert "runApplication decomposePar" not in allrun
    assert "runParallel" not in allrun
    assert "runApplication reconstructPar" not in allrun
    assert not (case_dir / "system" / "decomposeParDict").exists()
    assert "command -v sample" in allrun
    assert result["tutorial_template_import"]["template_id"] == "rheotool_5_1_6_cylinder_oldroydb_log"
    import_note = result["tutorial_template_import"]
    assert import_note["parallel_policy"] == "serial_certified"
    assert import_note["start_policy"] == "clean_case_dir_start_from_0"
    assert import_note["run_user_policy"] == "non_root_openfoam_user_required"
    assert import_note["certification"]["validated_runtime"] == "foundation-v9+rheotool-of90"
    assert import_note["certification"]["required_libs"] == ["libBCRheoTool.so"]
    assert import_note["certification"]["forbidden_libs"] == ["libRheoToolTutorialBCs.so"]


def test_template_import_consistency_rejects_cylinder_to_channel(tmp_path):
    source = _write_minimal_channel_template(tmp_path / "templates")
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
            user_requirement="RheoTool 5.1.6 confined cylinder Oldroyd-BLog",
        )


def test_plan_uses_rheotool_template_for_cylinder_benchmark(tmp_path, monkeypatch):
    _write_minimal_cylinder_template(tmp_path / "templates")
    monkeypatch.setenv("FOAMAGENT_RHEOTOOL_TUTORIAL_ROOT", str(tmp_path / "templates"))

    plan = generate_simulation_plan(
        user_requirement=(
            "RheoTool user guide 6.0 section 5.1.6 tutorial，Oldroyd-BLog confined cylinder benchmark，"
            "geometry channel with vertically centered cylinder radius R blockage ratio=50% "
            "Re=0 Wi=0.7 beta=0.59 rho=1 etaS=0.59 etaP=0.41 lambda=0.7，"
            "commands blockMesh mirrorMesh，输出阻力系数和第一法向应力差。"
        ),
        case_stats={},
        case_dir=str(tmp_path / "out"),
    )

    assert plan["case_solver"] == "rheoFoam"
    assert plan["tutorial_template_match"]["id"] == "rheotool_5_1_6_cylinder_oldroydb_log"
    assert any(item["file_name"] == "fvSchemes" for item in plan["subtasks"])


def test_find_rheotool_crossslot_oldroyd_template_from_structured_signature(tmp_path):
    _write_minimal_crossslot_template(tmp_path)
    prompt = (
        "请复现 RheoTool 手册 5.1.7 Case 5：二维 cross-slot Oldroyd-BLog 教程算例。"
        "Re=0，Wi=0.33，beta=0，Pe=500，etaS=0 etaP=1 lambda=0.33，"
        "启用被动标量，输出停滞点局部 Weissenberg 数和被动标量分布。"
    )
    compiled = compile_workflow(prompt)

    assert compiled.intent.geometry_class == "cross_slot"
    assert compiled.intent.dimensionless_groups["Pe"] == 500
    assert compiled.intent.reproduction_target == "rheotool_5_1_7_crossslot_oldroydb_log"

    match = find_rheotool_tutorial_template(
        prompt,
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path,
        compiled_workflow=compiled,
    )

    assert match is not None
    assert match["id"] == "rheotool_5_1_7_crossslot_oldroydb_log"
    assert match["tier"] == "A"
    assert match["source_dir"].endswith("rheoFoam/CrossSlot/Oldroyd-BLog")


def test_crossslot_request_never_falls_back_to_channel_when_source_missing(tmp_path):
    _write_minimal_channel_template(tmp_path)
    prompt = (
        "RheoTool 5.1.7 Oldroyd-BLog 2D cross-slot benchmark "
        "Re=0 Wi=0.33 beta=0 Pe=500 etaS=0 etaP=1 lambda=0.33。"
    )
    compiled = compile_workflow(prompt)

    with pytest.raises(FileNotFoundError, match="rheotool_5_1_7_crossslot_oldroydb_log"):
        find_rheotool_tutorial_template(
            prompt,
            CaseTarget.for_solver("rheoFoam"),
            root=tmp_path,
            compiled_workflow=compiled,
        )


def test_import_rheotool_crossslot_template_preserves_setfields(tmp_path):
    _write_minimal_crossslot_template(tmp_path / "templates")
    match = find_rheotool_tutorial_template(
        "RheoTool 5.1.7 cross-slot Oldroyd-BLog Re=0 Wi=0.33 beta=0 Pe=500",
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path / "templates",
    )
    case_dir = tmp_path / "case"

    result = import_rheotool_tutorial_template(str(case_dir), match)

    assert (case_dir / "TUTORIAL_TEMPLATE_IMPORT.json").is_file()
    assert (case_dir / "system" / "blockMeshDict").is_file()
    assert not (case_dir / "constant" / "polyMesh").exists()
    allrun = (case_dir / "Allrun").read_text(encoding="utf-8")
    assert "cp 0/C.org 0/C" in allrun
    assert "runApplication setFields" in allrun
    assert result["tutorial_template_import"]["template_id"] == "rheotool_5_1_7_crossslot_oldroydb_log"


def test_template_import_consistency_rejects_crossslot_to_channel(tmp_path):
    source = _write_minimal_channel_template(tmp_path / "templates")
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
            user_requirement="RheoTool 5.1.7 cross-slot Oldroyd-BLog",
        )


def test_plan_uses_rheotool_template_for_crossslot_benchmark(tmp_path, monkeypatch):
    _write_minimal_crossslot_template(tmp_path / "templates")
    monkeypatch.setenv("FOAMAGENT_RHEOTOOL_TUTORIAL_ROOT", str(tmp_path / "templates"))

    plan = generate_simulation_plan(
        user_requirement=(
            "RheoTool user guide 6.0 section 5.1.7 tutorial，Oldroyd-BLog 2D cross-slot bifurcation benchmark，"
            "geometry cross-slot four arms width W length=10W central square mesh=51x51 "
            "Re=0 Wi=0.33 beta=0 Pe=500 rho=1 etaS=0 etaP=1 lambda=0.33 D=0.002，"
            "commands blockMesh setFields，输出停滞点局部 Weissenberg 数和被动标量分布。"
        ),
        case_stats={},
        case_dir=str(tmp_path / "out"),
    )

    assert plan["case_solver"] == "rheoFoam"
    assert plan["tutorial_template_match"]["id"] == "rheotool_5_1_7_crossslot_oldroydb_log"
    assert any(item["file_name"] == "setFieldsDict" for item in plan["subtasks"])


def test_generic_oldroyd_cavity_is_b_tier_candidate_not_a_import(tmp_path):
    _write_minimal_cavity_template(tmp_path)
    prompt = "Oldroyd-B 顶盖驱动方腔，输出速度场。"
    compiled = compile_workflow(prompt)

    assert find_rheotool_tutorial_template(
        prompt,
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path,
        compiled_workflow=compiled,
        minimum_tier="A",
    ) is None

    candidate = find_rheotool_tutorial_template(
        prompt,
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path,
        compiled_workflow=compiled,
        minimum_tier="B",
    )

    assert candidate is not None
    assert candidate["id"] == "rheotool_5_1_4_cavity_oldroydb_log"
    assert candidate["tier"] == "B"
    assert candidate["rag_confidence"] == "medium"


def test_b_tier_tutorial_benchmark_intent_does_not_fall_back_to_llm(tmp_path, monkeypatch):
    _write_minimal_cavity_template(tmp_path / "templates")
    monkeypatch.setenv("FOAMAGENT_RHEOTOOL_TUTORIAL_ROOT", str(tmp_path / "templates"))

    with pytest.raises(ValueError) as excinfo:
        generate_simulation_plan(
            user_requirement=(
                "Oldroyd-B 顶盖驱动方腔 benchmark，"
                "etaS=0.5 etaP=0.5 lambda=1，输出速度场。"
            ),
            case_stats={},
            case_dir=str(tmp_path / "out"),
        )

    message = str(excinfo.value)
    assert "WORKFLOW_CLARIFICATION_REQUIRED" in message
    assert "rheotool_5_1_4_cavity_oldroydb_log" in message
    assert "B-tier" in message


def test_plan_uses_cavity_template_for_formula_groups_without_mesh_or_tutorial_words(tmp_path, monkeypatch):
    _write_minimal_cavity_template(tmp_path / "templates")
    monkeypatch.setenv("FOAMAGENT_RHEOTOOL_TUTORIAL_ROOT", str(tmp_path / "templates"))

    plan = generate_simulation_plan(
        user_requirement=(
            "顶盖驱动方腔算例。二维正方腔 L=1。流体为 Oldroyd-B 黏弹性流体，"
            "β=ηs/η0=0.5，De=λU/L=1，Re=ρUL/η0=0.01。"
            "使用无量纲制 L=1、U=1、η0=1、λ=1，因此 ηs=0.5、ηp=0.5、ρ=0.01。"
        ),
        case_stats={},
        case_dir=str(tmp_path / "out"),
    )

    assert plan["tutorial_template_match"]["id"] == "rheotool_5_1_4_cavity_oldroydb_log"
    assert plan["tutorial_template_match"]["tier"] == "A"
    assert plan["tutorial_template_candidate"] is None

def test_import_rheotool_cavity_template_normalizes_foundation_v9_layout(tmp_path):
    _write_minimal_cavity_template(tmp_path / "templates")
    match = find_rheotool_tutorial_template(
        "RheoTool 教程 5.1.4 顶盖驱动方腔 Oldroyd-BLog benchmark De=1 Re=0.01 beta=0.5",
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path / "templates",
    )
    case_dir = tmp_path / "case"

    result = import_rheotool_tutorial_template(str(case_dir), match)

    assert (case_dir / "TUTORIAL_TEMPLATE_IMPORT.json").is_file()
    assert (case_dir / "system" / "blockMeshDict").is_file()
    assert not (case_dir / "constant" / "polyMesh").exists()
    allrun = (case_dir / "Allrun").read_text(encoding="utf-8")
    control_dict = (case_dir / "system" / "controlDict").read_text(encoding="utf-8")
    fv_solution = (case_dir / "system" / "fvSolution").read_text(encoding="utf-8")
    assert '"libRheoToolTutorialBCs.so"' in control_dict
    assert "endTime         10;" in control_dict
    assert "calcKineticE" in fv_solution
    assert '"libpostProcessingRheoTool.so"' in control_dict
    assert '"libRheoToolTutorialPPUtils.so"' in control_dict
    assert "preconditioner   DILU;" in fv_solution
    assert "preconditioner\n        {" not in fv_solution
    assert "command -v sample" in allrun
    assert "runApplication postProcess -func sampleDict -latestTime" in allrun
    assert "rm -rf processor*" in allrun
    assert "runApplication decomposePar -force" in allrun
    assert "export OMPI_ALLOW_RUN_AS_ROOT=1" in allrun
    assert "export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1" in allrun
    assert "runParallel -np 4 rheoFoam" in allrun
    assert "runApplication reconstructPar" in allrun
    assert (case_dir / "system" / "decomposeParDict").is_file()

    sample = (case_dir / "system" / "sampleDict").read_text(encoding="utf-8")
    assert "lineVert_x0.5" in sample
    assert "lineHorz_y0.75" in sample
    assert "lineX35" not in sample
    assert "type            sets;" in sample
    assert 'libs            ("libsampling.so");' in sample
    assert "type        lineFace;" in sample
    assert result["tutorial_template_import"]["template_id"] == "rheotool_5_1_4_cavity_oldroydb_log"


def test_import_rheotool_cavity_template_overrides_explicit_end_time(tmp_path):
    _write_minimal_cavity_template(tmp_path / "templates")
    match = find_rheotool_tutorial_template(
        "Fattal Kupferman 2005 Oldroyd-B 顶盖驱动方腔 Re=0.01 De=1 beta=0.5",
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path / "templates",
    )
    case_dir = tmp_path / "case"

    result = import_rheotool_tutorial_template(
        str(case_dir),
        match,
        user_requirement="顶盖速度 tanh(8(t-0.5))，计算到 t=8。",
    )

    control_dict = (case_dir / "system" / "controlDict").read_text(encoding="utf-8")
    assert "endTime         8;" in control_dict
    assert "endTime         10;" not in control_dict
    assert result["tutorial_template_import"]["overrides"] == [
        {"field": "endTime", "value": 8.0, "source": "user_requirement"}
    ]


@pytest.mark.parametrize(
    "end_time_text",
    [
        "end_time: 8 (dimensionless time units)",
        "integrate to t=8",
        "run until time 8",
    ],
)
def test_import_rheotool_cavity_template_overrides_end_time_variants(tmp_path, end_time_text):
    _write_minimal_cavity_template(tmp_path / "templates")
    match = find_rheotool_tutorial_template(
        "Fattal Kupferman 2005 Oldroyd-B 顶盖驱动方腔 Re=0.01 De=1 beta=0.5",
        CaseTarget.for_solver("rheoFoam"),
        root=tmp_path / "templates",
    )
    case_dir = tmp_path / "case"

    import_rheotool_tutorial_template(str(case_dir), match, user_requirement=end_time_text)

    control_dict = (case_dir / "system" / "controlDict").read_text(encoding="utf-8")
    assert "endTime         8;" in control_dict
    assert "endTime         10;" not in control_dict


def test_plan_uses_rheotool_template_for_cavity_benchmark(tmp_path, monkeypatch):
    _write_minimal_cavity_template(tmp_path / "templates")
    monkeypatch.setenv("FOAMAGENT_RHEOTOOL_TUTORIAL_ROOT", str(tmp_path / "templates"))

    plan = generate_simulation_plan(
        user_requirement=(
            "RheoTool user guide 6.0 section 5.1.4 tutorial，"
            "Oldroyd-BLog 顶盖驱动方腔 benchmark，geometry square cavity side length L "
            "mesh=127x127 top lid velocity U stationary walls noSlip "
            "Re=0.01 De=1 beta=0.5 rho=0.01 etaS=0.5 etaP=0.5 lambda=1 "
            "stabilization=coupling passive scalar off，commands blockMesh sample，"
            "输出中心线速度、theta_xy 和平均动能。"
        ),
        case_stats={},
        case_dir=str(tmp_path / "out"),
    )

    assert plan["case_solver"] == "rheoFoam"
    assert plan["tutorial_template_match"]["id"] == "rheotool_5_1_4_cavity_oldroydb_log"
    assert plan["benchmark_match"] is None
    assert any(item["file_name"] == "fvSchemes" for item in plan["subtasks"])


def test_plan_uses_cavity_template_for_fk2005_signature_without_tutorial_words(tmp_path, monkeypatch):
    _write_minimal_cavity_template(tmp_path / "templates")
    monkeypatch.setenv("FOAMAGENT_RHEOTOOL_TUTORIAL_ROOT", str(tmp_path / "templates"))

    plan = generate_simulation_plan(
        user_requirement=(
            "请复现 Fattal & Kupferman 2005 的 Oldroyd-B 顶盖驱动方腔算例。"
            "二维正方腔 L=1，127×127 均匀结构网格。"
            "参数为 beta=0.5，De=1，Re=0.01，etaS=0.5 etaP=0.5 lambda=1。"
            "输出 x=0.5 的 u(y)、y=0.75 的 Theta_xy 和平均动能 Ek(t)。"
        ),
        case_stats={},
        case_dir=str(tmp_path / "out"),
    )

    assert plan["benchmark_match"] is None
    assert plan["tutorial_template_match"]["id"] == "rheotool_5_1_4_cavity_oldroydb_log"
    assert plan["similar_case_advice"].use_scope == "rheotool tutorial template import"



def test_plan_prefers_cavity_tutorial_over_polluted_rude_class_text(tmp_path, monkeypatch):
    _write_minimal_cavity_template(tmp_path / "templates")
    monkeypatch.setenv("FOAMAGENT_RHEOTOOL_TUTORIAL_ROOT", str(tmp_path / "templates"))

    plan = generate_simulation_plan(
        user_requirement=(
            "RheoTool user guide 6.0 section 5.1.4 tutorial，Oldroyd-BLog 顶盖驱动方腔 benchmark，"
            "RUDE-class log-conformation reference wording should not import RUDE，"
            "mesh=127x127 Re=0.01 De=1 beta=0.5 etaS=0.5 etaP=0.5 lambda=1，"
            "Fattal & Kupferman 2005 对比。"
        ),
        case_stats={},
        case_dir=str(tmp_path / "out"),
    )

    assert plan["benchmark_match"] is None
    assert plan["tutorial_template_match"]["id"] == "rheotool_5_1_4_cavity_oldroydb_log"
