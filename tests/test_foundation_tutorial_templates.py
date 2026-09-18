from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.foundation_templates import (  # noqa: E402
    find_foundation_tutorial_template,
    import_foundation_tutorial_template,
    summarize_foundation_multi_case,
)
from services.plan import generate_simulation_plan  # noqa: E402
from models import CaseTarget  # noqa: E402


def _write_minimal_foundation_cavity_template(root: Path) -> Path:
    case = root / "incompressible" / "icoFoam" / "cavity" / "cavity"
    (case / "0").mkdir(parents=True)
    (case / "constant").mkdir()
    (case / "system").mkdir()
    (case / "0" / "U").write_text("boundaryField { movingWall { type fixedValue; } }\n", encoding="utf-8")
    (case / "0" / "p").write_text("boundaryField { fixedWalls { type zeroGradient; } }\n", encoding="utf-8")
    (case / "constant" / "physicalProperties").write_text("nu [0 2 -1 0 0 0 0] 0.01;\n", encoding="utf-8")
    (case / "system" / "blockMeshDict").write_text("vertices (); blocks (); boundary ();\n", encoding="utf-8")
    (case / "system" / "controlDict").write_text("application icoFoam;\n", encoding="utf-8")
    (case / "system" / "fvSchemes").write_text("ddtSchemes {}\n", encoding="utf-8")
    (case / "system" / "fvSolution").write_text("solvers {}\n", encoding="utf-8")
    return case


def _write_minimal_foundation_cavity_family_template(root: Path) -> Path:
    parent = root / "incompressible" / "icoFoam" / "cavity"
    parent.mkdir(parents=True)
    (parent / "Allrun").write_text("#!/bin/sh\ncd ${0%/*} || exit 1\n", encoding="utf-8")
    for subcase in ("cavity", "cavityGrade", "cavityClipped"):
        case = parent / subcase
        (case / "0").mkdir(parents=True)
        (case / "constant").mkdir()
        (case / "system").mkdir()
        (case / "0" / "U").write_text("boundaryField {}\n", encoding="utf-8")
        (case / "0" / "p").write_text("boundaryField {}\n", encoding="utf-8")
        (case / "constant" / "physicalProperties").write_text("nu [0 2 -1 0 0 0 0] 0.01;\n", encoding="utf-8")
        (case / "system" / "blockMeshDict").write_text("vertices (); blocks (); boundary ();\n", encoding="utf-8")
        (case / "system" / "controlDict").write_text("application icoFoam;\n", encoding="utf-8")
        (case / "system" / "fvSchemes").write_text("ddtSchemes {}\n", encoding="utf-8")
        (case / "system" / "fvSolution").write_text("solvers {}\n", encoding="utf-8")
    return parent


PITZDAILY_TEMPLATE_CASES = {
    "foundation_v10_simplefoam_pitzdaily": (
        "incompressible/simpleFoam/pitzDaily",
        "simpleFoam",
        ("U", "p"),
        ("momentumTransport", "physicalProperties"),
    ),
    "foundation_v10_pimplefoam_ras_pitzdaily": (
        "incompressible/pimpleFoam/RAS/pitzDaily",
        "pimpleFoam",
        ("U", "p", "k", "epsilon", "nut"),
        ("momentumTransport", "physicalProperties"),
    ),
    "foundation_v10_pisofoam_les_pitzdaily": (
        "incompressible/pisoFoam/LES/pitzDaily",
        "pisoFoam",
        ("U", "p", "k", "nut"),
        ("momentumTransport", "physicalProperties"),
    ),
    "foundation_v10_potentialfoam_pitzdaily": (
        "basic/potentialFoam/pitzDaily",
        "potentialFoam",
        ("U.orig", "p.orig"),
        (),
    ),
    "foundation_v10_scalartransport_pitzdaily": (
        "basic/scalarTransportFoam/pitzDaily",
        "scalarTransportFoam",
        ("T", "U"),
        ("physicalProperties",),
    ),
}


def _write_minimal_foundation_pitzdaily_template(
    root: Path,
    template_id: str = "foundation_v10_simplefoam_pitzdaily",
) -> Path:
    relative_path, solver, zero_fields, constant_files = PITZDAILY_TEMPLATE_CASES[template_id]
    case = root / relative_path
    (case / "0").mkdir(parents=True)
    (case / "constant").mkdir()
    (case / "system").mkdir()
    for name in zero_fields:
        (case / "0" / name).write_text("boundaryField {}\n", encoding="utf-8")
    for name in constant_files:
        content = "simulationType RAS;\n" if name == "momentumTransport" else "nu [0 2 -1 0 0 0 0] 1e-05;\n"
        (case / "constant" / name).write_text(content, encoding="utf-8")
    (case / "system" / "controlDict").write_text(f"application {solver};\n", encoding="utf-8")
    (case / "system" / "fvSchemes").write_text("divSchemes {}\n", encoding="utf-8")
    (case / "system" / "fvSolution").write_text("solvers {}\n", encoding="utf-8")
    return case


