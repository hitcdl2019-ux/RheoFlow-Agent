from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "integrations" / "codebuddy" / "FOAM_AGENT_CODEBUDDY_PROMPT.md"


def test_codebuddy_prompt_separates_intake_from_case_target():
    text = PROMPT.read_text(encoding="utf-8")

    assert "`[1/6] Intake` 只回答 ready/clarify/reject" in text
    assert "`[2/6] CaseTarget` 才回答 channel/version/solver" in text
    assert "并列出 solver/channel/receipt" not in text

    intake_example = text.split("示例 intake ready 后：", 1)[1].split("示例 CaseTarget 锁定后：", 1)[0]
    assert "- intake: ready" in intake_example
    assert "- receipt: <path>" in intake_example
    assert "- solver:" not in intake_example
    assert "- channel:" not in intake_example
    assert "- version:" not in intake_example

    target_example = text.split("示例 CaseTarget 锁定后：", 1)[1].split("## MCP 工具边界", 1)[0]
    assert "[2/6] 目标锁定 CaseTarget：passed" in target_example
    assert "- channel:" in target_example
    assert "- version:" in target_example
    assert "- solver:" in target_example


def test_codebuddy_prompt_keeps_requirement_drafting_out_of_environment_check():
    text = PROMPT.read_text(encoding="utf-8")

    assert "`[0/6] 环境检查` 只检查" in text
    assert "双通道运行环境可用性" in text
    assert "不得在此阶段整理、生成或声称已生成 `user_requirement.txt`" in text
    assert "`user_requirement.txt` 的草稿整理、写入、receipt 生成和 `foamagent_intake` 调用全部属于 `[1/6] 需求理解与 Intake`" in text
    assert "不得把该动作归因到 `[0/6]`" in text


def test_codebuddy_prompt_does_not_prejudge_v10_during_environment_check():
    text = PROMPT.read_text(encoding="utf-8")

    assert "不得写成“Foundation OpenFOAM v10 运行环境检查”" in text
    assert "只面向 v10" in text
    assert "具体 `v9-rheotool` / `v10-foundation` 必须等 `[2/6] CaseTarget` 锁定后再展示" in text


def test_codebuddy_prompt_does_not_mark_openfoam_running_before_status_poll():
    text = PROMPT.read_text(encoding="utf-8")

    assert "立即调用一次 `foamagent_execute_status" in text
    assert "不要仅凭后台进程已启动就把 `[5/6] OpenFOAM 执行` 标成 `running`" in text


def test_codebuddy_prompt_requires_openfoam_substep_rendering_even_on_failure():
    text = PROMPT.read_text(encoding="utf-8")

    assert "只要 `openfoam_substeps` 中任一子步骤不是 `pending`，必须展开并逐项展示 `[5.1]` 到 `[5.6]`" in text
    assert "当 `status=failed` 后，仍必须展开 `[5.1]` 到 `[5.6]` 子步骤" in text
    failure_example = text.split("失败示例也必须展开：", 1)[1]
    assert "[5/6] OpenFOAM 执行：failed" in failure_example
    assert "[5.4] 求解器运行 rheoFoam：passed" in failure_example
    assert "[5.5] 后处理 / 结果提取：failed" in failure_example


def test_codebuddy_prompt_requires_server_side_watch_instead_of_manual_continue():
    text = PROMPT.read_text(encoding="utf-8")

    assert "watch_seconds=600" in text
    assert "watch_seconds=120" in text
    assert "poll_interval_seconds=10" in text
    assert "不要使用 `wait_until_terminal=true` 长时间阻塞 UI" in text
    assert "刷新 `rheoFoam Time=...`" in text
    assert "不要只回复“继续轮询中”然后停止" in text
    assert "严禁向用户请求“继续轮询/是否继续”的确认" in text


