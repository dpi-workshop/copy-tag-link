# Using CTL Packages With Agents

CTL-Core packages are meant to be durable shared memory for humans and AI
agents. The package is an ordinary folder. Agents should treat the files in that
folder as the source memory layer, not as temporary parser output.

The database, vector store, graph, MCP server, or model account is optional.
The CTL package is the record that survives tool changes.

## Agent Reading Order

When an agent receives a CTL package path, it should read in this order:

1. `manifest.json`
2. `manifests/provenance.json`
3. `search.json`
4. `assets/tables/ctl-records.json`
5. `okf/index.md`
6. `documents/*.html`
7. linked assets under `assets/`

This gives the agent the package summary, provenance, searchable text, canonical
records, catalogue cards, human-readable HTML, and reusable assets.

## Important Files

| File | How agents should use it |
| --- | --- |
| `manifest.json` | Start here. Identify the source, adapter list, record count, and package purpose. |
| `manifests/provenance.json` | Use this for source checksums, parser details, timestamps, and citation context. |
| `assets/tables/ctl-records.json` | Treat this as the canonical structured record table. |
| `search.json` | Use this for quick lookup before reading full records. It is rebuildable. |
| `okf/index.md` | Use this as a portable catalogue/index layer for OKF-style workflows. |
| `documents/*.html` | Use this for human-readable review and semantic structure. |
| `assets/original/` | Preserve these files. They are original source evidence. |
| `assets/images/` | Reuse copied/extracted visual assets with provenance links. |
| `intermediate/` | Adapter-specific raw outputs. Useful for debugging, not usually the public memory layer. |

## Agent Rules

Agents should:

- preserve original files
- cite record ids and source paths when using information
- prefer `ctl-records.json` for structured data
- prefer `documents/*.html` for readable context
- use `okf/index.md` as catalogue cards, not as a replacement for the richer package
- treat databases and vectors as indexes that can be rebuilt
- keep analysis, annotations, decisions, and corrections separate from original source records

Agents should not:

- overwrite files in `assets/original/`
- silently rewrite source evidence
- treat social or public-web signal as verified fact without review
- assume `search.json` is the only copy of the data
- treat a vector database as the owner of the memory
- mix private credentials, API keys, or account tokens into CTL packages

## Citation Pattern

When an agent uses a CTL record in an answer or derived output, it should keep
enough information to trace the claim back to the source.

Useful citation fields:

```text
package path
record id
record type
source path
asset path
page
bbox
provenance.parser
provenance.created_at
```

Example:

```text
Used record `pdf-p001-table-0001` from
`assets/tables/ctl-records.json`, source
`assets/original/market-snapshot.pdf`, page 1.
```

## Shared Memory Pattern

For shared AI memory, use CTL packages as the file-first layer:

```text
CTL package folder      = durable memory
SQL / graph / vectors   = rebuildable indexes
MCP / CLI / skills      = access methods
agents and humans       = readers, reviewers, and builders
```

Different AI systems can read the same CTL package without sharing the same
vendor account, model, database, or cloud service.

## Rebuilding Indexes

If an index is lost, rebuild it from the CTL package:

- rebuild text search from `search.json` or `ctl-records.json`
- rebuild SQL tables from `assets/tables/ctl-records.json`
- rebuild graph edges from records, links, manifests, and future graph exports
- rebuild vectors from record text, HTML fragments, and assets
- rebuild OKF catalogue cards from CTL records

The package should remain useful even if every external index disappears.

## Future Access Layers

CTL-Core currently provides scripts and a package layout. Future tools can wrap
the same files without changing the memory model.

Expected access layers:

```text
CLI      ctl inspect, ctl validate, ctl search, ctl export-okf
MCP      list packages, read manifest, search records, read assets
skills   use CTL memory, write annotations, build outputs from CTL assets
```

These are convenience layers. The package layout is the durable contract.

