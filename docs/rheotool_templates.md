# RheoTool Templates

RheoFlow-Agent uses RheoTool tutorial templates as reproducible baselines for rheological simulations. Template-baseline mode means the case inherits the original geometry, mesh, boundary conditions, operating conditions, and constitutive parameters unless the user explicitly requests and confirms allowed overrides.

## Template-baseline request pattern

```text
Use the certified RheoTool <family>/<variant> template baseline. Fully inherit the original geometry, mesh, boundary conditions, operating conditions, and constitutive parameters. Output <requested metrics>.
```

Chinese example:

```text
使用 RheoTool Channel / Oldroyd-BLog 平行板槽道流模板基线，完整继承模板原始几何、网格、边界、工况和本构参数，不修改参数。输出速度剖面和壁面剪切应力。
```

## Common template families

| Family | Typical solver | Status | Typical outputs |
|---|---|---:|---|
| Channel / Oldroyd-BLog | `rheoFoam` | Supported | Velocity profile, stress profile, pressure drop, wall shear stress. |
| Cylinder / Oldroyd-BLog | `rheoFoam` | Supported / experimental by image | Drag/lift indicators, velocity field, stress field. |
| Contraction / Oldroyd-BLog | `rheoFoam` | Supported / experimental by image | Stress concentration, pressure drop, vortex/recirculation features. |
| CrossSlot / Oldroyd-BLog | `rheoFoam` | Supported / experimental by image | Birefringent-strand-like stress structures, velocity symmetry. |
| DieSwell / Oldroyd-BLog | `rheoInterFoam` | Experimental | Free-surface contour, velocity/stress fields, swell ratio. |
| DieSwell / GiesekusLog | `rheoInterFoam` | Experimental | Free-surface contour, velocity/stress fields, swell ratio. |
| DieSwell / CarreauYasuda | `rheoInterFoam` | Experimental | Free-surface contour, velocity field, swell ratio. |

## Routing rules to preserve

- If a request explicitly names a known template id, the planner should prioritize that id over similarity search.
- `DieSwell` requests should route to `rheoInterFoam`, not `rheoFoam` channel templates.
- Template-baseline mode should not require physical parameters unless the user asks to override the template.
- Parameter override mode should require explicit review/confirmation before modifying template values.

## Case asset promotion

A successful case should only be promoted when:

1. It completed execution and post-processing.
2. Manifest and logs are consistent.
3. It is not already covered by an existing benchmark or RAG case.
4. A human reviewer explicitly confirms promotion.
