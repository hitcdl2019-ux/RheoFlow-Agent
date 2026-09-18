# Agent Session Example: Combustion Reject

## User

Simulate combustion of fuel and air in a chamber and output flame temperature.

## Agent action

Do not route to a non-certified solver. Explain capability boundary.

## Intake expectation

```text
reject -> combustion/reacting flow outside seven-solver MVP
```

Explain:

> The current Foam-Agent MVP does not certify reacting-flow solvers such as reactingFoam or fireFoam. It cannot generate or run this case until combustion capability is separately certified.
