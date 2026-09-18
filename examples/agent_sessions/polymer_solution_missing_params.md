# Agent Session Example: Polymer Solution Missing Parameters

## User

I need polymer solution flow through a contraction die, but I only know the die size and inlet speed.

## Agent action

Check material cards. Polymer solution suggests viscoelastic/shear-thinning behavior, but the agent must not invent Oldroyd-B/Giesekus/PTT parameters.

## Intake expectation

```text
clarify -> constitutive_model or rheology.parameters
```

Ask:

- Do you have rheometer or data sheet data?
- Do you observe stringing, rebound, inlet swelling, or elastic effects?
- Do you want to provide a model and parameters, or approve sourced typical values?
