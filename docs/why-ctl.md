# Why CTL-Core

CTL-Core exists because useful source material is richer than plain text.

Markdown is excellent for notes, but ingestion pipelines often flatten tables,
figures, diagrams, links, captions, layout clues, and provenance too early. RAG
systems often go further and shred sources into chunks that are useful for
search but hard for humans to inspect later.

CTL-Core is not trying to become the one database, model account, cloud bucket,
or dashboard that owns knowledge. It is the file-first evidence package under
those tools: a durable folder that humans can open, agents can read, and indexes
can rebuild.

CTL-Core takes a different path:

```text
Copy -> Tag -> Link
```

It preserves the original source, extracts reusable records and assets, writes
plain semantic HTML, and emits rebuildable indexes such as search JSON and
OKF-compatible Markdown cards.

CTL does not use Markdown as the main memory format. Markdown cards are only
catalogue/index files for OKF-style workflows. The richer source memory remains
the preserved originals, semantic HTML, assets, manifests, and JSON records.

## The Core Idea

```text
Original source files = preserved evidence
Semantic HTML        = source-of-truth memory view
Reusable assets      = copied parts linked to the source
Databases/vectors    = replaceable accelerators
```

The CTL package is the record. Semantic HTML is the view humans and agents can
read directly. Everything else can be rebuilt.

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

In other words, CTL does not flatten a PDF, website, or document into Markdown.
It preserves and links the parts, then emits Markdown cards so tools that expect
Markdown/YAML can find the richer package.

## Relationship To Databases

Databases are optional adapters.

Use SQLite, DuckDB, PostgreSQL, Qdrant, Kuzu, LanceDB, Neo4j, or any other
indexing system when it helps. If the database is lost, the CTL package can be
re-indexed.

The database is an index, not the owner of your knowledge.

## Zero Trust By Default

CTL preserves evidence without trusting it.

Every source should be treated as untrusted input until reviewed:

- public web pages
- PDFs and documents
- repositories and issues
- transcripts and translations
- OCR and parser output
- AI-generated summaries
- model, vendor, agent, skill, and tool outputs

CTL keeps originals, copied parts, provenance, and links together so later
agents and humans can inspect what happened without silently rewriting the
record.

If a source contains prompt injection or other hostile instructions, CTL should
preserve the text as evidence, isolate it from operational instructions, flag
the source, and record the review decision.
