# CTL-Core Parser Adapters

Parser adapters turn local source files into CTL records, assets, manifests,
semantic HTML, search indexes, and OKF-compatible cards.

They are intentionally separated from:

- database adapters
- graph/vector/search adapters
- social input adapters
- cloud storage adapters
- agent/workflow adapters

## Boundary Rule

Parser adapters may read local source files and write CTL package files.

Parser adapters should not:

- connect to databases
- call social platforms
- post comments or messages
- read credentials
- upload files
- mutate external systems
- run unreviewed contributor code

That keeps document ingestion boring, inspectable, and safe.

## Current Built-In Parser Adapters

| Adapter | Formats | Dependencies | Boundary |
| --- | --- | --- | --- |
| `fileinfo` | any file | none | local metadata only |
| `basic-html` | `.html`, `.htm` | none | local HTML only |
| `basic-json` | `.json` | none | local JSON only |
| `basic-text` | `.txt`, `.md`, `.markdown`, `.csv`, `.tsv` | none | local text only |
| `basic-pdf` | `.pdf` | `pdfplumber` or `pypdf` | local PDF only |

## Future External Parser Adapter Repos

Heavy parser integrations should usually live outside `ctl-core`:

- `ctl-adapter-docling`
- `ctl-adapter-mineru`
- `ctl-adapter-paddleocr`
- `ctl-adapter-pandoc`
- `ctl-adapter-playwright`

Those adapters can depend on larger tools without making CTL-Core hard to
install, audit, or license-check.

## Adapter Family Folders

| Folder | Responsibility |
| --- | --- |
| `parser/` | Local source files into CTL records and assets |
| `database/` | CTL packages into rebuildable search/SQL/graph/vector indexes |
| `social_input/` | Exported conversations and message streams into CTL packages |
| `cloud_storage/` | Syncing CTL packages to storage providers |
| `agent_workflow/` | Job routing, review loops, model/tool assignment |

These folders are boundary markers. CTL-Core includes the parser lane first.
Other lanes can grow as separate repos or higher-level CTL-Suite tools.
