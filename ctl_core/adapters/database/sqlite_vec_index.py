"""Optional sqlite-vec adapter for CTL packages.

This adapter stores precomputed embeddings in a rebuildable local SQLite file.
It does not call embedding providers. The caller supplies embeddings.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


ADAPTER_ID = "database.sqlite_vec"
ADAPTER_VERSION = "0.1"


def default_index_path(package_root: Path) -> Path:
    return package_root / "indexes" / "sqlite-vec" / "ctl-vector-index.sqlite"


def manifest_path(database_path: Path) -> Path:
    return database_path.parent / "index-manifest.json"


def load_sqlite_vec(connection: sqlite3.Connection) -> str:
    try:
        import sqlite_vec  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "sqlite-vec is not installed. Install it with: python -m pip install sqlite-vec"
        ) from exc

    try:
        sqlite_vec.load(connection)
    except AttributeError:
        connection.enable_load_extension(True)
        sqlite_vec.loadable_path()  # type: ignore[attr-defined]
        connection.load_extension(sqlite_vec.loadable_path())  # type: ignore[attr-defined]
        connection.enable_load_extension(False)
    return getattr(sqlite_vec, "__version__", "unknown")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_records(package_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = read_json(package_root / "manifest.json")
    records = read_json(package_root / "assets" / "tables" / "ctl-records.json")
    if not isinstance(manifest, dict):
        raise ValueError("manifest.json must contain an object")
    if not isinstance(records, list):
        raise ValueError("ctl-records.json must contain an array")
    return manifest, records


def load_embeddings(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        rows = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: invalid JSONL at line {line_number}") from exc
        return rows
    data = read_json(path)
    if isinstance(data, dict) and isinstance(data.get("embeddings"), list):
        return data["embeddings"]
    if isinstance(data, list):
        return data
    raise ValueError("Embedding file must be a JSON array, JSONL rows, or {'embeddings': [...]}")


def normalize_embedding(row: dict[str, Any], dimensions: int | None) -> tuple[str, list[float], dict[str, Any]]:
    record_id = str(row.get("record_id", row.get("id", ""))).strip()
    if not record_id:
        raise ValueError("Embedding row is missing record_id")
    vector = row.get("embedding", row.get("vector"))
    if not isinstance(vector, list) or not vector:
        raise ValueError(f"Embedding row for {record_id} is missing embedding/vector array")
    embedding = [float(value) for value in vector]
    if dimensions is not None and len(embedding) != dimensions:
        raise ValueError(f"Embedding for {record_id} has {len(embedding)} dimensions; expected {dimensions}")
    metadata = {key: value for key, value in row.items() if key not in {"record_id", "id", "embedding", "vector"}}
    return record_id, embedding, metadata


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.9g}" for value in values) + "]"


def open_connection(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("pragma foreign_keys = on")
    return connection


def index_package(
    package_root: Path,
    embeddings_path: Path,
    *,
    database_path: Path | None = None,
    dimensions: int | None = None,
    model: str = "user-provided",
) -> dict[str, Any]:
    package_root = package_root.resolve()
    embeddings_path = embeddings_path.resolve()
    database_path = (database_path or default_index_path(package_root)).resolve()
    manifest, records = load_records(package_root)
    valid_record_ids = {str(record.get("id", "")).strip() for record in records if isinstance(record, dict)}
    embedding_rows = load_embeddings(embeddings_path)
    normalized = [normalize_embedding(row, dimensions) for row in embedding_rows if isinstance(row, dict)]
    if not normalized:
        raise ValueError("No valid embeddings found")
    detected_dimensions = len(normalized[0][1])
    if any(len(embedding) != detected_dimensions for _record_id, embedding, _metadata in normalized):
        raise ValueError("All embeddings must have the same dimensions")

    with open_connection(database_path) as connection:
        sqlite_vec_version = load_sqlite_vec(connection)
        connection.executescript(
            """
            drop table if exists ctl_vector_records;
            drop table if exists ctl_embedding_models;
            drop table if exists ctl_vector_runs;
            drop table if exists ctl_vectors;
            """
        )
        connection.execute(
            f"create virtual table ctl_vectors using vec0(embedding float[{detected_dimensions}])"
        )
        connection.executescript(
            """
            create table ctl_vector_records (
              rowid integer primary key,
              record_id text not null unique,
              metadata_json text not null
            );

            create table ctl_embedding_models (
              id integer primary key,
              model text not null,
              dimensions integer not null
            );

            create table ctl_vector_runs (
              id integer primary key,
              adapter_id text not null,
              adapter_version text not null,
              sqlite_vec_version text not null,
              source_package text not null,
              embeddings_path text not null,
              indexed_record_count integer not null,
              ignored_record_count integer not null,
              created_at text not null
            );
            """
        )
        ignored = 0
        inserted = 0
        for record_id, embedding, metadata in normalized:
            if record_id not in valid_record_ids:
                ignored += 1
                continue
            cursor = connection.execute(
                "insert into ctl_vector_records (record_id, metadata_json) values (?, ?)",
                (record_id, json.dumps(metadata, ensure_ascii=False, sort_keys=True)),
            )
            rowid = cursor.lastrowid
            connection.execute(
                "insert into ctl_vectors (rowid, embedding) values (?, ?)",
                (rowid, vector_literal(embedding)),
            )
            inserted += 1

        created_at = str(connection.execute("select datetime('now')").fetchone()[0])
        connection.execute(
            "insert into ctl_embedding_models (model, dimensions) values (?, ?)",
            (model, detected_dimensions),
        )
        connection.execute(
            """
            insert into ctl_vector_runs (
              adapter_id, adapter_version, sqlite_vec_version, source_package,
              embeddings_path, indexed_record_count, ignored_record_count,
              created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ADAPTER_ID,
                ADAPTER_VERSION,
                sqlite_vec_version,
                package_root.as_posix(),
                embeddings_path.as_posix(),
                inserted,
                ignored,
                created_at,
            ),
        )
        connection.commit()

    index_manifest = {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "dependency": "sqlite-vec",
        "source_package": package_root.as_posix(),
        "source_id": manifest.get("source_id"),
        "source_schema_version": manifest.get("ctl_schema_version"),
        "created_at": created_at,
        "indexed_record_count": inserted,
        "ignored_record_count": ignored,
        "embedding_model": model,
        "dimensions": detected_dimensions,
        "database": database_path.as_posix(),
        "embeddings_path": embeddings_path.as_posix(),
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


def query_index(database_or_package: Path, embedding: list[float], limit: int = 10) -> list[dict[str, Any]]:
    database_path = resolve_database_path(database_or_package)
    if not database_path.exists():
        raise FileNotFoundError(f"SQLite-vec index not found: {database_path}")
    with open_connection(database_path) as connection:
        load_sqlite_vec(connection)
        rows = connection.execute(
            """
            select r.record_id, v.distance
            from ctl_vectors v
            join ctl_vector_records r on r.rowid = v.rowid
            where v.embedding match ?
              and k = ?
            order by v.distance
            """,
            (vector_literal(embedding), limit),
        ).fetchall()
        return [dict(row) for row in rows]
