# Why CTL-Core

CTL-Core exists because useful source material is richer than plain text.

Markdown is excellent for notes, but ingestion pipelines often flatten tables,
figures, diagrams, links, captions, layout clues, and provenance too early. RAG
systems often go further and shred sources into chunks that are useful for
search but hard for humans to inspect later.

CTL-Core takes a different path:

```text
Copy -> Tag -> Link
```

It preserves the original source, extracts reusable records and assets, writes
plain semantic HTML, and emits rebuildable indexes such as search JSON and
OKF-compatible Markdown cards.

## The Core Idea

```text
Original source files + semantic HTML + reusable assets = durable package
Databases, vectors, graphs, and search indexes = replaceable accelerators
```

The CTL package is the record. Everything else can be rebuilt.

## What CTL Preserves

- original source files
- extracted or copied assets
- semantic HTML records
- tables as HTML and records
- images/figures as reusable assets
- links between records, sources, and assets
- provenance and checksums
- OKF-compatible cards for catalogue/search workflows

## What CTL Avoids

- making a database the only copy of knowledge
- locking a user into one vendor or model
- requiring a cloud service to read local data
- mixing parser code, database code, cloud sync, and agent workflows into one
  brittle tool
- silently treating social/signal data as verified fact

## The Scrapyard Model

RAG often behaves like a shredder: useful for retrieval, but the original parts
are hard to reuse.

Markdown can behave like a crusher: readable, but many rich structures get
flattened.

CTL behaves like a parts catalogue: the source is disassembled into useful
pieces, tagged, linked, and shelved while the original source remains intact.

## Relationship To OKF

CTL treats OKF-style Markdown cards as a catalogue layer:

```text
CTL HTML/assets/manifests = rich source package
OKF Markdown cards        = portable catalogue/index cards
```

The cards point back to the richer package.

## Relationship To Databases

Databases are optional adapters.

Use SQLite, DuckDB, PostgreSQL, Qdrant, Kuzu, LanceDB, Neo4j, or any other
indexing system when it helps. If the database is lost, the CTL package can be
re-indexed.

The database is an index, not the owner of your knowledge.
