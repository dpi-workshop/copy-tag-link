"""SQLite and FTS index adapter for CTL packages.

The SQLite database is a rebuildable index. The CTL package remains the source
of truth.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


ADAPTER_ID = "database.sqlite"
ADAPTER_VERSION = "0.1"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now_sql(connection: sqlite3.Connection) -> str:
    return str(connection.execute("select datetime('now')").fetchone()[0])


def default_index_path(package_root: Path) -> Path:
    return package_root / "indexes" / "sqlite" / "ctl-index.sqlite"


def manifest_path(database_path: Path) -> Path:
    return database_path.parent / "index-manifest.json"


def load_package(package_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    manifest = read_json(package_root / "manifest.json")
    records = read_json(package_root / "assets" / "tables" / "ctl-records.json")
    search_rows = read_json(package_root / "search.json")
    if not isinstance(manifest, dict):
        raise ValueError("manifest.json must contain an object")
    if not isinstance(records, list):
        raise ValueError("ctl-records.json must contain an array")
    if not isinstance(search_rows, list):
        raise ValueError("search.json must contain an array")
    return manifest, records, search_rows


def open_connection(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("pragma foreign_keys = on")
    return connection


def reset_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        drop table if exists ctl_record_fts;
        drop table if exists ctl_record_tags;
        drop table if exists ctl_record_assets;
        drop table if exists ctl_record_links;
        drop table if exists ctl_record_text;
        drop table if exists ctl_records;
        drop table if exists ctl_index_runs;
        drop table if exists ctl_package;

        create table ctl_package (
          id integer primary key check (id = 1),
          source_id text not null,
          source text,
          source_sha256 text,
          ctl_schema_version text,
          record_count integer not null,
          package_manifest_json text not null,
          indexed_at text not null
        );

        create table ctl_records (
          record_id text primary key,
          source_id text,
          record_type text not null,
          record_order integer,
          source_path text,
          page integer,
          bbox_json text,
          asset_path text,
          confidence real,
          html text,
          metadata_json text,
          provenance_json text,
          raw_json text not null
        );

        create table ctl_record_text (
          record_id text primary key references ctl_records(record_id) on delete cascade,
          text text,
          html text,
          search_text text
        );

        create table ctl_record_links (
          id integer primary key autoincrement,
          record_id text not null references ctl_records(record_id) on delete cascade,
          target text,
          relation text,
          link_json text not null
        );

        create table ctl_record_assets (
          id integer primary key autoincrement,
          record_id text not null references ctl_records(record_id) on delete cascade,
          asset_path text not null
        );

        create table ctl_record_tags (
          id integer primary key autoincrement,
          record_id text not null references ctl_records(record_id) on delete cascade,
          tag text not null
        );

        create table ctl_index_runs (
          id integer primary key autoincrement,
          adapter_id text not null,
          adapter_version text not null,
          indexed_at text not null,
          record_count integer not null,
          source_package text not null,
          notes text
        );
        """
    )

    try:
        connection.execute(
            "create virtual table ctl_record_fts using fts5(record_id unindexed, record_type unindexed, search_text)"
        )
    except sqlite3.OperationalError:
        connection.execute(
            """
            create table ctl_record_fts (
              record_id text,
              record_type text,
              search_text text
            )
            """
        )


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def record_search_text(record: dict[str, Any]) -> str:
    parts = [
        str(record.get("id", "")),
        str(record.get("type", "")),
        str(record.get("text", "")),
        str(record.get("html", "")),
        " ".join(str(tag) for tag in record.get("tags", []) if tag is not None),
    ]
    return "\n".join(part for part in parts if part)


