from pathlib import Path
import importlib.util
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "services" / "solver_schema_validator.py"
MODULE_NAME = "solver_schema_validator_under_test"
spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[MODULE_NAME] = validator
spec.loader.exec_module(validator)


def _write_minimal_case(case_dir: Path) -> None:
    files = {
        "0/U": "FoamFile {}\n",
        "0/p": "FoamFile {}\n",
        "Allrun": "#!/bin/sh\nicoFoam\n",
        "constant/physicalProperties": "nu [0 2 -1 0 0 0 0] 0.01;\n",
        "system/controlDict": "application icoFoam;\n",
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
    }
    for relative_path, content in files.items():
        path = case_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def test_icofoam_schema_accepts_minimal_case(tmp_path):
    _write_minimal_case(tmp_path)
    result = validator.preflight_validate_case(tmp_path, "v10", "icoFoam")
    assert result is not None
    assert result.ok


def test_icofoam_schema_requires_physical_properties(tmp_path):
    _write_minimal_case(tmp_path)
    (tmp_path / "constant/physicalProperties").unlink()
    result = validator.preflight_validate_case(tmp_path, "v10", "icoFoam")
    assert result is not None
    assert not result.ok
    assert any(
        issue.code == "REQUIRED_FILE_MISSING" and issue.path == "constant/physicalProperties"
        for issue in result.issues
    )


def test_icofoam_schema_rejects_rheotool_properties(tmp_path):
    _write_minimal_case(tmp_path)
    (tmp_path / "constant/constitutiveProperties").write_text("parameters {}\n")
    result = validator.preflight_validate_case(tmp_path, "v10", "icoFoam")
    assert result is not None
    assert not result.ok
    assert any(issue.code == "FORBIDDEN_FILE_PRESENT" for issue in result.issues)


def test_schema_resolution_is_version_scoped():
    assert validator.resolve_solver_schema_path("v10", "icoFoam").is_file()
    assert validator.resolve_solver_schema_path("v9", "icoFoam") is None


def test_new_v10_foundation_pitzdaily_variant_schemas_exist():
    for solver in ("pisoFoam", "potentialFoam", "scalarTransportFoam"):
        assert validator.resolve_solver_schema_path("v10", solver).is_file()
        assert validator.resolve_solver_schema_path("v9", solver) is None


def test_new_v10_foundation_compressible_forwardstep_schemas_exist():
    for solver in ("rhoCentralFoam", "rhoPimpleFoam"):
        assert validator.resolve_solver_schema_path("v10", solver).is_file()
        assert validator.resolve_solver_schema_path("v9", solver) is None


def test_new_v10_foundation_buoyantfoam_schema_exists():
    assert validator.resolve_solver_schema_path("v10", "buoyantFoam").is_file()
    assert validator.resolve_solver_schema_path("v9", "buoyantFoam") is None


