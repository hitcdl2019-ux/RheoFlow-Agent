# ARX integration for Foam-Agent

This directory contains the ARX-side integration files for calling Foam-Agent through the product MCP server.

## Files

- `foamagent-mcp.json`: MCP server config that starts `src.mcp.product_server` in stdio mode.
- `FOAM_AGENT_ARX_PROMPT.md`: ARX system/skill prompt that restores Foam-Agent progress display and intake discipline.

## Why this exists

The old CodeBuddy progress UI was partly implemented in the CodeBuddy prompt and frontend behavior.  When another agent such as ARX only mounts the Foam-Agent MCP server, those prompt/UI rules are not automatically inherited.

Foam-Agent now exposes a backend-neutral progress protocol through `foamagent_execute_status`:

- `progress_events`: structured stage/substep events for page components;
- `rendered_progress`: canonical Chinese text block for text-only agents.

ARX should render `progress_events` when it has a UI component, or directly show `rendered_progress` as a fallback.

## Minimal ARX setup

Mount the Foam-Agent repository in the container as `/opt/Foam-Agent`, then configure ARX to use:

```text
/opt/Foam-Agent/integrations/arx/foamagent-mcp.json
/opt/Foam-Agent/integrations/arx/FOAM_AGENT_ARX_PROMPT.md
```

Environment variables such as `FOAMAGENT_MODEL_PROVIDER`, `FOAMAGENT_MODEL_VERSION`, `NOVA_API_KEY`, and `NOVA_API_BASE_URL` should be injected by the deployment system, not hardcoded in this repository.

## Required runtime behavior

1. Start with the `[0/6]...[6/6]` progress block.
2. Use `foamagent_intake` as the hard gate.
3. On `clarify`, stop and ask business-language questions.
4. On `ready`, call `foamagent_execute(background=true)`.
5. Poll `foamagent_execute_status`; render `progress_events` or `rendered_progress`.
6. Run postprocess/artifacts/case_evolution only after execution passes.

## Runs directory naming

When `foamagent_execute` is called without an explicit `output_dir`, Foam-Agent creates a fresh case directory under `runs/` using:

```text
runs/mcp-execute-<case-key>-<YYYYMMDD-HHMMSS>
```

`case-key` comes from `session_id` when provided; otherwise it falls back to the requirement session directory or requirement filename.  Unsafe characters are sanitized.  If the same directory already exists within the same second, Foam-Agent appends `-002`, `-003`, and so on.  An explicit `output_dir` always has highest priority and is not renamed.
