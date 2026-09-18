from pathlib import Path
import sys

from langgraph.graph import END


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from router_func import route_after_runner  # noqa: E402


def test_route_after_runner_stops_on_dynamic_code_root_blocker():
    state = {
        "error_logs": [
            {
                "file": "log.rheoFoam",
                "error_content": "This code should not be executed by someone with administrator rights",
            }
        ]
    }

    route = route_after_runner(state)

    assert route == END
    assert state["termination_reason"] == "openfoam_environment_blocked"


def test_route_after_runner_stops_on_foamagent_environment_blocker():
    state = {
        "error_logs": [
            {
                "file": "Allrun.err",
                "error_content": "FOAM FATAL ERROR: Foam-Agent OpenFOAM execution environment blocked",
            }
        ]
    }

    route = route_after_runner(state)

    assert route == END
    assert state["termination_reason"] == "openfoam_environment_blocked"


def test_route_after_runner_accepts_string_error_logs():
    state = {
        "error_logs": [
            "Schema preflight validation failed before running Allrun: CUSTOM_PATCH_FIELD_UNSUPPORTED",
        ]
    }

    route = route_after_runner(state)

    assert route == "reviewer"
