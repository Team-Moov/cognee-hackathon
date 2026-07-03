"""
Groundhog MCP Server — FastAPI + SSE transport.

Architecture
============
This server implements the Model Context Protocol (MCP) using an SSE
(Server-Sent Events) HTTP transport, which means it is:

  • Deployable to any cloud host (Railway, Fly.io, Render, etc.)
  • Reachable by any MCP client that supports the SSE transport:
      - Claude Desktop / Claude Code
      - Cursor
      - Any future MCP-compatible tool

The server exposes FOUR tools that map 1-to-1 to Groundhog's core memory
operations:

  groundhog_check_config  → POST /api/runs/check-config
  groundhog_remember      → POST /api/runs/remember
  groundhog_query         → POST /api/query
  groundhog_find          → GET  /api/files/find

Running locally
===============
  cd <repo-root>
  .\\venv\\Scripts\\python.exe -m uvicorn mcp_server.main:app --port 8002 --reload

Connecting Claude Desktop
=========================
Add to ~/AppData/Roaming/Claude/claude_desktop_config.json:

  {
    "mcpServers": {
      "groundhog": {
        "url": "http://localhost:8002/sse"
      }
    }
  }

Connecting Claude Code (CLI)
============================
  claude mcp add groundhog http://localhost:8002/sse --transport sse

Deploying
=========
Set the GROUNDHOG_API_URL env var to point to your deployed backend:
  GROUNDHOG_API_URL=https://your-backend.railway.app
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
)
import mcp.types as mcp_types

from mcp_server.config import settings
from mcp_server.tools import (
    tool_check_config,
    tool_find,
    tool_query,
    tool_remember,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("groundhog.mcp")

# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Groundhog MCP Server",
    description=(
        "Model Context Protocol server for Groundhog ML experiment memory. "
        "Exposes four tools: check_config, remember, query, find."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── MCP Server ─────────────────────────────────────────────────────────────────

mcp = Server("groundhog")

# Tool schemas ─────────────────────────────────────────────────────────────────

TOOLS: List[Tool] = [
    Tool(
        name="groundhog_check_config",
        description=(
            "Check whether a given experiment configuration has already been tried. "
            "Call this BEFORE starting any training run to avoid wasting compute on a "
            "duplicate or near-duplicate configuration. Returns match type (exact / similar / none), "
            "a human-readable recommendation, and metrics from any matching prior run."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "description": (
                        "The hyperparameter / configuration dict to check. "
                        "Example: {\"model\": \"ResNet50\", \"optimizer\": \"AdamW\", \"learning_rate\": 0.001}"
                    ),
                    "additionalProperties": True,
                },
                "experiment": {
                    "type": "string",
                    "description": "Optional experiment name to narrow the search scope.",
                },
            },
            "required": ["config"],
        },
    ),
    Tool(
        name="groundhog_remember",
        description=(
            "Record a completed (or failed) experiment run into Groundhog's memory. "
            "Call this after ANY training run, successful or not — failed runs are first-class "
            "memory and prevent future wasted compute. Always include a 'rationale' explaining "
            "WHY this configuration was chosen."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "experiment": {
                    "type": "string",
                    "description": "Experiment name / project slug (e.g. 'resnet-lr-sweep').",
                },
                "config": {
                    "type": "object",
                    "description": "The hyperparameter dict used for this run.",
                    "additionalProperties": True,
                },
                "metrics": {
                    "type": "object",
                    "description": "Final metrics (e.g. {\"val_acc\": 0.89, \"val_loss\": 0.31}).",
                    "additionalProperties": True,
                },
                "rationale": {
                    "type": "string",
                    "description": "WHY this configuration was chosen. Required — rationale is the core value of Groundhog.",
                },
                "status": {
                    "type": "string",
                    "enum": ["completed", "failed", "aborted"],
                    "description": "Run outcome. Defaults to 'completed'.",
                },
                "gpu_hours": {
                    "type": "number",
                    "description": "GPU-hours consumed. Strongly encouraged for cost tracking.",
                },
                "git_commit": {
                    "type": "string",
                    "description": "Git commit SHA at time of run.",
                },
                "error_message": {
                    "type": "string",
                    "description": "If status is 'failed', the error or failure reason.",
                },
                "artifacts": {
                    "type": "array",
                    "description": "List of produced files to index for later discovery.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "description": "checkpoint | plot | log | report | other"},
                            "path": {"type": "string", "description": "Absolute path to the file."},
                        },
                        "required": ["type", "path"],
                    },
                },
            },
            "required": ["experiment", "config", "metrics", "rationale"],
        },
    ),
    Tool(
        name="groundhog_query",
        description=(
            "Ask a free-form natural language question about all experiment history. "
            "Examples: 'What happened when we used learning rate 0.5?', "
            "'Which run had the best val_acc?', 'Why did we abandon SGD?', "
            "'Catch me up on the ResNet sweep.' Surfaces both successes AND failures."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The natural language question to ask Groundhog.",
                },
            },
            "required": ["question"],
        },
    ),
    Tool(
        name="groundhog_find",
        description=(
            "Find an artifact file (checkpoint, plot, eval report, log) by natural language description. "
            "Never spelunk through run_47_v2_final_FINAL/ again. "
            "Examples: 'best ResNet checkpoint from imagenet sweep', "
            "'validation loss curve for the AdamW run', 'confusion matrix from the failed run'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Natural language description of the artifact to locate.",
                },
            },
            "required": ["description"],
        },
    ),
]


@mcp.list_tools()
async def list_tools() -> ListToolsResult:
    return ListToolsResult(tools=TOOLS)


@mcp.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    logger.info("Tool called: %s | args=%s", name, arguments)

    try:
        if name == "groundhog_check_config":
            result = await tool_check_config(
                config=arguments["config"],
                experiment=arguments.get("experiment"),
            )

        elif name == "groundhog_remember":
            result = await tool_remember(
                experiment=arguments["experiment"],
                config=arguments["config"],
                metrics=arguments["metrics"],
                rationale=arguments["rationale"],
                status=arguments.get("status", "completed"),
                gpu_hours=arguments.get("gpu_hours"),
                git_commit=arguments.get("git_commit", "unknown"),
                error_message=arguments.get("error_message"),
                artifacts=arguments.get("artifacts"),
            )

        elif name == "groundhog_query":
            result = await tool_query(question=arguments["question"])

        elif name == "groundhog_find":
            result = await tool_find(description=arguments["description"])

        else:
            result = f"Unknown tool: {name}"

    except Exception as e:
        logger.exception("Tool %s raised an exception", name)
        result = f"[{name}] Error: {e}"

    return CallToolResult(content=[TextContent(type="text", text=result)])


# ── SSE transport mount ────────────────────────────────────────────────────────

sse_transport = SseServerTransport("/messages/")


@app.get("/sse")
async def handle_sse(request: Request):
    """SSE endpoint — MCP clients connect here."""
    logger.info("SSE client connected from %s", request.client)
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp.run(
            streams[0],
            streams[1],
            mcp.create_initialization_options(),
        )


@app.post("/messages/")
async def handle_messages(request: Request):
    """Message posting endpoint for the SSE transport."""
    await sse_transport.handle_post_message(
        request.scope, request.receive, request._send
    )


# ── REST helper endpoints (for testing without a full MCP client) ─────────────

@app.get("/health")
async def health():
    """Health check — also verifies backend reachability."""
    import httpx
    backend_ok = False
    backend_msg = ""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.groundhog_api_url}/api/health")
            backend_ok = r.status_code == 200
            backend_msg = r.json().get("status", "unknown")
    except Exception as e:
        backend_msg = str(e)

    return {
        "status": "ok",
        "mcp_tools": [t.name for t in TOOLS],
        "backend_url": settings.groundhog_api_url,
        "backend_reachable": backend_ok,
        "backend_status": backend_msg,
    }


@app.get("/tools")
async def list_tools_rest():
    """List all available MCP tools and their schemas (REST-accessible for testing)."""
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema,
            }
            for t in TOOLS
        ]
    }


@app.post("/test/check-config")
async def test_check_config(body: Dict[str, Any]):
    """Direct REST test for groundhog_check_config (no MCP client needed)."""
    result = await tool_check_config(
        config=body.get("config", {}),
        experiment=body.get("experiment"),
    )
    return {"result": result}


@app.post("/test/remember")
async def test_remember(body: Dict[str, Any]):
    """Direct REST test for groundhog_remember (no MCP client needed)."""
    result = await tool_remember(
        experiment=body.get("experiment", "test"),
        config=body.get("config", {}),
        metrics=body.get("metrics", {}),
        rationale=body.get("rationale", ""),
        status=body.get("status", "completed"),
        gpu_hours=body.get("gpu_hours"),
        git_commit=body.get("git_commit", "unknown"),
        error_message=body.get("error_message"),
        artifacts=body.get("artifacts"),
    )
    return {"result": result}


@app.post("/test/query")
async def test_query(body: Dict[str, Any]):
    """Direct REST test for groundhog_query (no MCP client needed)."""
    result = await tool_query(question=body.get("question", ""))
    return {"result": result}


@app.get("/test/find")
async def test_find(q: str):
    """Direct REST test for groundhog_find (no MCP client needed)."""
    result = await tool_find(description=q)
    return {"result": result}


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "mcp_server.main:app",
        host=settings.mcp_host,
        port=settings.mcp_port,
        reload=True,
        log_level="info",
    )
