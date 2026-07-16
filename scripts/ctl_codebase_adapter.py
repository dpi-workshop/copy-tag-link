#!/usr/bin/env python
"""Create a CTL package and graph for a source code repository."""

from __future__ import annotations

import argparse
import ast
import html
import json
import re
import subprocess
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ctl_okf_export import export_okf
from ctl_schema import CtlRecord, manifest, records_to_json, search_entries, sha256_file, slugify, utc_now, write_json


CTL_CODEBASE_VERSION = "0.1"

SKIP_DIRS = {
    ".git",
    ".agents",
    ".codex",
    ".codegraph",
    "node_modules",
    "dist",
    "output",
    "target",
    "__pycache__",
    ".svelte-kit",
    ".venv",
    ".venv-docling",
    ".venv-mineru",
    ".venv-paddleocr",
    ".venv-handwriting",
}

SKIP_TOP_LEVEL = {
    "projects",
    "tmp",
    "snapshots",
    "backups",
    "candidates",
}

CODE_EXTENSIONS = {".js", ".mjs", ".ts", ".svelte", ".rs", ".py", ".ps1", ".html", ".css", ".md", ".json", ".toml"}
MAX_TEXT_BYTES = 300_000


def relpath(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def should_skip(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    if parts and parts[0] in SKIP_TOP_LEVEL:
        return True
    return any(part in SKIP_DIRS for part in parts)


def iter_source_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file() or should_skip(path, root):
            continue
        if path.suffix.lower() in CODE_EXTENSIONS:
            files.append(path)
    return sorted(files)


def read_text(path: Path) -> str:
    data = path.read_bytes()
    if len(data) > MAX_TEXT_BYTES:
        data = data[:MAX_TEXT_BYTES]
    return data.decode("utf-8-sig", errors="replace")


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def add_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str, evidence: str = "") -> None:
    if not source or not target:
        return
    edges.append(
        {
            "id": f"edge-{len(edges) + 1:05d}",
            "source": source,
            "relation": relation,
            "target": target,
            "evidence": evidence,
        }
    )


def make_record(
    records: list[CtlRecord],
    *,
    record_id: str,
    source_id: str,
    record_type: str,
    order: int,
    text: str,
    source_path: str,
    html_fragment: str = "",
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    links: list[dict[str, Any]] | None = None,
) -> None:
    records.append(
        CtlRecord(
            id=record_id,
            source_id=source_id,
            type=record_type,
            order=order,
            text=text,
            html=html_fragment,
            source_path=source_path,
            links=links or [],
            tags=tags or [],
            confidence=1.0,
            provenance={
                "parser": "ctl-codebase-adapter",
                "parser_version": CTL_CODEBASE_VERSION,
                "adapter": "ctl-core-codebase",
                "created_at": utc_now(),
            },
            metadata=metadata or {},
        )
    )


def parse_python_symbols(text: str) -> list[dict[str, Any]]:
    symbols = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return symbols
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            symbols.append({"kind": "class", "name": node.name, "line": node.lineno})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append({"kind": "function", "name": node.name, "line": node.lineno})
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                names = [node.module or ""]
            for name in names:
                if name:
                    symbols.append({"kind": "import", "name": name, "line": node.lineno})
    return symbols


def parse_js_like_symbols(text: str) -> list[dict[str, Any]]:
    symbols = []
    patterns = [
        ("import", r"^\s*import\s+(?:.+?\s+from\s+)?['\"]([^'\"]+)['\"]"),
        ("function", r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\("),
        ("function", r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("),
        ("function", r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?[A-Za-z_$][\w$]*\s*=>"),
        ("component_ref", r"<([A-Z][A-Za-z0-9_]*)\b"),
    ]
    for kind, pattern in patterns:
        for match in re.finditer(pattern, text, re.MULTILINE):
            symbols.append({"kind": kind, "name": match.group(1), "line": line_for_offset(text, match.start())})
    return symbols


def parse_rust_symbols(text: str) -> list[dict[str, Any]]:
    symbols = []
    patterns = [
        ("import", r"^\s*use\s+([^;]+);"),
        ("function", r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_][\w]*)\s*\("),
        ("module", r"^\s*(?:pub\s+)?mod\s+([A-Za-z_][\w]*)\s*;?"),
        ("struct", r"^\s*(?:pub\s+)?struct\s+([A-Za-z_][\w]*)\b"),
        ("enum", r"^\s*(?:pub\s+)?enum\s+([A-Za-z_][\w]*)\b"),
    ]
    for kind, pattern in patterns:
        for match in re.finditer(pattern, text, re.MULTILINE):
            symbols.append({"kind": kind, "name": match.group(1).strip(), "line": line_for_offset(text, match.start())})
    return symbols


def parse_ps_symbols(text: str) -> list[dict[str, Any]]:
    return [
        {"kind": "function", "name": match.group(1), "line": line_for_offset(text, match.start())}
        for match in re.finditer(r"^\s*function\s+([A-Za-z0-9_-]+)\b", text, re.MULTILINE | re.IGNORECASE)
    ]


def parse_markdown_symbols(text: str) -> list[dict[str, Any]]:
    symbols = []
    for match in re.finditer(r"^(#{1,6})\s+(.+)$", text, re.MULTILINE):
        symbols.append({"kind": "heading", "name": match.group(2).strip(), "line": line_for_offset(text, match.start()), "level": len(match.group(1))})
    return symbols


def parse_symbols(path: Path, text: str) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return parse_python_symbols(text)
    if suffix in {".js", ".mjs", ".ts", ".svelte"}:
        symbols = parse_js_like_symbols(text)
        if suffix == ".svelte":
            symbols.insert(0, {"kind": "component", "name": path.stem, "line": 1})
        return symbols
    if suffix == ".rs":
        return parse_rust_symbols(text)
    if suffix == ".ps1":
        return parse_ps_symbols(text)
    if suffix == ".md":
        return parse_markdown_symbols(text)
    return []


def file_language(path: Path) -> str:
    return {
        ".js": "javascript",
        ".mjs": "javascript",
        ".ts": "typescript",
        ".svelte": "svelte",
        ".rs": "rust",
        ".py": "python",
        ".ps1": "powershell",
        ".html": "html",
        ".css": "css",
        ".md": "markdown",
        ".json": "json",
        ".toml": "toml",
    }.get(path.suffix.lower(), path.suffix.lower().lstrip(".") or "text")


def git_metadata(root: Path) -> dict[str, str]:
    data = {}
    commands = {
        "commit": ["git", "rev-parse", "HEAD"],
        "branch": ["git", "branch", "--show-current"],
        "status": ["git", "status", "--short"],
    }
    for key, command in commands.items():
        try:
            result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=5, check=False)
            data[key] = result.stdout.strip()
        except Exception:
            data[key] = ""
    return data


def write_html_report(output_dir: Path, package_name: str, records: list[CtlRecord], graph: dict[str, Any]) -> None:
    documents_dir = output_dir / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    file_records = [record for record in records if record.type == "code_file"]
    symbol_records = [record for record in records if record.type.startswith("code_") and record.type != "code_file"]
    file_rows = "\n".join(
        f"<tr><td><a href='#{html.escape(record.id)}'><code>{html.escape(record.source_path)}</code></a></td><td>{html.escape(record.metadata.get('language', ''))}</td><td>{record.metadata.get('line_count', '')}</td><td>{record.metadata.get('symbol_count', '')}</td></tr>"
        for record in file_records
    )
    symbol_rows = "\n".join(
        f"<tr><td>{html.escape(record.type.replace('code_', ''))}</td><td><code>{html.escape(record.metadata.get('name', record.id))}</code></td><td><a href='#{html.escape(record.metadata.get('file_record_id', ''))}'>{html.escape(record.source_path)}</a></td><td>{record.metadata.get('line', '')}</td></tr>"
        for record in symbol_records[:500]
    )
    relation_rows = "\n".join(
        f"<tr><td>{html.escape(relation)}</td><td>{count}</td></tr>"
        for relation, count in sorted(graph["summary"]["edge_relations"].items(), key=lambda item: item[1], reverse=True)
    )
    record_sections = "\n".join(
        f"<section id='{html.escape(record.id)}'><h3><code>{html.escape(record.source_path)}</code></h3><p>{html.escape(record.text)}</p></section>"
        for record in file_records
    )
    (documents_dir / "codebase-report.html").write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(package_name)} CTL Codebase Report</title>
  <style>
    body {{ font-family: system-ui, sans-serif; line-height: 1.45; margin: 2rem; max-width: 1200px; }}
    code {{ background: #f2f2f2; padding: 0.12rem 0.25rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; }}
    th, td {{ border: 1px solid #bbb; padding: 0.45rem 0.6rem; text-align: left; vertical-align: top; }}
    th {{ background: #f7f7f7; }}
  </style>
</head>
<body>
  <article>
    <h1>{html.escape(package_name)} CTL Codebase Report</h1>
    <p>This is a CTL package for code. The repository remains the source of truth; this package is the searchable map.</p>
    <section>
      <h2>Summary</h2>
      <p>{len(file_records)} files, {len(symbol_records)} symbols, {graph['summary']['node_count']} graph nodes, {graph['summary']['edge_count']} graph edges.</p>
      <p><a href="../graph/ctl-code-graph.json">Code graph JSON</a></p>
    </section>
    <section>
      <h2>Relations</h2>
      <table><thead><tr><th>Relation</th><th>Count</th></tr></thead><tbody>{relation_rows}</tbody></table>
    </section>
    <section>
      <h2>Files</h2>
      <table><thead><tr><th>File</th><th>Language</th><th>Lines</th><th>Symbols</th></tr></thead><tbody>{file_rows}</tbody></table>
    </section>
    <section>
      <h2>Symbols</h2>
      <table><thead><tr><th>Kind</th><th>Name</th><th>File</th><th>Line</th></tr></thead><tbody>{symbol_rows}</tbody></table>
    </section>
    <section>
      <h2>File Notes</h2>
      {record_sections}
    </section>
  </article>
</body>
</html>
""",
        encoding="utf-8",
    )


def build_codebase_package(root: Path, output_dir: Path, package_name: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    output_dir = output_dir.resolve()
    package_name = package_name or slugify(root.name or "codebase")
    tables_dir = output_dir / "assets" / "tables"
    graph_dir = output_dir / "graph"
    tables_dir.mkdir(parents=True, exist_ok=True)
    graph_dir.mkdir(parents=True, exist_ok=True)

    records: list[CtlRecord] = []
    edges: list[dict[str, Any]] = []
    files = iter_source_files(root)
    order = 1
    repo_node = f"repo:{package_name}"
    nodes: dict[str, dict[str, Any]] = {
        repo_node: {"id": repo_node, "kind": "repository", "label": package_name, "path": str(root)}
    }

    for path in files:
        relative = relpath(path, root)
        text = read_text(path)
        language = file_language(path)
        symbols = parse_symbols(path, text)
        file_id = f"file-{slugify(relative)}"
        file_node = f"file:{relative}"
        nodes[file_node] = {"id": file_node, "kind": "file", "label": relative, "path": relative, "language": language}
        add_edge(edges, repo_node, "contains_file", file_node, "filesystem")

        imports = [symbol for symbol in symbols if symbol["kind"] == "import"]
        links = []
        for item in imports:
            target = str(item["name"])
            links.append({"rel": "imports", "href": target, "label": target, "line": item.get("line")})
            add_edge(edges, file_node, "imports", f"module:{target}", f"{relative}:{item.get('line', '')}")
            nodes.setdefault(f"module:{target}", {"id": f"module:{target}", "kind": "module", "label": target})

        make_record(
            records,
            record_id=file_id,
            source_id=package_name,
            record_type="code_file",
            order=order,
            text=f"{relative} ({language}), {text.count(chr(10)) + 1} lines, {len(symbols)} parsed symbols.",
            source_path=relative,
            html_fragment=f"<article data-ctl-type='code-file'><h2><code>{html.escape(relative)}</code></h2><p>{html.escape(language)}</p></article>",
            tags=["code", f"language-{language}", "file"],
            metadata={
                "language": language,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "line_count": text.count("\n") + 1,
                "symbol_count": len(symbols),
            },
            links=links,
        )
        order += 1

        for symbol in symbols:
            if symbol["kind"] == "import":
                continue
            name = str(symbol["name"])
            kind = str(symbol["kind"])
            symbol_id = f"{kind}-{slugify(relative)}-{slugify(name)}-{symbol.get('line', 0)}"
            symbol_node = f"symbol:{relative}:{kind}:{name}:{symbol.get('line', 0)}"
            nodes[symbol_node] = {
                "id": symbol_node,
                "kind": kind,
                "label": name,
                "path": relative,
                "line": symbol.get("line"),
            }
            add_edge(edges, file_node, "defines", symbol_node, f"{relative}:{symbol.get('line', '')}")
            if kind == "component_ref":
                add_edge(edges, file_node, "renders_component", f"component:{name}", f"{relative}:{symbol.get('line', '')}")
                nodes.setdefault(f"component:{name}", {"id": f"component:{name}", "kind": "component_ref", "label": name})
            make_record(
                records,
                record_id=symbol_id,
                source_id=package_name,
                record_type=f"code_{kind}",
                order=order,
                text=f"{kind} {name} in {relative} at line {symbol.get('line', '')}.",
                source_path=relative,
                html_fragment=f"<section data-ctl-type='code-symbol'><h3>{html.escape(kind)} <code>{html.escape(name)}</code></h3><p>{html.escape(relative)}:{symbol.get('line', '')}</p></section>",
                tags=["code", "symbol", f"symbol-{kind}", f"language-{language}"],
                metadata={
                    "name": name,
                    "kind": kind,
                    "line": symbol.get("line"),
                    "file_record_id": file_id,
                    "file": relative,
                    **({"level": symbol.get("level")} if "level" in symbol else {}),
                },
                links=[{"rel": "defined_in", "href": file_id, "label": relative}],
            )
            order += 1

    for edge in edges:
        edge["id"] = f"edge-{edges.index(edge) + 1:05d}"

    degree = Counter()
    for edge in edges:
        degree[edge["source"]] += 1
        degree[edge["target"]] += 1
    for node in nodes.values():
        node["degree"] = degree[node["id"]]

    graph = {
        "ctl_graph_export_version": CTL_CODEBASE_VERSION,
        "created_at": utc_now(),
        "package": str(output_dir),
        "source_repository": str(root),
        "nodes": sorted(nodes.values(), key=lambda item: (item["kind"], item["label"])),
        "edges": edges,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "node_kinds": dict(Counter(node["kind"] for node in nodes.values())),
            "edge_relations": dict(Counter(edge["relation"] for edge in edges)),
        },
    }

    write_json(tables_dir / "ctl-records.json", records_to_json(records))
    write_json(tables_dir / "code-graph-edges.json", edges)
    write_json(tables_dir / "code-files.json", [{"path": relpath(path, root), "language": file_language(path), "size_bytes": path.stat().st_size} for path in files])
    write_json(output_dir / "search.json", search_entries(records))
    write_json(graph_dir / "ctl-code-graph.json", graph)

    git = git_metadata(root)
    write_json(
        output_dir / "manifest.json",
        manifest(
            ctl_version=f"{CTL_CODEBASE_VERSION}-codebase-adapter",
            source_id=package_name,
            source_path=str(root),
            source_sha256=None,
            adapters=[{"name": "ctl-codebase-adapter", "status": "ok", "record_count": len(records)}],
            record_count=len(records),
            extra={
                "source_type": "codebase",
                "file_count": len(files),
                "graph": "graph/ctl-code-graph.json",
                "git": git,
            },
        ),
    )
    write_html_report(output_dir, package_name, records, graph)
    export_okf(output_dir)
    return {"output": str(output_dir), "records": len(records), "files": len(files), "graph": graph["summary"]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CTL package from a source codebase.")
    parser.add_argument("root", type=Path, help="Repository root to ingest.")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output CTL package directory.")
    parser.add_argument("--name", default=None, help="Source/package id. Defaults to root folder name.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_codebase_package(args.root, args.output, args.name)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
