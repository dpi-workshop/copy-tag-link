"""Parser adapter registry helpers.

This module describes parser adapters without installing or vendoring their
external dependencies. CTL-Core can list adapters and check whether optional
tools are available, while the CTL package remains the source of truth.
"""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ParserAdapterSpec:
    id: str
    name: str
    status: str
    bundled: bool
    dependency_type: str
    requires: tuple[str, ...]
    formats: tuple[str, ...]
    capabilities: tuple[str, ...]
    best_for: tuple[str, ...]
    project_url: str = ""
    install_url: str = ""
    license: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PARSER_ADAPTERS: tuple[ParserAdapterSpec, ...] = (
    ParserAdapterSpec(
        id="parser.fileinfo",
        name="Built-in file info",
        status="working",
        bundled=True,
        dependency_type="stdlib",
        requires=(),
        formats=("*",),
        capabilities=("metadata", "checksums", "provenance"),
        best_for=("source metadata", "checksums", "provenance starter records"),
        license="Apache-2.0 core",
        notes="Implemented in the parser lab. Runs by default.",
    ),
    ParserAdapterSpec(
        id="parser.basic_html",
        name="Built-in basic HTML",
        status="working",
        bundled=True,
        dependency_type="stdlib",
        requires=(),
        formats=("html", "htm"),
        capabilities=("headings", "paragraphs", "links", "images", "semantic blocks"),
        best_for=("simple HTML", "generated HTML", "static semantic HTML"),
        license="Apache-2.0 core",
        notes="Not a JavaScript renderer. Use Playwright later for rendered pages.",
    ),
    ParserAdapterSpec(
        id="parser.basic_json",
        name="Built-in basic JSON",
        status="working",
        bundled=True,
        dependency_type="stdlib",
        requires=(),
        formats=("json",),
        capabilities=("top-level keys", "metadata", "structured source summaries"),
        best_for=("JSON metadata", "API exports", "structured manifests"),
        license="Apache-2.0 core",
    ),
    ParserAdapterSpec(
        id="parser.basic_text",
        name="Built-in basic text",
        status="working",
        bundled=True,
        dependency_type="stdlib",
        requires=(),
        formats=("txt", "md", "markdown", "csv", "tsv"),
        capabilities=("paragraphs", "plain text preservation"),
        best_for=("plain notes", "already-flat text", "CSV/TSV as text"),
        license="Apache-2.0 core",
        notes="Preserves flat text without pretending to recover lost structure.",
    ),
    ParserAdapterSpec(
        id="parser.basic_pdf",
        name="Built-in basic PDF",
        status="working_when_installed",
        bundled=True,
        dependency_type="optional_python",
        requires=("pdfplumber", "pypdf"),
        formats=("pdf",),
        capabilities=("text", "simple tables", "simple figure crops", "page coordinates"),
        best_for=("born-digital PDFs", "simple tables", "simple figures", "demo extraction"),
        project_url="https://github.com/jsvine/pdfplumber",
        install_url="https://github.com/jsvine/pdfplumber",
        license="verify dependency licenses before release packaging",
        notes="Uses pdfplumber when available, then pypdf as fallback. Not a Docling/MinerU replacement.",
    ),
    ParserAdapterSpec(
        id="parser.codebase",
        name="Codebase adapter",
        status="working",
        bundled=True,
        dependency_type="stdlib_plus_optional_tools",
        requires=(),
        formats=("source tree",),
        capabilities=("files", "symbols", "simple graph", "human-readable repo report"),
        best_for=("repositories", "code docs", "repo notes", "simple code graphs"),
        license="Apache-2.0 core",
        notes="Implemented by scripts/ctl_codebase_adapter.py.",
    ),
    ParserAdapterSpec(
        id="parser.docling",
        name="Docling",
        status="optional_bridge",
        bundled=False,
        dependency_type="optional_python_or_external_tool",
        requires=("docling",),
        formats=("pdf", "docx", "pptx", "html"),
        capabilities=("layout", "tables", "figures", "document structure"),
        best_for=("PDF/DOCX layout", "tables", "figures", "mixed document structure"),
        project_url="https://github.com/docling-project/docling",
        notes="Users install Docling themselves. CTL bridge should translate Docling output into CTL records.",
    ),
    ParserAdapterSpec(
        id="parser.mineru",
        name="MinerU",
        status="optional_bridge",
        bundled=False,
        dependency_type="optional_python_or_external_tool",
        requires=("mineru", "magic-pdf"),
        formats=("pdf",),
        capabilities=("academic PDF layout", "formula-heavy pages", "figures", "tables"),
        best_for=("scientific PDFs", "academic papers", "complex PDF layout"),
        project_url="https://github.com/opendatalab/MinerU",
        notes="Users install MinerU themselves. Adapter should fail cleanly when unavailable.",
    ),
    ParserAdapterSpec(
        id="parser.paddleocr",
        name="PaddleOCR",
        status="optional_bridge",
        bundled=False,
        dependency_type="optional_python_or_external_tool",
        requires=("paddleocr",),
        formats=("png", "jpg", "jpeg", "webp", "tif", "tiff", "pdf"),
        capabilities=("OCR", "text boxes", "image text", "scanned pages"),
        best_for=("screenshots", "scanned pages", "text inside images", "OCR-heavy workflows"),
        project_url="https://github.com/PaddlePaddle/PaddleOCR",
        notes="Users install PaddleOCR themselves. CTL should store OCR boxes and confidence without interpretation.",
    ),
    ParserAdapterSpec(
        id="parser.pandoc",
        name="Pandoc",
        status="planned_bridge",
        bundled=False,
        dependency_type="external_cli",
        requires=("pandoc",),
        formats=("docx", "epub", "odt", "html", "md"),
        capabilities=("format conversion", "legacy document bridge"),
        best_for=("legacy formats", "format conversion", "already-structured documents"),
        project_url="https://github.com/jgm/pandoc",
        notes="External CLI bridge only. Do not vendor GPL tool code into CTL-Core.",
    ),
    ParserAdapterSpec(
        id="parser.playwright",
        name="Playwright",
        status="planned_bridge",
        bundled=False,
        dependency_type="optional_node_or_python",
        requires=("playwright",),
        formats=("url", "html"),
        capabilities=("rendered DOM", "screenshots", "JavaScript pages"),
        best_for=("rendered websites", "dynamic pages", "browser screenshots"),
        project_url="https://github.com/microsoft/playwright",
        notes="Use when raw HTML is not enough.",
    ),
)


def list_parser_adapters() -> list[dict[str, Any]]:
    return [adapter.to_dict() for adapter in PARSER_ADAPTERS]


def get_parser_adapter(adapter_id: str) -> ParserAdapterSpec:
    normalized = adapter_id.casefold()
    for adapter in PARSER_ADAPTERS:
        if adapter.id.casefold() == normalized or adapter.name.casefold() == normalized:
            return adapter
    known = ", ".join(adapter.id for adapter in PARSER_ADAPTERS)
    raise ValueError(f"Unknown parser adapter: {adapter_id}. Known adapters: {known}")


def dependency_available(name: str) -> bool:
    if importlib.util.find_spec(name) is not None:
        return True
    return shutil.which(name) is not None


def check_parser_adapter(adapter_id: str) -> dict[str, Any]:
    adapter = get_parser_adapter(adapter_id)
    checks = []
    for dependency in adapter.requires:
        checks.append({"dependency": dependency, "available": dependency_available(dependency)})
    available = True if not checks else any(check["available"] for check in checks)
    return {
        "adapter": adapter.to_dict(),
        "available": available,
        "dependency_checks": checks,
        "source_of_truth": "CTL package files; parser dependencies are optional bridges.",
    }