CYLINDER_TEMPLATE_CASES = {
    "foundation_v10_potentialfoam_cylinder": (
        "basic/potentialFoam/cylinder",
        "potentialFoam",
        ("U.orig", "p.orig"),
        (),
        ("blockMeshDict", "controlDict", "fvSchemes", "fvSolution"),
    ),
    "foundation_v10_pimplefoam_laminar_offsetcylinder": (
        "incompressible/pimpleFoam/laminar/offsetCylinder",
        "pimpleFoam",
        ("U", "p"),
        ("momentumTransport", "physicalProperties"),
        ("blockMeshDict", "controlDict", "fvSchemes", "fvSolution"),
    ),
    "foundation_v10_interfoam_laminar_sloshingcylinder": (
        "multiphase/interFoam/laminar/sloshingCylinder",
        "interFoam",
        ("U", "p_rgh", "alpha.water.orig"),
        ("dynamicMeshDict", "g", "momentumTransport", "phaseProperties"),
        ("blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "meshQualityDict", "setFieldsDict", "snappyHexMeshDict"),
    ),
}


def _write_minimal_foundation_cylinder_template(
    root: Path,
    template_id: str = "foundation_v10_potentialfoam_cylinder",
) -> Path:
    relative_path, solver, zero_fields, constant_files, system_files = CYLINDER_TEMPLATE_CASES[template_id]
    case = root / relative_path
    (case / "0").mkdir(parents=True)
    (case / "constant").mkdir()
    (case / "system").mkdir()
    for name in zero_fields:
        (case / "0" / name).write_text("boundaryField {}\n", encoding="utf-8")
    for name in constant_files:
        if name == "g":
            content = "value (0 -9.81 0);\n"
        elif name == "phaseProperties":
            content = "phases (water air);\n"
        elif name == "physicalProperties":
            content = "nu [0 2 -1 0 0 0 0] 1e-05;\n"
        else:
            content = "simulationType laminar;\n"
        (case / "constant" / name).write_text(content, encoding="utf-8")
    for name in system_files:
        if name == "controlDict":
            content = f"application {solver};\n"
        elif name == "blockMeshDict":
            content = "vertices (); blocks (); boundary ();\n"
        elif name == "setFieldsDict":
            content = "defaultFieldValues ();\n"
        else:
            content = "FoamFile {}\n"
        (case / "system" / name).write_text(content, encoding="utf-8")
    return case


FORWARDSTEP_TEMPLATE_CASES = {
    "foundation_v10_rhocentralfoam_forwardstep": (
        "compressible/rhoCentralFoam/forwardStep",
        "rhoCentralFoam",
    ),
    "foundation_v10_rhopimplefoam_laminar_forwardstep": (
        "compressible/rhoPimpleFoam/laminar/forwardStep",
        "rhoPimpleFoam",
    ),
}


def _write_minimal_foundation_forwardstep_template(
    root: Path,
    template_id: str = "foundation_v10_rhocentralfoam_forwardstep",
) -> Path:
    relative_path, solver = FORWARDSTEP_TEMPLATE_CASES[template_id]
    case = root / relative_path
    (case / "0").mkdir(parents=True)
    (case / "constant").mkdir()
    (case / "system").mkdir()
    for name in ("U", "p", "T"):
        (case / "0" / name).write_text("boundaryField {}\n", encoding="utf-8")
    (case / "constant" / "momentumTransport").write_text("simulationType laminar;\n", encoding="utf-8")
    (case / "constant" / "physicalProperties").write_text("thermoType {}\n", encoding="utf-8")
    (case / "system" / "blockMeshDict").write_text("vertices (); blocks (); boundary ();\n", encoding="utf-8")
    (case / "system" / "controlDict").write_text(f"application {solver};\n", encoding="utf-8")
    (case / "system" / "fvSchemes").write_text("divSchemes {}\n", encoding="utf-8")
    (case / "system" / "fvSolution").write_text("solvers {}\n", encoding="utf-8")
    return case


def _write_minimal_foundation_bernardcells_template(root: Path) -> Path:
    case = root / "heatTransfer" / "buoyantFoam" / "BernardCells"
    (case / "0").mkdir(parents=True)
    (case / "constant").mkdir()
    (case / "system").mkdir()
    for name in ("U", "p", "p_rgh", "T", "alphat", "epsilon", "k", "nut"):
        (case / "0" / name).write_text("boundaryField {}\n", encoding="utf-8")
    (case / "constant" / "g").write_text("value (0 -9.81 0);\n", encoding="utf-8")
    (case / "constant" / "momentumTransport").write_text("simulationType RAS;\n", encoding="utf-8")
    (case / "constant" / "physicalProperties").write_text("thermoType {}\n", encoding="utf-8")
    (case / "system" / "blockMeshDict").write_text("vertices (); blocks (); boundary ();\n", encoding="utf-8")
    (case / "system" / "controlDict").write_text("application buoyantFoam;\n", encoding="utf-8")
    (case / "system" / "fvSchemes").write_text("divSchemes {}\n", encoding="utf-8")
    (case / "system" / "fvSolution").write_text("solvers {}\n", encoding="utf-8")
    return case


ADDITIONAL_V10_TEMPLATE_CASES = {
    "foundation_v10_pimplefoam_laminar_planarpoiseuille": (
        "incompressible/pimpleFoam/laminar/planarPoiseuille",
        "pimpleFoam",
        ("U", "p", "sigma"),
        ("fvModels", "momentumTransport", "physicalProperties"),
        ("blockMeshDict", "controlDict", "fvSchemes", "fvSolution"),
    ),
    "foundation_v10_rhocentralfoam_obliqueshock": (
        "compressible/rhoCentralFoam/obliqueShock",
        "rhoCentralFoam",
        ("U", "p", "T"),
        ("momentumTransport", "physicalProperties"),
        ("blockMeshDict", "controlDict", "fvSchemes", "fvSolution"),
    ),
    "foundation_v10_rhocentralfoam_shocktube": (
        "compressible/rhoCentralFoam/shockTube",
        "rhoCentralFoam",
        ("U.orig", "p.orig", "T.orig"),
        ("momentumTransport", "physicalProperties"),
        ("blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "setFieldsDict", "sample"),
    ),
    "foundation_v10_rhopimplefoam_laminar_shocktube": (
        "compressible/rhoPimpleFoam/laminar/shockTube",
        "rhoPimpleFoam",
        ("U.orig", "p.orig", "T.orig"),
        ("momentumTransport", "physicalProperties"),
        ("blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "setFieldsDict", "sample"),
    ),
    "foundation_v10_simplefoam_airfoil2d": (
        "incompressible/simpleFoam/airFoil2D",
        "simpleFoam",
        ("U", "p", "nut", "nuTilda"),
        ("momentumTransport", "physicalProperties"),
        ("controlDict", "fvSchemes", "fvSolution"),
    ),
    "foundation_v10_interfoam_laminar_capillaryrise": (
        "multiphase/interFoam/laminar/capillaryRise",
        "interFoam",
        ("U", "p_rgh", "alpha.water.orig"),
        ("g", "momentumTransport", "phaseProperties"),
        ("blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "setFieldsDict"),
    ),
    "foundation_v10_interfoam_laminar_wave": (
        "multiphase/interFoam/laminar/wave",
        "interFoam",
        ("U.orig", "p_rgh", "alpha.water.orig"),
        ("fvModels", "g", "momentumTransport", "phaseProperties", "waveProperties"),
        (
            "blockMeshDict", "controlDict", "decomposeParDict", "extrudeMeshDict",
            "fvSchemes", "fvSolution", "setWavesDict",
        ),
    ),
}


def _write_minimal_additional_v10_template(root: Path, template_id: str) -> Path:
    relative_path, solver, zero_fields, constant_files, system_files = ADDITIONAL_V10_TEMPLATE_CASES[template_id]
    case = root / relative_path
    (case / "0").mkdir(parents=True)
    (case / "constant").mkdir()
    (case / "system").mkdir()
    for name in zero_fields:
        (case / "0" / name).write_text("boundaryField {}\n", encoding="utf-8")
    for name in constant_files:
        if name == "g":
            content = "value (0 -9.81 0);\n"
        elif name == "phaseProperties":
            content = "phases (water air);\n"
        elif name == "waveProperties":
            content = "waves (regular);\n"
        else:
            content = "simulationType laminar;\n"
        (case / "constant" / name).write_text(content, encoding="utf-8")
    if template_id == "foundation_v10_simplefoam_airfoil2d":
        (case / "constant" / "polyMesh").mkdir()
        (case / "constant" / "polyMesh" / "points").write_text("FoamFile {}\n", encoding="utf-8")
    for name in system_files:
        if name == "controlDict":
            content = f"application {solver};\n"
        elif name == "blockMeshDict":
            content = "vertices (); blocks (); boundary ();\n"
        else:
            content = "FoamFile {}\n"
        (case / "system" / name).write_text(content, encoding="utf-8")
    return case


DAMBREAK_TEMPLATE_CASES = {
    "foundation_v10_interfoam_dambreak": (
        "multiphase/interFoam/laminar/damBreak/damBreak",
        ("U", "p_rgh", "alpha.water.orig"),
        ("g", "momentumTransport", "phaseProperties"),
        ("blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "setFieldsDict"),
    ),
    "foundation_v10_interfoam_dambreak_with_obstacle": (
        "multiphase/interFoam/laminar/damBreakWithObstacle",
        ("U.orig", "p_rgh", "alpha.water.orig"),
        ("g", "dynamicMeshDict", "momentumTransport", "phaseProperties"),
        ("blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "setFieldsDict", "topoSetDict"),
    ),
    "foundation_v10_interfoam_ras_dambreak": (
        "multiphase/interFoam/RAS/damBreak/damBreak",
        ("U", "p_rgh", "alpha.water.orig", "k", "epsilon", "nut"),
        ("g", "fvModels", "momentumTransport", "phaseProperties"),
        ("blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "setFieldsDict"),
    ),
    "foundation_v10_interfoam_ras_dambreak_porous_baffle": (
        "multiphase/interFoam/RAS/damBreakPorousBaffle",
        ("U.orig", "p_rgh.orig", "alpha.water.orig", "k.orig", "epsilon.orig", "nut.orig"),
        ("g", "momentumTransport", "phaseProperties"),
        ("blockMeshDict", "controlDict", "createBafflesDict", "fvSchemes", "fvSolution", "setFieldsDict"),
    ),
}


def _write_minimal_foundation_dambreak_template(
    root: Path,
    template_id: str = "foundation_v10_interfoam_dambreak",
) -> Path:
    relative_path, zero_fields, constant_files, system_files = DAMBREAK_TEMPLATE_CASES[template_id]
    case = root / relative_path
    (case / "0").mkdir(parents=True)
    (case / "constant").mkdir()
    (case / "system").mkdir()
    for name in zero_fields:
        (case / "0" / name).write_text("boundaryField {}\n", encoding="utf-8")
    for name in constant_files:
        if name == "g":
            content = "value (0 -9.81 0);\n"
        elif name == "phaseProperties":
            content = "phases (water air);\n"
        else:
            content = "simulationType laminar;\n"
        (case / "constant" / name).write_text(content, encoding="utf-8")
    for name in system_files:
        if name == "controlDict":
            content = "application interFoam;\n"
        elif name == "blockMeshDict":
            content = "vertices (); blocks (); boundary ();\n"
        elif name == "setFieldsDict":
            content = "defaultFieldValues ();\n"
        else:
            content = "FoamFile {}\n"
        (case / "system" / name).write_text(content, encoding="utf-8")
    return case


def _write_minimal_foundation_dambreak_family_template(root: Path, *, ras: bool = False) -> Path:
    parent = root / "multiphase" / "interFoam" / ("RAS" if ras else "laminar") / "damBreak"
    parent.mkdir(parents=True)
    (parent / "Allrun").write_text("#!/bin/sh\ncd ${0%/*} || exit 1\n", encoding="utf-8")
    child_id = "foundation_v10_interfoam_ras_dambreak" if ras else "foundation_v10_interfoam_dambreak"
    _write_minimal_foundation_dambreak_template(root, child_id)
    return parent


def test_find_foundation_v10_cavity_template(tmp_path):
    _write_minimal_foundation_cavity_template(tmp_path)
    target = CaseTarget.for_solver("icoFoam")

    match = find_foundation_tutorial_template(
        "OpenFOAM v10 cavity 模板基线，使用模板原始参数",
        target,
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": "foundation_v10_icofoam_cavity"})()},
        )(),
        template_root=tmp_path,
    )

    assert match is not None
    assert match["id"] == "foundation_v10_icofoam_cavity"
    assert match["template_kind"] == "foundation"
    assert match["solver"] == "icoFoam"
    assert match["source_dir"].endswith("incompressible/icoFoam/cavity/cavity")


def test_find_foundation_v10_cavity_full_allrun_template(tmp_path):
    _write_minimal_foundation_cavity_family_template(tmp_path)

    match = find_foundation_tutorial_template(
        "OpenFOAM v10 cavity 选择完整官方教程族 full_allrun",
        CaseTarget.for_solver("icoFoam"),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": "foundation_v10_icofoam_cavity_full_allrun"})()},
        )(),
        template_root=tmp_path,
    )

    assert match is not None
    assert match["id"] == "foundation_v10_icofoam_cavity_full_allrun"
    assert match["multi_case"] is True
    assert match["source_dir"].endswith("incompressible/icoFoam/cavity")


def test_find_foundation_v10_pitzdaily_template(tmp_path):
    _write_minimal_foundation_pitzdaily_template(tmp_path)

    match = find_foundation_tutorial_template(
        "OpenFOAM v10 pitzDaily 模板基线，使用模板原始参数",
        CaseTarget.for_solver("simpleFoam"),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": "foundation_v10_simplefoam_pitzdaily"})()},
        )(),
        template_root=tmp_path,
    )

    assert match is not None
    assert match["id"] == "foundation_v10_simplefoam_pitzdaily"
    assert match["solver"] == "simpleFoam"
    assert match["source_dir"].endswith("incompressible/simpleFoam/pitzDaily")


@pytest.mark.parametrize(
    ("template_id", "solver", "source_suffix"),
    [
        ("foundation_v10_pimplefoam_ras_pitzdaily", "pimpleFoam", "incompressible/pimpleFoam/RAS/pitzDaily"),
        ("foundation_v10_pisofoam_les_pitzdaily", "pisoFoam", "incompressible/pisoFoam/LES/pitzDaily"),
        ("foundation_v10_potentialfoam_pitzdaily", "potentialFoam", "basic/potentialFoam/pitzDaily"),
        ("foundation_v10_scalartransport_pitzdaily", "scalarTransportFoam", "basic/scalarTransportFoam/pitzDaily"),
    ],
)
def test_find_foundation_v10_pitzdaily_variant_templates(tmp_path, template_id, solver, source_suffix):
    _write_minimal_foundation_pitzdaily_template(tmp_path, template_id)

    match = find_foundation_tutorial_template(
        f"OpenFOAM v10 pitzDaily {solver} 模板，使用模板原始参数",
        CaseTarget.for_solver(solver),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": template_id})()},
        )(),
        template_root=tmp_path,
    )

    assert match is not None
    assert match["id"] == template_id
    assert match["solver"] == solver
    assert match["source_dir"].endswith(source_suffix)


@pytest.mark.parametrize(
    ("template_id", "solver", "source_suffix"),
    [
        ("foundation_v10_potentialfoam_cylinder", "potentialFoam", "basic/potentialFoam/cylinder"),
        (
            "foundation_v10_pimplefoam_laminar_offsetcylinder",
            "pimpleFoam",
            "incompressible/pimpleFoam/laminar/offsetCylinder",
        ),
        (
            "foundation_v10_interfoam_laminar_sloshingcylinder",
            "interFoam",
            "multiphase/interFoam/laminar/sloshingCylinder",
        ),
    ],
)
def test_find_foundation_v10_cylinder_variant_templates(tmp_path, template_id, solver, source_suffix):
    _write_minimal_foundation_cylinder_template(tmp_path, template_id)

    match = find_foundation_tutorial_template(
        f"OpenFOAM v10 cylinder 选择 {solver} 变体，使用模板原始参数",
        CaseTarget.for_solver(solver),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": template_id})()},
        )(),
        template_root=tmp_path,
    )

    assert match is not None
    assert match["id"] == template_id
    assert match["solver"] == solver
    assert match["source_dir"].endswith(source_suffix)


@pytest.mark.parametrize(
    ("template_id", "solver", "source_suffix"),
    [
        (
            "foundation_v10_rhocentralfoam_forwardstep",
            "rhoCentralFoam",
            "compressible/rhoCentralFoam/forwardStep",
        ),
        (
            "foundation_v10_rhopimplefoam_laminar_forwardstep",
            "rhoPimpleFoam",
            "compressible/rhoPimpleFoam/laminar/forwardStep",
        ),
    ],
)
def test_find_foundation_v10_forwardstep_variant_templates(tmp_path, template_id, solver, source_suffix):
    _write_minimal_foundation_forwardstep_template(tmp_path, template_id)

    match = find_foundation_tutorial_template(
        f"OpenFOAM v10 forwardStep 选择 {solver} 可压缩变体，使用模板原始参数",
        CaseTarget.for_solver(solver),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": template_id})()},
        )(),
        template_root=tmp_path,
    )

    assert match is not None
    assert match["id"] == template_id
    assert match["solver"] == solver
    assert match["source_dir"].endswith(source_suffix)


def test_find_foundation_v10_bernardcells_template(tmp_path):
    _write_minimal_foundation_bernardcells_template(tmp_path)

    match = find_foundation_tutorial_template(
        "OpenFOAM v10 Rayleigh-Benard / BernardCells buoyantFoam 教程，使用模板原始参数",
        CaseTarget.for_solver("buoyantFoam"),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": "foundation_v10_buoyantfoam_bernardcells"})()},
        )(),
        template_root=tmp_path,
    )

    assert match is not None
    assert match["id"] == "foundation_v10_buoyantfoam_bernardcells"
    assert match["solver"] == "buoyantFoam"
    assert match["source_dir"].endswith("heatTransfer/buoyantFoam/BernardCells")


