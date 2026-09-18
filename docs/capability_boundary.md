# Capability Boundary

RheoFlow-Agent is not a general-purpose promise to solve any CFD problem from one sentence. It is strongest when a request can be mapped to a validated template, benchmark, or clearly supported solver workflow.


## Runtime channels

RheoFlow-Agent separates supported cases by runtime channel:

- `v9-rheotool`: OpenFOAM Foundation v9 + RheoTool for rheological and viscoelastic workflows.
- `v10-foundation`: OpenFOAM Foundation v10 for standard Newtonian tutorial-style workflows.

See [OpenFOAM Runtime Matrix](openfoam_runtime_matrix.md) for the detailed solver/scenario mapping.

## Supported with higher confidence

| Area | Status | Notes |
|---|---:|---|
| RheoTool template import | Supported | Uses the `v9-rheotool` channel; template-baseline mode is preferred for reproducibility. |
| Oldroyd-B / Oldroyd-BLog channel flow | Supported | Stable demo and validation case. |
| Confined cylinder / contraction / cross-slot style RheoTool tutorials | Supported / experimental by case | Depends on template availability and runtime compatibility. |
| Die swell tutorial family | Experimental | Requires `rheoInterFoam`, free-surface post-processing, and correct template routing. |
| Foundation OpenFOAM v10 tutorial-style cases | Supported / experimental by solver | Uses the `v10-foundation` channel; not a RheoTool rheology route. |
| Post-processing reports | Supported | JSON/Markdown/report artifacts are produced when case execution succeeds. |
| Case evolution check | Supported | Promotion to certified benchmark requires human confirmation. |

## Requires clarification

RheoFlow-Agent should ask for more information when the request lacks critical physical inputs and does not explicitly select a template baseline.

Examples:

- Missing material model or rheological parameters for non-template rheology cases.
- Missing inlet velocity, flow rate, pressure drop, or equivalent operating condition.
- Ambiguous geometry without template reference.
- Turbulence request without model, Reynolds number, or clear solver family.
- Parameter override request that needs white-list confirmation.

## Not guaranteed

- Arbitrary industrial CAD meshing without a prepared meshing pipeline.
- High-Weissenberg viscoelastic cases without numerical-stability review.
- Unvalidated solver/model combinations.
- Automatic certification of new benchmark cases.
- Uploading artifacts to private object storage unless the target platform supplies credentials and upload tools.

## Recommended demo cases

For live demonstrations, start with:

1. Oldroyd-BLog parallel-plate channel template baseline.
2. Foundation damBreak-style free-surface baseline, if runtime is available.
3. Confined cylinder or contraction RheoTool tutorial, if already validated in the image.

Use DieSwell only when the installed image has verified `rheoInterFoam` routing and post-processing for the target template.
