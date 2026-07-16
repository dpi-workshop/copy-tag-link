# CTL-Core Roadmap

CTL-Core is starting as a small, file-first ingestion layer. The goal is not to
build every parser, database, dashboard, or agent workflow into the core repo.
The goal is to keep the package contract durable, readable, and easy to extend.

## Current MVP

The first public release proves the basic shape:

- preserve original source files
- copy reusable assets
- write semantic HTML review pages
- emit `manifest.json`
- emit `search.json`
- emit `assets/tables/ctl-records.json`
- emit `manifests/provenance.json`
- emit OKF-compatible Markdown cards
- run smoke tests and release safety checks
- document how agents should read CTL packages

## Next: CLI

Add a small command-line interface over the current scripts.

Planned commands:

```text
ctl ingest SOURCE -o PACKAGE
ctl inspect PACKAGE
ctl validate PACKAGE
ctl export-okf PACKAGE
ctl search PACKAGE QUERY
```

The CLI should remain thin. It should wrap the same package layout instead of
creating a new hidden data model.

## Next: Package Validation

Add a validator that checks whether a CTL package contains the expected files,
valid JSON, usable record ids, source references, and provenance.

Validation should answer:

```text
Can a human open it?
Can an agent read it?
Can an index be rebuilt from it?
Can the original source be traced?
```

## Next: Adapter Manifests

Formalize adapter metadata so external adapters can describe:

- supported source formats
- required dependencies
- license status
- emitted record types
- whether the adapter is local-only or network-enabled
- whether it is safe for untrusted input
- whether it preserves original files and assets

Adapters should be optional. CTL-Core should not vendor heavy parser projects.

## Next: Parser Adapters

Promote cleaned-up optional adapters for common ingestion needs:

- Docling for PDF/DOCX-style document layout
- MinerU for academic and scientific PDFs
- PaddleOCR for OCR and image text
- Pandoc as an external conversion bridge
- Playwright for rendered web pages
- codebase ingestion for source trees and repo notes

The core package contract should stay the same no matter which parser is used.

## Next: Index Adapters

Add rebuildable index adapters that read CTL packages and write optional search
layers.

Targets may include:

- SQLite
- DuckDB
- PostgreSQL
- Qdrant
- LanceDB
- Kuzu
- Neo4j/Cypher exports
- libSQL/Turso local experiments

These indexes are accelerators. They are not the source of truth.

## Next: MCP And Agent Skills

Expose CTL packages through agent-friendly tools.

Expected MCP operations:

```text
list_packages
read_manifest
search_records
read_record
read_asset
read_okf_cards
write_annotation
validate_package
```

Expected skill behavior:

- read CTL memory before answering
- cite CTL record ids and provenance
- preserve original source records
- write annotations and decisions separately
- use package assets in derived outputs

## Next: Annotation And Decision Layer

Add a separate derived layer for:

- notes
- corrections
- verification status
- disputes
- decisions
- follow-up tasks
- human approvals

This layer must not overwrite original source evidence. If a source claim is
wrong, CTL should preserve the original claim and attach the correction as a
linked annotation.

## Related Projects

CTL-Core is the document/data layer. Related tools may remain separate repos:

- Watcher: video, audio, meeting, screen, and transcript ingestion
- Translator: linked original/translated text packages
- CSS Fireworks: reusable styling for CTL HTML outputs
- Command Center: workflow scheduling, review, and output management

These tools may use CTL packages, but CTL-Core should remain useful without
them.

## Non-Goals

CTL-Core should not become:

- a SaaS dashboard
- a vector database
- a graph database
- a model wrapper
- a heavyweight parser bundle
- a cloud account requirement
- a hidden proprietary memory store

The core promise is simple:

```text
Copy, Tag, Link source material into portable semantic HTML packages.
The package survives the tools.
```

