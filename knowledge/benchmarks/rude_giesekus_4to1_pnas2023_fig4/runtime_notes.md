# RUDE Giesekus 4:1 contraction runtime notes

This certified benchmark represents the PNAS 2023 RUDE Figure 4 native Giesekus baseline case.

## Source of truth

- DOI: `10.1073/pnas.2304669120`
- Upstream repository: `https://github.com/krlennon/rude`
- Upstream case path: `giesekus/OpenFOAM/Giesekus`

`official_case/` is the source-of-truth case snapshot. It may contain OpenFOAM dynamic-code constructs such as `codedFixedValue`.

## Local runtime adaptation

`runtime_case/` is the locally completed Foam-Agent-compatible case. It completed with:

- channel: `v9-rheotool`
- solver: `rheoFoam`
- final time: `10`
- written time directories: `0, 2, 4, 6, 8, 10`

The local runtime case may replace dynamic-code inlet/function object logic with equivalent non-dynamic dictionary forms so it can run safely in automated local environments. This is a runtime compatibility adaptation, not an upstream source file.

## Known execution constraints

- OpenFOAM dynamic-code boundary conditions such as `codedFixedValue` must not be executed as root.
- If using upstream `official_case/` unchanged, execute OpenFOAM commands as a non-root OpenFOAM user.
- `checkMesh` may report high aspect ratio cells for the contraction/corner-refined mesh; topology, non-orthogonality, and skewness should still be checked.
- Do not silently replace this benchmark with a generic rheoFoam contraction template.

## RAG usage policy

When this benchmark is retrieved exactly, Foam-Agent should import/copy the registered case files instead of regenerating the critical dictionaries from scratch. If no exact benchmark match exists, the agent must not claim paper-level reproduction.
