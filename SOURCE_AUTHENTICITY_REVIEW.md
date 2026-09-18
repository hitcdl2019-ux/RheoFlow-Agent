# Source Authenticity Review Gate

Receipt validation proves that a requirement file passed intake and was not modified afterward. It does not prove that an upstream agent honestly labeled parameter sources. Before release, run a manual source-authenticity review.


## Standard review inputs

Use `tests/business_prompts/source_authenticity_cases.yaml` as the minimum manual review set.
Each case contains a raw business prompt, missing information, questions the agent must ask, and
source labels that must not be used for guessed values.

Suggested manual matrix:

```text
10 source-authenticity cases x each supported agent entrypoint
```

## Release gate

Review at least 10 missing-parameter business inputs for each supported agent entrypoint, for example Codex, Claude Code, OpenClaw, and CodeBuddy.

For every generated `user_requirement.txt`, verify:

- `user_provided` values were explicitly supplied by the user.
- `literature_typical` values include a source reference.
- `estimated_with_user_approval` values have explicit user approval.
- physical/rheological parameters are never hidden under `default`.
- unknown materials use behavior questions instead of fabricated model choices.

## Outcome

A release candidate is blocked if any agent mislabels guessed parameters as user-provided or omits required source references for typical values.
