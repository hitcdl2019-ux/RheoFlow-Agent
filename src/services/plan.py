import os
import re
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from utils import LLMService, retrieve_faiss, parse_directory_structure
from . import global_llm_service
from .solver_router import ensure_rheotool_solvers_in_case_stats
from .workflow_compiler import compile_workflow
from .benchmarks import benchmark_subtasks, find_certified_benchmark
from .rheotool_templates import (
    find_rheotool_tutorial_template,
    tutorial_template_subtasks,
)
from .foundation_templates import (
    find_foundation_tutorial_template,
    foundation_template_subtasks,
)
from models import CaseTarget


def _has_tutorial_reproduction_intent(user_requirement: str) -> bool:
    text = str(user_requirement or "").casefold()
    return any(
        term in text
        for term in (
            "复现", "benchmark", "tutorial", "教程", "user guide",
            "rheotool", "rheo tool", "fattal", "kupferman",
        )
    )


class CaseSummaryModel(BaseModel):
    case_name: str = Field(description="name of the case")
    case_domain: str = Field(description="domain of the case")
    case_category: str = Field(description="category of the case")
    case_solver: str = Field(description="solver of the case")


class SubtaskModel(BaseModel):
    file_name: str
    folder_name: str


class OpenFOAMPlanModel(BaseModel):
    subtasks: List[SubtaskModel]


def parse_requirement_to_case_info(user_requirement: str, case_stats: Dict[str, List[str]]) -> Dict[str, str]:
    """
    Parse user requirements into structured case information using LLM.

    This function uses LLM to analyze natural language user requirements
    and extract structured case information including name, domain, category,
    and solver. The extracted values are validated against available options.

    Args:
        user_requirement (str): Natural language description of simulation requirements
        case_stats (Dict[str, List[str]]): Available case statistics with keys:
            - case_domain: List of available domains (e.g., ["fluid", "solid"])
            - case_category: List of available categories (e.g., ["tutorial", "advanced"])
            - case_solver: List of available solvers (e.g., ["simpleFoam", "pimpleFoam"])

    Returns:
        Dict[str, str]: Structured case information containing:
            - case_name (str): Parsed case name with spaces replaced by underscores
            - case_domain (str): Selected domain from available options
            - case_category (str): Selected category from available options
            - case_solver (str): Selected solver from available options

    Raises:
        ValueError: If LLM fails to parse requirements or returns invalid values
        RuntimeError: If LLM service is unavailable

    Example:
        >>> case_stats = {
        ...     "case_domain": ["fluid", "solid"],
        ...     "case_category": ["tutorial", "advanced"],
        ...     "case_solver": ["simpleFoam", "pimpleFoam"]
        ... }
        >>> result = parse_requirement_to_case_info(
        ...     "Create a simple fluid flow tutorial",
        ...     case_stats
        ... )
        >>> print(f"Case: {result['case_name']}, Solver: {result['case_solver']}")
    """
    parse_system_prompt = (
        "Please transform the following user requirement into a standard case description using a structured format."
        "The key elements should include case name, case domain, case category, and case solver."
        f"Note: case domain must be one of {case_stats.get('case_domain', [])}."
        f"Note: case category must be one of {case_stats.get('case_category', [])}."
        f"Note: case solver must be one of {case_stats.get('case_solver', [])}."
    )
    parse_user_prompt = f"User requirement: {user_requirement}."
    res = global_llm_service.invoke(parse_user_prompt, parse_system_prompt, pydantic_obj=CaseSummaryModel)
    return {
        "case_name": res.case_name.replace(" ", "_"),
        "case_domain": res.case_domain,
        "case_category": res.case_category,
        "case_solver": res.case_solver,
    }


