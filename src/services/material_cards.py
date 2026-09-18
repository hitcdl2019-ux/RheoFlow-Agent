from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MATERIAL_ROOT = Path(__file__).resolve().parents[2] / "knowledge" / "materials"
NEGATED_ALIAS_TERMS = (
    "not applicable", "not used", "single phase", "single-phase",
    "不适用", "不用", "不使用", "单相",
)


def load_material_cards(root: Path = MATERIAL_ROOT) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    if not root.is_dir():
        return cards
    for path in sorted(root.glob("*.yaml")):
        # Files are YAML-compatible JSON to avoid adding a PyYAML dependency.
        card = json.loads(path.read_text(encoding="utf-8"))
        card["_path"] = str(path)
        cards.append(card)
    return cards


def match_material_card(text: str, root: Path = MATERIAL_ROOT) -> dict[str, Any] | None:
    normalized = text.lower()
    for card in load_material_cards(root):
        aliases = [card.get("material", "")] + list(card.get("aliases", []))
        for alias in aliases:
            alias_text = str(alias).lower()
            if not alias_text:
                continue
            index = normalized.find(alias_text)
            if index < 0:
                continue
            window = normalized[max(0, index - 40): index + len(alias_text) + 80]
            if card.get("material") == "water_air" and any(term in window for term in NEGATED_ALIAS_TERMS):
                continue
            return card
    return None


def unknown_material_questions() -> list[str]:
    return [
        "我没有找到该材料的已知材料卡片。请说明它是否像水一样近似牛顿流动。",
        "请说明它是否剪切越快越稀、是否有屈服行为、回弹、拉丝或入口胀大。",
        "如果有流变仪、厂家数据表、浓度或牌号，请提供这些业务信息。",
    ]