@pytest.mark.parametrize(
    ("template_id", "solver", "prompt", "source_suffix"),
    [
        (
            "foundation_v10_pimplefoam_laminar_planarpoiseuille",
            "pimpleFoam",
            "OpenFOAM v10 pimpleFoam planarPoiseuille 平面泊肃叶流教程，使用模板原始参数",
            "incompressible/pimpleFoam/laminar/planarPoiseuille",
        ),
        (
            "foundation_v10_rhocentralfoam_obliqueshock",
            "rhoCentralFoam",
            "OpenFOAM v10 rhoCentralFoam obliqueShock 斜激波教程，使用模板原始参数",
            "compressible/rhoCentralFoam/obliqueShock",
        ),
        (
            "foundation_v10_rhocentralfoam_shocktube",
            "rhoCentralFoam",
            "OpenFOAM v10 rhoCentralFoam shockTube 激波管教程，使用模板原始参数",
            "compressible/rhoCentralFoam/shockTube",
        ),
        (
            "foundation_v10_rhopimplefoam_laminar_shocktube",
            "rhoPimpleFoam",
            "OpenFOAM v10 rhoPimpleFoam laminar shockTube 激波管教程，使用模板原始参数",
            "compressible/rhoPimpleFoam/laminar/shockTube",
        ),
        (
            "foundation_v10_simplefoam_airfoil2d",
            "simpleFoam",
            "OpenFOAM v10 simpleFoam airFoil2D 翼型教程，使用模板原始参数",
            "incompressible/simpleFoam/airFoil2D",
        ),
        (
            "foundation_v10_interfoam_laminar_capillaryrise",
            "interFoam",
            "OpenFOAM v10 interFoam capillaryRise 毛细上升教程，使用模板原始参数",
            "multiphase/interFoam/laminar/capillaryRise",
        ),
        (
            "foundation_v10_interfoam_laminar_wave",
            "interFoam",
            "OpenFOAM v10 interFoam wave 波浪教程，使用模板原始参数",
            "multiphase/interFoam/laminar/wave",
        ),
    ],
)
def test_find_additional_foundation_v10_templates(tmp_path, template_id, solver, prompt, source_suffix):
    _write_minimal_additional_v10_template(tmp_path, template_id)

    match = find_foundation_tutorial_template(
        prompt,
        CaseTarget.for_solver(solver),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": template_id})()},
        )(),
        template_root=tmp_path,
    )

    assert match is not None
    assert match["id"] == template_id
    assert match["solver"] == solver
    assert match["source_dir"].endswith(source_suffix)


