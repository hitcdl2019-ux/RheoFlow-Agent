# Agent Session Example: Low-Re Water Pipe Ready

## User

I want the pressure drop for water in a small pipe. Diameter is 0.001 m, length is 0.1 m, inlet velocity is 0.001 m/s. Use standard water properties at 20C.

## Agent action

Draft `user_requirement.txt` with:

- geometry: pipe, `diameter=0.001 m`, `length=0.1 m`
- flow: steady, `inlet velocity=0.001 m/s`
- material properties: `nu=1e-6 m2/s`, `rho=1000 kg/m3`
- source: `literature_typical`, standard water properties at 20C, user approved
- missing information: empty

## Intake expectation

```text
ready -> v10-foundation/simpleFoam
```
