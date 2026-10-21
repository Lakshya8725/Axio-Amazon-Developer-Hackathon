"""Automated tests for Axio MCP Server and Streamable HTTP protocol."""

import json
import socket
import asyncio
import pytest
import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.client.streamable_http import streamable_http_client
from mcp.client.session import ClientSession

from app.tools.mcp_server import mcp_server, create_mcp_server
from app.main import app


def get_free_port() -> int:
    """Find an available TCP port for ephemeral test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_mcp_tool_registration():
    """Verify that all four required MCP tools are registered with schemas on the server."""
    tools = await mcp_server.list_tools()
    tool_names = {t.name for t in tools}

    expected_tools = {"get_tasks", "create_task", "update_task_status", "get_user_preferences"}
    assert expected_tools.issubset(tool_names), f"Missing tools. Registered: {tool_names}"

    # Verify descriptions are populated
    for tool in tools:
        if tool.name in expected_tools:
            assert tool.description is not None
            assert len(tool.description) > 10


@pytest.mark.asyncio
async def test_mcp_tool_direct_invocation():
    """Test calling registered MCP tools directly through call_tool API."""
    # 1. create_task
    create_res = await mcp_server.call_tool(
        "create_task",
        {"title": "Direct MCP Tool Test", "priority": "urgent", "description": "Created via call_tool"},
    )
    assert not create_res.is_error
    create_data = json.loads(create_res.content[0].text)
    assert create_data["success"] is True
    task_id = create_data["task"]["id"]
    assert create_data["task"]["priority"] == "urgent"

    # 2. get_tasks
    get_res = await mcp_server.call_tool("get_tasks", {"search": "Direct MCP Tool Test"})
    assert not get_res.is_error
    get_data = json.loads(get_res.content[0].text)
    assert get_data["success"] is True
    assert get_data["total"] >= 1
    assert any(t["id"] == task_id for t in get_data["tasks"])

    # 3. update_task_status
    update_res = await mcp_server.call_tool(
        "update_task_status",
        {"task_id": task_id, "status": "completed"},
    )
    assert not update_res.is_error
    update_data = json.loads(update_res.content[0].text)
    assert update_data["success"] is True
    assert update_data["task"]["status"] == "completed"

    # 4. get_user_preferences
    pref_res = await mcp_server.call_tool("get_user_preferences", {"category": "security"})
    assert not pref_res.is_error
    pref_data = json.loads(pref_res.content[0].text)
    assert pref_data["success"] is True
    assert "confirm_consequential_actions" in pref_data["preferences"]


@pytest.mark.asyncio
async def test_mcp_tool_validation_and_error_handling():
    """Test server-side argument validation for tools."""
    # Empty title
    bad_create = await mcp_server.call_tool("create_task", {"title": ""})
    bad_data = json.loads(bad_create.content[0].text)
    assert bad_data["success"] is False
    assert "empty" in bad_data["error"].lower()

    # Invalid priority
    bad_pri = await mcp_server.call_tool("create_task", {"title": "Valid", "priority": "nonexistent_priority"})
    bad_pri_data = json.loads(bad_pri.content[0].text)
    assert bad_pri_data["success"] is False
    assert "invalid priority" in bad_pri_data["error"].lower()

    # Invalid status
    bad_status = await mcp_server.call_tool("update_task_status", {"task_id": 1, "status": "wrong_status"})
    bad_status_data = json.loads(bad_status.content[0].text)
    assert bad_status_data["success"] is False
    assert "invalid status" in bad_status_data["error"].lower()

    # Non-existent task id
    missing_task = await mcp_server.call_tool("update_task_status", {"task_id": 9999999, "status": "completed"})
    missing_data = json.loads(missing_task.content[0].text)
    assert missing_data["success"] is False
    assert "not found" in missing_data["error"].lower()


@pytest.mark.asyncio
async def test_mcp_streamable_http_session_and_protocol():
    """Verify live MCP client protocol initialization, tool discovery, and tool execution over Streamable HTTP."""
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())

    # Wait for server ready
    await asyncio.sleep(0.5)

    endpoint_url = f"http://127.0.0.1:{port}/mcp"

    try:
        async with streamable_http_client(endpoint_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # 1. Initialize MCP protocol session
                init_result = await session.initialize()
                assert init_result.server_info.name == "axio"

                # 2. Discover tools
                tool_list = await session.list_tools()
                discovered_names = {t.name for t in tool_list.tools}
                assert "get_tasks" in discovered_names
                assert "create_task" in discovered_names
                assert "update_task_status" in discovered_names
                assert "get_user_preferences" in discovered_names

                # 3. Invoke create_task over Streamable HTTP
                call_create = await session.call_tool(
                    "create_task",
                    arguments={
                        "title": "Streamable HTTP Verified Task",
                        "priority": "high",
                        "description": "Created across live HTTP MCP transport",
                    },
                )
                assert not call_create.is_error
                created_payload = json.loads(call_create.content[0].text)
                assert created_payload["success"] is True
                new_id = created_payload["task"]["id"]

                # 4. Invoke get_tasks over Streamable HTTP
                call_get = await session.call_tool(
                    "get_tasks",
                    arguments={"search": "Streamable HTTP Verified"},
                )
                assert not call_get.is_error
                get_payload = json.loads(call_get.content[0].text)
                assert get_payload["total"] >= 1
                assert any(t["id"] == new_id for t in get_payload["tasks"])

                # 5. Invoke update_task_status over Streamable HTTP
                call_update = await session.call_tool(
                    "update_task_status",
                    arguments={"task_id": new_id, "status": "completed"},
                )
                assert not call_update.is_error
                update_payload = json.loads(call_update.content[0].text)
                assert update_payload["task"]["status"] == "completed"

                # 6. Invoke get_user_preferences over Streamable HTTP
                call_prefs = await session.call_tool(
                    "get_user_preferences",
                    arguments={},
                )
                assert not call_prefs.is_error
                prefs_payload = json.loads(call_prefs.content[0].text)
                assert prefs_payload["success"] is True
                assert "confirm_consequential_actions" in prefs_payload["preferences"]

    finally:
        server.should_exit = True
        serve_task.cancel()
        try:
            await serve_task
        except (asyncio.CancelledError, Exception):
            pass
