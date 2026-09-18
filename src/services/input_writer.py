import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
import shutil

import yaml
from utils import save_file, parse_context, retrieve_faiss, FoamPydantic, FoamfilePydantic, scan_case_directory, read_case_foamfiles, read_file
from models import CaseTarget
from .channel_prompts import load_channel_prompt
from .rheofoam_parallel import enable_rheofoam_parallel_if_large
from . import global_llm_service


RHEOTOOL_SOLVERS = {
    "rheoFoam",
    "rheoTestFoam",
    "rheoInterFoam",
    "rheoEFoam",
    "rheoHeatFoam",
    "rheoFilmFoam",
    "rheoBDFoam",
    "rheoMultiRegionFoam",
}


def _split_solver_metadata(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        parts = []
        for item in value:
            parts.extend(_split_solver_metadata(item))
        return parts
    text = str(value).strip()
    if not text or text.lower() in {"unknown", "none"}:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _normalize_target_solver(case_solver: Any) -> str:
    if isinstance(case_solver, (list, tuple, set)):
        return str(next(iter(case_solver), "")).strip()
    return str(case_solver or "").strip()


def _manual_section_owner(section: Any) -> str:
    text = str(section or "").strip()
    for prefix, solver in {
        "5.1": "rheoFoam",
        "5.2": "rheoTestFoam",
        "5.3": "rheoInterFoam",
        "5.4": "rheoEFoam",
        "5.5": "rheoHeatFoam",
        "5.6": "rheoMultiRegionFoam",
        "5.7": "rheoBDFoam",
        "5.8": "rheoFilmFoam",
    }.items():
        if text == prefix or text.startswith(prefix + "."):
            return solver
    return ""


def filter_rheotool_manual_rules(
    rules: List[Dict[str, Any]],
    target_solver: Any,
    topk: int,
) -> List[Dict[str, Any]]:
    """Apply solver-aware four-level filtering to RheoTool manual chunks.

    Priority order:
    1. Exact solver chunks, e.g. solver=rheoTestFoam for target rheoTestFoam.
    2. Multi-solver chunks that include the target solver.
    3. Generic chunks with no solver metadata.
    4. Explicit chunks for other solvers are excluded.
    """
    target = _normalize_target_solver(target_solver)
    if not target or target not in RHEOTOOL_SOLVERS:
        return []

    buckets = {"exact": [], "multi": [], "generic": []}
    excluded = 0
    for item in rules:
        solvers = _split_solver_metadata(item.get("solver"))
        owner = _manual_section_owner(item.get("section"))
        item = dict(item)

        # Chapter 5 tutorial sections have an authoritative owner. This prevents
        # inheritance mentions such as "rheoEFoam is derived from rheoFoam" from
        # causing 5.4 rheoEFoam rules to be injected into rheoFoam prompts.
        if owner and owner != target:
            excluded += 1
            continue
        if owner == target:
            item["manual_rule_match_level"] = "exact"
            buckets["exact"].append(item)
            continue

        if not solvers:
            item["manual_rule_match_level"] = "generic"
            buckets["generic"].append(item)
        elif target in solvers and len(solvers) == 1:
            item["manual_rule_match_level"] = "exact"
            buckets["exact"].append(item)
        elif target in solvers:
            item["manual_rule_match_level"] = "multi_solver"
            buckets["multi"].append(item)
        else:
            excluded += 1

    selected = (buckets["exact"] + buckets["multi"] + buckets["generic"])[:topk]
    print(
        f"<manual_rag_filter solver=\"{target}\" exact=\"{len(buckets['exact'])}\" "
        f"multi=\"{len(buckets['multi'])}\" generic=\"{len(buckets['generic'])}\" "
        f"excluded=\"{excluded}\" selected=\"{len(selected)}\"/>"
    )
    return selected


def _normalize_case_rel_path(folder_name: Any, file_name: Any) -> str:
    return os.path.join(str(folder_name or ""), str(file_name or "")).replace('\\', '/').lstrip('./')


def _schema_forbidden_files(case_target: CaseTarget) -> set[str]:
    schema_path = (
        Path(__file__).resolve().parent
        / "solver_schemas"
        / case_target.version
        / f"{case_target.solver}.yaml"
    )
    if not schema_path.exists():
        return set()
    data = yaml.safe_load(schema_path.read_text()) or {}
    return {str(path).replace('\\', '/').lstrip('./') for path in data.get("forbidden_files", []) or []}


def _change_requests_file_deletion(changes: Any) -> bool:
    text = str(changes or "").lower()
    patterns = (
        r"\bdelete\s+(?:the\s+)?file\b",
        r"\bremove\s+(?:the\s+|this\s+)?(?:forbidden\s+)?file\b",
        r"\bremove\s+file\s+from\s+(?:the\s+)?case\s+specification\b",
        r"\bremove\s+.*\bfrom\s+(?:the\s+)?case\s+specification\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _delete_case_rel_path(
    case_dir: str,
    rel_path: str,
    updated_dir: Dict[str, List[str]],
    foamfiles_list: List[FoamfilePydantic],
) -> List[FoamfilePydantic]:
    rel_path = rel_path.replace('\\', '/').lstrip('./')
    abs_path = os.path.join(case_dir, rel_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)
        print(f"<deleted_file>{rel_path}</deleted_file>")

    folder_name, file_name = os.path.split(rel_path)
    if folder_name in updated_dir and file_name in updated_dir[folder_name]:
        updated_dir[folder_name] = [name for name in updated_dir[folder_name] if name != file_name]

    return [
        foamfile
        for foamfile in foamfiles_list
        if _normalize_case_rel_path(foamfile.folder_name, foamfile.file_name) != rel_path
    ]




def _replace_foam_object_name(content: str, object_name: str) -> str:
    if re.search(r"object\s+\w+\s*;", content):
        return re.sub(r"object\s+\w+\s*;", f"object      {object_name};", content, count=1)
    return content


def _extract_boundary_patch_types(field_text: str) -> list[tuple[str, str]]:
    match = re.search(r"boundaryField\s*\{(?P<body>.*)\}\s*(?://.*)?$", field_text, re.DOTALL)
    if not match:
        return []
    body = match.group("body")
    patches: list[tuple[str, str]] = []
    index = 0
    while index < len(body):
        name_match = re.search(r"([A-Za-z0-9_().|*+-]+)\s*\{", body[index:])
        if not name_match:
            break
        name = name_match.group(1).strip('"')
        block_start = index + name_match.end()
        depth = 1
        cursor = block_start
        while cursor < len(body) and depth:
            if body[cursor] == "{":
                depth += 1
            elif body[cursor] == "}":
                depth -= 1
            cursor += 1
        block = body[block_start:cursor - 1]
        type_match = re.search(r"\btype\s+([^;]+);", block)
        patches.append((name, type_match.group(1).strip() if type_match else ""))
        index = cursor
    return patches


def _tau_boundary_type(patch_name: str, source_type: str) -> str:
    lowered = patch_name.lower()
    if source_type == "empty" or "frontandback" in lowered or lowered in {"front", "back"}:
        return "empty"
    if "inlet" in lowered:
        return "fixedValue"
    if "outlet" in lowered:
        return "zeroGradient"
    if any(token in lowered for token in ("wall", "lid", "moving", "fixed")):
        return "linearExtrapolation"
    return "zeroGradient"


def _default_tau_field_content(case_dir: str) -> str:
    u_path = Path(case_dir) / "0" / "U"
    patches = []
    if u_path.is_file():
        patches = _extract_boundary_patch_types(u_path.read_text(encoding="utf-8", errors="ignore"))
    if not patches:
        patches = [("walls", "fixedValue"), ("frontAndBack", "empty")]

    boundary_lines = []
    for patch_name, source_type in patches:
        tau_type = _tau_boundary_type(patch_name, source_type)
        boundary_lines.append(f"    {patch_name}\n    {{")
        boundary_lines.append(f"        type            {tau_type};")
        if tau_type in {"fixedValue", "linearExtrapolation"}:
            boundary_lines.append("        value           uniform (0 0 0 0 0 0);")
        boundary_lines.append("    }\n")

    return (
        "FoamFile\n"
        "{\n"
        "    version     2.0;\n"
        "    format      ascii;\n"
        "    class       volSymmTensorField;\n"
        "    object      tau;\n"
        "}\n"
        "\n"
        "dimensions      [1 -1 -2 0 0 0 0];\n"
        "\n"
        "internalField   uniform (0 0 0 0 0 0);\n"
        "\n"
        "boundaryField\n"
        "{\n"
        + "\n".join(boundary_lines)
        + "}\n"
    )


def _ensure_control_dict_lib(case_dir: str, lib_name: str) -> None:
    control_dict = Path(case_dir) / "system" / "controlDict"
    if not control_dict.is_file():
        return
    text = control_dict.read_text(encoding="utf-8", errors="ignore")
    if lib_name in text:
        return

    entry = f'    "{lib_name}"\n'
    libs_block = re.search(r"(?s)\blibs\s*\(.*?\)\s*;", text)
    if libs_block:
        block = libs_block.group(0)
        updated = re.sub(r"\)\s*;\s*$", entry + ");", block, count=1)
        text = text[:libs_block.start()] + updated + text[libs_block.end():]
    else:
        block = "libs\n(\n" + entry + ");\n"
        text = re.sub(
            r"(?m)^(\s*application\s+[^;]+;\s*)$",
            r"\1\n" + block,
            text,
            count=1,
        )
        if lib_name not in text:
            text = block + "\n" + text

    control_dict.write_text(text, encoding="utf-8")


def _ensure_v9_rheofoam_required_files(
    case_dir: str,
    case_target: CaseTarget,
    dir_structure: Dict[str, List[str]],
    written_files: List[FoamfilePydantic],
) -> None:
    if case_target.version != "v9" or case_target.solver != "rheoFoam":
        return

    case_path = Path(case_dir)
    has_generated_case_content = any(
        (case_path / rel_path).exists()
        for rel_path in (
            "system/controlDict",
            "0/U",
            "0/p",
            "constant/constitutiveProperties",
            "constant/viscoelasticProperties",
        )
    )
    if not has_generated_case_content:
        return

    constant_dir = case_path / "constant"
    constitutive_path = constant_dir / "constitutiveProperties"
    legacy_candidates = [constant_dir / "viscoelasticProperties"]
    if not constitutive_path.exists():
        for candidate in legacy_candidates:
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8", errors="ignore")
                content = _replace_foam_object_name(content, "constitutiveProperties")
                constitutive_path.write_text(content, encoding="utf-8")
                dir_structure.setdefault("constant", [])
                if "constitutiveProperties" not in dir_structure["constant"]:
                    dir_structure["constant"].append("constitutiveProperties")
                written_files.append(FoamfilePydantic(
                    file_name="constitutiveProperties",
                    folder_name="constant",
                    content=content,
                ))
                print(f"<rheofoam_v9_patch>Created constant/constitutiveProperties from {candidate.name}</rheofoam_v9_patch>")
                break

    zero_dir = Path(case_dir) / "0"
    tau_path = zero_dir / "tau"
    if not tau_path.exists():
        zero_dir.mkdir(parents=True, exist_ok=True)
        content = _default_tau_field_content(case_dir)
        tau_path.write_text(content, encoding="utf-8")
        dir_structure.setdefault("0", [])
        if "tau" not in dir_structure["0"]:
            dir_structure["0"].append("tau")
        written_files.append(FoamfilePydantic(
            file_name="tau",
            folder_name="0",
            content=content,
        ))
        print("<rheofoam_v9_patch>Created 0/tau initial extra-stress field</rheofoam_v9_patch>")

    if tau_path.is_file() and "linearExtrapolation" in tau_path.read_text(encoding="utf-8", errors="ignore"):
        _ensure_control_dict_lib(case_dir, "libBCRheoTool.so")


def compute_priority(subtask):
    if subtask["folder_name"] == "system":
        return 0
    elif subtask["folder_name"] == "constant":
        return 1
    elif subtask["folder_name"] == "0":
        return 2
    else:
        return 3


def initial_write(
    case_dir: str,
    subtasks: List[Dict[str, str]],
    user_requirement: str,
    tutorial_reference: str,
    case_target: CaseTarget,
    generation_mode: str = "sequential_dependency",
    case_info: str = "",
    allrun_reference: str = "",
    mesh_type: str = "blockMesh",
    mesh_commands: List[str] = None,
    database_path: str = "",
    searchdocs: int = 2,
    similar_case_advice: Optional[Any] = None,
    reuse_generated_dir: str = "",
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Generate OpenFOAM files from scratch based on user requirements and subtasks.
    
    This function creates OpenFOAM input files by analyzing user requirements,
    using similar case references, and generating files in the correct order
    (system -> constant -> 0 -> others). It also generates an Allrun script
    for automated execution.
    
    Args:
        case_dir (str): Directory path where the case files will be created
        subtasks (List[Dict[str, str]]): List of subtasks, each containing:
            - file_name: Name of the OpenFOAM file to create
            - folder_name: Directory where the file should be placed
        user_requirement (str): Natural language description of simulation requirements
        tutorial_reference (str): Reference content from similar tutorial cases
        case_solver (str): OpenFOAM solver to use (e.g., "simpleFoam", "pimpleFoam")
        case_info (str, optional): Additional case information. Defaults to "".
        allrun_reference (str, optional): Reference Allrun scripts from similar cases. Defaults to "".
        mesh_type (str, optional): Type of mesh to use. Defaults to "blockMesh".
        mesh_commands (List[str], optional): Custom mesh commands. Defaults to None.
        database_path (str, optional): Path to FAISS database for command lookup. Defaults to "".
        searchdocs (int, optional): Number of documents to search for commands. Defaults to 2.
    
    Returns:
        Dict[str, Any]: Contains:
            - dir_structure (Dict[str, List[str]]): Directory structure with files
            - foamfiles (FoamPydantic): Generated OpenFOAM files with metadata
    
    Raises:
        ValueError: If subtask format is invalid or file generation fails
        FileNotFoundError: If database files cannot be found
        RuntimeError: If LLM service fails to generate files
    
    Example:
        >>> subtasks = [
        ...     {"file_name": "controlDict", "folder_name": "system"},
        ...     {"file_name": "transportProperties", "folder_name": "constant"},
        ...     {"file_name": "U", "folder_name": "0"}
        ... ]
        >>> result = initial_write(
        ...     case_dir="/path/to/case",
        ...     subtasks=subtasks,
        ...     user_requirement="Simple fluid flow simulation",
        ...     tutorial_reference="Reference case content...",
        ...     case_solver="simpleFoam",
        ... )
        >>> print(f"Generated {len(result['dir_structure'])} directories")
    """
    print("<initial_write_service>")
    case_solver = case_target.solver

    def _report_progress(current: int, total: int, message: str) -> None:
        if progress_callback:
            try:
                progress_callback(current, total, message)
            except Exception:
                pass

    if generation_mode not in {"sequential_dependency", "parallel_no_context"}:
        raise ValueError(
            f"Unsupported generation_mode: {generation_mode}. "
            "Expected one of: sequential_dependency, parallel_no_context"
        )

    # Allrun is generated by build_allrun later. Planner models may still emit it
    # as a file-generation subtask, sometimes with an empty folder name; skip it
    # here to keep normal file generation focused on OpenFOAM dictionaries/fields.
    subtasks = [
        subtask for subtask in subtasks
        if subtask.get("file_name") != "Allrun"
    ]
    subtasks = sorted(subtasks, key=compute_priority)
    written_files = []
    dir_structure = {}

    # System prompt for file generation
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
    ) + "\n" + load_channel_prompt(case_target, "input_writer")

    def _extract_similar_file_reference(reference: str, folder_name: str, file_name: str, max_chars: int = 12000) -> str:
        if not reference:
            return ""

        file_name_re = re.escape(file_name)
        folder_name = (folder_name or "").strip()
        refs = []

        dir_pattern = re.compile(
            r"<directory_begin>directory name:\s*(.*?)\n(.*?)</directory_end>",
            re.DOTALL,
        )
        file_pattern = re.compile(
            rf"<file_begin>file name:\s*{file_name_re}\s*\n<file_content>(.*?)</file_content>\s*</file_end>",
            re.DOTALL,
        )

        for dir_match in dir_pattern.finditer(reference):
            ref_dir = dir_match.group(1).strip()
            dir_body = dir_match.group(2)
            if ref_dir != folder_name:
                continue
            for file_match in file_pattern.finditer(dir_body):
                refs.append(
                    f'<official_reference_file folder="{ref_dir}" name="{file_name}">\n'
                    f'{file_match.group(1).strip()}\n'
                    '</official_reference_file>'
                )

        # Fallback for unusual tutorial dumps where directory tags are absent or renamed.
        if not refs:
            for file_match in file_pattern.finditer(reference):
                refs.append(
                    f'<official_reference_file name="{file_name}">\n'
                    f'{file_match.group(1).strip()}\n'
                    '</official_reference_file>'
                )

        joined = "\n\n".join(refs)
        if len(joined) > max_chars:
            joined = joined[:max_chars] + "\n... <official_reference_truncated/>"
        return joined

    def _retrieve_rheotool_manual_rules(file_name: str, folder_name: str, max_chars: int = 10000) -> str:
        solver_text = ",".join(case_solver) if isinstance(case_solver, list) else str(case_solver or "")
        requirement_text = str(user_requirement or "")
        case_info_text = str(case_info or "")
        rheo_context = " ".join([solver_text, requirement_text, case_info_text]).lower()
        if "rheo" not in rheo_context and "viscoelastic" not in rheo_context and "流变" not in rheo_context:
            return ""

        query = "\n".join([
            f"solver: {solver_text}",
            f"target dictionary/file: {folder_name}/{file_name}",
            f"user requirement: {requirement_text}",
            "Return RheoTool manual rules for required keywords, valid model/library options, numerical algorithms, and dictionary structure.",
        ])

        requested_rules = min(5, max(2, int(searchdocs)))
        recall_rules = max(20, requested_rules * 6)
        try:
            raw_rules = retrieve_faiss(
                "rheotool_manual_rules", query, case_target, topk=recall_rules
            )
            rules = filter_rheotool_manual_rules(raw_rules, solver_text, requested_rules)
        except Exception as exc:
            print(f"Warning: RheoTool manual rules unavailable: {exc}")
            return ""

        def _xml_attr(value: Any) -> str:
            return str(value).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")

        blocks = []
        for idx, item in enumerate(rules, 1):
            content = item.get("full_content", "").strip()
            if not content or content == "unknown":
                continue
            if len(content) > 3000:
                content = content[:3000] + "\n... <manual_rule_truncated/>"
            attrs = (
                f'section="{_xml_attr(item.get("section", "unknown"))}" '
                f'title="{_xml_attr(item.get("title", "unknown"))}" '
                f'topic="{_xml_attr(item.get("topic", "unknown"))}" '
                f'dictionary="{_xml_attr(item.get("dictionary", "unknown"))}" '
                f'solver="{_xml_attr(item.get("solver", "unknown"))}" '
                f'match_level="{_xml_attr(item.get("manual_rule_match_level", "unfiltered"))}"'
            )
            blocks.append(f"<rheotool_manual_rule_{idx} {attrs}>\n{content}\n</rheotool_manual_rule_{idx}>")

        joined = "\n\n".join(blocks)
        if len(joined) > max_chars:
            joined = joined[:max_chars] + "\n... <rheotool_manual_rules_truncated/>"
        return joined

    def _build_prompts(file_name: str, folder_name: str, written_files_ctx: List[FoamfilePydantic]) -> tuple[str, str]:
        code_system_prompt = INITIAL_WRITE_SYSTEM_PROMPT.format(
            file_name=file_name,
            folder_name=folder_name,
            case_solver=case_solver,
        )

        advice_text = ""
        if isinstance(similar_case_advice, dict):
            advice_text = (
                f"Similar case match level: {similar_case_advice.get('match_level')}\n"
                f"Use scope: {similar_case_advice.get('use_scope')}\n"
                f"Advice: {similar_case_advice.get('advice')}\n"
            )
        elif similar_case_advice:
            advice_text = str(similar_case_advice)

        primary_file_reference = _extract_similar_file_reference(
            tutorial_reference,
            folder_name,
            file_name,
        )
        if primary_file_reference:
            similar_ref_block = (
                "Primary official reference for the same target file. Preserve its required dictionary structure, "
                "mandatory keywords, field names, and solver-specific conventions unless the user requirement explicitly changes them. "
                "Adapt only physical values, mesh sizes, boundary names, and runtime controls needed by the user:\n"
                f"<primary_similar_file_reference>{primary_file_reference}</primary_similar_file_reference>\n"
                f"Broader similar case context:\n<similar_case_reference>{tutorial_reference}</similar_case_reference>\n"
            )
        elif tutorial_reference:
            similar_ref_block = (
                f"Refer to the following similar case file content if helpful:\n<similar_case_reference>{tutorial_reference}</similar_case_reference>\n"
            )
        else:
            similar_ref_block = "No suitable similar case was found for this domain.\n"

        manual_rules = _retrieve_rheotool_manual_rules(file_name, folder_name)
        manual_rules_block = ""
        if manual_rules:
            manual_rules_block = (
                "RheoTool manual rules are authoritative for model names, required dictionaries, valid options, "
                "and solver-specific configuration. Use them to validate the tutorial template before writing the file:\n"
                f"<rheotool_manual_rules>{manual_rules}</rheotool_manual_rules>\n"
            )

        code_user_prompt = (
            f"User requirement: {user_requirement}\n"
            f"{similar_ref_block}"
            f"{manual_rules_block}"
            f"{advice_text}"
            "If the similar case is a weak match, do not copy it blindly. Use it only where it is consistent with the user requirement. "
            "Just modify the necessary parts to make the file complete and functional."
            "Please ensure that the generated file is complete, functional, and logically sound."
            "Additionally, apply your domain expertise to verify that all numerical values are consistent with the user's requirements, maintaining accuracy and coherence."
            "When generating controlDict, do not include anything to preform post processing. Just include the necessary settings to run the simulation."
        )

        if file_name == "fvSolution":
            code_user_prompt += (
                "\n\nCRITICAL for transient pressure-velocity coupling solvers using PISO/PIMPLE: "
                "the solvers dictionary must include matching Final solver entries for fields used on the final correction. "
                "For example, if p is defined, include pFinal { $p; relTol 0; }; "
                "if U is defined, include UFinal { $U; relTol 0; }. "
                "For grouped regex entries, use the matching grouped Final entry, e.g. "
                "\"(U|k|epsilon)Final\" { $U; relTol 0; }. "
                "Do not emit placeholder text such as $<field>; in the generated file. "
                "Also ensure the PIMPLE/PISO sub-dictionary matches the selected solver."
            )

        if generation_mode == "sequential_dependency" and written_files_ctx:
            code_user_prompt += (
                f"The following are files content already generated: {str(written_files_ctx)}\n\n\n"
                "You should ensure that the new file is consistent with the previous files. Such as boundary conditions, mesh settings, etc."
            )

        return code_user_prompt, code_system_prompt

    def _generate_one(subtask: Dict[str, str], written_files_ctx: List[FoamfilePydantic]) -> FoamfilePydantic:
        file_name = subtask["file_name"]
        folder_name = subtask["folder_name"]
        if not file_name or not folder_name:
            raise ValueError(f"Invalid subtask format: {subtask}")

        # Target output path (this run)
        file_path = os.path.join(case_dir, folder_name, file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Optional reuse: if a pre-generated file exists, copy it into output and
        # treat it as a written file (also included in context for subsequent generations).
        if reuse_generated_dir:
            reuse_src = os.path.join(reuse_generated_dir, folder_name, file_name)
            if os.path.exists(reuse_src):
                print(f"Reusing generated file: {reuse_src}")
                shutil.copy2(reuse_src, file_path)
                reused_content = read_file(reuse_src)
                return FoamfilePydantic(file_name=file_name, folder_name=folder_name, content=reused_content)

        code_user_prompt, code_system_prompt = _build_prompts(file_name, folder_name, written_files_ctx)

        if generation_mode == "parallel_no_context":
            # Avoid shared global LLM instance in parallel mode.
            from utils import LLMService
            from config import Config
            llm = LLMService(Config())
            generation_response = llm.invoke(code_user_prompt, code_system_prompt)
        else:
            generation_response = global_llm_service.invoke(code_user_prompt, code_system_prompt)

        code_context = parse_context(generation_response)
        save_file(file_path, code_context)
        return FoamfilePydantic(file_name=file_name, folder_name=folder_name, content=code_context)


    def _ensure_foundation_v9_transport_properties() -> None:
        constant_dir = os.path.join(case_dir, "constant")
        physical_path = os.path.join(constant_dir, "physicalProperties")
        transport_path = os.path.join(constant_dir, "transportProperties")
        if not os.path.exists(physical_path) or os.path.exists(transport_path):
            return

        content = read_file(physical_path)
        content = re.sub(r"object\s+physicalProperties\s*;", "object      transportProperties;", content)
        save_file(transport_path, content)
        dir_structure.setdefault("constant", [])
        if "transportProperties" not in dir_structure["constant"]:
            dir_structure["constant"].append("transportProperties")
        written_files.append(FoamfilePydantic(
            file_name="transportProperties",
            folder_name="constant",
            content=content,
        ))
        print("<foundation_v9_patch>Created constant/transportProperties from physicalProperties</foundation_v9_patch>")

    forbidden_files = _schema_forbidden_files(case_target)
    if forbidden_files:
        filtered_subtasks = []
        for subtask in subtasks:
            rel_path = _normalize_case_rel_path(subtask.get("folder_name"), subtask.get("file_name"))
            if rel_path in forbidden_files:
                print(f'<schema_forbidden_subtask_skipped path="{rel_path}"/>')
                continue
            filtered_subtasks.append(subtask)
        subtasks = filtered_subtasks

    # Build dir_structure upfront (deterministic ordering) and generate files
    for subtask in subtasks:
        folder_name = subtask.get("folder_name")
        file_name = subtask.get("file_name")
        if folder_name not in dir_structure:
            dir_structure[folder_name] = []
        dir_structure[folder_name].append(file_name)

    total_steps = len(subtasks) + (2 if database_path else 0)
    _report_progress(0, total_steps, f"Starting file generation for {len(subtasks)} files")

    if generation_mode == "parallel_no_context":
        print("<generation_mode>parallel_no_context (no cross-file context)</generation_mode>")
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        # Parallelize all file generations; keep output order consistent with sorted subtasks.
        results: List[Optional[FoamfilePydantic]] = [None] * len(subtasks)
        completed_count = 0
        count_lock = threading.Lock()
        with ThreadPoolExecutor(max_workers=min(32, max(4, len(subtasks)))) as ex:
            future_map = {
                ex.submit(_generate_one, subtasks[i], []): i
                for i in range(len(subtasks))
            }
            for fut in as_completed(future_map):
                i = future_map[fut]
                results[i] = fut.result()
                with count_lock:
                    completed_count += 1
                    _report_progress(
                        completed_count, total_steps,
                        f"Generated {subtasks[i]['file_name']} in {subtasks[i]['folder_name']} (parallel)"
                    )

        written_files.extend([r for r in results if r is not None])

    else:
        print("<generation_mode>sequential_dependency</generation_mode>")
        for idx, subtask in enumerate(subtasks):
            file_name = subtask["file_name"]
            folder_name = subtask["folder_name"]
            print(f"<generating_file>{file_name} in folder: {folder_name}</generating_file>")
            foamfile = _generate_one(subtask, written_files)
            written_files.append(foamfile)
            _report_progress(idx + 1, total_steps, f"Generated {file_name} in {folder_name}")
    
    _ensure_foundation_v9_transport_properties()
    _ensure_v9_rheofoam_required_files(case_dir, case_target, dir_structure, written_files)

    # Generate Allrun script if database_path is provided
    if database_path:
        allrun_result = build_allrun(
            case_dir, database_path, searchdocs, dir_structure, case_info,
            allrun_reference, mesh_type, mesh_commands or [], user_requirement,
            case_target=case_target,
            progress_callback=progress_callback,
            progress_offset=len(subtasks),
            total_steps=total_steps,
        )
        written_files.append(FoamfilePydantic(file_name="Allrun", folder_name=case_dir, content=allrun_result["allrun_script"]))
    
    foamfiles = FoamPydantic(list_foamfile=written_files)
    print("</initial_write_service>")
    return {"dir_structure": dir_structure, "foamfiles": foamfiles}


def build_allrun(
    case_dir: str,
    database_path: str,
    searchdocs: int,
    dir_structure: Dict[str, List[str]],
    case_info: str,
    allrun_reference: str,
    mesh_type: str,
    mesh_commands: List[str],
    user_requirement: str = "",
    case_target: CaseTarget = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    progress_offset: int = 0,
    total_steps: int = 0,
) -> Dict[str, Any]:
    """
    Build an Allrun script for automated OpenFOAM simulation execution.
    
    This function generates a complete Allrun script by analyzing the case structure,
    retrieving appropriate OpenFOAM commands from the database, and creating
    a shell script that automates the simulation workflow.
    
    Args:
        case_dir (str): Directory path where the Allrun script will be created
        database_path (str): Path to the FAISS database containing OpenFOAM commands
        searchdocs (int): Number of documents to search for command help
        dir_structure (Dict[str, List[str]]): Directory structure with file lists
        case_info (str): Case information including name, solver, domain, category
        allrun_reference (str): Reference Allrun scripts from similar cases
        mesh_type (str): Type of mesh ("blockMesh", "snappyHexMesh", "custom_mesh")
        mesh_commands (List[str]): Custom mesh commands to include
        user_requirement (str, optional): User requirements for context. Defaults to "".
    
    Returns:
        Dict[str, Any]: Contains:
            - allrun_path (str): Path to the created Allrun script
            - allrun_script (str): Content of the Allrun script
            - commands (List[str]): List of OpenFOAM commands used
    
    Raises:
        ValueError: If commands file cannot be read or no commands are generated
        FileNotFoundError: If database files are not found
        RuntimeError: If LLM service fails to generate script
    
    Example:
        >>> result = build_allrun(
        ...     case_dir="/path/to/case",
        ...     database_path="/path/to/database",
        ...     searchdocs=2,
        ...     dir_structure={"system": ["controlDict"], "0": ["U"]},
        ...     case_info="case name: test\ncase solver: simpleFoam",
        ...     allrun_reference="Reference scripts...",
        ...     mesh_type="blockMesh",
        ...     mesh_commands=[]
        ... )
        >>> print(f"Generated script with {len(result['commands'])} commands")
    """
    from pydantic import BaseModel, Field
    from typing import List
    
    # Parse allrun helper function
    def parse_allrun(text: str) -> str:
        match = re.search(r"```(?:bash|sh)?\s*(.*?)\s*```", text, re.DOTALL)
        return match.group(1).strip() if match else text

    def user_requires_check_mesh(text: str) -> bool:
        lowered = text.lower()
        return "checkmesh" in lowered or "check mesh" in lowered or "检查网格" in text

    def ensure_check_mesh(commands: List[str]) -> List[str]:
        if not user_requires_check_mesh(user_requirement):
            return commands
        if any(command.lower() == "checkmesh" for command in commands):
            return commands

        mesh_generators = {"blockmesh", "snappyhexmesh", "cartesianmesh", "gmshtofoam"}
        result = list(commands)
        insert_at = 1 if result else 0
        for index, command in enumerate(result):
            if command.lower() in mesh_generators:
                insert_at = index + 1
        result.insert(insert_at, "checkMesh")
        return result

    def ensure_check_mesh_in_allrun(script: str) -> str:
        if not user_requires_check_mesh(user_requirement):
            return script
        if "runApplication checkMesh" in script or " checkMesh" in script:
            return script

        lines = script.splitlines()
        insert_at = None
        for index, line in enumerate(lines):
            lowered = line.strip().lower()
            if lowered == "runapplication blockmesh" or lowered.startswith("blockmesh"):
                insert_at = index + 1
        if insert_at is None:
            for index, line in enumerate(lines):
                if line.strip().startswith("runApplication ") and "mesh" not in line.lower():
                    insert_at = index
                    break
        if insert_at is None:
            insert_at = len(lines)
        lines.insert(insert_at, "runApplication checkMesh")
        return "\n".join(lines)

    def ensure_fail_fast_allrun(script: str) -> str:
        lines = script.splitlines()
        if not lines:
            return "#!/bin/sh\nset -e"
        if not lines[0].startswith("#!"):
            lines.insert(0, "#!/bin/sh")
        has_fail_fast = any(line.strip() in {"set -e", "set -eu", "set -euo pipefail"} for line in lines[:8])
        if not has_fail_fast:
            insert_at = 1
            while insert_at < len(lines) and not lines[insert_at].strip():
                insert_at += 1
            lines.insert(insert_at, "set -e")
        return "\n".join(lines)
    
    if not isinstance(case_target, CaseTarget):
        raise TypeError("build_allrun requires an immutable CaseTarget")

    # CommandsPydantic class for structured response
    class CommandsPydantic(BaseModel):
        commands: List[str] = Field(description="List of commands")
    
    # Retrieve commands from file
    command_path = f"{database_path}/raw/openfoam_commands.txt"
    try:
        with open(command_path, 'r') as file:
            commands = file.readlines()
        commands = f"[{', '.join([c.strip() for c in commands])}]"
    except (FileNotFoundError, IOError) as e:
        raise ValueError(f"Could not read commands file {command_path}: {e}")

    # Handle mesh commands info
    mesh_commands_info = ""
    if mesh_type == "custom_mesh" and mesh_commands:
        mesh_commands_info = f"\nCustom mesh commands to include: {mesh_commands}"
        print(f"Including custom mesh commands: {mesh_commands}")

    # Command generation system prompt
    command_system_prompt = (
        "You are an expert in OpenFOAM. The user will provide a list of available commands. "
        "Your task is to generate only the necessary OpenFOAM commands required to create an Allrun script for the given user case, based on the provided directory structure. "
        "Return only the list of commands—no explanations, comments, or additional text."
    )

    if mesh_type == "custom_mesh":
        command_system_prompt += "If custom mesh commands are provided, include them in the appropriate order (typically after blockMesh or instead of blockMesh if custom mesh is used). "
    
    command_user_prompt = (
        f"Available OpenFOAM commands for the Allrun script: {commands}\n"
        f"Case directory structure: {dir_structure}\n"
        f"User case information: {case_info}\n"
        f"Reference Allrun scripts from similar cases: {allrun_reference}\n"
        "Generate only the required OpenFOAM command list—no extra text."
    )

    if mesh_type == "custom_mesh":
        command_user_prompt += f"{mesh_commands_info}\n"
    
    command_response = global_llm_service.invoke(command_user_prompt, command_system_prompt, pydantic_obj=CommandsPydantic)

    if progress_callback:
        try:
            progress_callback(progress_offset + 1, total_steps, "Generated Allrun commands")
        except Exception:
            pass

    if len(command_response.commands) == 0:
        print("Failed to generate commands.")
        raise ValueError("Failed to generate commands.")

    command_response.commands = ensure_check_mesh(command_response.commands)
    print(f"Need {len(command_response.commands)} commands.")
    
    # Get command help from FAISS
    commands_help = []
    for command in command_response.commands:
        command_help = retrieve_faiss(
            "openfoam_command_help", command, case_target, topk=searchdocs,
        )
        commands_help.append(command_help[0]['full_content'])
    commands_help = "\n".join(commands_help)

    # Allrun generation system prompt
    allrun_system_prompt = (
        "You are an expert in OpenFOAM. Generate an Allrun script based on the provided details."
        f"Available commands with descriptions: {commands_help}\n\n"
        f"Reference Allrun scripts from similar cases: {allrun_reference}\n\n"
        "If custom mesh commands are provided, make sure to include them in the appropriate order in the Allrun script. "
        "CRITICAL: Do not include any post processing commands in the Allrun script."
        "CRITICAL: Do not include any commands to convert mesh to foam format like gmshToFoam or others."
    ) + "\n" + load_channel_prompt(case_target, "input_writer")

    if mesh_type == "custom_mesh":
        allrun_system_prompt += "CRITICAL: Do not include any other mesh commands other than the custom mesh commands.\n"
        allrun_system_prompt += "CRITICAL: Do not include any gmshToFoam commands in the Allrun script."
    
    allrun_user_prompt = (
        f"User requirement: {user_requirement}\n"
        f"Case directory structure: {dir_structure}\n"
        f"User case infomation: {case_info}\n"
        f"{mesh_commands_info}\n"
        "All run scripts for these similar cases are for reference only and may not be correct, as you might be a different case solver or have a different directory structure. " 
        "You need to rely on your OpenFOAM and physics knowledge to discern this, and pay more attention to user requirements, " 
        "as your ultimate goal is to fulfill the user's requirements and generate an allrun script that meets those requirements."
        "CRITICAL: Do not include any post processing commands in the Allrun script."
        "CRITICAL: Do not include any commands to convert mesh to foam format like gmshToFoam or others."
        "CRITICAL: Do not include any commands that run gmsh to create the mesh."
        "Generate the Allrun script strictly based on the above information. Do not include explanations, comments, or additional text. Put the code in ``` tags."
    )

    if mesh_type == "custom_mesh":
        allrun_user_prompt += "CRITICAL: Do not include any other mesh commands other than the custom mesh commands.\n"
        allrun_user_prompt += "CRITICAL: Do not include any gmshToFoam commands in the Allrun script."

    allrun_response = global_llm_service.invoke(allrun_user_prompt, allrun_system_prompt)

    if progress_callback:
        try:
            progress_callback(progress_offset + 2, total_steps, "Generated Allrun script")
        except Exception:
            pass

    allrun_script = parse_allrun(allrun_response)
    allrun_script = ensure_check_mesh_in_allrun(allrun_script)
    allrun_script = ensure_fail_fast_allrun(allrun_script)
    allrun_script = enable_rheofoam_parallel_if_large(case_dir, case_target, allrun_script)
    allrun_file_path = os.path.join(case_dir, "Allrun")
    save_file(allrun_file_path, allrun_script)
    
    return {"allrun_path": allrun_file_path, "allrun_script": allrun_script, "commands": command_response.commands}



def rewrite_files(
    case_dir: str,
    error_logs: List[str],
    review_analysis: str,
    rewrite_plan: Optional[Dict[str, Any]],
    user_requirement: str,
    case_target: CaseTarget,
    foamfiles: Optional[Any] = None,
    dir_structure: Optional[Dict[str, List[str]]] = None
) -> Dict[str, Any]:
    """
    Rewrite OpenFOAM files based on error analysis and reviewer suggestions.
    
    This function analyzes error logs and reviewer suggestions to identify
    problematic files, then uses LLM to generate corrected versions of
    the files that need modification.
    
    The function automatically reads foamfiles and directory structure from
    case_dir if they are not provided.
    
    Args:
        case_dir (str): Directory path where the case files are located
        error_logs (List[str]): List of error messages from simulation runs
        review_analysis (str): Analysis and suggestions from the reviewer (required)
        user_requirement (str): Original user requirements for context
        foamfiles (Optional[Any]): FoamPydantic object containing current file contents.
                                   If None, will be read from case_dir.
        dir_structure (Optional[Dict[str, List[str]]]): Current directory structure.
                                                        If None, will be scanned from case_dir.
    
    Returns:
        Dict[str, Any]: Contains:
            - dir_structure (Dict[str, List[str]]): Updated directory structure
            - foamfiles (FoamPydantic): Updated file contents with corrections
            - error_logs (List[str]): Cleared error logs (empty on success)
    
    Raises:
        FileNotFoundError: If case directory does not exist
        ValueError: If review_analysis is empty or foamfiles format is invalid
        RuntimeError: If LLM service fails to generate corrections
    
    Example:
        >>> result = rewrite_files(
        ...     case_dir="/path/to/case",
        ...     error_logs=["Error: undefined reference"],
        ...     review_analysis="Add missing boundary condition",
        ...     user_requirement="Simple flow simulation"
        ...     # foamfiles and dir_structure will be read automatically
        ... )
        >>> print(f"Updated {len(result['foamfiles'].list_foamfile)} files")
    """
    # Validate case directory exists
    if not os.path.exists(case_dir):
        raise FileNotFoundError(f"Case directory does not exist: {case_dir}")
    
    # Validate review_analysis is provided
    if not review_analysis or review_analysis.strip() == "":
        raise ValueError("review_analysis is required and cannot be empty")
    
    # Read directory structure if not provided
    if dir_structure is None:
        print(f"Scanning directory structure from: {case_dir}")
        dir_structure = scan_case_directory(case_dir)
    
    # Read foamfiles if not provided
    if foamfiles is None:
        print(f"Reading OpenFOAM files from: {case_dir}")
        foamfiles = read_case_foamfiles(case_dir, dir_structure)
    
    from utils import FoamPydantic, FoamfilePydantic  # local import to avoid cycles
    import re

    if not isinstance(case_target, CaseTarget):
        raise TypeError("rewrite_files requires an immutable CaseTarget")

    rewrite_system_prompt = (
        "You are an expert in OpenFOAM simulation and numerical modeling. "
        "Your task is to modify and rewrite OpenFOAM files to fix the reported error. "
        "Please do not propose solutions that require modifying any parameters declared in the user requirement, try other approaches instead. "
        "You will receive a rewrite_plan. Follow it strictly: only modify files listed in rewrite_plan.target_files and apply only the requested changes. "
        "Do not modify files outside the plan. "
        "Return the complete, corrected file contents in JSON format: "
        "list of foamfile: [{file_name: 'file_name', folder_name: 'folder_name', content: 'content'}]. "
        "Ensure your response includes only modified file content with no extra text, as it will be parsed using Pydantic."
    ) + "\n" + load_channel_prompt(case_target, "error_fix")

    # Prepare updated structures before any LLM call so delete-only fixes can be applied deterministically.
    updated_dir = dict(dir_structure) if dir_structure else {}
    foamfiles_list = []
    if foamfiles and hasattr(foamfiles, "list_foamfile") and foamfiles.list_foamfile:
        foamfiles_list = list(foamfiles.list_foamfile)

    remaining_target_files = []
    if rewrite_plan and isinstance(rewrite_plan, dict):
        for item in rewrite_plan.get("target_files", []):
            file_path = item.get("file") if isinstance(item, dict) else None
            if not file_path:
                continue
            rel_path = file_path.strip().replace('\\', '/').lstrip("./")
            if _change_requests_file_deletion(item.get("changes")):
                foamfiles_list = _delete_case_rel_path(case_dir, rel_path, updated_dir, foamfiles_list)
                continue
            remaining_target_files.append(item)

    if rewrite_plan and isinstance(rewrite_plan, dict):
        rewrite_plan = {**rewrite_plan, "target_files": remaining_target_files}

    if not remaining_target_files:
        updated_foamfiles = FoamPydantic(list_foamfile=foamfiles_list)
        return {
            "dir_structure": updated_dir,
            "foamfiles": updated_foamfiles,
            "error_logs": [],
        }

    rewrite_user_prompt = (
        f"<foamfiles>{str(foamfiles)}</foamfiles>\n"
        f"<error_logs>{error_logs}</error_logs>\n"
        f"<reviewer_analysis>{review_analysis}</reviewer_analysis>\n"
        f"<rewrite_plan>{rewrite_plan}</rewrite_plan>\n\n"
        f"<user_requirement>{user_requirement}</user_requirement>\n\n"
        "Please update OpenFOAM files according to rewrite_plan only. "
        "Only include files from rewrite_plan.target_files in your output."
    )

    response = global_llm_service.invoke(rewrite_user_prompt, rewrite_system_prompt, pydantic_obj=FoamPydantic)

    allowed_files = set()
    for item in remaining_target_files:
        file_path = item.get("file") if isinstance(item, dict) else None
        if file_path:
            allowed_files.add(file_path.strip().lstrip("./"))

    for foamfile in response.list_foamfile:
        rel_path = os.path.join(foamfile.folder_name, foamfile.file_name).replace('\\', '/').lstrip('./')
        if allowed_files and rel_path not in allowed_files:
            print(f"Warning: Skipping unplanned rewrite file: {rel_path}")
            continue

        file_path = os.path.join(case_dir, foamfile.folder_name, foamfile.file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        save_file(file_path, foamfile.content)

        if foamfile.folder_name not in updated_dir:
            updated_dir[foamfile.folder_name] = []
        if foamfile.file_name not in updated_dir[foamfile.folder_name]:
            updated_dir[foamfile.folder_name].append(foamfile.file_name)

        foamfiles_list = [
            f for f in foamfiles_list
            if not (f.folder_name == foamfile.folder_name and f.file_name == foamfile.file_name)
        ]
        foamfiles_list.append(foamfile)

    updated_foamfiles = FoamPydantic(list_foamfile=foamfiles_list)
    return {
        "dir_structure": updated_dir,
        "foamfiles": updated_foamfiles,
        "error_logs": [],
    }
