# Quick Start

This guide describes a minimal local workflow for the open-source baseline.


## Runtime choice

Choose the runtime channel according to the case type:

- Use `v9-rheotool` for RheoTool rheology cases, including polymer/viscoelastic channel flow and DieSwell.
- Use `v10-foundation` for standard Foundation OpenFOAM tutorial baselines such as cavity, pitzDaily, and damBreak.

The runtime is locked by Foam-Agent during intake/planning; do not mix files or solvers across channels.

## 1. Prepare runtime dependencies

RheoFlow-Agent expects an OpenFOAM runtime. Rheology examples additionally require a compatible RheoTool installation.

The exact runtime is environment-specific. A typical development setup uses:

- Python 3.10+
- OpenFOAM Foundation or a compatible OpenFOAM distribution
- RheoTool for viscoelastic / rheological solvers
- Optional: FAISS database rebuilt from local reference data

## 2. Install Python package

```bash
git clone https://github.com/hitcdl2019-ux/RheoFlow-Agent.git
cd RheoFlow-Agent
pip install -e .
```

For a Conda-based environment:

```bash
conda env create -f environment.yml
conda activate FoamAgent
pip install -e .
```

The historical Conda environment name may still be `FoamAgent` for compatibility.

## 3. Configure model provider

Example OpenAI-compatible / gateway-style configuration:

```bash
export FOAMAGENT_MODEL_PROVIDER="novaapi"
export FOAMAGENT_MODEL_VERSION="your-model-name"
export NOVA_API_KEY="your-private-key"
export NOVA_API_BASE_URL="https://your-provider.example/v1"
```

Do not commit real API keys.

## 4. Run MCP server

```bash
rheoflow-agent-mcp --transport stdio
```

Legacy command kept for compatibility:

```bash
foamagent-mcp --transport stdio
```

## 5. Example request

For the most stable first run, use a template-baseline request:

```text
Use the certified RheoTool Channel / Oldroyd-BLog parallel-plate template baseline. Fully inherit the template geometry, mesh, boundary conditions, operating conditions, and constitutive parameters. Output velocity profile and wall shear stress.
```

In Chinese:

```text
使用平台已有 RheoTool Channel / Oldroyd-BLog 平行板槽道流模板基线，完整继承模板原始几何、网格、边界、工况和本构参数，不修改参数。输出速度分布和壁面剪切应力。
```

## 6. Outputs

Typical outputs are written under `runs/<case-name>/`:

```text
workflow.log
manifest.json
log.<solver>
POSTPROCESS_REPORT.json
POSTPROCESS_SUMMARY.md
FINAL_REPORT.docx
postprocess/
```

`runs/` is intentionally ignored by Git.
