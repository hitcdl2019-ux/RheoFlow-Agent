# input_writer_node.py
import os
import json
import shutil
from pathlib import Path
from utils import save_file, parse_context, retrieve_faiss, FoamPydantic, FoamfilePydantic, read_case_foamfiles, scan_case_directory
from services.input_writer import initial_write, build_allrun, rewrite_files
from services.benchmarks import import_certified_benchmark_case
from services.rheotool_templates import import_rheotool_tutorial_template, normalize_imported_rheotool_tutorial_case
from services.foundation_templates import import_foundation_tutorial_template
from services.case_manifest import validate_case_manifest
from services.solver_schema_validator import preflight_validate_case
from translation.esi_translator import convert_case_to_esi_if_needed
import re
from typing import List
from pydantic import BaseModel, Field

# System prompts for different modes
INITIAL_WRITE_SYSTEM_PROMPT = (
    "You are an expert in OpenFOAM simulation and numerical modeling."
    f"Your task is to generate a complete and functional file named: <file_name>{{file_name}}</file_name> within the <folder_name>{{folder_name}}</folder_name> directory. "
    "Ensure all required values are present and match with the files content already generated."
    "Before finalizing the output, ensure:\n"
    "- All necessary fields exist (e.g., if `nu` is defined in `constant/transportProperties`, it must be used correctly in `0/U`).\n"
    "- Cross-check field names between different files to avoid mismatches.\n"
    "- Ensure units and dimensions are correct** for all physical variables.\n"
    f"- Ensure case solver settings are consistent with the user's requirements. Available solvers are: {{case_solver}}.\n"
    "Provide only the code—no explanations, comments, or additional text."
)
        

def parse_allrun(text: str) -> str:
    match = re.search(r'```(.*?)```', text, re.DOTALL)
    
    return match.group(1).strip() 

def retrieve_commands(command_path) -> str:
    with open(command_path, 'r') as file:
        commands = file.readlines()
    
    return f"[{', '.join([command.strip() for command in commands])}]"
    
class CommandsPydantic(BaseModel):
    commands: List[str] = Field(description="List of commands")

def input_writer_node(state):
    """
    InputWriter node: Generate the complete OpenFOAM foamfile.
    
    Args:
        state: The current state containing all necessary information
    """

    mode = state["input_writer_mode"]
    
    if mode == "rewrite":
        return _rewrite_mode(state)
    else:
        return _initial_write_mode(state)

def _rewrite_mode(state):
    """Rewrite mode: delegate to service to modify files based on review analysis."""
    print("<input_writer mode=\"rewrite\">")
    if not state.get("review_analysis"):
        print("No review analysis available for rewrite mode.")
        print("</input_writer>")
        return state
    out = rewrite_files(
        case_dir=state["case_dir"],
        error_logs=state.get("error_logs", []),
        review_analysis=state.get("review_analysis", ""),
        rewrite_plan=state.get("rewrite_plan"),
        user_requirement=state.get("user_requirement", ""),
        case_target=state["case_target"],
        foamfiles=state.get("foamfiles"),
        dir_structure=state.get("dir_structure", {}),
    )
    print("</input_writer>")
    
    convert_case_to_esi_if_needed(state["case_dir"], state["config"])
    
    # Rescan the directory and foam files to reflect any translations
    out["dir_structure"] = scan_case_directory(state["case_dir"])
    out["foamfiles"] = read_case_foamfiles(state["case_dir"], out["dir_structure"])

    target = state["case_target"]
    try:
        validate_case_manifest(state["case_dir"], target)
        validation = preflight_validate_case(
            state["case_dir"], target.version, target.solver
        )
    except (ValueError, OSError) as exc:
        out["error_logs"] = [str(exc)]
    else:
        out["schema_validation"] = validation.as_dict() if validation else None
        if validation is None or not validation.ok:
            issues = validation.issues if validation else []
            out["error_logs"] = [
                "Post-rewrite validation failed: "
                + "; ".join(f"{issue.code}: {issue.message}" for issue in issues)
            ]

    return out

