# Foam-Agent Capability Boundary

Certified targets only:

- `v9-rheotool/rheoFoam`: GNF or viscoelastic single-phase flow.
- `v9-rheotool/rheoTestFoam`: material characterization and material functions.
- `v9-rheotool/rheoInterFoam`: rheological two-phase/free-surface flow.
- `v10-foundation/icoFoam`: Newtonian laminar benchmark cavity flow.
- `v10-foundation/simpleFoam`: Newtonian steady incompressible flow.
- `v10-foundation/pimpleFoam`: Newtonian transient incompressible flow.
- `v10-foundation/interFoam`: Newtonian two-phase/free-surface flow.

Reject or clarify unsupported requests:

- compressible flow (`rhoPimpleFoam`, `rhoSimpleFoam`, `sonicFoam`);
- combustion/reacting flow (`reactingFoam`, `fireFoam`, `rhoReactingFoam`);
- heat transfer or CHT (`buoyantSimpleFoam`, `chtMultiRegionFoam`);
- non-certified rheoTool solvers (`rheoEFoam`, `rheoHeatFoam`, `rheoFilmFoam`, `rheoBDFoam`);
- automatic ESI runtime fallback.

Do not expand capability from the skill. New solvers require separate Foam-Agent certification.
