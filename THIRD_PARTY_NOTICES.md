# Third-Party Notices

CTL-Core's basic HTML/text/JSON demo uses only the Python standard library.

Optional parser adapters may integrate with external tools. These tools are not
bundled in CTL-Core unless explicitly listed here, and their licenses must be
reviewed before any official adapter release.

| Tool | Purpose | Bundled? | License Status |
| --- | --- | --- | --- |
| pdfplumber | optional PDF text/table extraction | no | verify |
| pypdf | optional PDF text fallback | no | verify |
| ReportLab | optional demo PDF generation | no | verify |
| Pillow | optional demo image generation | no | verify |
| Docling | document/PDF parsing | no | verify |
| MinerU | document/PDF layout parsing | no | verify |
| PaddleOCR | OCR | no | verify |
| Pandoc | document conversion | no | verify |
| Playwright | rendered website capture | no | verify |

Adapters should call external tools through documented interfaces rather than
copying third-party source code into CTL-Core.
