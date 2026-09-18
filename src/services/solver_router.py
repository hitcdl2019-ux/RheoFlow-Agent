from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class SolverRoute:
    solver: Optional[str]
    confidence: float
    reason: str
    domain: Optional[str] = None
    category: Optional[str] = None

    def as_dict(self) -> Dict[str, object]:
        return {
            "solver": self.solver,
            "confidence": self.confidence,
            "reason": self.reason,
            "domain": self.domain,
            "category": self.category,
        }


KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "rheoTestFoam": (
        "rheotestfoam", "virtual rheometer", "rheometer", "material function", "material functions",
        "shear viscosity", "viscosity curve", "extensional viscosity", "oscillatory shear",
        "gammaepsilondotl", "rheotestfoamparameters", "剪切黏度", "剪切粘度", "黏度曲线",
        "粘度曲线", "材料函数", "流变仪", "虚拟流变仪", "拉伸黏度", "拉伸粘度", "振荡剪切",
    ),
    "rheoInterFoam": (
        "rheointerfoam", "two phase", "two-phase", "multiphase", "vof", "free surface",
        "surface tension", "interface", "alpha.water", "p_rgh", "dambreak", "dam break",
        "die swell", "impacting drop", "两相", "多相", "自由液面", "界面张力", "界面",
        "相分数", "液滴", "气泡", "溃坝", "挤出胀大",
    ),
    "rheoFoam": (
        "rheofoam", "viscoelastic flow", "polymer flow", "oldroyd", "fene", "giesekus",
        "ptt", "roly-poly", "rolie-poly", "x-pompom", "xpompom", "herschelbulkley",
        "herschel-bulkley", "carreau", "流变流动", "粘弹性流动", "黏弹性流动",
        "聚合物流动",
    ),
}

CATEGORY_BY_SOLVER = {
    "rheoFoam": "rheoFoam",
    "rheoTestFoam": "rheoTestFoam",
    "rheoInterFoam": "rheoInterFoam",
}


def _count_hits(text: str, keywords: Iterable[str]) -> List[str]:
    return [keyword for keyword in keywords if keyword in text]


def _earliest_explicit_solver(text: str) -> Optional[str]:
    positions: List[Tuple[int, str]] = []
    for solver in CATEGORY_BY_SOLVER:
        pos = text.find(solver.lower())
        if pos >= 0:
            positions.append((pos, solver))
    if not positions:
        return None
    return min(positions, key=lambda item: item[0])[1]


def _is_negated_hit(text: str, keyword: str) -> bool:
    negations = (
        "do not", "don't", "dont", "not ", "never", "without", "avoid",
        "不要", "不使用", "不能", "不得", "禁止", "避免", "无需", "不需要",
    )
    start = 0
    while True:
        pos = text.find(keyword, start)
        if pos < 0:
            return False
        window = text[max(0, pos - 32):pos]
        if any(negation in window for negation in negations):
            return True
        start = pos + len(keyword)


def _filter_negated_hits(text: str, hits: List[str]) -> List[str]:
    return [hit for hit in hits if not _is_negated_hit(text, hit)]


def route_rheotool_solver(user_requirement: str) -> SolverRoute:
    text = (user_requirement or "").lower()
    scores: Dict[str, List[str]] = {solver: _count_hits(text, words) for solver, words in KEYWORDS.items()}
    scores = {solver: _filter_negated_hits(text, hits) for solver, hits in scores.items()}

    explicit_solver = _earliest_explicit_solver(text)
    if explicit_solver:
        return SolverRoute(
            explicit_solver,
            1.0,
            f"explicit solver keyword: {explicit_solver}",
            "rheology",
            CATEGORY_BY_SOLVER[explicit_solver],
        )

    if scores["rheoTestFoam"]:
        hits = ", ".join(scores["rheoTestFoam"][:5])
        return SolverRoute("rheoTestFoam", 0.9, f"matched rheometer/material-function keywords: {hits}", "rheology", "rheoTestFoam")

    if scores["rheoInterFoam"]:
        hits = ", ".join(scores["rheoInterFoam"][:5])
        return SolverRoute("rheoInterFoam", 0.9, f"matched two-phase/interface keywords: {hits}", "rheology", "rheoInterFoam")

    if scores["rheoFoam"]:
        hits = ", ".join(scores["rheoFoam"][:5])
        return SolverRoute("rheoFoam", 0.75, f"matched single-phase rheology keywords: {hits}", "rheology", "rheoFoam")

    generic_rheology = ("rheology", "rheotool", "openfoam流变", "流变", "本构")
    generic_hits = _count_hits(text, generic_rheology)
    if generic_hits:
        return SolverRoute("rheoFoam", 0.6, f"generic rheology fallback: {', '.join(generic_hits[:5])}", "rheology", "rheoFoam")

    return SolverRoute(None, 0.0, "no rheoTool routing rule matched")


def ensure_rheotool_solvers_in_case_stats(case_stats: Dict[str, List[str]]) -> Dict[str, List[str]]:
    out = {key: list(value) for key, value in (case_stats or {}).items()}
    for key, values in {
        "case_domain": ["rheology"],
        "case_category": ["rheoFoam", "rheoTestFoam", "rheoInterFoam"],
        "case_solver": ["rheoFoam", "rheoTestFoam", "rheoInterFoam"],
    }.items():
        out.setdefault(key, [])
        for value in values:
            if value not in out[key]:
                out[key].append(value)
    return out
