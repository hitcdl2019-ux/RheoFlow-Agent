# Release Notes - Dual-Channel Seven-Solver MVP

## Added

- Immutable `CaseTarget` with certified `channel`, `version`, `solver`, and `distribution`.
- Strongly typed intermediate workflow objects: `ProblemIntent`, `PhysicsSpec`, `RheologySpec`, and `WorkflowPlan`.
- Deterministic workflow compiler for the seven certified solvers.
- Channel-isolated RAG metadata audit.
- Intake gate with ready/clarify/reject output and receipt validation.
- Local premerge regression script: `scripts/run_premerge_checks.sh`.
- Business prompt expectation set with 30 workflow-routing prompts.
- Real business intake set with 40 ready/clarify/reject prompts.
- Source authenticity manual-review set with 10 missing-information prompts.
- Agent entrypoint protocol for Codex/Claude/OpenClaw/CodeBuddy-style shell entrypoints.
- Physical sanity intake guard for Newtonian `nu`/`rho`, forbidden `parameters: none required`, and high-Re turbulence clarification.
- Capability matrix and user-facing capability boundary documents.

## Certified solver matrix

See `CAPABILITY_MATRIX.md`.

## Verification

Run locally:

```bash
./scripts/run_premerge_checks.sh
```

The script performs RAG metadata audit, offline routing/manifest/business prompt/intake business/source-auth/mixed-session tests, and seven solver end-to-end regression.

## Known limitations

- No certified compressible, combustion, heat-transfer, or CHT workflows.
- No automatic ESI runtime fallback.
- No certification for solvers outside the seven-solver matrix; explicit non-whitelisted solver requests are rejected.
- Source authenticity review is a release gate for agent-generated requirements.
- Final release image should be rebuilt only after the local development cycle is complete.
