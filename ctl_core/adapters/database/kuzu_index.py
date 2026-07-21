"""Optional Kuzu graph adapter for CTL packages.

Kuzu is a rebuildable local graph index. CTL package files remain the source of
truth.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ADAPTER_ID = "database.kuzu"
ADAPTER_VERSION = "0.1"


def default_index_path(package_root: Path) -> Path:
    return package_root / "indexes" / "kuzu" / "ctl-graph.kuzu"


def manifest_path(database_path: Path) -> Path:
    return database_path.parent / "index-manifest.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_package(package_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = read_json(package_root / "manifest.json")
    records = read_json(package_root / "assets" / "tables" / "ctl-records.json")
    if not isinstance(manifest, dict):
        raise ValueError("manifest.json must contain an object")
    if not isinstance(records, list):
        raise ValueError("ctl-records.json must contain an array")
    return manifest, records


def load_kuzu() -> tuple[Any, str]:
    try:
        import kuzu  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Kuzu is not installed. Install it with: python -m pip install kuzu") from exc
    return kuzu, getattr(kuzu, "__version__", "unknown")


def safe_reset_database(database_path: Path) -> None:
    database_path = database_path.resolve()
    parts = {part.lower() for part in database_path.parts}
    if "indexes" not in parts or database_path.name != "ctl-graph.kuzu":
        raise ValueError(f"Refusing to reset unexpected Kuzu path: {database_path}")
    if database_path.exists():
        if database_path.is_dir():
            shutil.rmtree(database_path)
        else:
            database_path.unlink()
    database_path.parent.mkdir(parents=True, exist_ok=True)


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def create_schema(connection: Any) -> None:
    connection.execute(
        "CREATE NODE TABLE Package(source_id STRING, source STRING, manifest_json STRING, PRIMARY KEY (source_id))"
    )
    connection.execute(
        """
        CREATE NODE TABLE Record(
          record_id STRING,
          source_id STRING,
          record_type STRING,
          record_order INT64,
          text STRING,
          html STRING,
          source_path STRING,
          page INT64,
          asset_path STRING,
          raw_json STRING,
          PRIMARY KEY (record_id)
        )
        """
    )
    connection.execute("CREATE NODE TABLE Tag(name STRING, PRIMARY KEY (name))")
    connection.execute("CREATE NODE TABLE Asset(path STRING, PRIMARY KEY (path))")
    connection.execute("CREATE NODE TABLE LinkTarget(target STRING, PRIMARY KEY (target))")
    connection.execute("CREATE REL TABLE CONTAINS(FROM Package TO Record)")
    connection.execute("CREATE REL TABLE HAS_TAG(FROM Record TO Tag)")
    connection.execute("CREATE REL TABLE HAS_ASSET(FROM Record TO Asset)")
    connection.execute("CREATE REL TABLE LINKS_TO(FROM Record TO LinkTarget, relation STRING, link_json STRING)")


def index_package(package_root: Path, database_path: Path | None = None) -> dict[str, Any]:
    package_root = package_root.resolve()
    database_path = (database_path or default_index_path(package_root)).resolve()
    manifest, records = load_package(package_root)
    kuzu, kuzu_version = load_kuzu()
    safe_reset_database(database_path)

    database = kuzu.Database(str(database_path))
    connection = kuzu.Connection(database)
    create_schema(connection)

    source_id = str(manifest.get("source_id", "package"))
    connection.execute(
        "CREATE (:Package {source_id: $source_id, source: $source, manifest_json: $manifest_json})",
        {
            "source_id": source_id,
            "source": str(manifest.get("source", "")),
            "manifest_json": as_json(manifest),
        },
    )

    record_count = 0
    tag_count = 0
    asset_count = 0
    link_count = 0
    seen_tags: set[str] = set()
    seen_assets: set[str] = set()
    seen_targets: set[str] = set()

    for record in records:
        if not isinstance(record, dict):
            continue
        record_id = str(record.get("id", "")).strip()
        if not record_id:
            continue
        params = {
            "record_id": record_id,
            "source_id": str(record.get("source_id", source_id)),
            "record_type": str(record.get("type", "")),
            "record_order": int(record.get("order") or 0),
            "text": str(record.get("text", "") or ""),
            "html": str(record.get("html", "") or ""),
            "source_path": str(record.get("source_path", "") or ""),
            "page": record.get("page"),
            "asset_path": str(record.get("asset_path", "") or ""),
            "raw_json": as_json(record),
        }
        connection.execute(
            """
            CREATE (:Record {
              record_id: $record_id,
              source_id: $source_id,
              record_type: $record_type,
              record_order: $record_order,
              text: $text,
              html: $html,
              source_path: $source_path,
              page: $page,
              asset_path: $asset_path,
              raw_json: $raw_json
            })
            """,
            params,
        )
        connection.execute(
            """
            MATCH (p:Package), (r:Record)
            WHERE p.source_id = $source_id AND r.record_id = $record_id
            CREATE (p)-[:CONTAINS]->(r)
            """,
            {"source_id": source_id, "record_id": record_id},
        )
        record_count += 1

        for tag in record.get("tags", []) or []:
            tag_name = str(tag)
            if tag_name not in seen_tags:
                connection.execute("CREATE (:Tag {name: $name})", {"name": tag_name})
                seen_tags.add(tag_name)
                tag_count += 1
            connection.execute(
                """
                MATCH (r:Record), (t:Tag)
                WHERE r.record_id = $record_id AND t.name = $tag
                CREATE (r)-[:HAS_TAG]->(t)
                """,
                {"record_id": record_id, "tag": tag_name},
            )

        asset_paths = []
        if record.get("asset_path"):
            asset_paths.append(str(record.get("asset_path")))
        asset_paths.extend(str(asset) for asset in (record.get("asset_paths", []) or []) if asset)
        for asset_path in asset_paths:
            if asset_path not in seen_assets:
                connection.execute("CREATE (:Asset {path: $path})", {"path": asset_path})
                seen_assets.add(asset_path)
                asset_count += 1
            connection.execute(
                """
                MATCH (r:Record), (a:Asset)
                WHERE r.record_id = $record_id AND a.path = $path
                CREATE (r)-[:HAS_ASSET]->(a)
                """,
                {"record_id": record_id, "path": asset_path},
            )

        for link in record.get("links", []) or []:
            if isinstance(link, dict):
                target = str(link.get("target", link.get("href", "")) or "")
                relation = str(link.get("relation", link.get("rel", "")) or "")
                link_json = as_json(link)
            else:
                target = str(link)
                relation = ""
                link_json = as_json({"target": target})
            if not target:
                continue
            if target not in seen_targets:
                connection.execute("CREATE (:LinkTarget {target: $target})", {"target": target})
                seen_targets.add(target)
            connection.execute(
                """
                MATCH (r:Record), (target:LinkTarget)
                WHERE r.record_id = $record_id AND target.target = $target
                CREATE (r)-[:LINKS_TO {relation: $relation, link_json: $link_json}]->(target)
                """,
                {"record_id": record_id, "target": target, "relation": relation, "link_json": link_json},
            )
            link_count += 1

    created_at = datetime.now(timezone.utc).isoformat()
    index_manifest = {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "dependency": "kuzu",
        "dependency_version": kuzu_version,
        "source_package": package_root.as_posix(),
        "source_id": manifest.get("source_id"),
        "source_schema_version": manifest.get("ctl_schema_version"),
        "created_at": created_at,
        "indexed_record_count": record_count,
        "tag_count": tag_count,
        "asset_count": asset_count,
        "link_count": link_count,
        "database": database_path.as_posix(),
        "tables": ["Package", "Record", "Tag", "Asset", "LinkTarget"],
        "relationships": ["CONTAINS", "HAS_TAG", "HAS_ASSET", "LINKS_TO"],
        "network_access": False,
        "credentials_required": False,
        "source_of_truth": "semantic HTML and CTL package files",
    }
    manifest_path(database_path).write_text(json.dumps(index_manifest, indent=2), encoding="utf-8")
    return index_manifest


def resolve_database_path(value: Path) -> Path:
    value = value.resolve()
    if value.is_dir():
        return default_index_path(value)
    return value


def query_neighbors(database_or_package: Path, record_id: str, limit: int = 20) -> list[dict[str, Any]]:
    database_path = resolve_database_path(database_or_package)
    if not database_path.exists():
        raise FileNotFoundError(f"Kuzu graph index not found: {database_path}")
    kuzu, _kuzu_version = load_kuzu()
    database = kuzu.Database(str(database_path))
    connection = kuzu.Connection(database)
    result = connection.execute(
        """
        MATCH (r:Record)-[rel]->(n)
        WHERE r.record_id = $record_id
        RETURN label(n) AS node_type, properties(n) AS node, label(rel) AS relation
        LIMIT $limit
        """,
        {"record_id": record_id, "limit": limit},
    )
    rows: list[dict[str, Any]] = []
    while result.has_next():
        row = result.get_next()
        rows.append({"node_type": row[0], "node": row[1], "relation": row[2]})
    return rows
