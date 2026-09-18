from pathlib import Path

from models import CaseTarget


PROMPT_ROOT = Path(__file__).resolve().parents[2] / "prompts"
PROMPT_NAMES = {"planner", "input_writer", "reviewer", "error_fix"}


def load_channel_prompt(target: CaseTarget, name: str) -> str:
    if not isinstance(target, CaseTarget):
        raise TypeError("channel prompts require an immutable CaseTarget")
    if name not in PROMPT_NAMES:
        raise ValueError(f"Unknown channel prompt: {name}")
    path = PROMPT_ROOT / target.channel / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Missing channel prompt: {path}")
    return path.read_text(encoding="utf-8").strip()
