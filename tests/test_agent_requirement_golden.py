from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.intake import evaluate_requirement  # noqa: E402


def test_golden_expected_requirements_are_intake_ready():
    for path in sorted((ROOT / "tests" / "golden_requirements").glob("*.expected.txt")):
        result = evaluate_requirement(path.read_text(encoding="utf-8"))
        assert result["status"] == "ready", path.name
        assert result["target_preview"] is not None, path.name


def test_golden_inputs_and_expected_outputs_are_paired():
    root = ROOT / "tests" / "golden_requirements"
    inputs = {path.stem.replace(".input", "") for path in root.glob("*.input.txt")}
    expected = {path.stem.replace(".expected", "") for path in root.glob("*.expected.txt")}
    assert inputs == expected