def test_find_foundation_v10_dambreak_template(tmp_path):
    _write_minimal_foundation_dambreak_template(tmp_path)

    match = find_foundation_tutorial_template(
        "OpenFOAM v10 damBreak 模板基线，使用模板原始参数",
        CaseTarget.for_solver("interFoam"),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": "foundation_v10_interfoam_dambreak"})()},
        )(),
        template_root=tmp_path,
    )

    assert match is not None
    assert match["id"] == "foundation_v10_interfoam_dambreak"
    assert match["solver"] == "interFoam"
    assert match["source_dir"].endswith("multiphase/interFoam/laminar/damBreak/damBreak")


@pytest.mark.parametrize(
    ("template_id", "source_suffix"),
    [
        (
            "foundation_v10_interfoam_dambreak_with_obstacle",
            "multiphase/interFoam/laminar/damBreakWithObstacle",
        ),
        (
            "foundation_v10_interfoam_ras_dambreak",
            "multiphase/interFoam/RAS/damBreak/damBreak",
        ),
        (
            "foundation_v10_interfoam_ras_dambreak_porous_baffle",
            "multiphase/interFoam/RAS/damBreakPorousBaffle",
        ),
    ],
)
def test_find_foundation_v10_dambreak_variant_templates(tmp_path, template_id, source_suffix):
    _write_minimal_foundation_dambreak_template(tmp_path, template_id)

    match = find_foundation_tutorial_template(
        "OpenFOAM v10 damBreak 选择具体 interFoam 变体，使用模板原始参数",
        CaseTarget.for_solver("interFoam"),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": template_id})()},
        )(),
        template_root=tmp_path,
    )

    assert match is not None
    assert match["id"] == template_id
    assert match["solver"] == "interFoam"
    assert match["source_dir"].endswith(source_suffix)