def index_package(package_root: Path, database_path: Path | None = None) -> dict[str, Any]:
    package_root = package_root.resolve()
    database_path = (database_path or default_index_path(package_root)).resolve()
    manifest, records, _search_rows = load_package(package_root)

    with open_connection(database_path) as connection:
        reset_schema(connection)
        indexed_at = utc_now_sql(connection)
        connection.execute(
            """
            insert into ctl_package (
              id, source_id, source, source_sha256, ctl_schema_version,
              record_count, package_manifest_json, indexed_at
            ) values (1, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(manifest.get("source_id", "")),
                str(manifest.get("source", "")),
                manifest.get("source_sha256"),
                str(manifest.get("ctl_schema_version", "")),
                len(records),
                as_json(manifest),
                indexed_at,
            ),
        )

        for record in records:
            if not isinstance(record, dict):
                continue
            record_id = str(record.get("id", "")).strip()
            if not record_id:
                continue
            asset_path = str(record.get("asset_path", "") or "")
            connection.execute(
                """
                insert into ctl_records (
                  record_id, source_id, record_type, record_order, source_path,
                  page, bbox_json, asset_path, confidence, html,
                  metadata_json, provenance_json, raw_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    str(record.get("source_id", "")),
                    str(record.get("type", "")),
                    record.get("order"),
                    str(record.get("source_path", "") or ""),
                    record.get("page"),
                    as_json(record.get("bbox")),
                    asset_path,
                    record.get("confidence"),
                    str(record.get("html", "") or ""),
                    as_json(record.get("metadata", {})),
                    as_json(record.get("provenance", {})),
                    as_json(record),
                ),
            )
            search_text = record_search_text(record)
            connection.execute(
                "insert into ctl_record_text (record_id, text, html, search_text) values (?, ?, ?, ?)",
                (
                    record_id,
                    str(record.get("text", "") or ""),
                    str(record.get("html", "") or ""),
                    search_text,
                ),
            )
            connection.execute(
                "insert into ctl_record_fts (record_id, record_type, search_text) values (?, ?, ?)",
                (record_id, str(record.get("type", "")), search_text),
            )
            if asset_path:
                connection.execute(
                    "insert into ctl_record_assets (record_id, asset_path) values (?, ?)",
                    (record_id, asset_path),
                )
            for asset in record.get("asset_paths", []) or []:
                if asset:
                    connection.execute(
                        "insert into ctl_record_assets (record_id, asset_path) values (?, ?)",
                        (record_id, str(asset)),
                    )
            for tag in record.get("tags", []) or []:
                connection.execute(
                    "insert into ctl_record_tags (record_id, tag) values (?, ?)",
                    (record_id, str(tag)),
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
                connection.execute(
                    "insert into ctl_record_links (record_id, target, relation, link_json) values (?, ?, ?, ?)",
                    (record_id, target, relation, link_json),
                )

        connection.execute(
            """
            insert into ctl_index_runs (
              adapter_id, adapter_version, indexed_at, record_count,
              source_package, notes
            ) values (?, ?, ?, ?, ?, ?)
            """,
            (ADAPTER_ID, ADAPTER_VERSION, indexed_at, len(records), package_root.as_posix(), "SQLite/FTS index"),
        )
        connection.commit()

    index_manifest = {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "dependency": "python sqlite3",
        "source_package": package_root.as_posix(),
        "source_id": manifest.get("source_id"),
        "source_schema_version": manifest.get("ctl_schema_version"),
        "created_at": indexed_at,
        "indexed_record_count": len(records),
        "database": database_path.as_posix(),
        "tables": [
            "ctl_package",
            "ctl_records",
            "ctl_record_text",
            "ctl_record_links",
            "ctl_record_assets",
            "ctl_record_tags",
            "ctl_index_runs",
            "ctl_record_fts",
        ],
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


def query_index(database_or_package: Path, query: str, limit: int = 10) -> list[dict[str, Any]]:
    database_path = resolve_database_path(database_or_package)
    if not database_path.exists():
        raise FileNotFoundError(f"SQLite index not found: {database_path}")

    with open_connection(database_path) as connection:
        try:
            rows = connection.execute(
                """
                select f.record_id, f.record_type, snippet(ctl_record_fts, 2, '[', ']', '...', 12) as snippet
                from ctl_record_fts f
                where ctl_record_fts match ?
                limit ?
                """,
                (query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            like_query = f"%{query}%"
            rows = connection.execute(
                """
                select record_id, record_type, search_text as snippet
                from ctl_record_fts
                where search_text like ?
                limit ?
                """,
                (like_query, limit),
            ).fetchall()
        return [dict(row) for row in rows]
