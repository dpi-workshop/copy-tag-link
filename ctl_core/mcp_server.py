"""Minimal MCP server for reading CTL packages.

The server intentionally has no third-party dependencies. It speaks enough of
the MCP JSON-RPC stdio protocol for agents to list packages, inspect manifests,
search records, and read assets from local CTL folders.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .cli import load_package, validate_package


PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "ctl-core"
TEXT_EXTENSIONS = {
    ".css",
    ".csv",
    ".htm",
    ".html",
    ".js",
    ".json",
    ".md",
    ".svg",
    ".text",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
SKIP_DIRS = {
    ".git",
    ".github",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
}


class McpError(Exception):
    """JSON-RPC compatible MCP error."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def json_text(value: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, indent=2, ensure_ascii=False)}]}


def configured_roots() -> list[Path]:
    raw = os.environ.get("CTL_MCP_ROOTS", "").strip()
    values = [part for part in raw.split(os.pathsep) if part] if raw else [os.getcwd()]
    roots: list[Path] = []
    for value in values:
        root = Path(value).expanduser().resolve()
        if root.exists() and root.is_dir():
            roots.append(root)
    if not roots:
        roots.append(Path.cwd().resolve())
    return roots


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def ensure_under_roots(path: Path, roots: list[Path]) -> Path:
    resolved = path.expanduser().resolve()
    if any(is_relative_to(resolved, root) for root in roots):
        return resolved
    raise McpError(-32602, f"Path is outside configured CTL_MCP_ROOTS: {path}")


def find_packages(root: Path, *, limit: int = 100, max_depth: int = 6) -> list[Path]:
    packages: list[Path] = []
    root = root.resolve()
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        depth = len(current_path.relative_to(root).parts)
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        if depth >= max_depth:
            dirs[:] = []
        if "manifest.json" in files and "search.json" in files:
            packages.append(current_path)
            dirs[:] = []
            if len(packages) >= limit:
                break
    return packages


def resolve_package(value: str, roots: list[Path]) -> Path:
    if not value:
        raise McpError(-32602, "Package path is required.")

    candidate = Path(value)
    if candidate.is_absolute() or candidate.exists():
        resolved = ensure_under_roots(candidate, roots)
        if not resolved.is_dir():
            raise McpError(-32602, f"Package is not a directory: {value}")
        return resolved

    for root in roots:
        direct = (root / value).resolve()
        if direct.exists() and direct.is_dir() and is_relative_to(direct, root):
            return direct
        for package in find_packages(root, limit=200):
            if package.name == value:
                return package
            manifest_path = package / "manifest.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(manifest.get("source_id", "")) == value:
                return package

    raise McpError(-32602, f"CTL package not found under configured roots: {value}")


def safe_package_child(package: Path, value: str) -> Path:
    if not value:
        raise McpError(-32602, "Path is required.")
    child = (package / value).resolve()
    if not is_relative_to(child, package):
        raise McpError(-32602, f"Path escapes package: {value}")
    if not child.exists():
        raise McpError(-32602, f"Package path does not exist: {value}")
    return child


def tool_list_packages(args: dict[str, Any]) -> dict[str, Any]:
    roots = configured_roots()
    limit = int(args.get("limit", 50))
    packages: list[dict[str, Any]] = []
    for root in roots:
        for package in find_packages(root, limit=max(limit - len(packages), 0)):
            try:
                manifest, _search, records = load_package(package)
            except (OSError, ValueError):
                continue
            packages.append(
                {
                    "path": str(package),
                    "name": package.name,
                    "source_id": manifest.get("source_id"),
                    "schema": manifest.get("ctl_schema_version"),
                    "record_count": len(records),
                    "source": manifest.get("source"),
                }
            )
            if len(packages) >= limit:
                break
        if len(packages) >= limit:
            break
    return json_text({"roots": [str(root) for root in roots], "packages": packages})


def tool_validate_package(args: dict[str, Any]) -> dict[str, Any]:
    package = resolve_package(str(args.get("package", "")), configured_roots())
    errors = validate_package(package)
    return json_text({"package": str(package), "valid": not errors, "errors": errors})