@pytest.mark.parametrize(
    ("template_id", "ras", "source_suffix"),
    [
        (
            "foundation_v10_interfoam_dambreak_laminar_full_allrun",
            False,
            "multiphase/interFoam/laminar/damBreak",
        ),
        (
            "foundation_v10_interfoam_ras_dambreak_full_allrun",
            True,
            "multiphase/interFoam/RAS/damBreak",
        ),
    ],
)
def test_find_foundation_v10_dambreak_full_allrun_templates(tmp_path, template_id, ras, source_suffix):
    _write_minimal_foundation_dambreak_family_template(tmp_path, ras=ras)

    match = find_foundation_tutorial_template(
        "OpenFOAM v10 damBreak 选择完整官方教程族 full_allrun",
        CaseTarget.for_solver("interFoam"),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": template_id})()},
        )(),
        template_root=tmp_path,
    )

    assert match is not None
    assert match["id"] == template_id
    assert match["multi_case"] is True
    assert match["source_dir"].endswith(source_suffix)


def test_plan_uses_foundation_template_without_llm(tmp_path, monkeypatch):
    _write_minimal_foundation_cavity_template(tmp_path / "templates")
    monkeypatch.setenv("FOAMAGENT_OPENFOAM10_TUTORIAL_ROOT", str(tmp_path / "templates"))

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("LLM-backed case parsing should not run for Foundation template baselines")

    monkeypatch.setattr("services.plan.parse_requirement_to_case_info", fail_if_called)

    plan = generate_simulation_plan(
        user_requirement=(
            "我想评估水在顶盖驱动方腔中的主涡结构和中心线速度分布。"
            "可以先使用平台已有 OpenFOAM v10 cavity 模板做基线评估，使用模板原始参数。"
        ),
        case_stats={},
        case_dir=str(tmp_path / "out"),
    )

    assert plan["case_solver"] == "icoFoam"
    assert plan["channel"] == "v10-foundation"
    assert plan["tutorial_template_match"]["id"] == "foundation_v10_icofoam_cavity"
    assert plan["tutorial_template_match"]["template_kind"] == "foundation"
    assert any(item["file_name"] == "Allrun" for item in plan["subtasks"])


