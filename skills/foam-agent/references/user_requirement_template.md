# user_requirement.txt Template Rules

Follow the project template at `templates/user_requirement.template.txt`.

Required sections:

- Business Problem
- Material and Phases
- Fluid / Material Properties
- Geometry
- Flow Conditions
- Rheology
- Time and Numerics
- Objectives
- Defaults Applied
- Assumptions Approved by User
- Missing / Unconfirmed Information
- Intake Rule

## Critical rules

- `Missing / Unconfirmed Information` must be empty before intake can issue a ready receipt.
- Newtonian fluids still require physical properties: provide at least `nu` and `rho` with source labels.
- `parameters: none required` is invalid for Newtonian physical properties.
- If Re is high and turbulence treatment is unresolved, keep the case in `clarify`.
- Rheological cases require supported constitutive model parameters or explicit sourced/approved typical values.
- Physical values cannot be labeled `default`.
