from pathlib import Path

from models import CaseTarget
from services.input_writer import initial_write, rewrite_files
from services.solver_schema_validator import preflight_validate_case
from utils import FoamPydantic, FoamfilePydantic


def test_initial_write_skips_schema_forbidden_file(tmp_path):
    case_target = CaseTarget.for_solver("rheoFoam")

    result = initial_write(
        case_dir=str(tmp_path),
        subtasks=[{"folder_name": "constant", "file_name": "momentumTransport"}],
        user_requirement="rheoFoam case",
        tutorial_reference="",
        case_target=case_target,
        database_path="",
    )

    assert not (tmp_path / "constant" / "momentumTransport").exists()
    assert result["dir_structure"] == {}
    assert result["foamfiles"].list_foamfile == []




def test_initial_write_normalizes_v9_rheofoam_required_files(tmp_path):
    reuse = tmp_path / "reuse"
    case = tmp_path / "case"
    files = {
        "system/controlDict": "application rheoFoam;\n",
        "system/fvSchemes": "FoamFile {}\n",
        "system/fvSolution": "FoamFile {}\n",
        "0/U": 'FoamFile\n{\n    class volVectorField;\n    object U;\n}\nboundaryField\n{\n    movingLid\n    {\n        type fixedValue;\n        value uniform (0 0 0);\n    }\n    fixedWalls\n    {\n        type fixedValue;\n        value uniform (0 0 0);\n    }\n    frontAndBack\n    {\n        type empty;\n    }\n}\n',
        "0/p": "FoamFile { class volScalarField; object p; }\n",
        "constant/viscoelasticProperties": "FoamFile { object viscoelasticProperties; }\nparameters { type Oldroyd-BLog; etaS 0.5; etaP 0.5; lambda 1; }\n",
        "Allrun": "#!/bin/sh\nrunApplication blockMesh\nrunApplication rheoFoam\n",
    }
    for relative_path, content in files.items():
        path = reuse / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    case.mkdir()
    (case / "Allrun").write_text(files["Allrun"], encoding="utf-8")
    result = initial_write(
        case_dir=str(case),
        subtasks=[
            {"folder_name": "system", "file_name": "controlDict"},
            {"folder_name": "system", "file_name": "fvSchemes"},
            {"folder_name": "system", "file_name": "fvSolution"},
            {"folder_name": "constant", "file_name": "viscoelasticProperties"},
            {"folder_name": "0", "file_name": "U"},
            {"folder_name": "0", "file_name": "p"},
        ],
        user_requirement="Oldroyd-BLog lid-driven cavity etaS=0.5 etaP=0.5 lambda=1",
        tutorial_reference="",
        case_target=CaseTarget.for_solver("rheoFoam"),
        database_path="",
        reuse_generated_dir=str(reuse),
    )

    assert (case / "constant" / "constitutiveProperties").is_file()
    assert "object      constitutiveProperties;" in (case / "constant" / "constitutiveProperties").read_text(encoding="utf-8")
    tau_text = (case / "0" / "tau").read_text(encoding="utf-8")
    assert "object      tau;" in tau_text
    assert "movingLid" in tau_text
    assert "type            linearExtrapolation;" in tau_text
    assert "frontAndBack" in tau_text
    assert "type            empty;" in tau_text

    rel_paths = {
        f"{foamfile.folder_name}/{foamfile.file_name}"
        for foamfile in result["foamfiles"].list_foamfile
    }
    assert "constant/constitutiveProperties" in rel_paths
    assert "0/tau" in rel_paths

    validation = preflight_validate_case(case, "v9", "rheoFoam")
    assert validation is not None
    assert validation.ok

def test_rewrite_files_deletes_target_file_without_llm(tmp_path):
    case_target = CaseTarget.for_solver("rheoFoam")
    forbidden = tmp_path / "constant" / "momentumTransport"
    forbidden.parent.mkdir()
    forbidden.write_text("simulationType laminar;\n")
    keep = tmp_path / "0" / "U"
    keep.parent.mkdir()
    keep.write_text("U\n")

    foamfiles = FoamPydantic(
        list_foamfile=[
            FoamfilePydantic(
                folder_name="constant",
                file_name="momentumTransport",
                content="simulationType laminar;\n",
            ),
            FoamfilePydantic(folder_name="0", file_name="U", content="U\n"),
        ]
    )

    result = rewrite_files(
        case_dir=str(tmp_path),
        error_logs=["ERROR FORBIDDEN_FILE_PRESENT [constant/momentumTransport]"],
        review_analysis="delete forbidden file",
        rewrite_plan={
            "target_files": [
                {"file": "constant/momentumTransport", "changes": "delete file"}
            ]
        },
        user_requirement="rheoFoam case",
        case_target=case_target,
        foamfiles=foamfiles,
        dir_structure={"constant": ["momentumTransport"], "0": ["U"]},
    )

    assert not forbidden.exists()
    assert keep.exists()
    assert result["dir_structure"]["constant"] == []
    rel_paths = {
        f"{foamfile.folder_name}/{foamfile.file_name}"
        for foamfile in result["foamfiles"].list_foamfile
    }
    assert "constant/momentumTransport" not in rel_paths
    assert "0/U" in rel_paths
