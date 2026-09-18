from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from models import CaseTarget


DEFAULT_RHEOFOAM_PARALLEL_PROCS = 4
DEFAULT_RHEOFOAM_PARALLEL_MIN_CELLS = 10_000


def estimate_blockmesh_cells(case_dir: str | Path) -> Optional[int]:
    """Estimate cell count from blockMeshDict hex block entries."""
    case = Path(case_dir)
    candidates = [
        case / "system" / "blockMeshDict",
        case / "constant" / "polyMesh" / "blockMeshDict",
    ]
    block_mesh = next((path for path in candidates if path.is_file()), None)
    if block_mesh is None:
        return None

    text = block_mesh.read_text(encoding="utf-8", errors="ignore")
    total = 0
    for match in re.finditer(
        r"\bhex\s*\([^)]*\)\s*\(\s*(\d+)\s+(\d+)\s+(\d+)\s*\)",
        text,
        flags=re.IGNORECASE,
    ):
        nx, ny, nz = (int(match.group(i)) for i in range(1, 4))
        total += nx * ny * nz
    return total or None


def should_parallelize_rheofoam(
    case_dir: str | Path,
    case_target: CaseTarget,
    *,
    min_cells: int = DEFAULT_RHEOFOAM_PARALLEL_MIN_CELLS,
) -> bool:
    if case_target.channel != "v9-rheotool" or case_target.solver != "rheoFoam":
        return False
    cells = estimate_blockmesh_cells(case_dir)
    return cells is not None and cells >= min_cells


def write_decompose_par_dict(
    case_dir: str | Path,
    *,
    nprocs: int = DEFAULT_RHEOFOAM_PARALLEL_PROCS,
) -> None:
    system_dir = Path(case_dir) / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    (system_dir / "decomposeParDict").write_text(
        "FoamFile\n"
        "{\n"
        "    version     2.0;\n"
        "    format      ascii;\n"
        "    class       dictionary;\n"
        "    object      decomposeParDict;\n"
        "}\n\n"
        f"numberOfSubdomains {nprocs};\n\n"
        "method          scotch;\n",
        encoding="utf-8",
    )


def make_rheofoam_allrun_parallel(
    script: str,
    *,
    nprocs: int = DEFAULT_RHEOFOAM_PARALLEL_PROCS,
) -> str:
    """Replace a serial rheoFoam/$application run in Allrun with 4-core parallel run."""
    def parallel_prelude(indent: str) -> list[str]:
        return [
            f"{indent}rm -rf processor*",
            f"{indent}runApplication decomposePar -force",
            f"{indent}export OMPI_ALLOW_RUN_AS_ROOT=1",
            f"{indent}export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1",
        ]

    lines = script.splitlines()
    if "runParallel" in script:
        normalized: list[str] = []
        inserted_prelude = False
        for line in lines:
            stripped = line.strip()
            if (
                stripped == "rm -rf processor*"
                or stripped.startswith("runApplication decomposePar")
                or stripped.startswith("export OMPI_ALLOW_RUN_AS_ROOT=")
                or stripped.startswith("export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=")
            ):
                continue
            if stripped.startswith("runParallel") and not inserted_prelude:
                indent = line[: len(line) - len(line.lstrip())]
                normalized.extend(parallel_prelude(indent))
                inserted_prelude = True
            parts = stripped.split()
            if len(parts) == 3 and parts[0] == "runParallel" and parts[2].isdigit():
                indent = line[: len(line) - len(line.lstrip())]
                normalized.append(f"{indent}runParallel -np {parts[2]} {parts[1]}")
            else:
                normalized.append(line)
        return "\n".join(normalized)
    if "mpirun" in script or "foamJob -parallel" in script:
        return script

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped in {"runApplication $application", "runApplication rheoFoam"}:
            solver = stripped.split()[-1]
            indent = line[: len(line) - len(line.lstrip())]
            lines[idx:idx + 1] = [
                *parallel_prelude(indent),
                f"{indent}runParallel -np {nprocs} {solver}",
                f"{indent}runApplication reconstructPar",
            ]
            return "\n".join(lines)
        if stripped in {"$application", "rheoFoam"}:
            indent = line[: len(line) - len(line.lstrip())]
            lines[idx:idx + 1] = [
                *parallel_prelude(indent),
                f"{indent}runParallel -np {nprocs} {stripped}",
                f"{indent}runApplication reconstructPar",
            ]
            return "\n".join(lines)

    return script


def enable_rheofoam_parallel_if_large(
    case_dir: str | Path,
    case_target: CaseTarget,
    allrun_script: str,
    *,
    nprocs: int = DEFAULT_RHEOFOAM_PARALLEL_PROCS,
    min_cells: int = DEFAULT_RHEOFOAM_PARALLEL_MIN_CELLS,
) -> str:
    if not should_parallelize_rheofoam(case_dir, case_target, min_cells=min_cells):
        return allrun_script
    parallel_script = make_rheofoam_allrun_parallel(allrun_script, nprocs=nprocs)
    if parallel_script != allrun_script:
        write_decompose_par_dict(case_dir, nprocs=nprocs)
        print(f'<rheofoam_parallel enabled="true" nprocs="{nprocs}" min_cells="{min_cells}"/>')
    return parallel_script
