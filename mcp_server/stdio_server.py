"""
Groundhog MCP Server — STDIO transport (for Claude Desktop).
"""
import asyncio
import logging
from mcp.server.stdio import stdio_server

from mcp_server.main import mcp, TOOLS

# Suppress noisy logs on stdout so they don't break the MCP protocol
logging.getLogger("groundhog.mcp").setLevel(logging.CRITICAL)

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(
            read_stream,
            write_stream,
            mcp.create_initialization_options(),
        )

if __name__ == "__main__":
    asyncio.run(main())
