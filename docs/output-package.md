# CTL Package Anatomy

A CTL package is an ordinary folder. It can be opened locally, zipped, backed
up, published as static files, or indexed with a database.

```text
package/
  assets/
    original/
    images/
    tables/
  documents/
  graph/
  intermediate/
  manifests/
  okf/
  manifest.json
  search.json
```

## Top-Level Files

| File | Purpose |
| --- | --- |
| `manifest.json` | Package summary, source id, source path/URL, adapter list, record count |
| `search.json` | Small rebuildable search index for quick local lookup |

## `assets/original/`

Stores the original source file or source reference.

Examples:

- input PDF
- input HTML file
- source URL text file
- source repository path metadata

Original sources are preserved. CTL records are derived from them.

## `assets/images/`

Stores copied or extracted visual assets.

Examples:

- PDF table crop
- PDF image crop
- diagram crop
- copied local HTML images

These are reusable pieces that can later be used in reports, lessons, videos,
web pages, or other outputs.

## `assets/tables/`

Stores canonical structured records.

Important files:

```text
assets/tables/ctl-records.json
```

Each record may include:

- `id`
- `source_id`
- `type`
- `order`
- `text`
- `html`
- `asset_path`
- `source_path`
- `page`
- `bbox`
- `links`
- `tags`
- `confidence`
- `provenance`
- `metadata`

## `documents/`

Stores plain semantic HTML review pages.

These pages are intentionally simple. They are for inspection, linking, and
static browsing. Styling belongs in downstream tools.

Examples:

- `parser-lab-report.html`
- `source-intake-report.html`
- `codebase-report.html`

## `intermediate/`

Stores adapter-specific raw or diagnostic output.

This helps explain what happened during ingestion without making intermediate
files the source of truth.

## `manifests/`

Stores provenance and source metadata.

Important files:

```text
manifests/provenance.json
```

This records where the source came from, what adapter touched it, when it was
processed, and what assumptions were made.

## `okf/`

Stores OKF-compatible Markdown cards.

Examples:

```text
okf/source.md
okf/parser-decision.md
okf/index.md
okf/records/
```

OKF cards are catalogue cards. They point back to CTL records, HTML pages, and
assets.

## `graph/`

Stores graph exports when an adapter produces graph-like relationships.

Examples:

```text
graph/ctl-code-graph.json
```

Graph files are optional. They can be indexed by Kuzu, Neo4j, Graphify,
CodeGraph bridges, or other graph tools.

## Source Of Truth Rule

```text
Original source + CTL package files = durable record
Database/index exports             = replaceable accelerators
Generated reports                  = derived outputs
```

If an index is deleted, rebuild it from the package.
