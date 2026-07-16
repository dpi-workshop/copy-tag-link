"""Built-in adapter metadata for CTL-Core.

Parser adapters only convert source files into CTL records and assets.
They must not connect to databases, social platforms, cloud accounts, or
external services unless a specific adapter explicitly documents that behavior.

This module is descriptive metadata for the public MVP. The current built-in
adapters are command-line scripts, not importable plugin classes.
"""

from __future__ import annotations

PARSER_ADAPTERS = {
    "fileinfo": {
        "entrypoint": "scripts/ctl_parser_lab.py",
        "formats": ["*"],
        "dependencies": [],
        "status": "built-in",
        "boundary": "local file metadata only",
    },
    "basic-html": {
        "entrypoint": "scripts/ctl_parser_lab.py",
        "formats": [".html", ".htm"],
        "dependencies": [],
        "status": "built-in",
        "boundary": "local HTML files only",
    },
    "basic-json": {
        "entrypoint": "scripts/ctl_parser_lab.py",
        "formats": [".json"],
        "dependencies": [],
        "status": "built-in",
        "boundary": "local JSON files only",
    },
    "basic-text": {
        "entrypoint": "scripts/ctl_parser_lab.py",
        "formats": [".txt", ".md", ".markdown", ".csv", ".tsv"],
        "dependencies": [],
        "status": "built-in",
        "boundary": "local text files only",
    },
    "basic-pdf": {
        "entrypoint": "scripts/ctl_parser_lab.py",
        "formats": [".pdf"],
        "dependencies": ["pdfplumber or pypdf"],
        "status": "optional dependency",
        "boundary": "local PDF files only",
    },
}