def test_plan_uses_foundation_pitzdaily_without_llm(tmp_path, monkeypatch):
    _write_minimal_foundation_pitzdaily_template(tmp_path / "templates")
    monkeypatch.setenv("FOAMAGENT_OPENFOAM10_TUTORIAL_ROOT", str(tmp_path / "templates"))
    monkeypatch.setattr(
        "services.plan.parse_requirement_to_case_info",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("LLM parse should not run")),
    )

    plan = generate_simulation_plan(
        user_requirement=(
            "我想使用平台已有 OpenFOAM v10 pitzDaily 模板做基线评估，"
            "模拟牛顿流体后向台阶稳态回流区，使用模板原始参数。"
        ),
        case_stats={},
        case_dir=str(tmp_path / "out"),
    )

    assert plan["case_solver"] == "simpleFoam"
    assert plan["channel"] == "v10-foundation"
    assert plan["tutorial_template_match"]["id"] == "foundation_v10_simplefoam_pitzdaily"


def test_import_foundation_template_writes_single_case_allrun_and_note(tmp_path):
    _write_minimal_foundation_cavity_template(tmp_path / "templates")
    match = find_foundation_tutorial_template(
        "OpenFOAM v10 cavity 模板基线，使用模板原始参数",
        CaseTarget.for_solver("icoFoam"),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": "foundation_v10_icofoam_cavity"})()},
        )(),
        template_root=tmp_path / "templates",
    )

    out = import_foundation_tutorial_template(str(tmp_path / "case"), match)

    case_dir = tmp_path / "case"
    assert (case_dir / "0" / "U").is_file()
    assert (case_dir / "constant" / "physicalProperties").is_file()
    assert (case_dir / "system" / "controlDict").is_file()
    assert "runApplication blockMesh" in (case_dir / "Allrun").read_text(encoding="utf-8")
    assert "runApplication checkMesh" in (case_dir / "Allrun").read_text(encoding="utf-8")
    assert "runApplication $(getApplication)" in (case_dir / "Allrun").read_text(encoding="utf-8")
    assert out["tutorial_template_import"]["template_id"] == "foundation_v10_icofoam_cavity"
    assert (case_dir / "TUTORIAL_TEMPLATE_IMPORT.json").is_file()


def test_import_foundation_dambreak_template_writes_setfields_allrun(tmp_path):
    _write_minimal_foundation_dambreak_template(tmp_path / "templates")
    match = find_foundation_tutorial_template(
        "OpenFOAM v10 damBreak 模板基线，使用模板原始参数",
        CaseTarget.for_solver("interFoam"),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": "foundation_v10_interfoam_dambreak"})()},
        )(),
        template_root=tmp_path / "templates",
    )

    out = import_foundation_tutorial_template(str(tmp_path / "case"), match)

    allrun = (tmp_path / "case" / "Allrun").read_text(encoding="utf-8")
    assert "runApplication blockMesh" in allrun
    assert "runApplication checkMesh" in allrun
    assert "runApplication setFields" in allrun
    assert "runApplication $(getApplication)" in allrun
    assert out["tutorial_template_import"]["template_id"] == "foundation_v10_interfoam_dambreak"


@pytest.mark.parametrize(
    ("template_id", "expected_steps"),
    [
        (
            "foundation_v10_interfoam_dambreak_with_obstacle",
            ("runApplication topoSet", "runApplication subsetMesh -overwrite c0 -patch walls -noFields"),
        ),
        (
            "foundation_v10_interfoam_ras_dambreak",
            ("runApplication setFields", "runApplication $(getApplication)"),
        ),
        (
            "foundation_v10_interfoam_ras_dambreak_porous_baffle",
            ("runApplication createBaffles -overwrite", "runApplication $(getApplication)"),
        ),
    ],
)
def test_import_foundation_dambreak_variants_write_allrun(tmp_path, template_id, expected_steps):
    _write_minimal_foundation_dambreak_template(tmp_path / "templates", template_id)
    match = find_foundation_tutorial_template(
        "OpenFOAM v10 damBreak 选择具体 interFoam 变体，使用模板原始参数",
        CaseTarget.for_solver("interFoam"),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": template_id})()},
        )(),
        template_root=tmp_path / "templates",
    )

    out = import_foundation_tutorial_template(str(tmp_path / "case"), match)

    allrun = (tmp_path / "case" / "Allrun").read_text(encoding="utf-8")
    assert "runApplication blockMesh" in allrun
    assert "runApplication checkMesh" in allrun
    for step in expected_steps:
        assert step in allrun
    assert out["tutorial_template_import"]["template_id"] == template_id


