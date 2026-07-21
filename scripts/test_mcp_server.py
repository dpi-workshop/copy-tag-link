"""Smoke test the dependency-free CTL-Core MCP server."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctl_core.mcp_server import handle_request


def call_tool(name: str, arguments: dict) -> dict:
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    if response is None or "error" in response:
        raise SystemExit(f"MCP tool failed: {response}")
    text = response["result"]["content"][0]["text"]
    return json.loads(text)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/test_mcp_server.py PACKAGE")

    package = Path(sys.argv[1]).expanduser().resolve()
    if not package.exists():
        raise SystemExit(f"Package does not exist: {package}")

    os.environ["CTL_MCP_ROOTS"] = str(package.parent)

    initialize = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    if not initialize or initialize.get("result", {}).get("serverInfo", {}).get("name") != "ctl-core":
        raise SystemExit(f"Unexpected initialize response: {initialize}")

    tools = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tool_names = {tool["name"] for tool in tools["result"]["tools"]}
    for required in ["ctl_list_packages", "ctl_search_records", "ctl_get_record", "ctl_get_asset"]:
        if required not in tool_names:
            raise SystemExit(f"Missing MCP tool: {required}")

    packages = call_tool("ctl_list_packages", {"limit": 10})
    if not packages["packages"]:
        raise SystemExit("MCP package list returned no packages")

    validation = call_tool("ctl_validate_package", {"package": str(package)})
    if not validation["valid"]:
        raise SystemExit(f"MCP validation failed: {validation}")

    search = call_tool("ctl_search_records", {"package": str(package), "query": "HTML", "limit": 5})
    if not search["matches"]:
        raise SystemExit("MCP search returned no matches")

    record_id = search["matches"][0]["id"]
    record = call_tool("ctl_get_record", {"package": str(package), "record_id": record_id})
    if record["record"]["id"] != record_id:
        raise SystemExit("MCP record lookup returned the wrong record")

    okf = call_tool("ctl_read_okf_card", {"package": str(package)})
    if "text" not in okf or not okf["text"].strip():
        raise SystemExit("MCP OKF card read returned empty text")

    print("MCP smoke test passed.")


if __name__ == "__main__":
    main()
