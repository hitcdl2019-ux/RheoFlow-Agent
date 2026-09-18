# Agent Session Example: Unknown Gel Clarify

## User

A new gel flows through a microchannel. I know the channel size and inlet velocity but not the rheology.

## Agent action

Do not reject only because the material card is missing. Ask behavior questions.

## Intake expectation

```text
clarify -> material.behavior
```

Ask:

- Does it flow like water?
- Does it become thinner at higher shear?
- Does it have yield behavior?
- Does it rebound, string, or swell at the outlet?
- Is there a data sheet, grade, concentration, or rheometer dataset?
