# CodeBuddy same-container integration

This integration lets CodeBuddy Code run inside the Foam-Agent runtime image and call Foam-Agent through MCP.

## Build

```bash
docker build -f docker/Dockerfile.codebuddy -t foamagent-codebuddy:dev .
```

The image extends `foamagent-dual-openfoam:v2` and adds:

- Node.js
- `@tencent-ai/codebuddy-code`
- CodeBuddy MCP config for Foam-Agent

## Run interactively

```bash
docker run --rm -it foamagent-codebuddy:dev \
  codebuddy \
  --mcp-config /opt/Foam-Agent/integrations/codebuddy/foamagent-mcp.json \
  --strict-mcp-config \
  --system-prompt-file /opt/Foam-Agent/integrations/codebuddy/FOAM_AGENT_CODEBUDDY_PROMPT.md
```

## Non-interactive smoke

```bash
docker run --rm foamagent-codebuddy:dev \
  codebuddy --version
```

Foam-Agent MCP is configured in stdio mode and uses the product-only server `src.mcp.product_server`. The MCP server starts when CodeBuddy opens the `foamagent` MCP server from `foamagent-mcp.json`. Only product tools are exposed, so CodeBuddy will call `foamagent_execute` after intake instead of legacy `plan`/`input_writer` step tools.

## Product rule

CodeBuddy is only the conversation and drafting layer. Foam-Agent intake remains the hard gate. Do not execute a case unless `foamagent_intake` returns `ready` and a receipt path. After that, use `foamagent_execute`; do not call legacy step tools directly.

## Expected CLI behavior

For every Foam-Agent request, CodeBuddy should first print a Chinese progress block:

```text
Foam-Agent 执行进度
[0/6] 环境检查：passed
[1/6] 需求理解与 Intake：running
[2/6] 目标锁定 CaseTarget：pending
[3/6] Case 文件生成：pending
[4/6] Schema / Manifest 校验：pending
[5/6] OpenFOAM 执行：pending
[6/6] 结果检查与业务解释：pending
```

If the progress block is missing, restart CodeBuddy with the documented `--system-prompt-file` argument and confirm the image contains the latest prompt.

Stage responsibilities must stay separated:

- `[0/6] 环境检查` only checks that CodeBuddy/Foam-Agent MCP tools, project paths, writable runs/sessions directories, and dual-channel runtime prerequisites are available. It must not create or claim to create `user_requirement.txt`. It must not claim a fixed Foundation OpenFOAM v10 runtime before CaseTarget is locked.
- `[1/6] 需求理解与 Intake` owns user requirement drafting, `user_requirement.txt` preparation, intake submission, and `ready` / `clarify` / `reject` reporting.
- `[2/6] 目标锁定 CaseTarget` is the only stage that reports `channel`, `version`, `solver`, and immutable CaseTarget details.

Do not describe OpenFOAM channel or solver selection as an Intake decision. Do not describe `user_requirement.txt` creation as an environment-check action.

For DOI/benchmark reproduction requests, CodeBuddy should call local Foam-Agent MCP first. It should not browse the web before `foamagent_intake`, because certified benchmark aliases are resolved from `knowledge/benchmarks/`.

## 运行目录命名

当 `foamagent_execute` 未显式传入 `output_dir` 时，Foam-Agent 会在 `runs/` 下创建新的 case 目录：

```text
runs/mcp-execute-<case-key>-<YYYYMMDD-HHMMSS>
```

`case-key` 优先来自 `session_id`，否则使用 requirement 所在 session 目录或 requirement 文件名；非法字符会被清洗。同一秒内如发生重名，会自动追加 `-002`、`-003` 等后缀。显式传入的 `output_dir` 优先级最高，不会被自动改名。
