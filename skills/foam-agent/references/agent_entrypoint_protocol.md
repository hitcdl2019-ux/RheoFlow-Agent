# Foam-Agent Agent Entrypoint Protocol

Use this reference when operating Foam-Agent through an interactive agent.

## Responsibility split

Interactive agents may:

- talk to the user in business language;
- inspect `knowledge/materials/*.yaml`;
- maintain `sessions/<session_id>/intent.json` if the workflow is multi-turn;
- draft `user_requirement.txt`;
- run `scripts/foamagent_intake.py --write-receipt`;
- explain `ready`, `clarify`, or `reject`.

Interactive agents must not:

- decide final OpenFOAM version, channel, or solver;
- bypass intake or manually edit receipts;
- fabricate physical parameters or source labels;
- silently switch Foundation failures to ESI runtime;
- run non-certified solvers.

## Loop

1. Capture raw business request.
2. Draft structured requirement with source labels.
3. Run intake.
4. If `clarify`, ask only business-language follow-ups.
5. If `reject`, explain unsupported capability.
6. If `ready`, use the stamped requirement for Foam-Agent execution.

`src/main.py` is batch-oriented; all clarification must happen before it runs.

## Local Codex command

Use the skill as a Chinese business-language entrypoint:

```text
$foam-agent-intake：<用户的中文业务需求>
```

The skill may run intake on the host when a Foam-Agent Python environment is available. If not, the
wrapper may execute intake inside `foamagent_dual_dev` from `foamagent-dual-openfoam:pytest-check`.
That is only an environment choice; the skill must still let Foam-Agent choose the final channel,
version, solver, and immutable `CaseTarget`.

## Status handling

- `ready`: report target preview and receipt path; continue only with the stamped requirement.
- `clarify`: stop and ask business-language questions for the missing fields.
- `reject`: explain the certified capability boundary and do not try fallback solvers or channels.

## 中文 CLI 进度展示

When the user is speaking Chinese, report Foam-Agent progress in Chinese with clear stages. Do not
dump raw Docker/API/provider setup details unless they are the blocking failure.

Use this stage board:

```text
Foam-Agent 执行进度
[0/6] 环境检查：running
[1/6] 需求理解与 Intake：pending
[2/6] 目标锁定 CaseTarget：pending
[3/6] Case 文件生成：pending
[4/6] Schema / Manifest 校验：pending
[5/6] OpenFOAM 执行：pending
[6/6] 结果检查与业务解释：pending
```

Allowed status values:

```text
pending / running / passed / clarify / rejected / failed / auto-fixing
```

Normal user-facing update:

```text
[2/6] 目标锁定 CaseTarget：passed
- channel: v10-foundation
- solver: simpleFoam
- 说明：求解器和版本由 Foam-Agent 确定，不需要用户指定
```

Clarification update:

```text
[1/6] 需求理解与 Intake：clarify
- 缺少信息：几何尺寸 / 入口速度 / 本构参数
- 需要用户确认：<用业务语言提问>
```

Failure or auto-fix update:

```text
[5/6] OpenFOAM 执行：auto-fixing
- 当前子步骤：[5.4] 求解器运行 simpleFoam
- 失败位置：simpleFoam
- 问题摘要：压力求解器发散
- 自动修复：第 3 次
- 下一步：调整 fvSolution 后重跑
- 详细日志：runs/<case>/log.simpleFoam
```

When stage `[5/6] OpenFOAM 执行` is active, expand it into substeps:

```text
[5/6] OpenFOAM 执行：running
  [5.1] 运行环境加载：passed
  [5.2] 网格生成 blockMesh：running
  [5.3] 网格质量检查 checkMesh：pending
  [5.4] 求解器运行 <solver>：pending
  [5.5] 后处理 / 结果提取：pending
  [5.6] 日志诊断 / 自动修复：pending
```

Substep meanings:

- `[5.1] 运行环境加载`: OpenFOAM channel environment is ready. Hide Docker/API details unless this fails.
- `[5.2] 网格生成 blockMesh`: mesh creation, `blockMesh`, `setFields`, or mesh conversion commands.
- `[5.3] 网格质量检查 checkMesh`: mesh-quality check or a clear note if the current workflow skips it.
- `[5.4] 求解器运行 <solver>`: run the certified solver selected by Foam-Agent.
- `[5.5] 后处理 / 结果提取`: post-processing, pressure-drop extraction, field sampling, or output summary.
- `[5.6] 日志诊断 / 自动修复`: diagnose logs and run the reviewer/rewrite loop after failures.

Successful environment setup should be collapsed to:

```text
[0/6] 环境检查：passed
- 已找到 Foam-Agent 认证运行环境
```

Do not expose these implementation details during normal operation:

- `docker exec ...`
- `NOVA_API_KEY`, `OPENAI_API_KEY`, or auth file paths
- `FOAMAGENT_MODEL_PROVIDER`, `FOAM_AGENT_CONTAINER`, or other internal env vars
- full raw logs when a short summary plus log path is enough

Expose them only when the workflow is blocked by that layer, and still avoid printing secret values.
