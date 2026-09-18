---
name: foam-agent
description: Draft, validate, and iterate Foam-Agent CFD requirements from business-language user requests. Use when Codex is asked to act as the human interaction entrypoint for Foam-Agent, create or refine user_requirement.txt, run foamagent_intake.py, interpret ready/clarify/reject intake output, or prepare a stamped requirement before Foam-Agent execution. Do not use for direct solver/version selection or bypassing Foam-Agent intake.
---

# Foam-Agent Intake Workflow

Use this skill to turn a user's CFD business request into a Foam-Agent `user_requirement.txt` and validate it through intake.

## Core rules

- Treat Codex as the conversation and drafting layer only.
- Prefer Foam-Agent MCP tools when available; fall back to the shell wrapper when MCP is unavailable.
- Let Foam-Agent decide final solver, OpenFOAM version, channel, and immutable `CaseTarget`.
- Never bypass `scripts/foamagent_intake.py`.
- Never invent geometry, flow conditions, constitutive parameters, material properties, or source labels.
- Never label inferred, default, or literature values as `user_provided`.
- Stop at `clarify` or `reject`; ask business-language follow-up questions instead of forcing execution.
- Report progress in Chinese by default using the stage template below. Hide Docker/API/provider details during normal operation; mention them only when they are the blocking failure.
- Never promote candidate cases into certified benchmarks automatically; require explicit user confirmation and a clean validation/coverage report.

## Workflow

1. Read references only as needed:
   - For full entry protocol, read `references/agent_entrypoint_protocol.md`.
   - For required `user_requirement.txt` fields, read `references/user_requirement_template.md`.
   - For capability boundaries and unsupported physics, read `references/capability_boundary.md`.
2. Gather the user's business problem and known facts.
3. Check materials against the repo's `knowledge/materials/*.yaml` when available.
4. Draft `user_requirement.txt` using source labels for every physical value.
5. Run intake through MCP when the Foam-Agent MCP server is available:

   ```text
   foamagent_intake(business_prompt=<draft or user_requirement text>, session_id=<session>)
   ```

   If MCP is not available, run the shell wrapper. The wrapper auto-detects common Foam-Agent repo paths, local Python environments with Foam-Agent dependencies, and the `foamagent_dual_dev` Docker container. Set `FOAM_AGENT_REPO_ROOT` only if repo auto-detection fails; set `FOAM_AGENT_PYTHON=/path/to/FoamAgent/bin/python` or `FOAM_AGENT_CONTAINER=foamagent_dual_dev` only if environment auto-detection fails:

   ```bash
   skills/foam-agent/scripts/intake_check.sh path/to/user_requirement.txt
   ```

6. Interpret intake:
   - `ready`: report the target preview and receipt path; execution may proceed through Foam-Agent.
   - `clarify`: ask the listed questions in business language and rewrite the requirement.
   - `reject`: explain the capability boundary and stop.
7. After Foam-Agent execution, run post-processing through MCP when available:

   ```text
   foamagent_postprocess(case_dir=<runs/case>, fields=["U","p","tau"])
   foamagent_artifacts(case_dir=<runs/case>)
   ```

   If MCP is unavailable, use the repo's postprocess outputs or run the shell/Python fallback.
8. Translate results back into business language and disclose assumptions.
9. After successful execution, perform the knowledge evolution check via MCP when available:

   ```text
   foamagent_case_evolution(case_dir=<runs/case>, action="evaluate")
   ```

   If MCP is unavailable, read `CASE_EVOLUTION_REPORT.json` if present, or run `scripts/capture_successful_case.py runs/<case_dir>` from the Foam-Agent repo. Report `duplicate` or `novel_candidate` in Chinese. Do not promote automatically.

## MCP tools

Use these Foam-Agent MCP tools as the stable cross-agent protocol:

- `foamagent_intake`: business prompt or `user_requirement.txt` → `ready` / `clarify` / `reject`, target preview, receipt path.
- `foamagent_postprocess`: completed case directory → `POSTPROCESS_REPORT.json`, `POSTPROCESS_SUMMARY.md`, visualizations, metrics, artifact manifest.
- `foamagent_artifacts`: completed case directory → structured artifact list without rerunning.
- `foamagent_case_evolution`: completed case directory → `duplicate` / `novel_candidate`; never promotes automatically.

Do not use MCP to bypass intake. Do not promote candidate cases through MCP; ask the user for explicit confirmation and use repository promotion tooling only if available.

## 中文阶段化进度展示

When operating in a Chinese conversation, show concise Chinese progress updates instead of raw implementation details. Use this template at the start of an intake/run and update it as the workflow advances:

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

Status words may be `pending`, `running`, `passed`, `clarify`, `rejected`, `failed`, or `auto-fixing`.

Keep user-facing updates short:

```text
[1/6] 需求理解与 Intake：passed
- intake: ready
- receipt: user_requirement.txt.intake.json
- 下一步：锁定 Foam-Agent 目标
```

For execution errors, report the current stage, the failed command or component, a plain-language reason, the auto-fix attempt number, and the next action:

