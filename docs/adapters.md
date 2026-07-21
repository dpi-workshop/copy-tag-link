# CTL-Core Adapter Guide

CTL-Core keeps the core small and database-optional. Parser integrations should
be adapters, not hard dependencies.

## Rule

```text
External source/tool -> adapter -> CTL package
```

Parser adapters live in the parser lane. They should not connect to databases,
social platforms, cloud accounts, or external workflow systems. Those belong in
separate adapter families.

Adapters may depend on external projects, but CTL-Core should not copy or
vendor their code unless the license has been reviewed.

## Adapter Families

| Family | Purpose | CTL-Core Policy |
| --- | --- | --- |
| `ctl_core/adapters/parser/` | Convert local files into CTL records/assets | Included only when small and safe |
| `ctl_core/adapters/database/` | Rebuild search, SQL, graph, or vector indexes | Separate from parsers |
| `ctl_core/adapters/source_input/` | Intake public feeds, websites, GitHub, YouTube metadata, and public social signals | Conservative public-source adapters |
| `ctl_core/adapters/code_intelligence/` | Wrap code graph/intelligence tools and link their outputs to CTL code records | Optional analysis layer |
| `ctl_core/adapters/social_input/` | Import from Slack, Discord, Zalo, email, etc. | Separate repos/tools |
| `ctl_core/adapters/cloud_storage/` | Sync packages to R2, Drive, S3, etc. | Separate repos/tools |
| `ctl_core/adapters/runtime/` | Run heavy or risky tools in local, Docker, WASM, or remote runtimes | Separate permission boundary |
| `ctl_core/adapters/versioning/` | Track package history, forks, diffs, and checkpoints | Separate from source parsing |
| `ctl_core/adapters/agent_workflow/` | Trigger jobs, review output, manage loops | CTL-Suite layer, not core |

## Official Adapter Contract

Every adapter should be able to emit records into:

```text
assets/tables/ctl-records.json
```

Each record should follow this shape:

```json
{
  "id": "record-0001",
  "source_id": "source-name",
  "type": "paragraph",
  "order": 1,
  "text": "Human-readable text if available.",
  "html": "<p>Semantic HTML fragment if available.</p>",
  "asset_path": "assets/images/example.png",
  "page": 1,
  "bbox": [0, 0, 100, 100],
  "links": [],
  "tags": [],
  "confidence": 0.8,
  "source_path": "assets/original/source.pdf",
  "provenance": {
    "parser": "example-parser",
    "parser_version": "1.0.0",
    "adapter": "ctl-adapter-example",
    "created_at": "2026-07-13T00:00:00+00:00"
  },
  "metadata": {}
}
```

See [../examples/adapter-manifest.json](../examples/adapter-manifest.json) for
a fuller example with dependency, permission, output, and quality-check fields.
The [SQLite-vec adapter manifest](../examples/sqlite-vec-adapter-manifest.json)
shows the same pattern for a rebuildable local vector index.
The [parser bridge manifest](../examples/parser-bridge-manifest.json) shows the
shape for external parser bridges such as Docling, MinerU, or PaddleOCR.

## Adapter Manifest

Community adapters should include a manifest like:

```json
{
  "name": "ctl-adapter-docling",
  "formats": ["pdf", "docx", "pptx"],
  "capabilities": ["text", "tables", "figures", "layout"],
  "external_dependencies": ["docling"],
  "license": "verify",
  "status": "experimental"
}
```

## Initial Adapter Categories

| Adapter | Best For | Integration Type | License Status | CTL Status |
| --- | --- | --- | --- | --- |
| built-in fileinfo | source metadata | stdlib | Apache-2.0 core | working |
| built-in basic-html | generated/simple HTML | stdlib | Apache-2.0 core | working |
| built-in basic-json | JSON metadata/data | stdlib | Apache-2.0 core | working |
| built-in basic-text | txt/md/csv/tsv | stdlib | Apache-2.0 core | working |
| built-in basic-pdf | born-digital PDF text/tables | optional `pdfplumber` or `pypdf` dependency | verify before release | working when installed |
| Docling | PDF/doc layout | optional dependency | verify before release | optional bridge |
| MinerU | complex PDF layout | optional dependency | verify before release | optional bridge |
| PaddleOCR | OCR/images | optional dependency | verify before release | optional bridge |
| Pandoc | format conversion | external CLI | verify before release | planned |
| Playwright | rendered websites | optional dependency | verify before release | planned |

The parser adapter registry is machine-readable:

```shell
python -m ctl_core list-parser-adapters --json
python -m ctl_core check-parser-adapter parser.docling
```

CTL-Core may check whether parser dependencies exist, but it does not install
Docling, MinerU, PaddleOCR, Pandoc, or Playwright for the user.

## Codebase And Code Intelligence

CTL can treat a repository like a document collection. The built-in codebase
adapter preserves files, parsed symbols, a simple code graph, and a human
readable HTML report.

```shell
python scripts/ctl_codebase_adapter.py . -o output/codebase-demo --name ctl-core
```

External intelligence tools can then be used as optional derived-analysis
adapters.