@pytest.mark.parametrize(
    ("template_id", "ras"),
    [
        ("foundation_v10_interfoam_dambreak_laminar_full_allrun", False),
        ("foundation_v10_interfoam_ras_dambreak_full_allrun", True),
    ],
)
def test_import_foundation_dambreak_full_allrun_preserves_parent_allrun(tmp_path, template_id, ras):
    _write_minimal_foundation_dambreak_family_template(tmp_path / "templates", ras=ras)
    match = find_foundation_tutorial_template(
        "OpenFOAM v10 damBreak 选择完整官方教程族 full_allrun",
        CaseTarget.for_solver("interFoam"),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": template_id})()},
        )(),
        template_root=tmp_path / "templates",
    )

    out = import_foundation_tutorial_template(str(tmp_path / "case"), match)
    case_dir = tmp_path / "case"
    for subcase in ("damBreak", "damBreakFine"):
        (case_dir / subcase).mkdir(exist_ok=True)
        (case_dir / subcase / "1").mkdir(exist_ok=True)
        (case_dir / subcase / "log.interFoam").write_text("End\n", encoding="utf-8")

    summary = summarize_foundation_multi_case(case_dir)

    assert out["tutorial_template_import"]["template_id"] == template_id
    assert out["tutorial_template_import"]["multi_case"] is True
    assert "runApplication blockMesh" not in (case_dir / "Allrun").read_text(encoding="utf-8")
    assert summary["all_passed"] is True


@pytest.mark.parametrize(
    ("template_id", "solver", "expected_solver_step"),
    [
        ("foundation_v10_pimplefoam_ras_pitzdaily", "pimpleFoam", "runApplication $(getApplication)"),
        ("foundation_v10_pisofoam_les_pitzdaily", "pisoFoam", "runApplication $(getApplication)"),
        ("foundation_v10_potentialfoam_pitzdaily", "potentialFoam", "runApplication $(getApplication) -writePhi -writep"),
        ("foundation_v10_scalartransport_pitzdaily", "scalarTransportFoam", "runApplication $(getApplication)"),
    ],
)
def test_import_foundation_pitzdaily_variants_write_allrun(tmp_path, template_id, solver, expected_solver_step):
    _write_minimal_foundation_pitzdaily_template(tmp_path / "templates", template_id)
    match = find_foundation_tutorial_template(
        f"OpenFOAM v10 pitzDaily {solver} 模板，使用模板原始参数",
        CaseTarget.for_solver(solver),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": template_id})()},
        )(),
        template_root=tmp_path / "templates",
    )

    out = import_foundation_tutorial_template(str(tmp_path / "case"), match)

    allrun = (tmp_path / "case" / "Allrun").read_text(encoding="utf-8")
    assert "runApplication blockMesh -dict $FOAM_TUTORIALS/resources/blockMesh/pitzDaily" in allrun
    assert "runApplication checkMesh" in allrun
    assert expected_solver_step in allrun
    assert out["tutorial_template_import"]["template_id"] == template_id


@pytest.mark.parametrize(
    ("template_id", "solver", "expected_steps"),
    [
        (
            "foundation_v10_potentialfoam_cylinder",
            "potentialFoam",
            ("runApplication $(getApplication) -withFunctionObjects -writePhi -writep", "runApplication postProcess -func streamFunction"),
        ),
        (
            "foundation_v10_pimplefoam_laminar_offsetcylinder",
            "pimpleFoam",
            ("runApplication blockMesh", "runApplication checkMesh", "runApplication $(getApplication)"),
        ),
        (
            "foundation_v10_interfoam_laminar_sloshingcylinder",
            "interFoam",
            ("runApplication snappyHexMesh -overwrite", "runApplication setFields", "runApplication $(getApplication)"),
        ),
    ],
)
def test_import_foundation_cylinder_variants_write_allrun(tmp_path, template_id, solver, expected_steps):
    _write_minimal_foundation_cylinder_template(tmp_path / "templates", template_id)
    match = find_foundation_tutorial_template(
        f"OpenFOAM v10 cylinder 选择 {solver} 变体，使用模板原始参数",
        CaseTarget.for_solver(solver),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": template_id})()},
        )(),
        template_root=tmp_path / "templates",
    )

    out = import_foundation_tutorial_template(str(tmp_path / "case"), match)

    allrun = (tmp_path / "case" / "Allrun").read_text(encoding="utf-8")
    for step in expected_steps:
        assert step in allrun
    assert out["tutorial_template_import"]["template_id"] == template_id


@pytest.mark.parametrize(
    ("template_id", "solver"),
    [
        ("foundation_v10_rhocentralfoam_forwardstep", "rhoCentralFoam"),
        ("foundation_v10_rhopimplefoam_laminar_forwardstep", "rhoPimpleFoam"),
    ],
)
def test_import_foundation_forwardstep_variants_write_allrun(tmp_path, template_id, solver):
    _write_minimal_foundation_forwardstep_template(tmp_path / "templates", template_id)
    match = find_foundation_tutorial_template(
        f"OpenFOAM v10 forwardStep 选择 {solver} 可压缩变体，使用模板原始参数",
        CaseTarget.for_solver(solver),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": template_id})()},
        )(),
        template_root=tmp_path / "templates",
    )

    out = import_foundation_tutorial_template(str(tmp_path / "case"), match)

    allrun = (tmp_path / "case" / "Allrun").read_text(encoding="utf-8")
    assert "runApplication blockMesh" in allrun
    assert "runApplication checkMesh" in allrun
    assert "runApplication $(getApplication)" in allrun
    assert out["tutorial_template_import"]["template_id"] == template_id