```text
[5/6] OpenFOAM 执行：auto-fixing
- 当前子步骤：[5.2] 网格生成 blockMesh
- 失败位置：blockMesh
- 问题摘要：网格块顶点方向错误
- 自动修复：第 2 次
- 下一步：重写 system/blockMeshDict 后重新运行
- 详细日志：runs/<case>/log.blockMesh
```

When `[5/6] OpenFOAM 执行` is active, expand it with substeps:

```text
[5/6] OpenFOAM 执行：running
  [5.1] 运行环境加载：passed
  [5.2] 网格生成 blockMesh：running
  [5.3] 网格质量检查 checkMesh：pending
  [5.4] 求解器运行 <solver>：pending
  [5.5] 后处理 / 结果提取：pending
  [5.6] 日志诊断 / 自动修复：pending
```

Use these substeps consistently:

- `[5.1] 运行环境加载`: OpenFOAM channel environment is available, without exposing Docker/API details.
- `[5.2] 网格生成 blockMesh`: `blockMesh`, `setFields`, or mesh conversion commands.
- `[5.3] 网格质量检查 checkMesh`: `checkMesh` if available or a mesh-quality summary if skipped.
- `[5.4] 求解器运行 <solver>`: the certified solver such as `simpleFoam`, `rheoFoam`, or `interFoam`.
- `[5.5] 后处理 / 结果提取`: `postProcess`, sample extraction, pressure drop calculation, or field summary.
- `[5.6] 日志诊断 / 自动修复`: reviewer diagnosis and rewrite loop after any failure.

Do not normally show `docker exec`, `NOVA_API_KEY`, `FOAMAGENT_MODEL_PROVIDER`, `FOAM_AGENT_CONTAINER`, or raw auth paths to end users. Collapse successful environment setup into:

```text
[0/6] 环境检查：passed
- 已找到 Foam-Agent 认证运行环境
```

Only expose environment details if they are the reason the workflow is blocked.


## 知识库自进化检查

After `[6/6]` succeeds, check whether the successful case adds new knowledge before ending the workflow.

Use this user-facing block:

```text
知识库自进化检查：running
- 检查对象：runs/<case_dir>
- 规则：只在现有 RAG/benchmark 覆盖不足时进入 candidate_cases
```

Then read the existing report if it was created by Foam-Agent:

```bash
cat runs/<case_dir>/CASE_EVOLUTION_REPORT.json
```

If it is missing and the repository script exists, run:

```bash
PYTHONPATH=src python scripts/capture_successful_case.py runs/<case_dir>
```

Interpret the result:

- `duplicate`: report the nearest certified benchmark and stop; do not create or promote anything.
- `novel_candidate`: report the generated `knowledge/candidate_cases/<case_id>` path and ask for explicit user confirmation before promotion.
- validation failed: report the validation issues and stop; do not add to knowledge.

For duplicate cases, use:

```text
知识库自进化检查：duplicate
- 已有 benchmark 覆盖：<nearest_match>
- 处理：不进入 candidate_cases，不同步 RAG
```

For novel candidates, use:

```text
知识库自进化检查：novel_candidate
- 已生成候选 case：knowledge/candidate_cases/<case_id>
- 当前状态：未认证，不进入 RAG
- 下一步：如需晋级为 certified benchmark，请明确确认
```

Only after the user explicitly confirms promotion:

1. Verify the candidate path and validation report.
2. If `scripts/promote_candidate_case.py` exists, run it with the candidate path; otherwise report that promotion tooling is not yet available and stop.
3. After promotion succeeds, run `scripts/sync_benchmarks_to_rag.py --build-faiss`.
4. Report the new benchmark id and RAG sync result.

Never silently move files from `knowledge/candidate_cases/` to `knowledge/benchmarks/`. Never promote private, duplicate, failed, or source-unclear cases.

## Requirement drafting checklist

Before running intake, verify:

- Geometry has type and dimensions, or an explicitly certified benchmark geometry.
- Flow has inlet velocity, flow rate, pressure drop, or equivalent operating condition.
- Newtonian Foundation-channel cases include `nu`, `rho`, source reference, and user approval if typical values are used.
- High-Re cases do not silently pass as laminar; unresolved turbulence must remain `clarify`.
- Rheology cases include supported model and required parameters, or remain `clarify`.
- `Missing / Unconfirmed Information` is empty only when all critical data is confirmed.

## Source labels

Use only:

- `user_provided`: explicitly supplied by the user.
- `literature_typical`: sourced from a named reference, data sheet, DOI, or approved local material card.
- `estimated_with_user_approval`: explicitly approved by the user as an estimate.
- `default`: non-physical execution defaults only, such as mesh baseline or output interval.
- `unknown`: still missing; intake should return `clarify`.

Physical values such as `nu`, `rho`, `etaS`, `etaP`, `lambda`, `alpha`, `epsilon`, `tau0`, `k`, `n`, geometry dimensions, and inlet conditions must not be hidden under `default`.
