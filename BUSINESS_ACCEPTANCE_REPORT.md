# Business Prompt Acceptance Report

## Scope

This report covers the seven certified solver MVP:

- `v9-rheotool/rheoFoam`
- `v9-rheotool/rheoTestFoam`
- `v9-rheotool/rheoInterFoam`
- `v10-foundation/icoFoam`
- `v10-foundation/simpleFoam`
- `v10-foundation/pimpleFoam`
- `v10-foundation/interFoam`

## Acceptance inputs

Four offline acceptance sets are used:

1. `tests/test_workflow_compiler.py`
   - 35 representative prompts.
   - 30 prompts do not name a solver.
2. `tests/business_prompts/business_prompt_expectations.yaml`
   - 30 business-style prompts for deterministic `compile_workflow()` routing.
   - All prompts avoid asking users to choose OpenFOAM versions or solver channels.
3. `tests/business_prompts/real_business_prompts.yaml`
   - 40 intake-level business prompts covering `ready`, `clarify`, and `reject`.
   - Includes missing geometry, missing flow condition, missing rheology parameters, unknown material, unsupported physics, non-whitelisted solver, and automatic ESI runtime rejection.
4. `tests/business_prompts/source_authenticity_cases.yaml`
   - 10 manual-review cases for detecting dishonest source labels in agent-generated `user_requirement.txt` files.

## Covered behavior

- Newtonian steady incompressible flow -> `simpleFoam`.
- Newtonian transient incompressible flow -> `pimpleFoam`.
- Newtonian two-phase/free-surface flow -> `interFoam`.
- GNF or viscoelastic single-phase flow -> `rheoFoam`.
- Material characterization -> `rheoTestFoam`.
- Rheological two-phase/free-surface flow -> `rheoInterFoam`.
- Missing constitutive model or parameters produces clarification requirements.
- Conflicting steady/transient or Newtonian/rheological evidence is detected.
- Unsupported physics such as compressible flow, combustion, heat transfer, and thermal coupling is rejected.
- Format-complete Newtonian inputs with missing `nu`/`rho`, forbidden `parameters: none required`, or high Re without turbulence confirmation produce clarification requirements.

## Current acceptance status

The local premerge checks run:

```bash
./scripts/run_premerge_checks.sh
```

Expected result:

- RAG metadata audit: pass.
- Offline workflow/manifest/business prompt/intake business/source-auth/mixed-session/intake/material/golden tests: pass.
- Seven certified solver regression: pass.

## Limitations

This acceptance does not certify new solvers, ESI runtime compatibility, heat transfer, compressible flow, combustion, or thermal coupling. Those require separate solver-by-solver certification.

## Source authenticity

Receipt validation prevents bypass and post-intake edits, but it does not prove an agent honestly labeled parameter sources. See `SOURCE_AUTHENTICITY_REVIEW.md`; that manual review remains a release gate.
