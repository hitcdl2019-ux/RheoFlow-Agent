# Benchmark and Validation Plan

RheoFlow-Agent should be evaluated with reproducible cases rather than broad claims. The initial benchmark suite can be named `RheoFlow-Bench`.

## Suggested benchmark dimensions

| Metric | Meaning |
|---|---|
| Intake pass/clarify/reject accuracy | Whether missing information and unsupported requests are handled correctly. |
| Template routing accuracy | Whether the selected template and solver match the intended case. |
| Case generation success | Whether required OpenFOAM dictionaries are generated or imported correctly. |
| Schema / manifest validity | Whether preflight checks pass before execution. |
| Solver success rate | Whether OpenFOAM/RheoTool runs complete without fatal errors. |
| Post-processing completeness | Whether required figures, metrics, JSON, Markdown, and report artifacts are created. |
| Physical sanity | Whether key metrics match analytical results or trusted references within expected tolerance. |

## Initial cases

| Case | Purpose | Expected check |
|---|---|---|
| Oldroyd-BLog channel baseline | Stable rheology demo | Velocity profile and wall shear stress agree with reference/analytic values. |
| Confined cylinder | Viscoelastic benchmark routing | Correct template and solver selection; valid stress/velocity output. |
| DamBreak | Free-surface baseline | Interface motion and field outputs generated. |
| DieSwell / Oldroyd-BLog | Free-surface rheology | Correct `rheoInterFoam` route; swell ratio extracted. |
| Cavity or pitzDaily | Foundation OpenFOAM baseline | Foundation solver setup and logs complete. |

## Reporting template

Each benchmark run should record:

```text
case_id
request_text
selected_solver
selected_template_or_generation_mode
run_status
validation_status
postprocess_status
key_metrics
known_limitations
artifact_paths
```

## Release policy

Do not advertise aggregate success rates until the benchmark suite, runtime image, provider configuration, and scoring rules are published or reproducibly documented.
