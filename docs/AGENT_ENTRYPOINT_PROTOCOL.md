# Agent Entrypoint Protocol

This protocol defines how Codex, Claude Code, OpenClaw, CodeBuddy, or another
interactive agent may drive Foam-Agent during local development.

## Responsibility split

Interactive agents may:

- talk to the user in business language;
- read `AGENT_INTAKE_PROMPT.md` and material cards under `knowledge/materials/`;
- maintain `sessions/<session_id>/intent.json` across turns;
- ask clarification questions;
- generate `user_requirement.txt` from confirmed information;
- call `scripts/foamagent_intake.py --write-receipt`;
- translate final run results back into business language.

Interactive agents must not:

- make the final OpenFOAM version or solver decision;
- bypass `scripts/foamagent_intake.py`;
- edit `CaseTarget` or receipt files manually;
- invent constitutive parameters, geometry dimensions, flow rates, or source labels;
- relabel inferred/default/literature values as `user_provided`;
- fall back across OpenFOAM channels or run unsupported solvers.

Foam-Agent owns the deterministic backend:

```text
user_requirement.txt
  -> foamagent_intake.py
  -> ready / clarify / reject
  -> src/main.py receipt check
  -> compile_workflow()
  -> immutable CaseTarget
  -> channel-isolated RAG, dictionary generation, validation, execution
```

## Required interaction loop

1. Read prior state from `sessions/<session_id>/intent.json` if it exists.
2. Collect the user's raw business request.
3. Match known materials against `knowledge/materials/*.yaml`.
4. Ask only business-language questions for missing information.
5. Write a standard `user_requirement.txt` using `templates/user_requirement.template.txt`.
6. Run:

   ```bash
   python scripts/foamagent_intake.py user_requirement.txt --write-receipt
   ```

7. If intake returns `clarify`, ask the listed questions and rewrite the requirement.
8. If intake returns `reject`, explain the capability boundary and stop.
9. If intake returns `ready`, run Foam-Agent only with the stamped requirement file.
10. After execution, summarize results in business language and disclose assumptions.

## Local Codex skill usage

For local single-user development, Codex may be used as the human interaction entrypoint through:

```text
$foam-agent-intake：<用户的中文业务需求>
```

The skill must draft or update `user_requirement.txt`, then call the intake wrapper rather than calling
`src/main.py` directly. The wrapper may run on the host if a Foam-Agent Python environment is available;
otherwise it may execute inside the certified dual-channel container:

```text
foamagent_dual_dev
image: foamagent-dual-openfoam:pytest-check
```

This container selection is only an execution-environment choice for intake. It must not be used as a
place for the interactive agent to choose OpenFOAM version, channel, or solver. Those decisions remain
inside Foam-Agent's deterministic `compile_workflow()` and immutable `CaseTarget`.

## Intake status handling

Interactive agents must handle intake's three statuses as follows:

- `ready`: report the target preview and receipt path, then use the stamped requirement for Foam-Agent
  execution if the user asks to proceed.
- `clarify`: stop execution and ask the missing items in business language. Do not convert unknown
  dimensions, flow rates, material behavior, rheology parameters, density, or viscosity into defaults.
- `reject`: explain the capability boundary and stop. Do not try another solver, channel, OpenFOAM
  distribution, or ESI fallback.

## `user_requirement.txt` source labels

Every numeric or physics-critical value must carry one of these labels:

- `user_provided`: explicitly supplied by the user in this session.
- `default`: a non-physical execution default, such as output interval or coarse mesh.
- `inferred`: inferred from a material card or deterministic rule and still needs disclosure.
- `literature_typical`: sourced from a named reference, DOI, data sheet, or approved local card.
- `estimated_with_user_approval`: a typical or estimated value explicitly approved by the user.
- `unknown`: required but not yet known; intake should return `clarify`.

Physical parameters such as `etaS`, `etaP`, `lambda`, `alpha`, `epsilon`, `tau0`, `k`,
`n`, `nu0`, `nuInf`, `L2`, density, viscosity, geometry dimensions, and inlet/flow
conditions must never be hidden under `default`.

## Material unknown fallback

An unknown material is not an automatic rejection. The agent should ask behavior questions:

- Does it flow like water?
- Does it become thinner when sheared faster?
- Does it have yield behavior?
- Does it rebound, string, swell at the outlet, or show elastic memory?
- Is there a data sheet, grade, concentration, or rheometer dataset?

Only Foam-Agent's intake/compile stage may convert the confirmed behavior into a certified workflow.

## Batch boundary

`src/main.py` is batch-oriented. It must not ask follow-up questions. All clarification happens before
`src/main.py`, inside the agent/intake loop. A missing or mismatched intake receipt must stop execution.
