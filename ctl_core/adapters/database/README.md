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

Examples:

- SQLite
- DuckDB
- PostgreSQL
- MongoDB
- Qdrant
- Kuzu
- Neo4j
- LanceDB
- libSQL/Turso local
