from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.material_cards import load_material_cards, match_material_card, unknown_material_questions  # noqa: E402


def test_material_cards_cover_initial_mvp_materials():
    cards = {card["material"]: card for card in load_material_cards()}
    for name in ("polymer_solution", "polymer_melt", "toothpaste", "blood", "slurry", "water_air", "unknown_material"):
        assert name in cards


def test_known_materials_match_business_terms():
    assert match_material_card("聚合物溶液过收缩模具")["material"] == "polymer_solution"
    assert match_material_card("牙膏挤出过程")["material"] == "toothpaste"
    assert match_material_card("血液在血管中流动")["material"] == "blood"
    assert match_material_card("水和空气自由液面")["material"] == "water_air"


def test_negated_water_air_card_does_not_match_single_phase_water():
    assert match_material_card("water-air material card: not applicable; single phase water only") is None


def test_unknown_material_questions_are_behavior_based():
    questions = "\n".join(unknown_material_questions())
    assert "剪切" in questions
    assert "回弹" in questions
    assert "流变仪" in questions
