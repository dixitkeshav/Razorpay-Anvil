"""Phase 11 gate: a real MCP client connects and successfully calls all
three tools (get_incident, explain_attribution, query_recovery_ledger).
See docs/PHASES.md.

Launches src/mcp/server.py as a real subprocess over stdio -- the same
transport Claude Desktop and Claude Code use to connect to a local MCP
server -- rather than calling the Python functions in-process, so this
proves actual protocol compliance, not just that the underlying logic
works.
"""

import asyncio
import json
import pathlib
import sys

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.mcp.server"],
        cwd=str(REPO_ROOT),
    )


def _tool_text(result) -> dict:
    """MCP tool results carry their payload as structured content when the
    tool returns a dict (this SDK populates it directly), falling back to
    parsing the text content block as JSON."""
    assert not result.is_error, f"tool call returned an error: {result.content}"
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(result.content[0].text)


async def _run_all_three_tools() -> tuple[dict, dict, dict]:
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert {"get_incident", "explain_attribution", "query_recovery_ledger"} <= names

            incident = await session.call_tool("get_incident", {"incident_index": 0})
            attribution = await session.call_tool("explain_attribution", {"incident_index": 0})
            ledger = await session.call_tool("query_recovery_ledger", {"limit": 5})

            return _tool_text(incident), _tool_text(attribution), _tool_text(ledger)


def test_real_mcp_client_calls_all_three_tools():
    incident, attribution, ledger = asyncio.run(
        asyncio.wait_for(_run_all_three_tools(), timeout=180)
    )

    assert "slice" in incident
    assert incident["affected_attempts"] > 0
    assert incident["at_risk_gmv_paise"] > 0

    assert "minimal_cut" in attribution
    assert "trace" in attribution
    assert attribution["trace"]

    assert "entries" in ledger
    assert ledger["total_matching"] > 0
    assert ledger["entries"]
    first = ledger["entries"][0]
    assert first["action"] in ("RETRY", "REROUTE", "HOLD", "ESCALATE_HUMAN")


def test_get_incident_out_of_range_reports_available_count():
    from src.mcp.server import _load_state, get_incident

    _load_state()
    result = get_incident(99999)
    assert "error" in result
    assert "available_incidents" in result


def test_query_recovery_ledger_filters_by_action():
    from src.mcp.server import query_recovery_ledger

    result = query_recovery_ledger(action="HOLD", limit=5)
    assert all(e["action"] == "HOLD" for e in result["entries"])