def resolve_case_dir(
    case_name: str,
    case_dir: str = "",
    run_times: int = 1,
    run_directory: str = None
) -> str:
    """
    Resolve the case directory path based on case name and run configuration.

    This function determines the appropriate directory path for a case,
    handling both custom paths and default run directories with
    optional run numbering for multiple executions.

    Args:
        case_name (str): Name of the case (used for directory naming)
        case_dir (str, optional): Custom case directory path. If provided, this is returned directly.
        run_times (int, optional): Number of runs for this case. Defaults to 1.
        run_directory (str, optional): Base directory for runs. If None, uses default runs directory.

    Returns:
        str: Resolved case directory path

    Example:
        >>> # Custom directory
        >>> path = resolve_case_dir("test_case", case_dir="/custom/path")
        >>> print(path)  # "/custom/path"

        >>> # Default directory with run numbering
        >>> path = resolve_case_dir("test_case", run_times=3)
        >>> print(path)  # "/path/to/runs/test_case_3"

        >>> # Single run in default directory
        >>> path = resolve_case_dir("test_case")
        >>> print(path)  # "/path/to/runs/test_case"
    """
    if case_dir:
        return case_dir
    if run_directory is None:
        run_directory = str(Path(__file__).resolve().parent.parent / "runs")
    base_dir = str(run_directory)
    if run_times > 1:
        return os.path.join(base_dir, f"{case_name}_{run_times}")
    return os.path.join(base_dir, case_name)


class SimilarCaseAdviceModel(BaseModel):
    match_level: str = Field(description="high/medium/low/none")
    use_scope: str = Field(description="short guidance about which files can use the reference")
    advice: str = Field(description="one-sentence advice to include in prompts")


def _log_top3(label: str, items: List[Dict[str, Any]]) -> None:
    print(f"{label} (top-3):")
    for i, it in enumerate(items[:3], 1):
        print(
            f"  {i}. {it.get('case_name')} | {it.get('case_domain')} | {it.get('case_category')} | {it.get('case_solver')} | score={it.get('score')}"
        )


def _rerank_candidates(
    candidates: List[Dict[str, Any]],
    case_solver: str,
) -> List[Dict[str, Any]]:
    def key(item: Dict[str, Any]) -> tuple:
        solver_match = 1 if item.get("case_solver") == case_solver else 0
        score = item.get("score")
        score_val = 0.0 if score is None else float(score)
        return (-solver_match, score_val)

    return sorted(candidates, key=key)


def _build_advice(
    user_requirement: str,
    case_info: str,
    selected: Optional[Dict[str, Any]],
    candidates: List[Dict[str, Any]],
) -> SimilarCaseAdviceModel:
    cand_lines = [
        f"- {c.get('case_name')} | {c.get('case_domain')} | {c.get('case_category')} | {c.get('case_solver')} | score={c.get('score')}"
        for c in candidates[:5]
    ]
    cand_block = "\n".join(cand_lines) if cand_lines else "(none)"

    selected_line = (
        f"{selected.get('case_name')} | {selected.get('case_domain')} | {selected.get('case_category')} | {selected.get('case_solver')} | score={selected.get('score')}"
        if selected else "(none)"
    )

    sys_prompt = (
        "You are a CFD expert. Based on the user requirement and the retrieved similar cases, "
        "produce a concise usage guidance. If no suitable case is available, set match_level to 'none' "
        "and advise not to rely on similar case templates."
    )
    user_prompt = (
        f"User requirement:\n{user_requirement}\n\n"
        f"Case info:\n{case_info}\n\n"
        f"Selected similar case:\n{selected_line}\n\n"
        f"Top candidates:\n{cand_block}\n\n"
        "Return JSON with keys: match_level (high/medium/low/none), use_scope, advice."
    )

    return global_llm_service.invoke(user_prompt, sys_prompt, pydantic_obj=SimilarCaseAdviceModel)


