from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_rheotool_tutorial_bcs.py"
spec = importlib.util.spec_from_file_location("check_rheotool_tutorial_bcs_under_test", SCRIPT)
checker = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["check_rheotool_tutorial_bcs_under_test"] = checker
spec.loader.exec_module(checker)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_rheotool_bc_check_scans_all_known_tutorial_bcs(tmp_path):
    tutorial_root = tmp_path / "tutorials"
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    _write(tutorial_root / "rheoFoam" / "Cavity" / "Oldroyd-BLog" / "0" / "U", "type uLid;\n")
    _write(tutorial_root / "rheoFoam" / "Contraction41" / "Oldroyd-BLog" / "0" / "U", "type uCos;\n")
    _write(tutorial_root / "rheoFoam" / "Contraction41" / "Oldroyd-BLog" / "0" / "tau", "type linearExtrapolation;\n")
    _write(tutorial_root / "rheoFoam" / "Aneurysm" / "HerschelBulkley" / "0" / "U", "type HBprofile;\n")
    _write(tutorial_root / "rheoFoam" / "fluidDamper" / "CarreauYasuda" / "0" / "U", "type uShaft;\n")
    _write(tutorial_root / "rheoFoam" / "fluidDamper" / "CarreauYasuda" / "0" / "U2", "type navierSlip;\n")
    _write(tutorial_root / "rheoEFoam" / "EKmixer" / "slipSmoluchowski" / "0" / "phiE", "type ACPotential;\n")
    _write(lib_dir / "libRheoToolTutorialBCs.so", "uLid\nuCos\nHBprofile\nuShaft\nACPotential\n")
    _write(lib_dir / "libBCRheoTool.so", "navierSlip\nlinearExtrapolation\n")

    report = checker.check_environment(tutorial_root, [lib_dir], checker.DEFAULT_BC_LIBS)

    assert report["ok"] is True
    assert {item["bc_type"] for item in report["checks"]} == {"uLid", "uCos", "HBprofile", "uShaft", "ACPotential", "linearExtrapolation", "navierSlip"}
    assert all(item["tutorial_usage_count"] >= 1 for item in report["checks"])


def test_rheotool_bc_check_fails_when_library_does_not_register_used_bc(tmp_path):
    tutorial_root = tmp_path / "tutorials"
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    _write(tutorial_root / "rheoFoam" / "Aneurysm" / "HerschelBulkley" / "0" / "U", "type HBprofile;\n")
    _write(lib_dir / "libRheoToolTutorialBCs.so", "uLid\nuCos\n")

    report = checker.check_environment(tutorial_root, [lib_dir], checker.DEFAULT_BC_LIBS)

    hb = next(item for item in report["checks"] if item["bc_type"] == "HBprofile")
    assert report["ok"] is False
    assert hb["library_found"] is True
    assert hb["registered"] is False
    assert hb["status"] == "failed"


def test_rheotool_bc_check_scans_tutorial_pputils(tmp_path):
    tutorial_root = tmp_path / "tutorials"
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    _write(tutorial_root / "rheoFoam" / "Cavity" / "Oldroyd-BLog" / "system" / "fvSolution", "funcType calcKineticE;\n")
    _write(tutorial_root / "rheoFoam" / "Contraction41" / "Oldroyd-BLog" / "system" / "fvSolution", "funcType calcVortexL;\n")
    _write(lib_dir / "libpostProcessingRheoTool.so", "ppUtil\n")
    _write(lib_dir / "libRheoToolTutorialPPUtils.so", "calcKineticE\ncalcVortexL\n")

    report = checker.check_environment(
        tutorial_root,
        [lib_dir],
        {},
        {
            "calcKineticE": ("libpostProcessingRheoTool.so", "libRheoToolTutorialPPUtils.so"),
            "calcVortexL": ("libpostProcessingRheoTool.so", "libRheoToolTutorialPPUtils.so"),
        },
    )

    assert report["ok"] is True
    assert {item["pputil_type"] for item in report["pputil_checks"]} == {"calcKineticE", "calcVortexL"}
    assert all(item["tutorial_usage_count"] == 1 for item in report["pputil_checks"])
