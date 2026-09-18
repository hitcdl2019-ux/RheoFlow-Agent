"""Product-only Foam-Agent MCP server for external agent entrypoints.

This server intentionally exposes only the stable Foam-Agent product tools used
by human-facing agents such as CodeBuddy. It hides the legacy step tools
(`plan`, `input_writer`, `run`, `review`, `apply_fixes`, `visualization`) because
those tools may invoke Foam-Agent's internal LLM provider and require separate
server-side credentials.
"""

from __future__ import annotations

import argparse

from fastmcp import Context, FastMCP

from .fastmcp_server import (
    FoamAgentArtifactsRequest,
    FoamAgentArtifactsResponse,
    FoamAgentCaseEvolutionRequest,
    FoamAgentCaseEvolutionResponse,
    FoamAgentExecuteRequest,
    FoamAgentExecuteResponse,
    FoamAgentExecuteStatusRequest,
    FoamAgentExecuteStatusResponse,
    FoamAgentIntakeRequest,
    FoamAgentIntakeResponse,
    FoamAgentPostprocessRequest,
    FoamAgentPostprocessResponse,
    foamagent_artifacts as _foamagent_artifacts,
    foamagent_case_evolution as _foamagent_case_evolution,
    foamagent_execute as _foamagent_execute,
    foamagent_execute_status as _foamagent_execute_status,
    foamagent_intake as _foamagent_intake,
    foamagent_postprocess as _foamagent_postprocess,
)

mcp = FastMCP(
    name="Foam-Agent Product Entry",
    version="1.0.0",
    instructions="""
Foam-Agent product entry MCP server for external assistants.

Use `foamagent_intake` as the hard gate for business-language CFD requests.
Only proceed when intake returns `ready` and a receipt path. Use
`foamagent_execute` to run the stamped requirement through Foam-Agent, then use
`foamagent_execute_status` to poll long OpenFOAM runs. The status response
includes `progress_events` for page/UI renderers and `rendered_progress` for
text-only agents such as ARX. Use `foamagent_postprocess`,
`foamagent_artifacts`, and `foamagent_case_evolution` after a completed run.
This server does not expose legacy planning step tools.
""",
)


@mcp.tool(name="foamagent_intake")
async def foamagent_intake(
    request: FoamAgentIntakeRequest,
    ctx: Context,
) -> FoamAgentIntakeResponse:
    """Validate a business-language request through Foam-Agent intake."""
    return await _foamagent_intake(request, ctx)


@mcp.tool(name="foamagent_execute")
async def foamagent_execute(
    request: FoamAgentExecuteRequest,
    ctx: Context,
) -> FoamAgentExecuteResponse:
    """Execute the Foam-Agent main workflow for a stamped ready requirement."""
    return await _foamagent_execute(request, ctx)


@mcp.tool(name="foamagent_execute_status")
async def foamagent_execute_status(
    request: FoamAgentExecuteStatusRequest,
    ctx: Context,
) -> FoamAgentExecuteStatusResponse:
    """Poll Foam-Agent/OpenFOAM execution progress for a case directory."""
    return await _foamagent_execute_status(request, ctx)


@mcp.tool(name="foamagent_postprocess")
async def foamagent_postprocess(
    request: FoamAgentPostprocessRequest,
    ctx: Context,
) -> FoamAgentPostprocessResponse:
    """Run standard Foam-Agent post-processing for a completed case."""
    return await _foamagent_postprocess(request, ctx)


@mcp.tool(name="foamagent_artifacts")
async def foamagent_artifacts(
    request: FoamAgentArtifactsRequest,
    ctx: Context,
) -> FoamAgentArtifactsResponse:
    """Read Foam-Agent post-processing artifacts without rerunning."""
    return await _foamagent_artifacts(request, ctx)


@mcp.tool(name="foamagent_case_evolution")
async def foamagent_case_evolution(
    request: FoamAgentCaseEvolutionRequest,
    ctx: Context,
) -> FoamAgentCaseEvolutionResponse:
    """Evaluate whether a successful case should become a candidate case."""
    return await _foamagent_case_evolution(request, ctx)


def main() -> None:
    parser = argparse.ArgumentParser(description="Foam-Agent product-only MCP server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()

    if args.transport == "http":
        mcp.run("http", host=args.host, port=args.port, uvicorn_config={"ws": "websockets"})
    else:
        mcp.run("stdio")


if __name__ == "__main__":
    main()