def _fetch_matching_detail_reference(
    selected: Dict[str, Any], searchdocs: int, case_target: CaseTarget
) -> str:
    query = (
        f"case name: {selected.get('case_name')}\n"
        f"case domain: {selected.get('case_domain')}\n"
        f"case category: {selected.get('case_category')}\n"
        f"case solver: {selected.get('case_solver')}"
    )
    exact_filter = {
        "case_name": selected.get("case_name"),
        "case_domain": selected.get("case_domain"),
        "case_category": selected.get("case_category"),
        "case_solver": selected.get("case_solver"),
    }

    try:
        detail_candidates = retrieve_faiss(
            "openfoam_tutorials_details",
            query,
            case_target,
            topk=max(1, int(searchdocs)),
            metadata_filter=exact_filter,
            min_results=1,
            filter_label=f"details exact {selected.get('case_solver')}::{selected.get('case_name')}",
        )
        if detail_candidates:
            return detail_candidates[0].get("full_content", "")
    except ValueError:
        pass

    # Same-solver fallback only. Never fall back across solvers, because that
    # silently reintroduces cross-solver contamination after full RAG injection.
    same_solver_filter = {"case_solver": selected.get("case_solver")}
    try:
        detail_candidates = retrieve_faiss(
            "openfoam_tutorials_details",
            query,
            case_target,
            topk=max(10, int(searchdocs)),
            metadata_filter=same_solver_filter,
            min_results=1,
            filter_label=f"details solver {selected.get('case_solver')}",
        )
    except ValueError:
        return selected.get("full_content", "")

    for item in detail_candidates:
        if item.get("case_name") == selected.get("case_name"):
            return item.get("full_content", "")

    return selected.get("full_content", "")


def retrieve_references(case_name: str,
                        case_solver: str,
                        case_domain: str,
                        case_category: str,
                        searchdocs: int = 2,
                        user_requirement: str = "",
                        metadata_constraints: Optional[Dict[str, Any]] = None) -> Tuple[str, str, str, str, SimilarCaseAdviceModel]:
    # Build case_info
    case_info = f"case name: {case_name}\ncase domain: {case_domain}\ncase category: {case_category}\ncase solver: {case_solver}"
    print("Retrieval query:\n" + case_info)
    case_target = CaseTarget.for_solver(case_solver)

    recall_k = max(10, int(searchdocs))
    structure_filter = {
        "case_domain": case_domain,
        "case_solver": case_solver,
        **(metadata_constraints or {}),
    }
    try:
        faiss_structure_all = retrieve_faiss(
            "openfoam_tutorials_structure",
            case_info,
            case_target,
            topk=recall_k,
            metadata_filter=structure_filter,
            min_results=1,
            filter_label=f"structure {case_domain}/{case_solver}",
        )
    except ValueError:
        faiss_structure_all = []
    print(f"Retrieved {len(faiss_structure_all)} same-solver candidates from FAISS.")

    # Hard constraints: domain and solver must match. The retrieve_faiss metadata
    # filter already enforces this, and this second check keeps the invariant local.
    domain_matched = [
        c for c in faiss_structure_all
        if c.get("case_domain") == case_domain and c.get("case_solver") == case_solver
    ]
    _log_top3("Same-solver structure candidates", domain_matched)

    if not domain_matched:
        print(f"No suitable similar case found under domain={case_domain}, solver={case_solver}. No cross-solver fallback used.")
        advice = _build_advice(user_requirement, case_info, None, faiss_structure_all)
        return "", "", "", "", advice

    # Semantic rank among same-solver candidates only.
    ranked = _rerank_candidates(domain_matched, case_solver)
    selected = ranked[0]

    # Fetch full tutorial details for the selected structure candidate. The structure
    # index contains directory metadata; input generation needs the actual file
    # contents from openfoam_tutorials_details.
    faiss_detailed = _fetch_matching_detail_reference(selected, searchdocs, case_target)
    faiss_detailed = re.sub(r"\n{3}", "\n", faiss_detailed)

    m = re.search(r"<directory_structure>(.*?)</directory_structure>", faiss_detailed, re.DOTALL)
    if not m:
        print("Warning: No directory_structure found in selected similar case details.")
        advice = _build_advice(user_requirement, case_info, selected, ranked)
        return "", "", "", "", advice
    dir_structure = m.group(1).strip()
    dir_counts = parse_directory_structure(dir_structure)
    dir_counts_str = ',\n'.join([f"There are {count} files in Directory: {directory}" for directory, count in dir_counts.items()])

    # Build allrun reference
    index_content = f"<index>\ncase name: {selected.get('case_name')}\ncase solver: {selected.get('case_solver')}\n</index>\n<directory_structure>\n{dir_structure}\n</directory_structure>"
    try:
        faiss_allrun = retrieve_faiss(
            "openfoam_allrun_scripts",
            index_content,
            case_target,
            topk=searchdocs,
            metadata_filter={"case_solver": selected.get("case_solver")},
            min_results=1,
            filter_label=f"allrun solver {selected.get('case_solver')}",
        )
    except ValueError:
        faiss_allrun = []
    allrun_reference = "Similar cases are ordered, with smaller numbers indicating greater similarity. For example, similar_case_1 is more similar than similar_case_2, and similar_case_2 is more similar than similar_case_3.\n"
    for idx, item in enumerate(faiss_allrun):
        allrun_reference += f"<similar_case_{idx + 1}>{item['full_content']}</similar_case_{idx + 1}>\n\n\n"

    advice = _build_advice(user_requirement, case_info, selected, ranked)
    return faiss_detailed, dir_structure, dir_counts_str, allrun_reference, advice


