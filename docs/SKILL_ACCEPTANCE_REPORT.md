# Foam-Agent Skill Acceptance Report

## Scope

This report covers the project-local `skills/foam-agent` Codex Skill MVP. The skill is an interactive entrypoint layer only; it does not choose final solver/version and does not bypass Foam-Agent intake.

## Acceptance criteria

- Skill folder validates with `quick_validate.py`.
- `SKILL.md` instructs agents to draft `user_requirement.txt`, run intake, and interpret `ready/clarify/reject`.
- References cover entry protocol, template rules, and capability boundaries.
- `scripts/intake_check.sh` delegates to `scripts/foamagent_intake.py --write-receipt`.
- Example sessions cover:
  - low-Re water pipe ready;
  - high-Re water pipe clarify;
  - polymer solution missing parameters clarify;
  - unknown gel clarify;
  - combustion reject.
- Skill guidance prohibits fabricated parameters and dishonest source labels.
- Skill guidance does not hard-code final solver or OpenFOAM version selection.

## Validation command

```bash
python3 /home/chendl/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/foam-agent
```

## Local regression

Run after changes:

```bash
ARTIFACT_DIR=runs/premerge-checks-011 ./scripts/run_premerge_checks.sh
```

Actual result for `LOCAL_REGRESSION_REPORT_011`:

- Skill validation: PASS.
- Skill intake wrapper smoke test: PASS.
- RAG metadata audit: PASS, `ok: true`.
- Offline tests: PASS, `73 passed, 1 warning`.
- Seven solver regression: PASS.

## Source authenticity gate

Before release, run the 10 cases in `tests/business_prompts/source_authenticity_cases.yaml` through each supported agent entrypoint and verify no guessed value is labeled `user_provided`.

## Installed skill acceptance

The project-local skill was installed to:

```text
/home/chendl/.codex/skills/foam-agent
```

Installation validation and one real business ready-path intake test are recorded in `reports/SKILL_INSTALLATION_ACCEPTANCE_001.md`.

## Repo-root auto-detection fix

After testing a fresh Codex invocation, the skill wrapper was updated so `intake_check.sh` no longer requires the current working directory to be the Foam-Agent repo. It now resolves repo root in this order:

1. `FOAM_AGENT_REPO_ROOT`, when explicitly set;
2. parent directories of the current working directory;
3. common local paths such as `/data/chendl/cfd_project/Foam-Agent`.

Validation: running the installed wrapper from `/tmp` without `FOAM_AGENT_REPO_ROOT` successfully produced `ready` and a receipt for the low-Re water microtube request.
