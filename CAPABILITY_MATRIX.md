# Certified Solver Capability Matrix

This release certifies two isolated OpenFOAM execution channels. Requests outside
this matrix must be rejected or handled as explicitly marked best-effort
translation; they must not fall back across channels.

Image:

```text
foamagent-dual-openfoam@sha256:c15f3b22d2bcc648b95ae0e2ef929bfb88723eb901b51de4e1b2719945650e5d
```

## Certified channels

| Channel | Version | Solver | Certified workflow |
|---|---|---|---|
| v9-rheotool | v9 | rheoFoam | Rheological single-phase flow: GNF and viscoelastic |
| v9-rheotool | v9 | rheoTestFoam | Material characterization and material functions |
| v9-rheotool | v9 | rheoInterFoam | Rheological two-phase/free-surface flow |
| v10-foundation | v10 | icoFoam | Newtonian laminar transient benchmark flow |
| v10-foundation | v10 | simpleFoam | Newtonian steady incompressible flow |
| v10-foundation | v10 | pimpleFoam | Newtonian transient incompressible flow |
| v10-foundation | v10 | interFoam | Newtonian two-phase/free-surface flow |

## Routing policy

- Newtonian steady incompressible flow -> `v10-foundation/simpleFoam`
- Newtonian transient incompressible flow -> `v10-foundation/pimpleFoam`
- Newtonian two-phase/free-surface flow -> `v10-foundation/interFoam`
- GNF or viscoelastic single-phase flow -> `v9-rheotool/rheoFoam`
- Material characterization -> `v9-rheotool/rheoTestFoam`
- Rheological two-phase/free-surface flow -> `v9-rheotool/rheoInterFoam`
- Uncertified solvers and unsupported physics -> reject with a clear reason

## Explicitly rejected examples

| Request class | Examples |
|---|---|
| Compressible flow | `rhoPimpleFoam`, `rhoSimpleFoam`, `sonicFoam` |
| Combustion/reacting flow | `reactingFoam`, `fireFoam`, `rhoReactingFoam` |
| Heat transfer / CHT | `buoyantSimpleFoam`, `chtMultiRegionFoam` |
| Non-certified rheoTool solvers | `rheoEFoam`, `rheoHeatFoam`, `rheoFilmFoam`, `rheoBDFoam` |
| Automatic ESI runtime fallback | Any request to silently switch Foundation failures to ESI execution |

## Guardrails

- `CaseTarget` is immutable after workflow compilation.
- Missing constitutive parameters require clarification; they must not be fabricated.
- Cross-channel RAG fallback is forbidden.
- Reviewer and rewrite steps must preserve the original `CaseTarget` and rerun Manifest/Schema validation.
