# OpenFOAM Runtime Matrix

RheoFlow-Agent uses two runtime channels. They are not interchangeable: each channel targets a different OpenFOAM/RheoTool stack and a different class of simulation cases.

## Channel summary

| Channel | Runtime | Main purpose | Typical solvers | Typical cases |
|---|---|---|---|---|
| `v9-rheotool` | OpenFOAM Foundation v9 + RheoTool | Rheological and viscoelastic flows | `rheoFoam`, `rheoInterFoam`, `rheoTestFoam` | Oldroyd-B channel, confined cylinder, contraction, cross-slot, rheometer/material tests, impacting drop, DieSwell |
| `v10-foundation` | OpenFOAM Foundation v10 | General OpenFOAM tutorial and Newtonian CFD baselines | `icoFoam`, `simpleFoam`, `pimpleFoam`, `pisoFoam`, `potentialFoam`, `scalarTransportFoam`, `interFoam`, `rhoCentralFoam`, `rhoPimpleFoam`, `buoyantFoam` | cavity, pitzDaily, damBreak, capillaryRise, wave, sloshingCylinder, airFoil2D, shockTube, forwardStep, BernardCells |

## v9-rheotool: rheology-focused channel

Use this channel when the request involves non-Newtonian or viscoelastic rheology and RheoTool-specific solvers or boundary conditions.

| Scenario | Solver | Status |
|---|---|---:|
| Single-phase viscoelastic channel / cavity / contraction / cylinder / cross-slot | `rheoFoam` | Supported by registered templates where available |
| Rheometer or material-function tests | `rheoTestFoam` | Supported by registered templates where available |
| Viscoelastic two-phase / free-surface flows, such as impacting drop or die swell | `rheoInterFoam` | Experimental; requires template and post-processing validation |

Typical models include:

- Oldroyd-B / Oldroyd-BLog
- Giesekus / GiesekusLog
- FENE-CR
- Herschel-Bulkley
- Carreau-Yasuda

## v10-foundation: general CFD baseline channel

Use this channel for standard Foundation OpenFOAM tutorial-style cases that do not require RheoTool.

| Scenario | Solver | Status |
|---|---|---:|
| Lid-driven cavity / low-Re incompressible transient flow | `icoFoam` | Supported |
| Steady incompressible internal/external flow | `simpleFoam` | Supported by registered templates |
| Transient incompressible laminar or RAS cases | `pimpleFoam` | Supported / experimental by template |
| Potential-flow initialization or baseline cases | `potentialFoam` | Supported by registered templates |
| Scalar transport tutorial variants | `scalarTransportFoam` | Supported / experimental by template |
| Newtonian free-surface cases such as damBreak, capillary rise, waves | `interFoam` | Supported by registered templates |
| Compressible tutorial baselines such as shock tube / forward step | `rhoCentralFoam`, `rhoPimpleFoam` | Experimental; verify case by case |
| Buoyant heat-transfer tutorial baselines | `buoyantFoam` | Experimental; verify case by case |

## Routing rule of thumb

- If the request is about **polymer solution/melt, viscoelastic stress, relaxation time, Oldroyd-B, Giesekus, FENE-CR, Herschel-Bulkley, Carreau-Yasuda**, route to `v9-rheotool`.
- If the request is about **standard Newtonian OpenFOAM tutorials**, route to `v10-foundation`.
- If the request is about **free surface**:
  - Newtonian water/air free surface usually routes to `v10-foundation/interFoam`.
  - Viscoelastic/rheological free surface usually routes to `v9-rheotool/rheoInterFoam`.
- Do not silently substitute a v10 Newtonian case for a v9 RheoTool case, or a v9 rheology case for a v10 Foundation case.

## Examples

| User intent | Expected channel | Expected solver |
|---|---|---|
| Polymer solution between two parallel plates, velocity profile and wall shear stress | `v9-rheotool` | `rheoFoam` |
| Oldroyd-B confined cylinder flow | `v9-rheotool` | `rheoFoam` |
| Polymer melt extrudate swell / DieSwell with free surface | `v9-rheotool` | `rheoInterFoam` |
| Water damBreak free-surface tutorial | `v10-foundation` | `interFoam` |
| Lid-driven cavity baseline | `v10-foundation` | `icoFoam` |
| pitzDaily steady incompressible baseline | `v10-foundation` | `simpleFoam` |
| pitzDaily RAS transient variant | `v10-foundation` | `pimpleFoam` |

## Implementation note

The `CaseTarget` should lock the channel before case generation. Once locked, downstream steps should not fall back to another OpenFOAM version or solver family unless the intake/planner explicitly re-runs and records a new target.