def decompose_to_subtasks(user_requirement: str, dir_structure: str, dir_counts_str: str) -> List[Dict]:
    decompose_system_prompt = (
        "You are an experienced Planner specializing in OpenFOAM projects. "
        "Your task is to break down the following user requirement into a series of smaller, manageable subtasks. "
        "For each subtask, identify the file name of the OpenFOAM input file (foamfile) and the corresponding folder name where it should be stored. "
        "Your final output must strictly follow the JSON schema below and include no additional keys or information:\n\n"
        "```\n{\n  \"subtasks\": [\n    {\n      \"file_name\": \"<string>\",\n      \"folder_name\": \"<string>\"\n    }\n    // ... more subtasks\n  ]\n}\n```\n\n"
        "Make sure that your output is valid JSON and strictly adheres to the provided schema."
        "Make sure you generate all the necessary files for the user's requirements."
    )

    decompose_user_prompt = (
        f"User Requirement: {user_requirement}\n\n"
        f"Reference Directory Structure (similar case): {dir_structure}\n\n{dir_counts_str}\n\n"
        "Make sure you generate all the necessary files for the user's requirements."
        "Do not include any gmsh files like .geo etc. in the subtasks."
        "Only include blockMesh or snappyHexMesh if the user hasnt requested for gmsh mesh or user isnt using an external uploaded custom mesh"
        "Please generate the output as structured JSON."
    )

    res = global_llm_service.invoke(decompose_user_prompt, decompose_system_prompt, pydantic_obj=OpenFOAMPlanModel)
    return [{"file_name": s.file_name, "folder_name": s.folder_name} for s in res.subtasks]


