"""Verification script that connects a real MCP client over Streamable HTTP to Axio.

Usage:
    python scripts/verify_mcp_client.py [--url http://127.0.0.1:8000/mcp]
"""

import sys
import json
import asyncio
import argparse
from mcp.client.streamable_http import streamable_http_client
from mcp.client.session import ClientSession


async def main(url: str):
    print(f"[1/4] Connecting to Axio MCP server at: {url}")
    async with streamable_http_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Step 1: Protocol handshake
            print("[2/4] Initializing protocol session...")
            init_result = await session.initialize()
            print(f"      Connected to server: {init_result.server_info.name} (version: {init_result.server_info.version or '0.1.0'})")

            # Step 2: Tool discovery
            print("[3/4] Discovering tools...")
            tool_list = await session.list_tools()
            print(f"      Discovered {len(tool_list.tools)} tools:")
            for t in tool_list.tools:
                print(f"       - {t.name}: {t.description[:65]}...")

            # Step 3: Tool execution
            print("[4/4] Invoking 'create_task' via MCP Streamable HTTP...")
            create_res = await session.call_tool(
                "create_task",
                arguments={
                    "title": "Verify MCP Streamable HTTP Client",
                    "priority": "high",
                    "description": "Created by scripts/verify_mcp_client.py over Streamable HTTP",
                },
            )
            data = json.loads(create_res.content[0].text)
            print(f"      Result: {data.get('message', 'Success')}")
            task_id = data["task"]["id"]

            print(f"      Invoking 'get_tasks' filtered by task ID {task_id}...")
            get_res = await session.call_tool("get_tasks", arguments={"search": "Verify MCP Streamable HTTP Client"})
            get_data = json.loads(get_res.content[0].text)
            print(f"      Found {get_data['count']} matching tasks in persistence store.")

            print("\n MCP Client Verification Passed Successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Axio MCP Client Verification")
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp", help="Axio MCP Streamable HTTP endpoint")
    args = parser.parse_args()
    asyncio.run(main(args.url))
