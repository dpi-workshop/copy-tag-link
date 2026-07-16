# Parser Adapters

Parser adapters convert local source files into CTL packages.

They may:

- read local documents, PDFs, HTML, text, JSON, images, and archives
- extract text, tables, figures, captions, metadata, and visual crops
- write CTL records, assets, manifests, semantic HTML, search indexes, and OKF cards

They must not:

- connect to databases
- call social platforms
- sync cloud storage
- post messages
- manage agents or workflow jobs
- read credentials except documented parser-specific config
- mutate external systems

## Built-In MVP Parser Adapters

- `fileinfo`
- `basic-html`
- `basic-json`
- `basic-text`
- `basic-pdf`
