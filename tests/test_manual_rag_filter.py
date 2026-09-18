from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.input_writer import filter_rheotool_manual_rules


def test_manual_filter_prioritizes_exact_then_multi_then_generic():
    rows = [
        {"section": "5.4.1", "solver": "rheoEFoam", "full_content": "ef"},
        {"section": "5.1.1", "solver": "rheoFoam", "full_content": "rf"},
        {"section": "4.7", "solver": "rheoFoam,rheoTestFoam", "full_content": "multi"},
        {"section": "4.1", "solver": "", "full_content": "generic"},
    ]

    out = filter_rheotool_manual_rules(rows, "rheoFoam", 3)

    assert [r["section"] for r in out] == ["5.1.1", "4.7", "4.1"]
    assert [r["manual_rule_match_level"] for r in out] == ["exact", "multi_solver", "generic"]


def test_manual_filter_excludes_explicit_other_solver_chunks():
    rows = [
        {"section": "5.4.1", "solver": "rheoEFoam", "full_content": "ef"},
        {"section": "5.8.1", "solver": "rheoFilmFoam", "full_content": "film"},
        {"section": "5.2.1", "solver": "rheoTestFoam", "full_content": "test"},
        {"section": "4.7", "solver": "rheoFoam,rheoTestFoam", "full_content": "multi"},
    ]

    out = filter_rheotool_manual_rules(rows, "rheoTestFoam", 5)

    assert [r["section"] for r in out] == ["5.2.1", "4.7"]
    assert all("rheoEFoam" not in r["solver"] for r in out)
    assert all("rheoFilmFoam" not in r["solver"] for r in out)


def test_manual_filter_non_rheotool_solver_returns_nothing():
    rows = [
        {"section": "a", "solver": "rheoEFoam"},
        {"section": "b", "solver": "rheoFoam"},
    ]

    out = filter_rheotool_manual_rules(rows, "simpleFoam", 1)

    assert out == []


def test_manual_filter_section_owner_overrides_inheritance_mentions():
    rows = [
        {"section": "5.4.1", "solver": "rheoFoam,rheoEFoam", "full_content": "rheoEFoam is derived from rheoFoam"},
        {"section": "5.1.1", "solver": "rheoFoam", "full_content": "rheoFoam guidelines"},
        {"section": "4.7.1", "solver": "rheoFoam", "full_content": "rheoFoam solver"},
    ]

    out = filter_rheotool_manual_rules(rows, "rheoFoam", 5)

    assert [r["section"] for r in out] == ["5.1.1", "4.7.1"]
