from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml


RHEOTOOL_CUSTOM_BC_LIBS = {
    "navierSlip": "libBCRheoTool.so",
    "uLid": "libRheoToolTutorialBCs.so",
    "uCos": "libRheoToolTutorialBCs.so",
    "HBprofile": "libRheoToolTutorialBCs.so",
    "uShaft": "libRheoToolTutorialBCs.so",
    "ACPotential": "libRheoToolTutorialBCs.so",
    "linearExtrapolation": "libBCRheoTool.so",
}

STANDARD_PATCH_FIELD_TYPES = {
    "calculated",
    "codedFixedValue",
    "compressible::alphatJayatillekeWallFunction",
    "cyclic",
    "empty",
    "epsilonWallFunction",
    "fWallFunction",
    "fixedFluxPressure",
    "fixedGradient",
    "fixedMean",
    "fixedNormalSlip",
    "fixedValue",
    "flowRateInletVelocity",
    "freestream",
    "freestreamPressure",
    "freestreamVelocity",
    "inletOutlet",
    "kqRWallFunction",
    "mapped",
    "movingWallVelocity",
    "noSlip",
    "nutkWallFunction",
    "nutkRoughWallFunction",
    "nutUSpaldingWallFunction",
    "omegaWallFunction",
    "outletPhaseMeanVelocity",
    "outletInlet",
    "partialSlip",
    "prghTotalPressure",
    "pressureInletOutletVelocity",
    "processor",
    "slip",
    "symmetry",
    "symmetryPlane",
    "timeVaryingMappedFixedValue",
    "turbulentInlet",
    "uniformFixedValue",
    "v2WallFunction",
    "waveTransmissive",
    "waveAlpha",
    "waveVelocity",
    "wedge",
    "zeroGradient",
    "constantAlphaContactAngle",
}


@dataclass
class ValidationIssue:
    level: str
    code: str
    message: str
    path: Optional[str] = None

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "path": self.path,
        }


@dataclass
class ValidationResult:
    solver: str
    case_dir: str
    schema_path: str
    issues: List[ValidationIssue] = field(default_factory=list)
    detected_models: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    def add(self, level: str, code: str, message: str, path: Optional[str] = None) -> None:
        self.issues.append(ValidationIssue(level=level, code=code, message=message, path=path))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "solver": self.solver,
            "case_dir": self.case_dir,
            "schema_path": self.schema_path,
            "detected_models": self.detected_models,
            "issues": [issue.as_dict() for issue in self.issues],
        }