def tool_read_manifest(args: dict[str, Any]) -> dict[str, Any]:
    package = resolve_package(str(args.get("package", "")), configured_roots())
    manifest, _search, records = load_package(package)
    return json_text({"package": str(package), "manifest": manifest, "record_count": len(records)})


def tool_package_summary(args: dict[str, Any]) -> dict[str, Any]:
    package = resolve_package(str(args.get("package", "")), configured_roots())
    manifest, search_rows, records = load_package(package)
    record_types: dict[str, int] = {}
    for record in records:
        record_type = str(record.get("type", "unknown"))
        record_types[record_type] = record_types.get(record_type, 0) + 1
    documents = sorted(path.relative_to(package).as_posix() for path in (package / "documents").glob("*.html"))
    okf_cards = sorted(path.relative_to(package).as_posix() for path in (package / "okf").rglob("*.md"))
    return json_text(
        {
            "package": str(package),
            "source_id": manifest.get("source_id"),
            "schema": manifest.get("ctl_schema_version"),
            "record_count": len(records),
            "search_entries": len(search_rows),
            "record_types": record_types,
            "documents": documents,
            "okf_cards": okf_cards,
        }
    )


def tool_search_records(args: dict[str, Any]) -> dict[str, Any]:
    package = resolve_package(str(args.get("package", "")), configured_roots())
    query = str(args.get("query", "")).casefold()
    limit = int(args.get("limit", 10))
    if not query:
        raise McpError(-32602, "Search query is required.")

    _manifest, search_rows, records = load_package(package)
    by_id = {str(record.get("id", "")): record for record in records if isinstance(record, dict)}
    matches: list[dict[str, Any]] = []
    for row in search_rows:
        if not isinstance(row, dict):
            continue
        haystack = " ".join(str(row.get(key, "")) for key in ["id", "type", "text", "source_id"]).casefold()
        if query in haystack:
            record_id = str(row.get("id", ""))
            match = dict(row)
            if record_id in by_id:
                match["record"] = by_id[record_id]
            matches.append(match)
            if len(matches) >= limit:
                break
    return json_text({"package": str(package), "query": query, "matches": matches})


def tool_get_record(args: dict[str, Any]) -> dict[str, Any]:
    package = resolve_package(str(args.get("package", "")), configured_roots())
    record_id = str(args.get("record_id", ""))
    if not record_id:
        raise McpError(-32602, "record_id is required.")
    _manifest, _search_rows, records = load_package(package)
    for record in records:
        if isinstance(record, dict) and str(record.get("id", "")) == record_id:
            return json_text({"package": str(package), "record": record})
    raise McpError(-32602, f"Record not found: {record_id}")


def tool_get_asset(args: dict[str, Any]) -> dict[str, Any]:
    package = resolve_package(str(args.get("package", "")), configured_roots())
    asset_path = str(args.get("asset_path", ""))
    include_base64 = bool(args.get("include_base64", False))
    max_bytes = int(args.get("max_bytes", 256_000))
    target = safe_package_child(package, asset_path)
    if not target.is_file():
        raise McpError(-32602, f"Asset is not a file: {asset_path}")

    stat = target.stat()
    mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    result: dict[str, Any] = {
        "package": str(package),
        "asset_path": target.relative_to(package).as_posix(),
        "bytes": stat.st_size,
        "mime_type": mime_type,
    }
    if target.suffix.lower() in TEXT_EXTENSIONS and stat.st_size <= max_bytes:
        result["text"] = target.read_text(encoding="utf-8", errors="replace")
    elif include_base64 and stat.st_size <= max_bytes:
        result["base64"] = base64.b64encode(target.read_bytes()).decode("ascii")
    else:
        result["content_omitted"] = "File is binary or larger than max_bytes."
    return json_text(result)


def tool_list_okf_cards(args: dict[str, Any]) -> dict[str, Any]:
    package = resolve_package(str(args.get("package", "")), configured_roots())
    okf_root = package / "okf"
    cards = []
    if okf_root.exists():
        for path in sorted(okf_root.rglob("*.md")):
            cards.append({"path": path.relative_to(package).as_posix(), "bytes": path.stat().st_size})
    return json_text({"package": str(package), "cards": cards})


