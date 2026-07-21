# Database Adapter Contract

Database adapters are rebuildable index writers. They read CTL package files and
write optional search, SQL, graph, vector, or analytics indexes. They do not own
the source data.

```text
CTL package -> database adapter -> rebuildable index
```

The CTL package remains the durable source of truth.

## Required Inputs

A database adapter should read these package files when they are present:

| File | Purpose |
| --- | --- |
| `manifest.json` | package identity, schema version, source id, adapter list |
| `manifests/provenance.json` | source custody, parser details, timestamps, traceability |
| `assets/tables/ctl-records.json` | canonical CTL records |
| `search.json` | lightweight text search rows |
| `okf/index.md` | OKF-compatible catalogue entry point |

Adapters may read `documents/*.html` and linked assets when they need richer
HTML fragments, image paths, table crops, or derived embeddings. They should not
modify source package files.

## Required Outputs

Database adapters should write their outputs under an index-specific folder:

```text
indexes/
  sqlite/
    ctl-index.sqlite
    index-manifest.json
  sqlite-vec/
    ctl-vector-index.sqlite
    index-manifest.json
```

The `index-manifest.json` file should record:

- adapter name and version
- upstream dependency name and version
- source package path or package id
- source package schema version
- created timestamp
- indexed record count
- embedding model and dimensions when vectors are used
- tables/collections created
- whether network access was used
- whether credentials were required

## Safety Rules

Database adapters must:

- preserve original CTL files
- use relative paths when storing references back to package assets
- keep CTL record ids intact
- fail gracefully when optional dependencies are missing
- make indexes delete-safe and rebuildable
- record enough metadata to reproduce the index

Database adapters must not:

- parse original PDFs, documents, videos, or websites directly
- mutate `assets/original/`
- rewrite `ctl-records.json`
- overwrite provenance
- hide credentials in package folders
- treat the database as the authoritative memory layer

## Baseline Tables

SQL-style adapters should start with a small common shape:

```text
ctl_package
ctl_records
ctl_record_text
ctl_record_links
ctl_record_assets
ctl_record_tags
ctl_index_runs
```

Vector adapters may add:

```text
ctl_embeddings
ctl_embedding_models
ctl_vector_queries
```

Graph adapters may add:

```text
ctl_nodes
ctl_edges
ctl_graph_runs
```

Exact database schemas can vary, but the CTL record id must remain the join key
back to the package.

## SQLite Implementation Plan

SQLite is the first local index target because it is small, portable, and
already available in Python through the standard library.

Implemented in `ctl_core/adapters/database/sqlite_index.py`.

```shell
python -m ctl_core index-sqlite output/my-package
python -m ctl_core query-sqlite output/my-package "search words"
```

The adapter reads a CTL package and writes `indexes/sqlite/ctl-index.sqlite`.
It creates tables for package metadata, records, text rows, links, tags, and
assets, adds SQLite FTS for keyword search, writes
`indexes/sqlite/index-manifest.json`, and is covered by the default smoke test.

SQLite should require no network access and no credentials.

## SQLite-vec Implementation Plan

SQLite-vec is the first lightweight local vector target. It should be optional,
detected at runtime, and never vendored into CTL-Core.

Implemented in `ctl_core/adapters/database/sqlite_vec_index.py`.

```shell
python -m ctl_core index-sqlite-vec output/my-package --embeddings examples/sqlite-vec-demo-embeddings.jsonl
python -m ctl_core query-sqlite-vec output/my-package --embedding "[0.1, 0.2, 0.3]"
```

This adapter accepts embeddings from a user-provided embedding provider or
precomputed embedding file. It does not require or call any hosted model
provider in CTL-Core. It writes vectors into
`indexes/sqlite-vec/ctl-vector-index.sqlite`, stores embedding model metadata,
and records dimensions in `indexes/sqlite-vec/index-manifest.json`.
The included demo embeddings file is synthetic and exists only to document the
file shape.

SQLite-vec should sit between plain SQLite keyword search and heavier vector
stores such as Qdrant or LanceDB.

## Kuzu Implementation

Implemented in `ctl_core/adapters/database/kuzu_index.py`.

```shell
python -m ctl_core index-kuzu output/my-package
python -m ctl_core query-kuzu output/my-package record-0001
```

Kuzu creates an embedded graph index under `indexes/kuzu/ctl-graph.kuzu`.
The adapter stores package, record, tag, asset, and link-target nodes, plus
relationships from packages to records and from records to their tags, assets,
and links. It is optional and fails with install guidance when Kuzu is missing.

## Future Adapter Targets

After SQLite, SQLite-vec, and Kuzu, promote database adapters in this order:

1. DuckDB for local analytics.
2. PostgreSQL for multi-user/server deployments.
3. Qdrant for serious vector search.
4. LanceDB for local multimodal vectors.
5. MongoDB for document-shaped workflow metadata.
6. Neo4j/Cypher export for server graph workflows.
7. libSQL/Turso local for SQLite-compatible experiments.

Each adapter should follow the same rule:

```text
The database is an index. The CTL package is the source.
```
