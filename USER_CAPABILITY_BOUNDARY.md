# User Capability Boundary

Foam-Agent currently provides two certified local execution channels:

- `v9-rheotool`: rheology-focused OpenFOAM Foundation v9 + rheoTool workflows.
- `v10-foundation`: standard OpenFOAM Foundation v10 CFD workflows.

Users may describe physical problems in business language. They do not need to choose an
OpenFOAM solver or version. Solver and version selection remain deterministic inside Foam-Agent.

## Certified capabilities

| User problem type | Certified target |
|---|---|
| Newtonian steady incompressible flow | `v10-foundation/simpleFoam` |
| Newtonian transient incompressible flow | `v10-foundation/pimpleFoam` |
| Newtonian free-surface/two-phase flow | `v10-foundation/interFoam` |
| Newtonian laminar benchmark cavity flow | `v10-foundation/icoFoam` |
| GNF or viscoelastic single-phase flow | `v9-rheotool/rheoFoam` |
| Material characterization/material functions | `v9-rheotool/rheoTestFoam` |
| Rheological two-phase/free-surface flow | `v9-rheotool/rheoInterFoam` |

## Required user information

A runnable case needs, at minimum:

- geometry type and key dimensions, or an explicitly certified benchmark geometry;
- inlet velocity, flow rate, pressure drop, or equivalent operating condition;
- phase state and whether the case is steady, transient, or free-surface/two-phase;
- for rheological workflows, a supported constitutive model and required parameters.

Missing physical data is handled by `clarify`, not by fabricated defaults.

For Newtonian Foundation-channel cases, users or approved sources must provide `nu` and `rho`. If Foam-Agent can estimate Re and it exceeds the laminar threshold without confirmed turbulence treatment, intake returns `clarify` rather than silently running a likely-invalid laminar case.

Examples of required rheology parameters:

- Oldroyd-B: `etaS`, `etaP`, `lambda`.
- FENE-CR: `etaS`, `etaP`, `lambda`, `L2`.
- Giesekus: `etaS`, `etaP`, `lambda`, `alpha`.
- PTT: `etaS`, `etaP`, `lambda`, `epsilon`.
- Carreau-Yasuda: `nu0`, `nuInf`, `lambda`, `n`, `a`.
- Herschel-Bulkley: `tau0`, `k`, `n`.

## Explicitly unsupported in this MVP

The current seven-solver MVP rejects the following categories:

| Unsupported request | Typical solvers involved | Why not supported yet |
|---|---|---|
| Compressible flow | `rhoPimpleFoam`, `rhoSimpleFoam`, `sonicFoam` | No certified compressible dictionaries, schemas, prompts, benchmarks, or regression cases. |
| Combustion/reacting flow | `reactingFoam`, `fireFoam`, `rhoReactingFoam` | Requires chemistry, thermodynamics, species transport, and reacting-flow validation not present in this MVP. |
| Heat transfer | `buoyantSimpleFoam`, `buoyantPimpleFoam`, `chtMultiRegionFoam` | Temperature/energy equations and thermal boundary conditions are not certified. |
| Thermal coupling / multi-region CHT | `chtMultiRegionFoam`, `rheoMultiRegionFoam` | Multi-region coupling and region-specific dictionaries are outside the current validation chain. |
| Non-whitelisted rheoTool solvers | `rheoEFoam`, `rheoHeatFoam`, `rheoFilmFoam`, `rheoBDFoam` | They are not part of the seven certified solver matrix. |
| Automatic ESI runtime fallback | ESI OpenFOAM variants | Foundation-channel failures must not silently switch syntax or runtime. |

These are rejected because they do not yet have a complete certification chain: solver audit, RAG
metadata, schema, channel prompt, deterministic routing rule, benchmark case, and end-to-end regression.

## How to add capability later

To add a new solver or physics class, create a dedicated certification branch and add all of the following
before enabling routing:

1. solver capability entry and user-facing boundary update;
2. version/channel decision and immutable `CaseTarget` mapping;
3. RAG corpus split and metadata audit for that channel;
4. solver schema under `src/services/solver_schemas/`;
5. prompt pack for planner/input_writer/reviewer/error_fix;
6. deterministic routing and intake clarify/reject rules;
7. at least one benchmark or tutorial-derived end-to-end regression;
8. real business prompt cases that avoid naming the solver;
9. local premerge report proving the new solver passes.

Only after those steps may the solver leave the unsupported list.

## ESI boundary

ESI OpenFOAM outputs may be handled only as explicitly marked best-effort translations. Foundation-channel
failures must not silently switch to ESI syntax or ESI execution.
