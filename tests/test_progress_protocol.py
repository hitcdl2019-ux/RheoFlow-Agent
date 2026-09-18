from services.progress import build_progress_events, render_progress_text


def test_progress_protocol_renders_openfoam_solver_substeps():
    stages = {
        "0": "passed",
        "1": "passed",
        "2": "passed",
        "3": "passed",
        "4": "passed",
        "5": "running",
        "6": "pending",
    }
    substeps = {
        "5.1": "passed",
        "5.2": "passed",
        "5.3": "passed",
        "5.4": "running",
        "5.5": "pending",
        "5.6": "pending",
    }

    events = build_progress_events(
        stages,
        substeps,
        solver="rheoFoam",
        current_time=0.5,
        end_time=10,
        progress_percent=5.0,
    )

    stage5 = next(event for event in events if event["id"] == "5")
    assert stage5["children"][3] == {
        "id": "5.4",
        "name": "求解器运行 rheoFoam",
        "status": "running",
        "progress": {"current_time": 0.5, "end_time": 10, "percent": 5.0},
    }

    rendered = render_progress_text(
        stages,
        substeps,
        solver="rheoFoam",
        current_time=0.5,
        end_time=10,
        progress_percent=5.0,
    )
    assert "Foam-Agent 执行进度" in rendered
    assert "[5/6] OpenFOAM 执行：running" in rendered
    assert "[5.4] 求解器运行 rheoFoam：running（Time=0.5/10，约 5.00%）" in rendered
