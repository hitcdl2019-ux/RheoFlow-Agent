# RheoFlow-Agent MCP Server

Expose OpenFOAM/RheoTool CFD simulation as tools for any AI coding assistant via [MCP (Model Context Protocol)](https://modelcontextprotocol.io/).

> **OpenFOAM runtime channels:** RheoFlow-Agent separates `v9-rheotool` for OpenFOAM Foundation v9 + RheoTool rheology workflows and `v10-foundation` for Foundation OpenFOAM v10 tutorial-style CFD baselines. See `docs/openfoam_runtime_matrix.md` for the solver/scenario mapping. If `FOAMAGENT_OPENFOAM_FORK=esi` is set, generated files may be translated to ESI OpenFOAM naming on a best-effort basis; verify each case locally.

## Quick Start

### 1. Install

```bash
# Clone and install
git clone https://github.com/hitcdl2019-ux/RheoFlow-Agent.git
cd RheoFlow-Agent
pip install -e .
```

Or with conda (full environment including PyTorch, FAISS, etc.):

```bash
conda env create -f environment.yml
conda activate FoamAgent
pip install -e .
```

### 2. Register with your AI tool (one command)

**Claude Code:**
```bash
claude mcp add rheoflow-agent -- rheoflow-agent-mcp
```

**Cursor:**
Add to `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "foamagent": {
      "command": "rheoflow-agent-mcp"
    }
  }
}
```

**Windsurf / Other MCP-compatible tools:**
```json
{
  "mcpServers": {
    "foamagent": {
      "command": "rheoflow-agent-mcp"
    }
  }
}
```

**HTTP mode** (for web clients or remote access):
```bash
rheoflow-agent-mcp --transport http --host 0.0.0.0 --port 7860
```

### 3. Configure LLM provider (optional)

Set environment variables to choose your LLM backend:

```bash
export FOAMAGENT_MODEL_PROVIDER=anthropic          # openai, anthropic, bedrock, ollama
export FOAMAGENT_MODEL_VERSION=claude-sonnet-4-6   # model identifier
export ANTHROPIC_API_KEY=sk-ant-...                # API key for your provider
```

## Available MCP Tools

RheoFlow-Agent locks either the `v9-rheotool` or `v10-foundation` channel before case generation. If
`FOAMAGENT_OPENFOAM_FORK=esi` is set for generated Foundation cases, generated input files may be translated to ESI OpenFOAM
conventions on a best-effort basis before they are returned.

| Tool | Description |
|------|-------------|
| `plan` | Analyze user requirements and plan simulation structure, including channel, solver, domain, and subtasks |
| `input_writer` | Generate OpenFOAM configuration files; optionally translate generated files when `FOAMAGENT_OPENFOAM_FORK=esi` |
| `run` | Execute Allrun script locally with error collection for the locked runtime channel |
| `review` | Analyze simulation errors and suggest fixes via LLM using the locked runtime channel context |
| `apply_fixes` | Rewrite OpenFOAM files based on review analysis; ESI cases remain best-effort |
| `visualization` | Generate PyVista visualization of simulation results |

## Typical Workflow

Once registered, ask your AI assistant naturally:

> "Simulate lid-driven cavity flow at Re=1000"

The assistant will call the tools in sequence:
1. **plan** - Parse requirements, select solver, generate subtasks
2. **input_writer** - Generate all OpenFOAM files
3. **run** - Execute the simulation
4. **review + apply_fixes** - Fix errors if any (automatic retry loop)
5. **visualization** - Render results

## Prerequisites

- **Python 3.10+** with dependencies installed
- **OpenFOAM Foundation v10** for `v10-foundation` standard CFD templates, and **OpenFOAM Foundation v9 + RheoTool** for `v9-rheotool` rheology templates. ESI OpenFOAM generation is best-effort and should be verified per case.
- An LLM API key (OpenAI, Anthropic, or local via Ollama)

## Architecture

```
AI Tool (Claude Code / Cursor / ...)
    ↓ MCP protocol (stdio or HTTP)
foamagent-mcp (this server)
    ↓
Service Layer (src/services/*.py)
    ↓
OpenFOAM + LLM Services
```

## Advanced Configuration

| Environment Variable | Purpose | Default |
|---------------------|---------|---------|
| `FOAMAGENT_MODEL_PROVIDER` | LLM backend | `openai-codex` |
| `FOAMAGENT_MODEL_VERSION` | Model identifier | `gpt-5.3-codex` |
| `FOAMAGENT_EMBEDDING_PROVIDER` | Embedding backend | `huggingface` |
| `FOAMAGENT_EMBEDDING_MODEL` | Embedding model | `Qwen/Qwen3-Embedding-0.6B` |
| `FOAMAGENT_OPENFOAM_FORK` | OpenFOAM target fork for generated files: `foundation` or `esi` | `foundation` |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `NOVA_API_KEY` | NovaAPI key for `FOAMAGENT_MODEL_PROVIDER=novaapi` | — |
| `ANTHROPIC_API_KEY` | Anthropic API key | — |

## Troubleshooting

**Import errors:** Ensure you ran `pip install -e .` from the repo root.

**Database errors:** The FAISS indices ship pre-built in `database/faiss/`. If missing, rebuild with:
```bash
python init_database.py --openfoam_path $WM_PROJECT_DIR --force
```

**OpenFOAM not found:** Install the runtime required by the locked channel: Foundation OpenFOAM v10 for `v10-foundation`, or Foundation OpenFOAM v9 plus RheoTool for `v9-rheotool`. If using ESI OpenFOAM, set `FOAMAGENT_OPENFOAM_FORK=esi` and verify the generated case against your local ESI installation.
```bash
docker build -f docker/Dockerfile -t foamagent:latest .
docker run -it -p 7860:7860 foamagent:latest foamagent-mcp --transport http
```