class SolverSchemaValidator:
    """Validate an OpenFOAM/rheoTool case against a solver schema YAML."""

    def __init__(self, schema_path: Path | str):
        self.schema_path = Path(schema_path)
        with self.schema_path.open("r", encoding="utf-8") as f:
            self.schema: Dict[str, Any] = yaml.safe_load(f) or {}
        self.solver = str(self.schema.get("solver") or self.schema_path.stem)

    def validate(self, case_dir: Path | str) -> ValidationResult:
        case_path = Path(case_dir)
        result = ValidationResult(
            solver=self.solver,
            case_dir=str(case_path),
            schema_path=str(self.schema_path),
        )

        if not case_path.exists():
            result.add("error", "CASE_DIR_MISSING", "Case directory does not exist.", str(case_path))
            return result

        self._check_required_files(case_path, result)
        self._check_required_any_files(case_path, result)
        self._check_forbidden_files(case_path, result)
        self._check_required_content(case_path, result)
        self._check_mesh_constraints(case_path, result)
        result.detected_models = self._detect_models(case_path)
        self._check_conditional_rules(case_path, result, result.detected_models)
        self._check_unsupported_custom_patch_fields(case_path, result)
        self._check_rheotool_custom_bc_libraries(case_path, result)
        return result

    def _exists(self, case_path: Path, rel_path: str) -> bool:
        return (case_path / rel_path).exists()

    def _read_text(self, case_path: Path, rel_path: str) -> str:
        path = case_path / rel_path
        if not path.exists() or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")

    def _check_required_files(self, case_path: Path, result: ValidationResult) -> None:
        for rel_path in self.schema.get("required_files", []) or []:
            if not self._exists(case_path, rel_path):
                result.add("error", "REQUIRED_FILE_MISSING", f"Missing required file: {rel_path}", rel_path)

    def _check_required_any_files(self, case_path: Path, result: ValidationResult) -> None:
        for group in self.schema.get("required_any_files", []) or []:
            files = group.get("files", []) if isinstance(group, dict) else []
            if files and not any(self._exists(case_path, rel_path) for rel_path in files):
                result.add(
                    "error",
                    "REQUIRED_ANY_FILE_MISSING",
                    f"Missing one of required alternative files: {', '.join(files)}",
                    group.get("name") if isinstance(group, dict) else None,
                )

    def _check_forbidden_files(self, case_path: Path, result: ValidationResult) -> None:
        for rel_path in self.schema.get("forbidden_files", []) or []:
            if self._exists(case_path, rel_path):
                result.add("error", "FORBIDDEN_FILE_PRESENT", f"Forbidden file is present: {rel_path}", rel_path)

    def _check_required_content(self, case_path: Path, result: ValidationResult) -> None:
        for rule in self.schema.get("required_content", []) or []:
            rel_path = rule.get("file")
            if not rel_path:
                continue
            text = self._read_text(case_path, rel_path)
            if not text:
                result.add("error", "REQUIRED_CONTENT_FILE_MISSING", f"Cannot inspect missing file: {rel_path}", rel_path)
                continue

            for token in rule.get("must_contain", []) or []:
                if token not in text:
                    result.add("error", "REQUIRED_CONTENT_MISSING", f"File must contain token: {token}", rel_path)

            any_tokens = rule.get("must_contain_any", []) or []
            if any_tokens and not any(token in text for token in any_tokens):
                result.add(
                    "error",
                    "REQUIRED_CONTENT_ANY_MISSING",
                    f"File must contain at least one token: {', '.join(any_tokens)}",
                    rel_path,
                )

    def _check_mesh_constraints(self, case_path: Path, result: ValidationResult) -> None:
        constraints = self.schema.get("mesh_constraints") or {}
        expected_cells = constraints.get("expected_cells")
        if not expected_cells:
            return

        block_mesh = self._read_text(case_path, "system/blockMeshDict")
        if not block_mesh:
            result.add("error", "MESH_BLOCKMESHDICT_MISSING", "Cannot verify mesh constraints without blockMeshDict.", "system/blockMeshDict")
            return

        cells = self._extract_first_block_cells(block_mesh)
        if cells is None:
            result.add("warning", "MESH_CELLS_UNPARSED", "Could not parse cell counts from first hex block.", "system/blockMeshDict")
            return

        if list(cells) != list(expected_cells):
            result.add(
                "error",
                "MESH_CELLS_MISMATCH",
                f"Expected cells {expected_cells}, found {list(cells)}.",
                "system/blockMeshDict",
            )

    def _extract_first_block_cells(self, block_mesh: str) -> Optional[List[int]]:
        match = re.search(r"hex\s*\([^)]*\)\s*\(\s*(\d+)\s+(\d+)\s+(\d+)\s*\)", block_mesh)
        if not match:
            return None
        return [int(match.group(1)), int(match.group(2)), int(match.group(3))]

    def _detect_models(self, case_path: Path) -> List[str]:
        text = self._read_text(case_path, "constant/constitutiveProperties")
        models: List[str] = []
        for pattern in (
            r"\btype\s+([A-Za-z0-9_.+-]+)\s*;",
            r"\bconstitutiveModel\s+([A-Za-z0-9_.+-]+)\s*;",
        ):
            models.extend(re.findall(pattern, text))
        return sorted(set(model.strip() for model in models if model.strip()))

    def _model_family(self, models: Iterable[str]) -> str:
        gnf = set(self.schema.get("models", {}).get("gnf", []) or [])
        viscoelastic = set(self.schema.get("models", {}).get("viscoelastic", []) or [])
        model_set = set(models)
        if model_set and model_set.issubset(gnf):
            return "GNF"
        if model_set and model_set.intersection(viscoelastic):
            return "viscoelastic"
        return "unknown"

    def _check_conditional_rules(self, case_path: Path, result: ValidationResult, models: List[str]) -> None:
        family = self._model_family(models)
        has_log_model = any(model.endswith("Log") for model in models)

        for rule in self.schema.get("conditional_rules", []) or []:
            name = rule.get("name", "")
            condition = str(rule.get("if", ""))
            active = False

            if ".*Log$" in condition:
                active = has_log_model
            elif "model_family == GNF" in condition:
                active = family == "GNF"
            elif "model_family == viscoelastic" in condition:
                active = family == "viscoelastic"
            elif "0/alpha.water.org exists" in condition:
                active = self._exists(case_path, "0/alpha.water.org")

            if not active:
                continue

            for rel_path in rule.get("require", []) or []:
                if not self._exists(case_path, rel_path):
                    result.add("error", "CONDITIONAL_FILE_MISSING", f"Rule {name} requires file: {rel_path}", rel_path)

            for rel_path in rule.get("prefer", []) or []:
                if not self._exists(case_path, rel_path):
                    result.add("warning", "PREFERRED_FILE_MISSING", f"Rule {name} prefers file: {rel_path}", rel_path)

            for rel_path in rule.get("forbid", []) or []:
                if self._exists(case_path, rel_path):
                    result.add("error", "CONDITIONAL_FORBIDDEN_FILE_PRESENT", f"Rule {name} forbids file: {rel_path}", rel_path)

            for pattern in rule.get("require_pattern", []) or []:
                if not list(case_path.glob(pattern)):
                    result.add("error", "CONDITIONAL_PATTERN_MISSING", f"Rule {name} requires a path matching: {pattern}", pattern)

            sequence = rule.get("require_allrun_sequence", []) or []
            if sequence:
                self._check_allrun_sequence(case_path, result, name, sequence)

    def _check_allrun_sequence(self, case_path: Path, result: ValidationResult, rule_name: str, sequence: List[str]) -> None:
        text = self._read_text(case_path, "Allrun")
        if not text:
            result.add("error", "ALLRUN_MISSING", f"Rule {rule_name} requires Allrun sequence.", "Allrun")
            return

        cursor = -1
        for token in sequence:
            aliases = [token]
            if token == self.solver:
                aliases.extend(["$application", "runApplication $application"])

            found = [(text.find(alias, cursor + 1), alias) for alias in aliases]
            found = [(idx, alias) for idx, alias in found if idx != -1]
            if not found:
                result.add("error", "ALLRUN_SEQUENCE_MISSING", f"Rule {rule_name} requires sequence token: {token}", "Allrun")
                return
            cursor, _ = min(found, key=lambda item: item[0])

    def _field_patch_types(self, case_path: Path) -> dict[str, set[str]]:
        patch_types: dict[str, set[str]] = {}
        zero_dir = case_path / "0"
        if not zero_dir.is_dir():
            return patch_types
        for path in zero_dir.glob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            types = set(re.findall(r"\btype\s+([A-Za-z_][A-Za-z0-9_:]*)\s*;", text))
            if types:
                patch_types[str(path.relative_to(case_path))] = types
        return patch_types

    def _loaded_library_names(self, case_path: Path) -> set[str]:
        control_dict = self._read_text(case_path, "system/controlDict")
        libs: set[str] = set()
        for block in re.findall(r"(?s)\blibs\s*\((.*?)\)\s*;", control_dict):
            libs.update(re.findall(r'"([^"]+\.so)"', block))
            libs.update(re.findall(r"(?m)^\s*([A-Za-z0-9_./+-]+\.so)\s*$", block))
        return libs

    def _patch_type_registered_in_loaded_libraries(self, case_path: Path, patch_type: str) -> bool:
        for lib_name in self._loaded_library_names(case_path):
            if self._runtime_library_registers_bc(self._runtime_library_candidates(lib_name), patch_type):
                return True
        return False

    def _check_unsupported_custom_patch_fields(self, case_path: Path, result: ValidationResult) -> None:
        allowed = STANDARD_PATCH_FIELD_TYPES | set(RHEOTOOL_CUSTOM_BC_LIBS)
        for rel_path, patch_types in sorted(self._field_patch_types(case_path).items()):
            for patch_type in sorted(patch_types):
                if patch_type in allowed:
                    continue
                if self._patch_type_registered_in_loaded_libraries(case_path, patch_type):
                    continue
                result.add(
                    "error",
                    "CUSTOM_PATCH_FIELD_UNSUPPORTED",
                    (
                        f"Detected unknown boundary condition type {patch_type}. "
                        "The current product does not support automatic compilation or onboarding of new customer C++ patchField types. "
                        "Provide a precompiled registered library through the maintained runtime image, or use a supported standard/built-in boundary condition."
                    ),
                    rel_path,
                )

    def _check_rheotool_custom_bc_libraries(self, case_path: Path, result: ValidationResult) -> None:
        required: dict[str, set[str]] = {}
        for patch_types in self._field_patch_types(case_path).values():
            for bc_type, lib_name in RHEOTOOL_CUSTOM_BC_LIBS.items():
                if bc_type in patch_types:
                    required.setdefault(lib_name, set()).add(bc_type)

        if not required:
            return

        control_dict = self._read_text(case_path, "system/controlDict")
        for lib_name, bc_types in sorted(required.items()):
            bc_list = ", ".join(sorted(bc_types))
            if lib_name not in control_dict:
                result.add(
                    "error",
                    "RHEOTOOL_CUSTOM_BC_LIBRARY_NOT_LOADED",
                    f"Custom boundary condition(s) {bc_list} require {lib_name} in system/controlDict libs.",
                    "system/controlDict",
                )
            lib_paths = self._runtime_library_candidates(lib_name)
            if not lib_paths:
                result.add(
                    "error",
                    "RHEOTOOL_CUSTOM_BC_LIBRARY_MISSING",
                    f"Custom boundary condition(s) {bc_list} require runtime library {lib_name}.",
                    lib_name,
                )
                continue
            for bc_type in sorted(bc_types):
                if not self._runtime_library_registers_bc(lib_paths, bc_type):
                    result.add(
                        "error",
                        "RHEOTOOL_CUSTOM_BC_NOT_REGISTERED",
                        f"Custom boundary condition {bc_type} is used by the case, but {lib_name} does not register it in the current runtime.",
                        lib_name,
                    )

    def _runtime_library_candidates(self, lib_name: str) -> list[Path]:
        candidates: list[Path] = []
        for env_name in ("FOAM_USER_LIBBIN", "FOAM_SITE_LIBBIN", "FOAM_LIBBIN"):
            value = os.environ.get(env_name)
            if value:
                candidates.append(Path(value) / lib_name)
        for item in os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep):
            if item:
                candidates.append(Path(item) / lib_name)
        candidates.extend(
            Path(path) / lib_name
            for path in (
                "/home/openfoam/platforms/linux64GccDPInt32Opt/lib",
                "/opt/openfoam9/platforms/linux64GccDPInt32Opt/lib",
            )
        )
        return [path for path in candidates if path.is_file()]

    def _runtime_library_exists(self, lib_name: str) -> bool:
        return bool(self._runtime_library_candidates(lib_name))

    def _runtime_library_registers_bc(self, lib_paths: Iterable[Path], bc_type: str) -> bool:
        token = bc_type.encode("utf-8")
        for path in lib_paths:
            try:
                if token in path.read_bytes():
                    return True
            except OSError:
                continue
        return False


