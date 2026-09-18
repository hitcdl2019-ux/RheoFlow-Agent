from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from models import CaseTarget  # noqa: E402
from services.rheofoam_parallel import (  # noqa: E402
    enable_rheofoam_parallel_if_large,
    estimate_blockmesh_cells,
    make_rheofoam_allrun_parallel,
    should_parallelize_rheofoam,
)


def _write_block_mesh(case: Path, cells: tuple[int, int, int]) -> None:
    (case / "system").mkdir(parents=True, exist_ok=True)
    nx, ny, nz = cells
    (case / "system" / "blockMeshDict").write_text(
        "blocks\n"
        "(\n"
        f"    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)\n"
        ");\n",
        encoding="utf-8",
    )


def test_estimate_blockmesh_cells_from_hex_blocks(tmp_path):
    _write_block_mesh(tmp_path, (127, 127, 1))

    assert estimate_blockmesh_cells(tmp_path) == 16129


def test_should_parallelize_only_large_v9_rheofoam_cases(tmp_path):
    target = CaseTarget.for_solver("rheoFoam")
    _write_block_mesh(tmp_path, (50, 60, 1))
    assert not should_parallelize_rheofoam(tmp_path, target)

    _write_block_mesh(tmp_path, (127, 127, 1))
    assert should_parallelize_rheofoam(tmp_path, target)
    assert not should_parallelize_rheofoam(tmp_path, CaseTarget.for_solver("simpleFoam"))


def test_make_rheofoam_allrun_parallel_replaces_serial_application_run():
    script = "#!/bin/sh\nrunApplication blockMesh\nrunApplication $application\nrunApplication postProcess -func sampleDict\n"

    out = make_rheofoam_allrun_parallel(script)

    assert "runApplication blockMesh" in out
    assert "rm -rf processor*" in out
    assert "runApplication decomposePar -force" in out
    assert "export OMPI_ALLOW_RUN_AS_ROOT=1" in out
    assert "export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1" in out
    assert "runParallel -np 4 $application" in out
    assert "runApplication reconstructPar" in out
    assert "runApplication postProcess -func sampleDict" in out


def test_make_rheofoam_allrun_parallel_normalizes_existing_parallel_run():
    script = (
        "#!/bin/sh\n"
        "runApplication blockMesh\n"
        "runApplication decomposePar\n"
        "runParallel rheoFoam 4\n"
        "runApplication reconstructPar\n"
    )

    out = make_rheofoam_allrun_parallel(script)

    assert "rm -rf processor*" in out
    assert "runApplication decomposePar -force" in out
    assert "runApplication decomposePar\n" not in out
    assert "export OMPI_ALLOW_RUN_AS_ROOT=1" in out
    assert "runParallel -np 4 rheoFoam" in out
    assert "runParallel rheoFoam 4" not in out


def test_enable_parallel_writes_decompose_dict_for_large_rheofoam_case(tmp_path):
    _write_block_mesh(tmp_path, (127, 127, 1))
    script = "#!/bin/sh\nrunApplication blockMesh\nrunApplication rheoFoam\n"

    out = enable_rheofoam_parallel_if_large(tmp_path, CaseTarget.for_solver("rheoFoam"), script)

    assert "runParallel -np 4 rheoFoam" in out
    assert "runApplication decomposePar -force" in out
    decompose = (tmp_path / "system" / "decomposeParDict").read_text(encoding="utf-8")
    assert "numberOfSubdomains 4;" in decompose
    assert "method          scotch;" in decompose