def test_v10_buoyantfoam_accepts_compressible_alphat_wall_function(tmp_path):
    files = {
        "0/U": "boundaryField { walls { type noSlip; } }\n",
        "0/p": "boundaryField { walls { type calculated; } }\n",
        "0/p_rgh": "boundaryField { walls { type fixedFluxPressure; } }\n",
        "0/T": "boundaryField { hot { type fixedValue; } cold { type fixedValue; } }\n",
        "0/alphat": "boundaryField { walls { type compressible::alphatJayatillekeWallFunction; } }\n",
        "0/epsilon": "boundaryField { walls { type epsilonWallFunction; } }\n",
        "0/k": "boundaryField { walls { type kqRWallFunction; } }\n",
        "0/nut": "boundaryField { walls { type nutkWallFunction; } }\n",
        "constant/g": "value (0 -9.81 0);\n",
        "constant/momentumTransport": "simulationType RAS;\n",
        "constant/physicalProperties": "thermoType {}\n",
        "system/blockMeshDict": "vertices (); blocks (); boundary ();\n",
        "system/controlDict": "application buoyantFoam;\n",
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    result = validator.preflight_validate_case(tmp_path, "v10", "buoyantFoam")

    assert result is not None
    assert result.ok


def test_v10_rhopimplefoam_accepts_wave_transmissive_patch(tmp_path):
    files = {
        "0/U": "boundaryField { outlet { type zeroGradient; } }\n",
        "0/p": "boundaryField { outlet { type waveTransmissive; } }\n",
        "0/T": "boundaryField { outlet { type zeroGradient; } }\n",
        "constant/momentumTransport": "simulationType laminar;\n",
        "constant/physicalProperties": "thermoType {}\n",
        "system/blockMeshDict": "vertices (); blocks (); boundary ();\n",
        "system/controlDict": "application rhoPimpleFoam;\n",
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    result = validator.preflight_validate_case(tmp_path, "v10", "rhoPimpleFoam")

    assert result is not None
    assert result.ok


def test_v10_rhocentralfoam_accepts_orig_initial_fields(tmp_path):
    files = {
        "0/U.orig": "boundaryField { outlet { type zeroGradient; } }\n",
        "0/p.orig": "boundaryField { outlet { type zeroGradient; } }\n",
        "0/T.orig": "boundaryField { outlet { type zeroGradient; } }\n",
        "constant/momentumTransport": "simulationType laminar;\n",
        "constant/physicalProperties": "thermoType {}\n",
        "system/blockMeshDict": "vertices (); blocks (); boundary ();\n",
        "system/controlDict": "application rhoCentralFoam;\n",
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    result = validator.preflight_validate_case(tmp_path, "v10", "rhoCentralFoam")

    assert result is not None
    assert result.ok


def test_v10_simplefoam_accepts_airfoil_boundary_conditions(tmp_path):
    files = {
        "0/U": "boundaryField { farfield { type freestreamVelocity; } airfoil { type noSlip; } }\n",
        "0/p": "boundaryField { farfield { type freestreamPressure; } airfoil { type zeroGradient; } }\n",
        "0/nut": "boundaryField { airfoil { type nutUSpaldingWallFunction; } }\n",
        "constant/momentumTransport": "simulationType RAS;\n",
        "constant/physicalProperties": "nu [0 2 -1 0 0 0 0] 1e-05;\n",
        "system/controlDict": "application simpleFoam;\n",
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    result = validator.preflight_validate_case(tmp_path, "v10", "simpleFoam")

    assert result is not None
    assert result.ok


def test_v10_interfoam_accepts_capillary_rise_contact_angle(tmp_path):
    files = {
        "0/U": "boundaryField { atmosphere { type pressureInletOutletVelocity; } }\n",
        "0/p_rgh": "boundaryField { walls { type fixedFluxPressure; } }\n",
        "0/alpha.water.orig": "boundaryField { walls { type constantAlphaContactAngle; } }\n",
        "constant/g": "value (0 -9.81 0);\n",
        "constant/momentumTransport": "simulationType laminar;\n",
        "constant/phaseProperties": "phases (water air);\n",
        "system/controlDict": "application interFoam;\n",
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    result = validator.preflight_validate_case(tmp_path, "v10", "interFoam")

    assert result is not None
    assert result.ok


def test_v10_interfoam_accepts_wave_boundary_conditions(tmp_path):
    files = {
        "0/U.orig": "boundaryField { inlet { type waveVelocity; } outlet { type outletPhaseMeanVelocity; } }\n",
        "0/p_rgh": "boundaryField { outlet { type prghTotalPressure; } }\n",
        "0/alpha.water.orig": "boundaryField { inlet { type waveAlpha; } outlet { type inletOutlet; } }\n",
        "constant/g": "value (0 -9.81 0);\n",
        "constant/momentumTransport": "simulationType laminar;\n",
        "constant/phaseProperties": "phases (water air);\n",
        "system/controlDict": "application interFoam;\n",
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    result = validator.preflight_validate_case(tmp_path, "v10", "interFoam")

    assert result is not None
    assert result.ok


def test_v10_simplefoam_accepts_standard_turbulence_wall_functions(tmp_path):
    files = {
        "0/U": "boundaryField { wall { type noSlip; } }\n",
        "0/p": "boundaryField { wall { type zeroGradient; } }\n",
        "0/epsilon": "boundaryField { wall { type epsilonWallFunction; } }\n",
        "0/f": "boundaryField { wall { type fWallFunction; } }\n",
        "0/k": "boundaryField { wall { type kqRWallFunction; } }\n",
        "0/nut": "boundaryField { wall { type nutkWallFunction; } }\n",
        "0/omega": "boundaryField { wall { type omegaWallFunction; } }\n",
        "0/v2": "boundaryField { wall { type v2WallFunction; } }\n",
        "constant/momentumTransport": "simulationType RAS;\n",
        "constant/physicalProperties": "nu [0 2 -1 0 0 0 0] 1e-05;\n",
        "system/controlDict": "application simpleFoam;\n",
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    result = validator.preflight_validate_case(tmp_path, "v10", "simpleFoam")

    assert result is not None
    assert result.ok


def test_v10_pisofoam_accepts_turbulent_inlet_patch(tmp_path):
    files = {
        "0/U": "boundaryField { inlet { type turbulentInlet; } }\n",
        "0/p": "boundaryField { outlet { type zeroGradient; } }\n",
        "constant/momentumTransport": "simulationType LES;\n",
        "constant/physicalProperties": "nu [0 2 -1 0 0 0 0] 1e-05;\n",
        "system/controlDict": "application pisoFoam;\n",
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    result = validator.preflight_validate_case(tmp_path, "v10", "pisoFoam")

    assert result is not None
    assert result.ok


def test_v10_interfoam_accepts_prgh_total_pressure(tmp_path):
    files = {
        "0/U": "boundaryField { atmosphere { type pressureInletOutletVelocity; } }\n",
        "0/p_rgh": "boundaryField { atmosphere { type prghTotalPressure; } }\n",
        "0/alpha.water.orig": "boundaryField { atmosphere { type inletOutlet; } }\n",
        "constant/g": "value (0 -9.81 0);\n",
        "constant/momentumTransport": "simulationType laminar;\n",
        "constant/phaseProperties": "phases (water air);\n",
        "system/controlDict": "application interFoam;\n",
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    result = validator.preflight_validate_case(tmp_path, "v10", "interFoam")

    assert result is not None
    assert result.ok


def test_v10_interfoam_accepts_rough_wall_function(tmp_path):
    files = {
        "0/U.orig": "boundaryField { wall { type noSlip; } }\n",
        "0/p_rgh": "boundaryField { atmosphere { type prghTotalPressure; } }\n",
        "0/alpha.water.orig": "boundaryField { atmosphere { type inletOutlet; } }\n",
        "0/nut": "boundaryField { wall { type nutkRoughWallFunction; } }\n",
        "constant/g": "value (0 -9.81 0);\n",
        "constant/momentumTransport": "simulationType RAS;\n",
        "constant/phaseProperties": "phases (water air);\n",
        "system/controlDict": "application interFoam;\n",
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    result = validator.preflight_validate_case(tmp_path, "v10", "interFoam")

    assert result is not None
    assert result.ok


def test_v9_rheofoam_schema_rejects_v10_dictionary(tmp_path):
    files = {
        "0/U": "FoamFile {}\n",
        "0/p": "FoamFile {}\n",
        "0/tau": "FoamFile {}\n",
        "constant/constitutiveProperties": "parameters { type Oldroyd-B; }\n",
        "constant/momentumTransport": "simulationType laminar;\n",
        "system/controlDict": "application rheoFoam;\n",
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    result = validator.preflight_validate_case(tmp_path, "v9", "rheoFoam")
    assert not result.ok
    assert any(
        issue.code == "FORBIDDEN_FILE_PRESENT"
        and issue.path == "constant/momentumTransport"
        for issue in result.issues
    )


def _write_minimal_rheofoam_case(case_dir: Path, control_dict: str, bc_type: str = "uLid") -> None:
    files = {
        "0/U": f"boundaryField {{ movingLid {{ type {bc_type}; value uniform (0 0 0); }} }}\n",
        "0/p": "FoamFile {}\n",
        "0/tau": "FoamFile {}\n",
        "constant/constitutiveProperties": "parameters { type Oldroyd-BLog; }\n",
        "system/controlDict": control_dict,
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
    }
    for relative_path, content in files.items():
        path = case_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def test_v9_rheofoam_requires_custom_bc_library_loaded(tmp_path):
    _write_minimal_rheofoam_case(tmp_path, "application rheoFoam;\n")

    result = validator.preflight_validate_case(tmp_path, "v9", "rheoFoam")

    assert result is not None
    assert not result.ok
    assert any(issue.code == "RHEOTOOL_CUSTOM_BC_LIBRARY_NOT_LOADED" for issue in result.issues)


def test_v9_rheofoam_accepts_loaded_custom_bc_library(tmp_path, monkeypatch):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "libRheoToolTutorialBCs.so").write_text("fake library for preflight containing uLid\n")
    monkeypatch.setenv("FOAM_USER_LIBBIN", str(lib_dir))
    _write_minimal_rheofoam_case(
        tmp_path / "case",
        'application rheoFoam;\nlibs\n(\n    "libRheoToolTutorialBCs.so"\n);\n',
    )

    result = validator.preflight_validate_case(tmp_path / "case", "v9", "rheoFoam")

    assert result is not None
    assert result.ok


def test_v9_rheofoam_rejects_custom_bc_missing_from_loaded_library(tmp_path, monkeypatch):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    fake_lib = lib_dir / "libRheoToolTutorialBCs.so"
    fake_lib.write_text("fake library without cosine boundary condition\n")
    monkeypatch.setenv("FOAM_USER_LIBBIN", str(lib_dir))
    monkeypatch.setattr(
        validator.SolverSchemaValidator,
        "_runtime_library_candidates",
        lambda self, lib_name: [fake_lib],
    )
    _write_minimal_rheofoam_case(
        tmp_path / "case",
        'application rheoFoam;\nlibs\n(\n    "libRheoToolTutorialBCs.so"\n);\n',
        bc_type="uCos",
    )

    result = validator.preflight_validate_case(tmp_path / "case", "v9", "rheoFoam")

    assert result is not None
    assert not result.ok
    assert any(issue.code == "RHEOTOOL_CUSTOM_BC_NOT_REGISTERED" for issue in result.issues)


def test_v9_rheofoam_rejects_unknown_customer_patch_field_type(tmp_path):
    _write_minimal_rheofoam_case(
        tmp_path,
        "application rheoFoam;\n",
        bc_type="customerSpecialBC",
    )

    result = validator.preflight_validate_case(tmp_path, "v9", "rheoFoam")

    assert result is not None
    assert not result.ok
    assert any(
        issue.code == "CUSTOM_PATCH_FIELD_UNSUPPORTED"
        and "customerSpecialBC" in issue.message
        for issue in result.issues
    )


def test_v9_rheofoam_accepts_coded_fixed_value_as_standard_dynamic_bc(tmp_path):
    _write_minimal_rheofoam_case(
        tmp_path,
        "application rheoFoam;\n",
        bc_type="codedFixedValue",
    )

    result = validator.preflight_validate_case(tmp_path, "v9", "rheoFoam")

    assert result is not None
    assert result.ok


def test_v9_rheofoam_accepts_unknown_patch_field_when_precompiled_library_is_loaded(tmp_path, monkeypatch):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "libCustomerBCs.so").write_text("registered customerSpecialBC patch field\n")
    monkeypatch.setenv("FOAM_USER_LIBBIN", str(lib_dir))
    _write_minimal_rheofoam_case(
        tmp_path / "case",
        'application rheoFoam;\nlibs\n(\n    "libCustomerBCs.so"\n);\n',
        bc_type="customerSpecialBC",
    )

    result = validator.preflight_validate_case(tmp_path / "case", "v9", "rheoFoam")

    assert result is not None
    assert result.ok