def tool_read_okf_card(args: dict[str, Any]) -> dict[str, Any]:
    package = resolve_package(str(args.get("package", "")), configured_roots())
    card_path = str(args.get("card_path", "okf/index.md"))
    target = safe_package_child(package, card_path)
    if target.suffix.lower() != ".md":
        raise McpError(-32602, "OKF card path must point to a Markdown file.")
    return json_text({"package": str(package), "card_path": target.relative_to(package).as_posix(), "text": target.read_text(encoding="utf-8")})


TOOLS: dict[str, dict[str, Any]] = {
    "ctl_list_packages": {
        "description": "List CTL packages under configured CTL_MCP_ROOTS.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 50}},
        },
        "handler": tool_list_packages,
    },
    "ctl_validate_package": {
        "description": "Validate a CTL package folder.",
        "inputSchema": {
            "type": "object",
            "properties": {"package": {"type": "string"}},
            "required": ["package"],
        },
        "handler": tool_validate_package,
    },
    "ctl_read_manifest": {
        "description": "Read manifest.json from a CTL package.",
        "inputSchema": {
            "type": "object",
            "properties": {"package": {"type": "string"}},
            "required": ["package"],
        },
        "handler": tool_read_manifest,
    },
    "ctl_package_summary": {
        "description": "Summarize CTL package record types, documents, and OKF cards.",
        "inputSchema": {
            "type": "object",
            "properties": {"package": {"type": "string"}},
            "required": ["package"],
        },
        "handler": tool_package_summary,
    },
    "ctl_search_records": {
        "description": "Search CTL search.json and return matching records.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "package": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["package", "query"],
        },
        "handler": tool_search_records,
    },
    "ctl_get_record": {
        "description": "Read one canonical CTL record by id.",
        "inputSchema": {
            "type": "object",
            "properties": {"package": {"type": "string"}, "record_id": {"type": "string"}},
            "required": ["package", "record_id"],
        },
        "handler": tool_get_record,
    },
    "ctl_get_asset": {
        "description": "Read a package asset or document by relative path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "package": {"type": "string"},
                "asset_path": {"type": "string"},
                "include_base64": {"type": "boolean", "default": False},
                "max_bytes": {"type": "integer", "default": 256000},
            },
            "required": ["package", "asset_path"],
        },
        "handler": tool_get_asset,
    },
    "ctl_list_okf_cards": {
        "description": "List OKF-compatible Markdown cards in a CTL package.",
        "inputSchema": {
            "type": "object",
            "properties": {"package": {"type": "string"}},
            "required": ["package"],
        },
        "handler": tool_list_okf_cards,
    },
    "ctl_read_okf_card": {
        "description": "Read an OKF-compatible Markdown card from a CTL package.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "package": {"type": "string"},
                "card_path": {"type": "string", "default": "okf/index.md"},
            },
            "required": ["package"],
        },
        "handler": tool_read_okf_card,
    },
}


def public_tools() -> list[dict[str, Any]]:
    return [
        {"name": name, "description": data["description"], "inputSchema": data["inputSchema"]}
        for name, data in TOOLS.items()
    ]


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": __version__},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": public_tools()}}

    if method == "tools/call":
        name = str(params.get("name", ""))
        arguments = params.get("arguments") or {}
        if name not in TOOLS:
            raise McpError(-32601, f"Unknown tool: {name}")
        result = TOOLS[name]["handler"](arguments)
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    raise McpError(-32601, f"Unsupported MCP method: {method}")


def error_response(request_id: Any, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, McpError):
        code = exc.code
        message = exc.message
    else:
        code = -32603
        message = str(exc)
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def serve() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request_id = None
        try:
            message = json.loads(line)
            request_id = message.get("id")
            response = handle_request(message)
            if response is not None:
                print(json.dumps(response, ensure_ascii=False), flush=True)
        except Exception as exc:  # noqa: BLE001 - MCP server must report protocol errors.
            print(json.dumps(error_response(request_id, exc), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())
