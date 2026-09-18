from dataclasses import asdict, dataclass, field
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


RHEOTOOL_SOLVERS = frozenset({
    "rheoFoam", "rheoTestFoam", "rheoInterFoam", "rheoEFoam",
    "rheoHeatFoam", "rheoFilmFoam", "rheoBDFoam", "rheoMultiRegionFoam",
})
CERTIFIED_SOLVERS = frozenset({
    "rheoFoam", "rheoTestFoam", "rheoInterFoam",
    "icoFoam", "simpleFoam", "pimpleFoam", "interFoam",
    "pisoFoam", "potentialFoam", "scalarTransportFoam",
    "rhoCentralFoam", "rhoPimpleFoam", "buoyantFoam",
})


@dataclass(frozen=True)
class CaseTarget:
    channel: Literal["v9-rheotool", "v10-foundation"]
    version: Literal["v9", "v10"]
    solver: str
    distribution: Literal["foundation+rheotool", "foundation"]

    @classmethod
    def for_solver(cls, solver: str) -> "CaseTarget":
        solver = str(solver or "").strip()
        if not solver:
            raise ValueError("CaseTarget requires a solver")
        if solver not in CERTIFIED_SOLVERS:
            raise ValueError(f"Solver is not in the certified capability matrix: {solver}")
        if solver in RHEOTOOL_SOLVERS:
            return cls("v9-rheotool", "v9", solver, "foundation+rheotool")
        return cls("v10-foundation", "v10", solver, "foundation")

    def as_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ProblemIntent:
    application: str
    phases: tuple[str, ...]
    objectives: tuple[str, ...]
    rheology_evidence: tuple[str, ...]
    newtonian_evidence: tuple[str, ...]
    steady_or_transient: Optional[str]
    free_surface: Optional[bool]
    known_parameters: Dict[str, float]
    missing_critical_fields: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    geometry_class: Optional[str] = None
    dimensionless_groups: Dict[str, float] = field(default_factory=dict)
    reproduction_target: Optional[str] = None


@dataclass(frozen=True)
class PhysicsSpec:
    phase_type: Literal["single-phase", "two-phase"]
    incompressible: bool
    transient: Optional[bool]
    free_surface: bool
    objectives: tuple[str, ...]


@dataclass(frozen=True)
class RheologySpec:
    behavior: Literal["newtonian", "generalized-newtonian", "viscoelastic", "unknown"]
    selected_model: Optional[str]
    parameters: Dict[str, float]
    missing_parameters: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowPlan:
    workflow_type: str
    stages: tuple[str, ...]
    required_inputs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    target: Optional[CaseTarget]
    ready: bool
    clarification_questions: tuple[str, ...] = ()
    rejection_reason: Optional[str] = None


class CreateCaseIn(BaseModel):
    user_prompt: str
    output_dir: Optional[str] = None


class CreateCaseOut(BaseModel):
    case_id: str
    case_dir: str


# NOTE: These models are deprecated and replaced by FastMCP server models in src/mcp/fastmcp_server.py
# Use PlanRequest/PlanResponse and GenerateFilesRequest/GenerateFilesResponse instead
class PlanIn(BaseModel):
    """Deprecated: Use PlanRequest in fastmcp_server.py instead."""
    case_id: str  # Deprecated: case_id is no longer required, use user_requirement only


class Subtask(BaseModel):
    file: str
    folder: str


class PlanOut(BaseModel):
    """Deprecated: Use PlanResponse in fastmcp_server.py instead."""
    plan: List[Subtask]
    case_info: Dict  # Deprecated: case_info is now expanded to case_name, case_solver, case_domain, case_category


class GenerateFileIn(BaseModel):
    """Deprecated: Use GenerateFilesRequest in fastmcp_server.py instead."""
    case_id: str  # Deprecated: use case_name instead
    file: str
    folder: str
    write: bool = True
    overwrite: bool = True


class GenerateFileOut(BaseModel):
    content: str
    written_path: Optional[str] = None


class MeshIn(BaseModel):
    case_id: str
    mesh_config: Dict


class MeshOut(BaseModel):
    job_id: Optional[str] = None
    status: str


class HPCScriptIn(BaseModel):
    case_id: str
    hpc_config: Dict


class HPCScriptOut(BaseModel):
    script_content: str
    script_path: str


class RunIn(BaseModel):
    case_id: str
    environment: str  # "local" | "hpc"
    extra: Optional[Dict] = None


class RunOut(BaseModel):
    job_id: Optional[str]
    status: str  # "submitted" | "completed" | "failed"


class JobStatusIn(BaseModel):
    job_id: str


class JobStatusOut(BaseModel):
    status: str
    details: Optional[Dict] = None


class LogsIn(BaseModel):
    case_id: str
    job_id: Optional[str] = None


class LogsOut(BaseModel):
    logs: Dict[str, str]


class ApplyFixIn(BaseModel):
    case_id: str
    foamfiles: Optional[Any] = None  # FoamPydantic object
    error_logs: List[str] = []
    review_analysis: str = ""
    user_requirement: str = ""
    dir_structure: Optional[Dict] = None


class ApplyFixOut(BaseModel):
    status: str
    written: List[str]
    updated_dir_structure: Optional[Dict] = None
    updated_foamfiles: Optional[Any] = None  # FoamPydantic object
    cleared_error_logs: List[str] = []


class VisualizationIn(BaseModel):
    case_id: str
    quantity: str
    extra: Optional[Dict] = None


class VisualizationOut(BaseModel):
    job_id: Optional[str]
    artifacts: List[str]
