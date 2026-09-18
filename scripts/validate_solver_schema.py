#!/usr/bin/env python
from pathlib import Path
import importlib.util
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "services" / "solver_schema_validator.py"
MODULE_NAME = "solver_schema_validator_cli"
spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[MODULE_NAME] = module
spec.loader.exec_module(module)


if __name__ == "__main__":
    raise SystemExit(module.main())