| Adapter | Best For | Integration Type | License Status | CTL Status |
| --- | --- | --- | --- | --- |
| CTL codebase adapter | human-readable repo packages, file/symbol records, simple graph | stdlib | Apache-2.0 core | working |
| CodeGraph | symbol lookup, call paths, impact analysis | external tool/MCP | external terms | planned bridge |
| Graphify | graph.html, graph.json, graph reports over code/docs/media | external CLI/skill | verify upstream | planned bridge |
| Understand Anything | interactive codebase learning, guided tours, domain views | external plugin/tool | verify upstream | planned bridge |

CTL preserves the repo as durable data. Code-intelligence tools explain it.

## Database And Index Adapters

Database/index adapters rebuild search, SQL, graph, or vector indexes from CTL
packages. They do not own the data.

The shared database adapter contract is documented in
[database-adapter-contract.md](database-adapter-contract.md).

| Adapter | Best For | Integration Type | License Status | CTL Status |
| --- | --- | --- | --- | --- |
| SQLite | portable local indexes, FTS keyword search | stdlib/embedded | public domain style SQLite core | working |
| SQLite-vec | local semantic search beside SQLite/FTS indexes | optional SQLite extension/Python package | MIT/Apache-2.0 upstream; pre-v1, verify before adapter release | working optional |
| DuckDB | local analytical SQL | optional dependency | MIT | working/private |
| PostgreSQL | multi-user server indexes | server database | PostgreSQL License | working/private |
| MongoDB | document-shaped records/manifests | server database | external terms vary | working/private |
| Qdrant | vectors/semantic search | vector store | Apache-2.0 | working/private |
| LanceDB | local multimodal/vector tables | vector lake | Apache-2.0 | working/private |
| Kuzu | embedded graph/GraphRAG | optional dependency | MIT | working optional |
| Neo4j/Cypher | server graph import/export | graph server/export | external terms vary | working/private |
| libSQL/Turso local | SQLite-compatible local index | embedded/local adapter | verify before release | planned |

The working/private status means prototype code exists in the internal CTL tree
and should be promoted only after cleanup, security review, and dependency
license review. Working optional means the public adapter exists, but users must
install the upstream dependency themselves.

## Source Input Adapters

Source input adapters collect public source signals into CTL packages. They are
not allowed to bypass paywalls, scrape private accounts, or treat social data as
verified fact.

| Adapter | Best For | Integration Type | License Status | CTL Status |
| --- | --- | --- | --- | --- |
| RSS/Atom | feeds, updates, research queues | stdlib | Apache-2.0 core | working |
| Static website | public pages, headings, paragraphs, links, image references | stdlib | Apache-2.0 core | working |
| GitHub repo | public repo metadata, topics, license/stars/issues | public API | Apache-2.0 core | working |
| YouTube metadata | RSS feeds, channel IDs, video oEmbed metadata | public feed/oEmbed | Apache-2.0 core | working/limited |
| Reddit public JSON | technical discussions and sentiment signals | public JSON | Apache-2.0 core | working/limited |

Reddit, X/Twitter, forums, and other social sources should be tagged as signal
unless independently verified. Signal means "people are reacting to something";
it does not mean the claim is true.

## Cloud Storage Bridge Adapters

Cloud storage adapters are optional bridges. CTL-Core should not require cloud
credentials or bundled cloud-sync tools to run.

| Adapter | Best For | Integration Type | License Status | CTL Status |
| --- | --- | --- | --- | --- |
| local-folder | local mirrors, offline packages, removable drives | built-in filesystem operations | Apache-2.0 core | planned |
| rclone | copying/syncing CTL packages across many cloud providers | external CLI bridge | MIT, external tool | planned |
| AList | unified web file browser/WebDAV bridge for many storages | external service/WebDAV bridge | AGPL-3.0, external tool | planned |
| Cloudflare R2 | static package hosting and durable object storage | API/S3-compatible bridge | service/API terms | planned |
| Google Drive | classroom/resource sharing and backups | API bridge | service/API terms | planned |

Rclone and AList are not CTL-Core dependencies. They are optional tools a user
may install separately. CTL adapters should detect whether the external tool is
available and fail gracefully when it is not.

## Runtime And Versioning Adapters

Runtime adapters run tools. Versioning adapters track history. Neither should
own CTL package data.

| Adapter | Best For | Integration Type | License Status | CTL Status |
| --- | --- | --- | --- | --- |
| local-process | small trusted adapters | host runtime | Apache-2.0 core | planned |
| Docker | heavy parsers and fragile dependencies | external runtime | external terms | planned |
| WebAssembly/WASI | sandboxed community skills/tools | sandbox runtime | runtime-specific | planned |
| Git | prompts, manifests, OKF cards, small assets, decision logs | external CLI | GPL-2.0 external CLI | planned |

Git can track CTL history, but large audio/video/image batches should usually
live in asset storage with checksums and manifests. Use Git LFS only when the
project explicitly wants Git to manage large binary assets.

## Community Adapters

Community adapters should remain separate repositories unless they become small,
stable, and license-clean enough to include.

Examples:

- `ctl-adapter-moodle`
- `ctl-adapter-canvas`
- `ctl-adapter-zalo`
- `ctl-adapter-slack`
- `ctl-adapter-teams`
- `ctl-adapter-khan`

CTL-Core defines the package contract. Adapters compete to produce useful CTL
packages.
