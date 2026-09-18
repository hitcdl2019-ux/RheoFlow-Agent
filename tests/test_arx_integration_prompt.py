import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "integrations" / "arx" / "FOAM_AGENT_ARX_PROMPT.md"
CONFIG = ROOT / "integrations" / "arx" / "foamagent-mcp.json"
README = ROOT / "integrations" / "arx" / "README.md"


def test_arx_prompt_uses_backend_progress_protocol():
    text = PROMPT.read_text(encoding="utf-8")

    assert "progress_events" in text
    assert "rendered_progress" in text
    assert "不要重新猜测阶段状态" in text
    assert "[0/6] 环境检查" in text
    assert "[5.1]" in text and "[5.6]" in text
    assert "foamagent_execute_status" in text
    assert "严禁向用户请求“继续轮询/是否继续”的确认" in text


def test_arx_prompt_preserves_intake_and_case_target_boundary():
    text = PROMPT.read_text(encoding="utf-8")

    assert "`[1/6]` 只回答 `ready` / `clarify` / `reject`" in text
    assert "`[2/6]` 才展示 channel/version/solver" in text
    assert "不得在此阶段整理、生成或声称已生成 `user_requirement.txt`" in text
    assert "多子变体模板族才追问子变体；单变体模板不得臆造" in text


def test_arx_mcp_config_points_to_product_server():
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    server = data["mcpServers"]["foamagent"]

    assert server["command"] == "/opt/conda/envs/FoamAgent/bin/python"
    assert server["args"] == ["-m", "src.mcp.product_server", "--transport", "stdio"]
    assert server["cwd"] == "/opt/Foam-Agent"
    assert server["env"]["PYTHONPATH"] == "/opt/Foam-Agent"


def test_arx_readme_documents_progress_migration_reason():
    text = README.read_text(encoding="utf-8")

    assert "CodeBuddy progress UI" in text
    assert "progress_events" in text
    assert "rendered_progress" in text
