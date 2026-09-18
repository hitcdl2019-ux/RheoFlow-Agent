# visualization_node.py
import os
from services.postprocess import run_standard_postprocess
from services.visualization import (
    ensure_foam_file,
    generate_deterministic_pyvista_script,
    generate_pyvista_script,
    run_pyvista_script,
    fix_pyvista_script,
)


# Routing should decide whether to enter this node (see router_func.llm_requires_visualization).

def _guess_primary_field(user_requirement: str) -> str:
    """Very small heuristic; keep deterministic and conservative."""
    if not user_requirement:
        return "U"
    text = user_requirement
    # Prefer explicit mentions
    if " p " in f" {text} " or "pressure" in text.lower():
        return "p"
    if "temperature" in text.lower():
        return "T"
    if "u" in text.lower() or "velocity" in text.lower():
        return "U"
    return "U"

def visualization_node(state):
    """Visualization node: create a minimal PyVista screenshot for an OpenFOAM case.

    Design goals:
      - Only run if the user asked for visualization
      - Deterministic output path + deterministic artifact detection
      - Prefer a fixed, headless-safe renderer; fall back to LLM self-correct if needed
    """
    user_requirement = state.get("user_requirement", "")
    case_dir = state.get("case_dir")

    print("<visualization>")

    # Note: routing logic should decide whether we reach this node.

    if not case_dir:
        print("</visualization>")
        return {
            **state,
            "plot_configs": [],
            "plot_outputs": [],
            "visualization_summary": {"error": "Missing case_dir"},
            "pyvista_visualization": {"success": False, "error": "Missing case_dir"},
        }

    case_dir = os.path.abspath(case_dir)
    if not os.path.exists(case_dir):
        print(f"Case directory does not exist: {case_dir}")
        print("</visualization>")
        return {
            **state,
            "plot_configs": [],
            "plot_outputs": [],
            "visualization_summary": {"error": f"Case directory does not exist: {case_dir}"},
            "pyvista_visualization": {"success": False, "error": f"Case directory does not exist: {case_dir}"},
        }

    try:
        postprocess_result = run_standard_postprocess(
            case_dir,
            user_requirement=user_requirement,
            fields=("U", "p", "tau"),
        )
        field_outputs = [
            item["output"]
            for item in postprocess_result.get("field_visualizations", {}).get("fields", {}).values()
            if item.get("status") == "passed" and item.get("output")
        ]
        line_output = postprocess_result.get("line_plot", {}).get("output")
        plot_outputs = field_outputs + ([line_output] if line_output else [])
        if plot_outputs:
            print("</visualization>")
            return {
                **state,
                "plot_configs": [
                    {"plot_type": "postprocess", "output_path": path}
                    for path in plot_outputs
                ],
                "plot_outputs": plot_outputs,
                "visualization_summary": {
                    "total_plots_generated": len(plot_outputs),
                    "plot_types": ["postprocess", "pyvista"],
                    "fields_visualized": list(postprocess_result.get("field_visualizations", {}).get("fields", {}).keys()),
                    "output_directory": case_dir,
                    "pyvista_success": bool(field_outputs),
                    "used": "standard_postprocess",
                    "report_json": postprocess_result.get("report_json"),
                    "summary_markdown": postprocess_result.get("summary_markdown"),
                },
                "pyvista_visualization": {
                    "success": bool(field_outputs),
                    "output_image": field_outputs[0] if field_outputs else line_output,
                    "used": "standard_postprocess",
                },
                "postprocess_result": postprocess_result,
            }
    except Exception as exc:
        print(f"<postprocess_warning>{exc}</postprocess_warning>")

    foam_file = ensure_foam_file(case_dir)

    max_loop = getattr(state.get("config"), "max_loop", 2)
    timeout_s = 180

    # Deterministic artifact path (relative to case_dir)
    output_png_rel = "visualization.png"

    field_name = _guess_primary_field(user_requirement)

    error_logs = []

    # Attempt 1: deterministic template (preferred)
    deterministic_script = generate_deterministic_pyvista_script(
        foam_file=foam_file,
        output_png=output_png_rel,
        field_preference=field_name,
    )
    success, output_image, errs = run_pyvista_script(
        case_dir,
        deterministic_script,
        filename="visualization.py",
        expected_png=output_png_rel,
        timeout_s=timeout_s,
    )
    if success and output_image:
        plot_configs = [
            {
                "plot_type": "pyvista",
                "field_name": field_name,
                "time_step": "latest",
                "output_format": "png",
                "output_path": output_image,
            }
        ]
        print("</visualization>")
        return {
            **state,
            "plot_configs": plot_configs,
            "plot_outputs": [output_image],
            "visualization_summary": {
                "total_plots_generated": 1,
                "plot_types": ["pyvista"],
                "fields_visualized": [field_name],
                "output_directory": case_dir,
                "pyvista_success": True,
                "used": "deterministic_template",
            },
            "pyvista_visualization": {
                "success": True,
                "output_image": output_image,
                "script": deterministic_script,
                "used": "deterministic_template",
            },
        }

    error_logs.extend(errs)

    # Fallback: LLM generate + self-correct loop (kept, but artifact path is deterministic)
    current_loop = 0
    while current_loop < max_loop:
        current_loop += 1
        print(f"LLM visualization attempt {current_loop} of {max_loop}")

        viz_script = generate_pyvista_script(case_dir, foam_file, user_requirement, error_logs[-2:])
        success, output_image, errs = run_pyvista_script(
            case_dir,
            viz_script,
            filename="visualization_llm.py",
            expected_png=output_png_rel,
            timeout_s=timeout_s,
        )

        if success and output_image:
            plot_configs = [
                {
                    "plot_type": "pyvista",
                    "field_name": field_name,
                    "time_step": "latest",
                    "output_format": "png",
                    "output_path": output_image,
                }
            ]
            print("</visualization>")
            return {
                **state,
                "plot_configs": plot_configs,
                "plot_outputs": [output_image],
                "visualization_summary": {
                    "total_plots_generated": 1,
                    "plot_types": ["pyvista"],
                    "fields_visualized": [field_name],
                    "output_directory": case_dir,
                    "pyvista_success": True,
                    "used": "llm_script",
                },
                "pyvista_visualization": {
                    "success": True,
                    "output_image": output_image,
                    "script": viz_script,
                    "used": "llm_script",
                },
            }

        error_logs.extend(errs)

        if current_loop < max_loop:
            fixed_script = fix_pyvista_script(foam_file, viz_script, error_logs[-2:])
            success, output_image, errs = run_pyvista_script(
                case_dir,
                fixed_script,
                filename="visualization_fixed.py",
                expected_png=output_png_rel,
                timeout_s=timeout_s,
            )
            if success and output_image:
                plot_configs = [
                    {
                        "plot_type": "pyvista",
                        "field_name": field_name,
                        "time_step": "latest",
                        "output_format": "png",
                        "output_path": output_image,
                    }
                ]
                print("</visualization>")
                return {
                    **state,
                    "plot_configs": plot_configs,
                    "plot_outputs": [output_image],
                    "visualization_summary": {
                        "total_plots_generated": 1,
                        "plot_types": ["pyvista"],
                        "fields_visualized": [field_name],
                        "output_directory": case_dir,
                        "pyvista_success": True,
                        "used": "llm_fixed_script",
                    },
                    "pyvista_visualization": {
                        "success": True,
                        "output_image": output_image,
                        "script": fixed_script,
                        "used": "llm_fixed_script",
                    },
                }
            error_logs.extend(errs)

    error_message = f"Visualization failed after {max_loop} LLM attempts"
    print(f"<visualization_error>{error_message}</visualization_error>")
    print("</visualization>")
    return {
        **state,
        "plot_configs": [],
        "plot_outputs": [],
        "visualization_summary": {
            "total_plots_generated": 0,
            "plot_types": [],
            "fields_visualized": [],
            "output_directory": case_dir,
            "pyvista_success": False,
            "error": error_message,
            "error_logs": error_logs,
        },
        "pyvista_visualization": {"success": False, "error": error_message, "error_logs": error_logs},
    }
