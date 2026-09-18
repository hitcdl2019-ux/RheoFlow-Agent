from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from models import CaseTarget  # noqa: E402
import utils  # noqa: E402
from utils import openfoam_command_args  # noqa: E402


def test_case_target_is_frozen_and_routes_rheotool():
    target = CaseTarget.for_solver("rheoFoam")

    assert target.as_dict() == {
        "channel": "v9-rheotool",
        "version": "v9",
        "solver": "rheoFoam",
        "distribution": "foundation+rheotool",
    }
    with pytest.raises(Exception):
        target.channel = "v10-foundation"


def test_case_target_routes_foundation_solver():
    target = CaseTarget.for_solver("icoFoam")

    assert target.channel == "v10-foundation"
    assert target.version == "v10"


def test_openfoam_command_uses_explicit_channel_runner():
    args = openfoam_command_args("v10-foundation", "checkMesh", "-case", "/tmp/case")

    assert args[0].endswith("scripts/run_openfoam_channel.sh")
    assert args[1:] == ["v10-foundation", "checkMesh", "-case", "/tmp/case"]


def test_openfoam_command_rejects_unknown_channel():
    with pytest.raises(ValueError):
        openfoam_command_args("", "blockMesh")


def test_openfoam_execution_drops_root_privileges(monkeypatch, tmp_path):
    monkeypatch.setattr(utils.os, "geteuid", lambda: 0)
    monkeypatch.setattr(utils, "_configured_openfoam_run_user", lambda: "openfoam")
    monkeypatch.setattr(utils, "_chown_case_tree", lambda case_dir, user: None)
    monkeypatch.setattr(utils.shutil, "which", lambda name: "/usr/sbin/runuser" if name == "runuser" else None)

    args = utils.openfoam_execution_args("v9-rheotool", str(tmp_path), "bash", "Allrun")

    assert args[:4] == ["/usr/sbin/runuser", "-u", "openfoam", "--"]
    assert args[4].endswith("scripts/run_openfoam_channel.sh")
    assert args[5:] == ["v9-rheotool", "bash", "Allrun"]


def test_openfoam_execution_can_be_left_as_current_user(monkeypatch, tmp_path):
    monkeypatch.setattr(utils.os, "geteuid", lambda: 1000)

    args = utils.openfoam_execution_args("v9-rheotool", str(tmp_path), "bash", "Allrun")

    assert args[0].endswith("scripts/run_openfoam_channel.sh")
    assert args[1:] == ["v9-rheotool", "bash", "Allrun"]


def test_run_command_reports_nonroot_environment_blocker(monkeypatch, tmp_path):
    script = tmp_path / "Allrun"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    out_file = tmp_path / "Allrun.out"
    err_file = tmp_path / "Allrun.err"

    def fail_execution_args(*args, **kwargs):
        raise RuntimeError("FOAMAGENT_OPENFOAM_RUN_USER='openfoam' does not exist")

    monkeypatch.setattr(utils, "openfoam_execution_args", fail_execution_args)

    utils.run_command(str(script), str(out_file), str(err_file), str(tmp_path), 5, "v9-rheotool")

    assert "FOAM FATAL ERROR: Foam-Agent OpenFOAM execution environment blocked" in err_file.read_text(encoding="utf-8")
    assert "openfoam" in err_file.read_text(encoding="utf-8")


def test_check_foam_errors_ignores_openfoam_continuity_error_lines(tmp_path, capsys):
    (tmp_path / "log.icoFoam").write_text(
        "\n".join(
            [
                "Time = 0.5s",
                "time step continuity errors : sum local = 1e-09, global = 0, cumulative = 0",
                "End",
            ]
        ),
        encoding="utf-8",
    )

    assert utils.check_foam_errors(str(tmp_path)) == []
    assert "contains 'error'" not in capsys.readouterr().out
