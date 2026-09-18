from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEWER_PROMPT = ROOT / "prompts" / "v9-rheotool" / "reviewer.md"
ERROR_FIX_PROMPT = ROOT / "prompts" / "v9-rheotool" / "error_fix.md"


def test_v9_rheotool_prompts_forbid_guessed_custom_bc_libraries():
    text = REVIEWER_PROMPT.read_text(encoding="utf-8") + "\n" + ERROR_FIX_PROMPT.read_text(encoding="utf-8")

    assert "uLid, uCos, HBprofile, uShaft, ACPotential -> libRheoToolTutorialBCs.so" in text
    assert "linearExtrapolation, navierSlip -> libBCRheoTool.so" in text
    assert "Never add guessed libraries" in text
    assert "libRheoToolUtilities.so" in text
    assert "libRheoToolModels.so" in text
    assert "libRheoToolBoundaryConditions.so" in text


def test_v9_rheotool_prompts_treat_unregistered_custom_bc_as_environment_blocker():
    text = REVIEWER_PROMPT.read_text(encoding="utf-8") + "\n" + ERROR_FIX_PROMPT.read_text(encoding="utf-8")

    assert "RHEOTOOL_CUSTOM_BC_NOT_REGISTERED" in text
    assert "environment/source-template blocker" in text
    assert "do not replace the boundary condition with codedFixedValue" in text
    assert "do not rewrite the physical boundary condition" in text