def test_import_foundation_bernardcells_writes_allrun(tmp_path):
    _write_minimal_foundation_bernardcells_template(tmp_path / "templates")
    match = find_foundation_tutorial_template(
        "OpenFOAM v10 Rayleigh-Benard / BernardCells buoyantFoam 教程，使用模板原始参数",
        CaseTarget.for_solver("buoyantFoam"),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": "foundation_v10_buoyantfoam_bernardcells"})()},
        )(),
        template_root=tmp_path / "templates",
    )

    out = import_foundation_tutorial_template(str(tmp_path / "case"), match)

    allrun = (tmp_path / "case" / "Allrun").read_text(encoding="utf-8")
    assert "runApplication blockMesh" in allrun
    assert "runApplication checkMesh" in allrun
    assert "runApplication $(getApplication)" in allrun
    assert out["tutorial_template_import"]["template_id"] == "foundation_v10_buoyantfoam_bernardcells"


@pytest.mark.parametrize(
    ("template_id", "solver", "prompt", "expected_steps"),
    [
        (
            "foundation_v10_pimplefoam_laminar_planarpoiseuille",
            "pimpleFoam",
            "OpenFOAM v10 pimpleFoam planarPoiseuille 平面泊肃叶流教程，使用模板原始参数",
            ("runApplication blockMesh", "runApplication checkMesh", "runApplication $(getApplication)"),
        ),
        (
            "foundation_v10_rhocentralfoam_obliqueshock",
            "rhoCentralFoam",
            "OpenFOAM v10 rhoCentralFoam obliqueShock 斜激波教程，使用模板原始参数",
            ("runApplication blockMesh", "runApplication checkMesh", "runApplication $(getApplication)"),
        ),
        (
            "foundation_v10_rhocentralfoam_shocktube",
            "rhoCentralFoam",
            "OpenFOAM v10 rhoCentralFoam shockTube 激波管教程，使用模板原始参数",
            ("runApplication setFields", "runApplication -s sample postProcess -func sample"),
        ),
        (
            "foundation_v10_rhopimplefoam_laminar_shocktube",
            "rhoPimpleFoam",
            "OpenFOAM v10 rhoPimpleFoam laminar shockTube 激波管教程，使用模板原始参数",
            ("runApplication setFields", "runApplication -s sample postProcess -func sample"),
        ),
        (
            "foundation_v10_simplefoam_airfoil2d",
            "simpleFoam",
            "OpenFOAM v10 simpleFoam airFoil2D 翼型教程，使用模板原始参数",
            ("runApplication $(getApplication)",),
        ),
        (
            "foundation_v10_interfoam_laminar_capillaryrise",
            "interFoam",
            "OpenFOAM v10 interFoam capillaryRise 毛细上升教程，使用模板原始参数",
            ("runApplication setFields", "runApplication $(getApplication)"),
        ),
        (
            "foundation_v10_interfoam_laminar_wave",
            "interFoam",
            "OpenFOAM v10 interFoam wave 波浪教程，使用模板原始参数",
            ("runApplication setWaves", "runParallel $(getApplication)", "runApplication reconstructPar"),
        ),
    ],
)
def test_import_additional_foundation_v10_templates_write_allrun(tmp_path, template_id, solver, prompt, expected_steps):
    _write_minimal_additional_v10_template(tmp_path / "templates", template_id)
    match = find_foundation_tutorial_template(
        prompt,
        CaseTarget.for_solver(solver),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": template_id})()},
        )(),
        template_root=tmp_path / "templates",
    )

    out = import_foundation_tutorial_template(str(tmp_path / "case"), match)

    allrun = (tmp_path / "case" / "Allrun").read_text(encoding="utf-8")
    for step in expected_steps:
        assert step in allrun
    assert out["tutorial_template_import"]["template_id"] == template_id


def test_import_foundation_cavity_full_allrun_preserves_parent_allrun_and_summarizes(tmp_path):
    _write_minimal_foundation_cavity_family_template(tmp_path / "templates")
    match = find_foundation_tutorial_template(
        "OpenFOAM v10 cavity 选择完整官方教程族 full_allrun",
        CaseTarget.for_solver("icoFoam"),
        compiled_workflow=type(
            "Compiled",
            (),
            {"intent": type("Intent", (), {"reproduction_target": "foundation_v10_icofoam_cavity_full_allrun"})()},
        )(),
        template_root=tmp_path / "templates",
    )

    out = import_foundation_tutorial_template(str(tmp_path / "case"), match)
    case_dir = tmp_path / "case"
    for subcase in ("cavity", "cavityFine", "cavityGrade", "cavityHighRe", "cavityClipped"):
        (case_dir / subcase).mkdir(exist_ok=True)
        (case_dir / subcase / "0.5").mkdir(exist_ok=True)
        (case_dir / subcase / "log.icoFoam").write_text("End\n", encoding="utf-8")
    (case_dir / "cavityFine" / "log.mapFields").write_text("End\n", encoding="utf-8")

    summary = summarize_foundation_multi_case(case_dir)

    assert out["tutorial_template_import"]["template_id"] == "foundation_v10_icofoam_cavity_full_allrun"
    assert out["tutorial_template_import"]["multi_case"] is True
    assert "runApplication blockMesh" not in (case_dir / "Allrun").read_text(encoding="utf-8")
    assert summary["all_passed"] is True
    assert (case_dir / "FOUNDATION_MULTI_CASE_SUMMARY.json").is_file()
