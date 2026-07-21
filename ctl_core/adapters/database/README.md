# Database And Index Adapters

Database/index adapters rebuild searchable indexes from CTL packages.

They may:

- read CTL package files
- write local or remote indexes
- create SQL, graph, vector, or search-store records

They must not:

- parse original source documents directly
- alter CTL package source-of-truth files
- connect to social platforms
- manage workflow jobs

Database adapters are optional acceleration layers. CTL package files remain
the durable source.

See [../../../docs/database-adapter-contract.md](../../../docs/database-adapter-contract.md)
for the shared contract, safety rules, baseline tables, and SQLite/SQLite-vec
implementation plan.

Included adapters:

- `sqlite_index.py` builds a local SQLite database with FTS keyword search.
- `sqlite_vec_index.py` builds an optional `sqlite-vec` vector index from
  user-provided embeddings.
- `kuzu_index.py` builds an optional Kuzu graph index from records, tags, links,
  and assets.

Common commands:

```shell
python -m ctl_core index-sqlite output/my-package
python -m ctl_core query-sqlite output/my-package "search words"
python -m ctl_core index-sqlite-vec output/my-package --embeddings examples/sqlite-vec-demo-embeddings.jsonl
python -m ctl_core index-kuzu output/my-package
```

Adapter targets:

- SQLite
- SQLite-vec
- DuckDB
- PostgreSQL
- MongoDB
- Qdrant
- Kuzu
- Neo4j
- LanceDB
- libSQL/Turso local

## Lightweight Local Vector Option

`sqlite-vec` belongs between plain SQLite and heavier vector stores such as
Qdrant or LanceDB. It should be treated as an optional local vector index:

- CTL package files remain the source of truth.
- SQLite FTS can handle keyword search.
- `sqlite-vec` can hold rebuildable embeddings for semantic search.
- The resulting `.sqlite` file can sit beside a CTL package and be deleted or
  rebuilt without damaging the package.

Do not vendor `sqlite-vec` into CTL-Core. Detect whether the user installed it,
then fail gracefully with install guidance when it is unavailable.

The example embeddings file in `examples/sqlite-vec-demo-embeddings.jsonl` is
synthetic. Real use should write one row per CTL record id using whatever
embedding provider the user trusts.

## Embedded Graph Option

Kuzu is the first local graph target. It can represent CTL packages as package,
record, tag, asset, and link nodes. Like SQLite and sqlite-vec, the Kuzu folder
is a rebuildable index:

- The CTL package files remain the source of truth.
- The graph can be deleted and rebuilt.
- Kuzu is optional and must be installed by the user.
- Missing Kuzu dependency should produce install guidance, not a crash trace.
