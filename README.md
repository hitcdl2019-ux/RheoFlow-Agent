# RheoFlow-Agent

RheoFlow-Agent is an AI-assisted OpenFOAM/RheoTool workflow framework focused on rheology CFD simulation, validated templates, automated execution, post-processing, and case-asset evolution.

The project is designed around reproducible CFD workflows rather than unconstrained file generation. It emphasizes certified templates, explicit intake validation, solver/channel routing, manifest checks, OpenFOAM execution, and engineering-style result reporting.

## What it does

- Converts business-language CFD/rheology requests into structured simulation requirements.
- Routes cases to supported OpenFOAM / RheoTool workflows.
- Generates or imports case files from validated templates.
- Runs OpenFOAM solvers and records execution artifacts.
- Produces post-processing summaries, plots, reports, and case manifests.
- Evaluates whether successful cases should become reusable case assets.

## Current focus

RheoFlow-Agent is currently focused on template-driven and validation-driven workflows, including examples such as:

- Oldroyd-B / Oldroyd-BLog parallel-plate channel flow
- Confined cylinder flow
- Dam-break style free-surface examples
- Die swell / extrudate swell templates where supported by the runtime image
- Foundation OpenFOAM tutorial-style baseline cases

> Capability depends on the installed OpenFOAM/RheoTool runtime, available template assets, and configured model provider.


## Documentation

- [Quick Start](docs/quickstart.md)
- [Architecture](docs/architecture.md)
- [OpenFOAM Runtime Matrix](docs/openfoam_runtime_matrix.md)
- [Capability Boundary](docs/capability_boundary.md)
- [Provider Configuration](docs/provider_config.md)
- [RheoTool Templates](docs/rheotool_templates.md)
- [Benchmark and Validation Plan](docs/benchmark.md)


## OpenFOAM runtime channels

RheoFlow-Agent distinguishes two runtime channels:

| Channel | Runtime | Primary use |
|---|---|---|
| `v9-rheotool` | OpenFOAM Foundation v9 + RheoTool | Rheological / viscoelastic workflows such as Oldroyd-B channel flow, cylinder, contraction, cross-slot, rheometer tests, impacting drop, and DieSwell. |
| `v10-foundation` | OpenFOAM Foundation v10 | Standard Newtonian OpenFOAM tutorial baselines such as cavity, pitzDaily, damBreak, capillary rise, wave, airFoil2D, shock tube, and related Foundation cases. |

See [OpenFOAM Runtime Matrix](docs/openfoam_runtime_matrix.md) for the detailed solver and scenario mapping.

## Repository layout

```text
src/                    Core services, MCP server, planning, validation, execution helpers
scripts/                Utility scripts and validation helpers
templates/              Case/report templates where applicable
knowledge/              Public benchmark/case metadata
database/               RAG source data and generated-index placeholders
docs/                   Project documentation
integrations/           Example MCP integration configs
tests/                  Regression and unit tests
THIRD_PARTY_NOTICES.md  Third-party open-source notices
```

## Configuration

LLM/API credentials should be supplied through environment variables or private local configuration. Do not commit secrets.

Common environment variables include:

```bash
export FOAMAGENT_MODEL_PROVIDER="novaapi"
export FOAMAGENT_MODEL_VERSION="your-model-name"
export NOVA_API_KEY="..."
export NOVA_API_BASE_URL="https://example.com/v1"
```

The historical `FOAMAGENT_*` environment-variable prefix is retained for compatibility. A future release may introduce `RHEOFLOW_AGENT_*` aliases.

## MCP usage

The project exposes an MCP server entrypoint. The legacy command name is currently retained for compatibility:

```bash
foamagent-mcp
```

A RheoFlow-branded alias is also provided when installed from this repository:

```bash
rheoflow-agent-mcp
```

Example MCP config files are under `integrations/`. Replace all provider keys and URLs with your own private values.

## Data and generated artifacts

Prebuilt FAISS/vector indices and runtime outputs are intentionally excluded from Git:

```text
database/faiss/
database/v10-foundation/faiss/
runs/
sessions/
```

Rebuild generated indices from the documented data-preparation workflow before enabling RAG retrieval in a fresh environment.

## License and notices

See `LICENSE` and `THIRD_PARTY_NOTICES.md`.