SCHEMA_ROOT = Path(__file__).resolve().parent / "solver_schemas"


def normalize_solver_name(case_solver: object) -> str:
    if case_solver is None:
        return ""
    if isinstance(case_solver, (list, tuple, set)):
        return str(next(iter(case_solver), "")).strip()
    return str(case_solver).strip()


def resolve_solver_schema_path(
    version: str,
    case_solver: object,
    schema_dir: Path | str | None = None,
) -> Optional[Path]:
    version = str(version or "").strip()
    if version not in {"v9", "v10"}:
        raise ValueError(f"Unsupported OpenFOAM schema version: {version or '<empty>'}")
    solver = normalize_solver_name(case_solver)
    if not solver:
        return None

    root = Path(schema_dir) if schema_dir else SCHEMA_ROOT
    schema_path = root / version / f"{solver}.yaml"
    return schema_path if schema_path.exists() else None


def preflight_validate_case(
    case_dir: Path | str,
    version: str,
    case_solver: object,
    schema_dir: Path | str | None = None,
) -> Optional[ValidationResult]:
    schema_path = resolve_solver_schema_path(version, case_solver, schema_dir=schema_dir)
    if schema_path is None:
        return None
    return validate_case(case_dir, schema_path)


def validate_case(case_dir: Path | str, schema_path: Path | str) -> ValidationResult:
    return SolverSchemaValidator(schema_path).validate(case_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an OpenFOAM/rheoTool case against a solver schema YAML.")
    parser.add_argument("--case-dir", required=True, help="Path to the generated case directory.")
    parser.add_argument("--schema", required=True, help="Path to solver schema YAML.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    result = validate_case(args.case_dir, args.schema)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    else:
        status = "PASS" if result.ok else "FAIL"
        print(f"{status}: {result.solver} schema validation for {result.case_dir}")
        if result.detected_models:
            print(f"Detected models: {', '.join(result.detected_models)}")
        for issue in result.issues:
            path = f" [{issue.path}]" if issue.path else ""
            print(f"- {issue.level.upper()} {issue.code}{path}: {issue.message}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
