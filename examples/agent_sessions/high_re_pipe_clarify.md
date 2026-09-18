# Agent Session Example: High-Re Pipe Clarify

## User

I want pressure drop for water in a pipe. Diameter is 0.1 m, length is 10 m, inlet velocity is 1 m/s. Use standard water properties at 20C.

## Agent action

Drafting is allowed, but do not mark ready unless turbulence treatment is confirmed.

Estimated:

```text
Re = U D / nu = 1 * 0.1 / 1e-6 = 100000
```

## Intake expectation

```text
clarify -> physics.reynolds_number
```

Ask in business language:

> This looks turbulent. Should we use a certified turbulence treatment, or should the speed/pipe size/properties be changed for a laminar validation case?