def test_codebuddy_prompt_does_not_promote_tutorial_template_imports():
    text = PROMPT.read_text(encoding="utf-8")

    assert "`decision=template_import`" in text
    assert "`TUTORIAL_TEMPLATE_IMPORT.json`" in text
    assert "不得向最终用户推荐“晋级 certified benchmark”" in text



def test_codebuddy_prompt_forbids_benchmark_alias_pollution():
    text = PROMPT.read_text(encoding="utf-8")

    assert "不得在 `user_requirement.txt` 草稿中加入用户未明确提到的论文名" in text
    assert "特别禁止把未出现的 `RUDE`" in text
    assert "不得改写成 “RUDE-class”" in text



def test_codebuddy_prompt_forbids_pre_intake_history_lookup():
    text = PROMPT.read_text(encoding="utf-8")

    assert "Intake 前的 requirement 草稿必须只来自用户本轮输入" in text
    assert "不得搜索、读取或引用 `runs/`、`sessions/`" in text
    assert "旧 `.intake.json`" in text
    assert "旧 `POSTPROCESS_*`" in text
    assert "不得在 Intake 前用旧 runs 数据替代当前需求" in text
    assert "历史产物隔离" in text


def test_codebuddy_prompt_forbids_dieswell_variant_pollution_before_intake():
    text = PROMPT.read_text(encoding="utf-8")

    assert "RheoTool 教程族变体防污染" in text
    assert "tutorial_family: RheoTool 5.3.3 DieSwell" in text
    assert "tutorial_variant: unknown" in text
    assert "不得写入“通常使用 Oldroyd-B / 推荐 Oldroyd-BLog / 黏弹性本构如 Oldroyd-B / 标准 Oldroyd-B 变体”" in text
    assert "`Missing / Unconfirmed Information` 中也不得列出 `Oldroyd-BLog / GiesekusLog / CarreauYasuda` 候选词" in text
    assert "推荐项只能出现在 intake 返回 `clarify` 后的用户可选项说明中" in text
    assert "若用户明确写 `DieSwell/Oldroyd-BLog`" in text


def test_codebuddy_prompt_requires_task_mode_before_business_request_completion():
    text = PROMPT.read_text(encoding="utf-8")

    assert "业务型请求的分层澄清" in text
    assert "task_mode: unknown" in text
    assert "不得在草稿里列出“平台已有相似案例/教程模板基线、真实设备/真实几何、参数扫描”等候选项" in text
    assert "任务模式候选项只能由 intake 返回 `clarify` 后在用户界面展示" in text
    assert "真实设备/真实几何" in text
    assert "几何→工况→材料参数" in text


def test_codebuddy_prompt_requires_template_parameter_policy_after_variant():
    text = PROMPT.read_text(encoding="utf-8")

    assert "模板基线参数策略" in text
    assert "parameter_policy: unknown" in text
    assert "不得立即执行" in text
    assert "使用模板原始参数（推荐）" in text
    assert "基于模板原始参数修改部分参数" in text
    assert "模板参数白名单校验" in text


def test_codebuddy_prompt_forbids_parallel_plate_fake_variant_choice():
    text = PROMPT.read_text(encoding="utf-8")

    assert "单变体模板防污染" in text
    assert "Channel/Oldroyd-BLog" in text
    assert "当前只有一个已认证模板变体" in text
    assert "不得对 Case 1 用户说“平行板槽道流模板可能支持 Oldroyd-B / Giesekus / PTT 等多种本构变体”" in text
    assert "直接沿用唯一认证模板 `rheotool_5_1_3_channel_oldroydb_log`" in text
    assert "这不是 Case 1 原始认证模板逐字复现" in text

def test_codebuddy_prompt_forbids_dambreak_baseline_ras_pollution():
    text = PROMPT.read_text(encoding="utf-8")

    assert "Foundation damBreak 模板族防污染" in text
    assert "不得在 intake 前写入 `foundation_v10_interfoam_ras_dambreak`" in text
    assert "foundation_v10_interfoam_dambreak`（laminar interFoam baseline）" in text
    assert "不得静默升级为 RAS" in text

