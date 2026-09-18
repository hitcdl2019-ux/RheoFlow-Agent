from pathlib import Path
import importlib.util
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "services" / "solver_router.py"
MODULE_NAME = "solver_router_under_test"
spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
solver_router = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[MODULE_NAME] = solver_router
spec.loader.exec_module(solver_router)


def test_route_rheotestfoam_material_function_prompt():
    route = solver_router.route_rheotool_solver("计算 FENE-CR 材料的剪切黏度曲线和材料函数")
    assert route.solver == "rheoTestFoam"
    assert route.domain == "rheology"


def test_route_rheointerfoam_two_phase_prompt():
    route = solver_router.route_rheotool_solver("模拟含界面张力的两相自由液面流动 VOF alpha.water")
    assert route.solver == "rheoInterFoam"
    assert route.domain == "rheology"


def test_route_rheofoam_single_phase_prompt():
    route = solver_router.route_rheotool_solver("Oldroyd-BLog 粘弹性顶盖驱动空腔流")
    assert route.solver == "rheoFoam"
    assert route.domain == "rheology"


def test_non_rheology_prompt_is_not_overridden():
    route = solver_router.route_rheotool_solver("模拟普通不可压缩圆柱绕流")
    assert route.solver is None


def test_newtonian_icofoam_cavity_is_not_overridden():
    route = solver_router.route_rheotool_solver(
        "使用 icoFoam 模拟不可压缩层流顶盖驱动空腔流，运动黏度 nu=0.01"
    )
    assert route.solver is None


def test_case_stats_are_extended_without_duplicates():
    stats = {"case_solver": ["rheoFoam"], "case_domain": [], "case_category": []}
    out = solver_router.ensure_rheotool_solvers_in_case_stats(stats)
    assert out["case_solver"].count("rheoFoam") == 1
    assert "rheoTestFoam" in out["case_solver"]
    assert "rheoInterFoam" in out["case_solver"]