def generate_simulation_plan(
    user_requirement: str,
    case_stats: Dict[str, List[str]],
    case_dir: str = "",
    searchdocs: int = 2
) -> Dict[str, Any]:
    """
    Generate a complete simulation plan by parsing requirements and creating subtasks.

    This function orchestrates the entire planning process:
    1. Parse user requirements into structured case information
    2. Resolve case directory
    3. Retrieve similar case references from FAISS database
    4. Decompose requirements into manageable subtasks

    Args:
        user_requirement (str): Natural language description of simulation requirements
        case_stats (Dict[str, List[str]]): Available case statistics
        case_dir (str, optional): Custom case directory path
        searchdocs (int, optional): Number of similar documents to retrieve

    Returns:
        Dict[str, Any]: Complete plan containing:
            - case_name, case_domain, case_category, case_solver
            - case_dir: Resolved case directory
            - tutorial_reference: FAISS detailed reference
            - case_path_reference: Path to reference file
            - dir_structure_reference: Directory structure
            - allrun_reference: Allrun script references
            - subtasks: List of subtasks with file and folder names

    Raises:
        ValueError: If subtasks cannot be generated
        RuntimeError: If any step in the planning process fails
    """
    # Step 1: Compile physics before allowing an LLM-selected solver.
    compiled_workflow = compile_workflow(user_requirement)
    workflow_plan = compiled_workflow.plan
    if workflow_plan.rejection_reason:
        raise ValueError(workflow_plan.rejection_reason)
    if not workflow_plan.ready or workflow_plan.target is None:
        raise ValueError(
            "WORKFLOW_CLARIFICATION_REQUIRED: "
            + " ".join(workflow_plan.clarification_questions)
        )

    case_target = workflow_plan.target
    benchmark_match = find_certified_benchmark(user_requirement, case_target)
    tutorial_template_match = (
        None
        if benchmark_match
        else find_rheotool_tutorial_template(
            user_requirement,
            case_target,
            compiled_workflow=compiled_workflow,
            minimum_tier="A",
        )
    )
    if benchmark_match is None and tutorial_template_match is None:
        tutorial_template_match = find_foundation_tutorial_template(
            user_requirement,
            case_target,
            compiled_workflow=compiled_workflow,
        )
    tutorial_template_candidate = (
        None
        if benchmark_match or tutorial_template_match
        else find_rheotool_tutorial_template(
            user_requirement,
            case_target,
            compiled_workflow=compiled_workflow,
            minimum_tier="B",
        )
    )
    if tutorial_template_candidate and _has_tutorial_reproduction_intent(user_requirement):
        missing_reason = ", ".join(tutorial_template_candidate.get("match_reasons") or ())
        raise ValueError(
            "WORKFLOW_CLARIFICATION_REQUIRED: "
            "RheoTool tutorial template candidate found, but confidence is B-tier so it will not be "
            "silently replaced by LLM-generated dictionaries. "
            f"candidate={tutorial_template_candidate['id']} "
            f"tier={tutorial_template_candidate.get('tier')} "
            f"reasons={missing_reason}. "
            "Please confirm importing this tutorial template, or provide the missing signature parameters."
        )
    if benchmark_match:
        case_name = benchmark_match["id"]
        physics = benchmark_match.get("physics") or {}
        case_domain = physics.get("case_domain", "rheology")
        case_category = physics.get("case_category", "benchmark")
        original_solver = "certified_benchmark"
    elif tutorial_template_match:
        case_name = tutorial_template_match["case_name"]
        case_domain = tutorial_template_match["case_domain"]
        case_category = tutorial_template_match["case_category"]
        original_solver = (
            "foundation_tutorial_template"
            if tutorial_template_match.get("template_kind") == "foundation"
            else "rheotool_tutorial_template"
        )
    else:
        # Parse naming/category metadata only; the compiler owns CaseTarget.
        case_stats = ensure_rheotool_solvers_in_case_stats(case_stats)
        case_info = parse_requirement_to_case_info(user_requirement, case_stats)
        case_name = case_info["case_name"]
        case_domain = case_info["case_domain"]
        case_category = case_info["case_category"]
        original_solver = case_info["case_solver"]

    case_solver = case_target.solver
    channel = case_target.channel
    print(
        f"<workflow_compiler solver=\"{case_solver}\" channel=\"{channel}\">"
        f"workflow={workflow_plan.workflow_type}; original_solver={original_solver}"
        "</workflow_compiler>"
    )

    if benchmark_match:
        print(
            f"<certified_benchmark_match id=\"{benchmark_match['id']}\" "
            f"case_set=\"{benchmark_match['case_set']}\" "
            f"alias=\"{benchmark_match['matched_alias']}\"/>"
        )
    if tutorial_template_match:
        template_label = (
            "foundation_tutorial_template_match"
            if tutorial_template_match.get("template_kind") == "foundation"
            else "rheotool_tutorial_template_match"
        )
        print(
            f'<{template_label} id="{tutorial_template_match["id"]}" '
            f'solver="{tutorial_template_match.get("solver")}" '
            f'name="{tutorial_template_match.get("template_name")}" '
            f'tier="{tutorial_template_match.get("tier")}" '
            f'alias="{tutorial_template_match["matched_alias"]}"/>'
        )
    elif tutorial_template_candidate:
        print(
            f"<rheotool_tutorial_template_candidate id=\"{tutorial_template_candidate['id']}\" "
            f"tier=\"{tutorial_template_candidate.get('tier')}\" "
            f"policy=\"not_imported_low_confidence\"/>"
        )

    # Step 2: Resolve case directory
    resolved_case_dir = resolve_case_dir(
        case_name=case_name,
        case_dir=case_dir,
        run_times=1,
        run_directory=str(Path(__file__).resolve().parent.parent / "runs")
    )

    if benchmark_match:
        faiss_detailed = ""
        dir_structure = ""
        allrun_reference = ""
        advice = SimilarCaseAdviceModel(
            match_level="high",
            use_scope="certified benchmark import",
            advice=(
                f"Import certified benchmark {benchmark_match['id']} "
                f"from {benchmark_match['case_set']} instead of regenerating dictionaries."
            ),
        )
        subtasks = benchmark_subtasks(benchmark_match)
    elif tutorial_template_match:
        faiss_detailed = ""
        dir_structure = ""
        allrun_reference = ""
        template_scope = (
            "foundation tutorial template import"
            if tutorial_template_match.get("template_kind") == "foundation"
            else "rheotool tutorial template import"
        )
        advice = SimilarCaseAdviceModel(
            match_level="high",
            use_scope=template_scope,
            advice=(
                f"Import tutorial template {tutorial_template_match['id']} "
                "instead of regenerating dictionaries."
            ),
        )
        if tutorial_template_match.get("template_kind") == "foundation":
            subtasks = foundation_template_subtasks(tutorial_template_match)
        else:
            subtasks = tutorial_template_subtasks(tutorial_template_match)
    else:
        # Step 3: Retrieve references
        faiss_detailed, dir_structure, dir_counts_str, allrun_reference, advice = retrieve_references(
            case_name=case_name,
            case_solver=case_solver,
            case_domain=case_domain,
            case_category=case_category,
            searchdocs=searchdocs,
            user_requirement=user_requirement,
            metadata_constraints={
                "phase_type": compiled_workflow.physics.phase_type,
                "constitutive_family": compiled_workflow.rheology.behavior,
            },
        )

        # Step 4: Decompose to subtasks
        subtasks = decompose_to_subtasks(user_requirement, dir_structure, dir_counts_str)

    if len(subtasks) == 0:
        raise ValueError("Failed to generate subtasks.")

    # Prepare reference file path
    case_path_reference = os.path.join(resolved_case_dir, "similar_case.txt")

    return {
        "case_name": case_name,
        "case_domain": case_domain,
        "case_category": case_category,
        "case_solver": case_solver,
        "case_target": case_target,
        "channel": channel,
        "version": case_target.version,
        "distribution": case_target.distribution,
        "case_dir": resolved_case_dir,
        "tutorial_reference": faiss_detailed,
        "case_path_reference": case_path_reference,
        "dir_structure_reference": dir_structure,
        "allrun_reference": allrun_reference,
        "subtasks": subtasks,
        "similar_case_advice": advice,
        "solver_route": {
            "solver": case_solver,
            "confidence": 1.0,
            "reason": f"certified workflow: {workflow_plan.workflow_type}",
            "domain": case_domain,
            "category": case_category,
        },
        "benchmark_match": benchmark_match,
        "tutorial_template_match": tutorial_template_match,
        "tutorial_template_candidate": tutorial_template_candidate,
        "problem_intent": compiled_workflow.intent,
        "physics_spec": compiled_workflow.physics,
        "rheology_spec": compiled_workflow.rheology,
        "workflow_plan": workflow_plan,
    }
