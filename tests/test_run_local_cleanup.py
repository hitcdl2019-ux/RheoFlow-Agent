from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils import remove_processor_folders  # noqa: E402
import services.run_local as run_local  # noqa: E402


def test_remove_processor_folders_removes_stale_parallel_decomposition(tmp_path):
    (tmp_path / "processor0" / "0.001").mkdir(parents=True)
    (tmp_path / "processor1" / "0").mkdir(parents=True)
    (tmp_path / "postProcessing").mkdir()

    remove_processor_folders(str(tmp_path))

    assert not (tmp_path / "processor0").exists()
    assert not (tmp_path / "processor1").exists()
    assert (tmp_path / "postProcessing").exists()


def test_run_allrun_cleans_stale_numeric_time_dirs_before_execution(monkeypatch, tmp_path):
    (tmp_path / "Allrun").write_text("#!/bin/sh\n", encoding="utf-8")
    (tmp_path / "0").mkdir()
    (tmp_path / "2").mkdir()
    (tmp_path / "4.5").mkdir()
    (tmp_path / "constant").mkdir()

    def fake_run_command(script_path, out_file, err_file, case_dir, timeout, channel):
        assert not (tmp_path / "2").exists()
        assert not (tmp_path / "4.5").exists()
        assert (tmp_path / "0").exists()
        (tmp_path / "log.fake").write_text("End\n", encoding="utf-8")

    monkeypatch.setattr(run_local, "run_command", fake_run_command)

    errors = run_local.run_allrun_and_collect_errors(str(tmp_path), channel="v9-rheotool")

    assert errors == []
