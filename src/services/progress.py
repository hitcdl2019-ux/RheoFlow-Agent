"""Shared Foam-Agent progress event protocol and text renderer.

This module keeps human-facing agents (CodeBuddy, ARX, or future MCP clients)
from re-inventing the [0/6]...[6/6] progress mapping.  The backend still owns
only facts; each frontend may render these events as text cards, progress bars,
or page components.
"""

from __future__ import annotations

from typing import Any


STAGE_NAMES: dict[str, str] = {
    "0": "环境检查",
    "1": "需求理解与 Intake",
    "2": "目标锁定 CaseTarget",
    "3": "Case 文件生成",
    "4": "Schema / Manifest 校验",
    "5": "OpenFOAM 执行",
    "6": "结果检查与业务解释",
}

SUBSTEP_NAMES: dict[str, str] = {
    "5.1": "运行环境加载",
    "5.2": "网格生成 blockMesh",
    "5.3": "网格质量检查 checkMesh",
    "5.4": "求解器运行",
    "5.5": "后处理 / 结果提取",
    "5.6": "日志诊断 / 自动修复",
}


def _ordered_statuses(statuses: dict[str, str], names: dict[str, str]) -> list[tuple[str, str, str]]:
    return [(key, names[key], statuses.get(key, "pending")) for key in names]


def build_progress_events(
    stages: dict[str, str],
    openfoam_substeps: dict[str, str] | None = None,
    *,
    solver: str | None = None,
    current_time: float | None = None,
    end_time: float | None = None,
    progress_percent: float | None = None,
) -> list[dict[str, Any]]:
    """Build a stable JSON progress-event tree for external agents.

    The shape is intentionally simple so agents without a custom UI can still
    render it directly.  Stage 5 includes substeps only when OpenFOAM execution
    has actually started or a substep carries a non-pending state.
    """
    openfoam_substeps = openfoam_substeps or {}
    events: list[dict[str, Any]] = []
    include_substeps = any(value != "pending" for value in openfoam_substeps.values())

    for stage_id, name, status in _ordered_statuses(stages, STAGE_NAMES):
        event: dict[str, Any] = {"id": stage_id, "name": name, "status": status}
        if stage_id == "5" and include_substeps:
            children: list[dict[str, Any]] = []
            for sub_id, sub_name, sub_status in _ordered_statuses(openfoam_substeps, SUBSTEP_NAMES):
                child_name = f"{sub_name} {solver}" if sub_id == "5.4" and solver else sub_name
                child: dict[str, Any] = {"id": sub_id, "name": child_name, "status": sub_status}
                if sub_id == "5.4" and current_time is not None:
                    progress: dict[str, Any] = {"current_time": current_time}
                    if end_time is not None:
                        progress["end_time"] = end_time
                    if progress_percent is not None:
                        progress["percent"] = progress_percent
                    child["progress"] = progress
                children.append(child)
            event["children"] = children
        events.append(event)
    return events


def _format_number(value: float) -> str:
    return f"{value:g}"


def render_progress_text(
    stages: dict[str, str],
    openfoam_substeps: dict[str, str] | None = None,
    *,
    solver: str | None = None,
    current_time: float | None = None,
    end_time: float | None = None,
    progress_percent: float | None = None,
) -> str:
    """Render the canonical Chinese text progress block used by agent UIs."""
    events = build_progress_events(
        stages,
        openfoam_substeps,
        solver=solver,
        current_time=current_time,
        end_time=end_time,
        progress_percent=progress_percent,
    )
    lines = ["Foam-Agent 执行进度"]
    for event in events:
        lines.append(f"[{event['id']}/6] {event['name']}：{event['status']}")
        for child in event.get("children", []):
            suffix = ""
            progress = child.get("progress") or {}
            if child["id"] == "5.4" and progress:
                current = _format_number(progress["current_time"])
                if "end_time" in progress:
                    end = _format_number(progress["end_time"])
                    suffix = f"（Time={current}/{end}"
                    if "percent" in progress:
                        suffix += f"，约 {progress['percent']:.2f}%"
                    suffix += "）"
                else:
                    suffix = f"（Time={current}）"
            lines.append(f"  [{child['id']}] {child['name']}：{child['status']}{suffix}")
    return "\n".join(lines)