def _initial_write_mode(state):
    """
    Initial write mode: Generate files from scratch
    """
    print("<input_writer mode=\"initial\">")
    
    config = state["config"]
    benchmark_match = state.get("benchmark_match")
    tutorial_template_match = state.get("tutorial_template_match")
    if benchmark_match:
        print(
            f"<certified_benchmark_import id=\"{benchmark_match['id']}\" "
            f"case_set=\"{benchmark_match.get('case_set', 'runtime_case')}\">"
        )
        write_out = import_certified_benchmark_case(
            case_dir=state["case_dir"],
            benchmark_match=benchmark_match,
        )
        print("</certified_benchmark_import>")
        print("</input_writer>")

        convert_case_to_esi_if_needed(state["case_dir"], config)

        dir_structure = scan_case_directory(state["case_dir"])
        foamfiles = read_case_foamfiles(state["case_dir"], dir_structure)

        return {
            "dir_structure": dir_structure,
            "commands": [],
            "foamfiles": foamfiles,
            "benchmark_import": write_out.get("benchmark_import"),
        }

    if tutorial_template_match:
        if tutorial_template_match.get("template_kind") == "foundation":
            print(
                f'<foundation_tutorial_template_import id="{tutorial_template_match["id"]}">'
            )
            write_out = import_foundation_tutorial_template(
                case_dir=state["case_dir"],
                template_match=tutorial_template_match,
                user_requirement=state.get("user_requirement", ""),
            )
            print("</foundation_tutorial_template_import>")
            print("</input_writer>")

            convert_case_to_esi_if_needed(state["case_dir"], config)

            dir_structure = scan_case_directory(state["case_dir"])
            foamfiles = read_case_foamfiles(state["case_dir"], dir_structure)

            return {
                "dir_structure": dir_structure,
                "commands": [],
                "foamfiles": foamfiles,
                "tutorial_template_import": write_out.get("tutorial_template_import"),
            }

        reuse_generated_dir = getattr(config, "reuse_generated_dir", "")
        if reuse_generated_dir and Path(reuse_generated_dir).is_dir():
            reuse_path = Path(reuse_generated_dir).resolve()
            case_path = Path(state["case_dir"]).resolve()
            print(
                f'<rheotool_tutorial_template_reuse id="{tutorial_template_match["id"]}" '
                f'source="{reuse_path}"/>'
            )
            if reuse_path != case_path:
                shutil.copytree(reuse_path, case_path, dirs_exist_ok=True)
            normalize_imported_rheotool_tutorial_case(
                state["case_dir"],
                tutorial_template_match["id"],
            )
            print("</input_writer>")

            convert_case_to_esi_if_needed(state["case_dir"], config)

            dir_structure = scan_case_directory(state["case_dir"])
            foamfiles = read_case_foamfiles(state["case_dir"], dir_structure)
            note = None
            import_note = Path(state["case_dir"]) / "TUTORIAL_TEMPLATE_IMPORT.json"
            if import_note.is_file():
                try:
                    note = json.loads(import_note.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    note = None

            return {
                "dir_structure": dir_structure,
                "commands": [],
                "foamfiles": foamfiles,
                "tutorial_template_import": note,
            }

        print(
            f'<rheotool_tutorial_template_import id="{tutorial_template_match["id"]}">'
        )
        write_out = import_rheotool_tutorial_template(
            case_dir=state["case_dir"],
            template_match=tutorial_template_match,
            user_requirement=state.get("user_requirement", ""),
        )
        print("</rheotool_tutorial_template_import>")
        print("</input_writer>")

        convert_case_to_esi_if_needed(state["case_dir"], config)

        dir_structure = scan_case_directory(state["case_dir"])
        foamfiles = read_case_foamfiles(state["case_dir"], dir_structure)

        return {
            "dir_structure": dir_structure,
            "commands": [],
            "foamfiles": foamfiles,
            "tutorial_template_import": write_out.get("tutorial_template_import"),
        }

    write_out = initial_write(
        case_dir=state["case_dir"],
        subtasks=state["subtasks"],
        user_requirement=state["user_requirement"],
        tutorial_reference=state["tutorial_reference"],
        case_target=state["case_target"],
        generation_mode=getattr(config, "input_writer_generation_mode", "sequential_dependency"),
        similar_case_advice=state.get("similar_case_advice"),
        reuse_generated_dir=getattr(config, "reuse_generated_dir", ""),
    )

    dir_structure = write_out["dir_structure"]
    foamfiles = write_out["foamfiles"]

    # Build Allrun via service
    mesh_type = state.get("mesh_type")
    mesh_commands = state.get("mesh_commands") or []
    allrun_out = build_allrun(
        case_dir=state["case_dir"],
        database_path=config.database_path,
        searchdocs=config.searchdocs,
        dir_structure=dir_structure,
        case_info=state["case_info"],
        allrun_reference=state["allrun_reference"],
        mesh_type=mesh_type,
        mesh_commands=mesh_commands,
        user_requirement=state.get("user_requirement", ""),
        case_target=state["case_target"],
    )

    print("</input_writer>")

    convert_case_to_esi_if_needed(state["case_dir"], config)
    
    # Rescan the directory and foam files to reflect any translations
    dir_structure = scan_case_directory(state["case_dir"])
    foamfiles = read_case_foamfiles(state["case_dir"], dir_structure)

    return {
        "dir_structure": dir_structure,
        "commands": [],
        "foamfiles": foamfiles,
    }
