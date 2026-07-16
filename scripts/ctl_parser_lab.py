#!/usr/bin/env python
"""Run parser-adapter experiments and normalize them into draft CTL records.

This is the lightweight harness for ctl-core parser lab work. Heavy parsers
such as Docling, MinerU, PaddleOCR, and Marker should be wrapped as adapters
that return the same record shape used here.
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
import mimetypes
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ctl_okf_export import export_okf


CTL_VERSION = "0.1-parser-lab"


@dataclass
class CtlRecord:
    id: str
    type: str
    text: str = ""
    html: str = ""
    asset: str = ""
    bbox: list[int] | None = None
    page: int | None = None
    source: str = ""
    confidence: float | None = None
    provenance: dict | None = None


@dataclass
class AdapterResult:
    adapter: str
    status: str
    records: list[CtlRecord]
    raw: dict
    warnings: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "source"


def relpath(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def record_to_json(record: CtlRecord, source_id: str = "", order: int | None = None) -> dict:
    data = asdict(record)
    if source_id:
        data["source_id"] = source_id
    if order is not None:
        data["order"] = order
    if data.get("asset") and not data.get("asset_path"):
        data["asset_path"] = data["asset"]
    if data.get("source") and not data.get("source_path"):
        data["source_path"] = data["source"]
    data.setdefault("links", [])
    data.setdefault("tags", [])
    data.setdefault("metadata", {})
    return {key: value for key, value in data.items() if value not in (None, "", [])}


class BasicHtmlTextParser(html.parser.HTMLParser):
    """Small stdlib HTML extractor for parser-lab smoke tests."""

    BLOCK_TAGS = {
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "li",
        "figcaption",
        "caption",
        "th",
        "td",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.current_tag: str | None = None
        self.current_text: list[str] = []
        self.blocks: list[tuple[str, str]] = []
        self.links: list[dict] = []
        self.images: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        self.stack.append(tag)
        if tag in self.BLOCK_TAGS:
            self.flush()
            self.current_tag = tag
        if tag == "a" and attr_map.get("href"):
            self.links.append({"href": attr_map.get("href", ""), "text": ""})
        if tag == "img":
            self.images.append(
                {
                    "src": attr_map.get("src", ""),
                    "alt": attr_map.get("alt", ""),
                    "title": attr_map.get("title", ""),
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == self.current_tag:
            self.flush()
        if self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self.current_tag:
            self.current_text.append(text)
        if self.links:
            self.links[-1]["text"] = (self.links[-1]["text"] + " " + text).strip()

    def flush(self) -> None:
        if self.current_tag and self.current_text:
            text = re.sub(r"\s+", " ", " ".join(self.current_text)).strip()
            if text:
                self.blocks.append((self.current_tag, text))
        self.current_tag = None
        self.current_text = []

    def close(self) -> None:
        self.flush()
        super().close()


class Adapter:
    name = "adapter"

    def run(self, source: Path, output_dir: Path, copied_source: Path) -> AdapterResult:
        raise NotImplementedError


class FileInfoAdapter(Adapter):
    name = "fileinfo"

    def run(self, source: Path, output_dir: Path, copied_source: Path) -> AdapterResult:
        mime, _ = mimetypes.guess_type(source.name)
        stat = source.stat()
        raw = {
            "name": source.name,
            "suffix": source.suffix.lower(),
            "size_bytes": stat.st_size,
            "mime_type": mime or "application/octet-stream",
            "sha256": sha256_file(source),
            "copied_source": relpath(copied_source, output_dir),
        }
        record = CtlRecord(
            id="source-file",
            type="source",
            text=source.name,
            asset=raw["copied_source"],
            source=raw["copied_source"],
            confidence=1.0,
            provenance={
                "parser": self.name,
                "parser_version": "stdlib",
                "adapter": "ctl-core-fileinfo",
                "created_at": utc_now(),
            },
        )
        return AdapterResult(self.name, "ok", [record], raw, [])


class BasicHtmlAdapter(Adapter):
    name = "basic-html"

    def copy_local_image(self, source: Path, output_dir: Path, src: str, index: int) -> str:
        if not src or re.match(r"^(?:https?:)?//|data:|mailto:", src, re.IGNORECASE):
            return src
        source_image = (source.parent / src).resolve()
        try:
            source_image.relative_to(source.parent.resolve())
        except ValueError:
            return src
        if not source_image.exists() or not source_image.is_file():
            return src
        images_dir = output_dir / "assets" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        target = images_dir / f"html-image-{index:04d}-{slugify(source_image.stem)}{source_image.suffix.lower()}"
        shutil.copy2(source_image, target)
        return relpath(target, output_dir)

    def run(self, source: Path, output_dir: Path, copied_source: Path) -> AdapterResult:
        if source.suffix.lower() not in {".html", ".htm"}:
            return AdapterResult(
                self.name,
                "skipped",
                [],
                {"reason": "not an HTML file"},
                [],
            )

        text = source.read_text(encoding="utf-8", errors="replace")
        parser = BasicHtmlTextParser()
        parser.feed(text)
        parser.close()

        records: list[CtlRecord] = []
        for index, (tag, block_text) in enumerate(parser.blocks, start=1):
            if tag.startswith("h"):
                record_type = "heading"
            elif tag in {"th", "td", "caption"}:
                record_type = "table_text"
            elif tag == "figcaption":
                record_type = "caption"
            elif tag == "li":
                record_type = "list_item"
            else:
                record_type = "paragraph"
            records.append(
                CtlRecord(
                    id=f"html-{index:04d}",
                    type=record_type,
                    text=block_text,
                    html=f"<{tag}>{escape(block_text)}</{tag}>",
                    source=relpath(copied_source, output_dir),
                    confidence=0.6,
                    provenance={
                        "parser": self.name,
                        "parser_version": "stdlib-html-parser",
                        "adapter": "ctl-core-basic-html",
                        "created_at": utc_now(),
                    },
                )
            )

        for index, image in enumerate(parser.images, start=1):
            asset_path = self.copy_local_image(source, output_dir, image.get("src", ""), index)
            records.append(
                CtlRecord(
                    id=f"html-image-{index:04d}",
                    type="figure",
                    text=image.get("alt", ""),
                    html=(
                        f"<figure><img src=\"{escape(asset_path)}\" alt=\"{escape(image.get('alt', ''))}\">"
                        f"<figcaption>{escape(image.get('alt', '') or image.get('title', ''))}</figcaption></figure>"
                    ),
                    asset=asset_path,
                    source=relpath(copied_source, output_dir),
                    confidence=0.5,
                    provenance={
                        "parser": self.name,
                        "parser_version": "stdlib-html-parser",
                        "adapter": "ctl-core-basic-html",
                        "created_at": utc_now(),
                    },
                )
            )

        raw = {
            "block_count": len(parser.blocks),
            "image_count": len(parser.images),
            "link_count": len(parser.links),
            "links": parser.links[:200],
            "images": parser.images[:200],
        }
        warnings = []
        if not records:
            warnings.append("No semantic blocks found by basic HTML parser.")
        return AdapterResult(self.name, "ok", records, raw, warnings)


class BasicJsonAdapter(Adapter):
    name = "basic-json"

    def run(self, source: Path, output_dir: Path, copied_source: Path) -> AdapterResult:
        if source.suffix.lower() != ".json":
            return AdapterResult(self.name, "skipped", [], {"reason": "not a JSON file"}, [])

        data = json.loads(source.read_text(encoding="utf-8"))
        raw = {
            "top_level_type": type(data).__name__,
            "top_level_keys": list(data.keys())[:100] if isinstance(data, dict) else [],
            "item_count": len(data) if isinstance(data, (dict, list)) else None,
        }
        record = CtlRecord(
            id="json-root",
            type="data",
            text=json.dumps(raw, ensure_ascii=False),
            source=relpath(copied_source, output_dir),
            confidence=0.7,
            provenance={
                "parser": self.name,
                "parser_version": "stdlib-json",
                "adapter": "ctl-core-basic-json",
                "created_at": utc_now(),
            },
        )
        return AdapterResult(self.name, "ok", [record], raw, [])


class BasicTextAdapter(Adapter):
    name = "basic-text"

    TEXT_EXTS = {".txt", ".md", ".markdown", ".csv", ".tsv"}

    def run(self, source: Path, output_dir: Path, copied_source: Path) -> AdapterResult:
        if source.suffix.lower() not in self.TEXT_EXTS:
            return AdapterResult(self.name, "skipped", [], {"reason": "not a text file"}, [])
        text = source.read_text(encoding="utf-8", errors="replace")
        chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
        records = [
            CtlRecord(
                id=f"text-{index:04d}",
                type="paragraph",
                text=re.sub(r"\s+", " ", chunk).strip(),
                html=f"<p>{escape(re.sub(r'\\s+', ' ', chunk).strip())}</p>",
                source=relpath(copied_source, output_dir),
                confidence=0.5,
                provenance={
                    "parser": self.name,
                    "parser_version": "stdlib-text",
                    "adapter": "ctl-core-basic-text",
                    "created_at": utc_now(),
                },
            )
            for index, chunk in enumerate(chunks[:500], start=1)
        ]
        raw = {"chunk_count": len(chunks), "character_count": len(text)}
        return AdapterResult(self.name, "ok", records, raw, [])


class BasicPdfAdapter(Adapter):
    name = "basic-pdf"

    def save_page_crop(self, page: object, output_dir: Path, bbox: tuple[float, float, float, float], record_id: str) -> str:
        images_dir = output_dir / "assets" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        target = images_dir / f"{record_id}.png"
        page.crop(bbox).to_image(resolution=144).save(target)
        return relpath(target, output_dir)

    def html_table(self, table: list[list[str | None]]) -> str:
        rows = []
        for row_index, row in enumerate(table):
            cells = []
            cell_tag = "th" if row_index == 0 else "td"
            for cell in row:
                cells.append(f"<{cell_tag}>{escape((cell or '').strip())}</{cell_tag}>")
            rows.append(f"<tr>{''.join(cells)}</tr>")
        if not rows:
            return "<table></table>"
        return f"<table><thead>{rows[0]}</thead><tbody>{''.join(rows[1:])}</tbody></table>"

    def diagram_bbox(self, page: object) -> tuple[float, float, float, float] | None:
        words = page.extract_words()
        diagram_words = [
            word for word in words
            if word.get("text") in {"Source", "PDF", "Copy", "Tag", "Link", "CTL", "Package", "Original"}
            and float(word.get("top", 0)) > 350
        ]
        if len(diagram_words) < 4:
            return None
        x0 = max(0, min(float(word["x0"]) for word in diagram_words) - 40)
        top = max(0, min(float(word["top"]) for word in diagram_words) - 55)
        x1 = min(float(page.width), max(float(word["x1"]) for word in diagram_words) + 40)
        bottom = min(float(page.height), max(float(word["bottom"]) for word in diagram_words) + 35)
        return (x0, top, x1, bottom)

    def image_bbox(self, image: dict) -> tuple[float, float, float, float] | None:
        try:
            return (float(image["x0"]), float(image["top"]), float(image["x1"]), float(image["bottom"]))
        except KeyError:
            return None

    def records_with_pdfplumber(self, source: Path, output_dir: Path, copied_source: Path) -> tuple[list[CtlRecord], dict]:
        import pdfplumber

        records: list[CtlRecord] = []
        page_count = 0
        table_count = 0
        diagram_count = 0
        image_count = 0
        with pdfplumber.open(source) as pdf:
            page_count = len(pdf.pages)
            for page_index, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                table_objects = page.find_tables()
                skip_lines = set()
                for table_index, table in enumerate(tables, start=1):
                    clean_table = [[(cell or "").strip() for cell in row] for row in table if row]
                    if not clean_table:
                        continue
                    table_count += 1
                    record_id = f"pdf-p{page_index:03d}-table-{table_index:04d}"
                    asset_path = ""
                    if table_index <= len(table_objects):
                        try:
                            asset_path = self.save_page_crop(page, output_dir, table_objects[table_index - 1].bbox, record_id)
                        except Exception:
                            asset_path = ""
                    for row in clean_table:
                        skip_lines.add(re.sub(r"\s+", " ", " ".join(cell for cell in row if cell)).strip())
                    table_text = " | ".join(" / ".join(cell for cell in row if cell) for row in clean_table)
                    records.append(
                        CtlRecord(
                            id=record_id,
                            type="table",
                            text=table_text,
                            html=self.html_table(clean_table),
                            asset=asset_path,
                            bbox=[round(value, 2) for value in table_objects[table_index - 1].bbox] if table_index <= len(table_objects) else None,
                            page=page_index,
                            source=relpath(copied_source, output_dir),
                            confidence=0.65,
                            provenance={
                                "parser": self.name,
                                "parser_version": "pdfplumber",
                                "adapter": "ctl-core-basic-pdf",
                                "created_at": utc_now(),
                            },
                        )
                    )

                diagram_box = self.diagram_bbox(page)
                if diagram_box:
                    diagram_count += 1
                    record_id = f"pdf-p{page_index:03d}-diagram-{diagram_count:04d}"
                    asset_path = ""
                    try:
                        asset_path = self.save_page_crop(page, output_dir, diagram_box, record_id)
                    except Exception:
                        asset_path = ""
                    diagram_text = "Source PDF -> Copy -> Tag -> Link -> CTL Package"
                    records.append(
                        CtlRecord(
                            id=record_id,
                            type="diagram",
                            text=diagram_text,
                            html=(
                                f"<figure><img src=\"{escape(asset_path)}\" alt=\"{escape(diagram_text)}\">"
                                f"<figcaption>{escape(diagram_text)}</figcaption></figure>"
                            ),
                            asset=asset_path,
                            bbox=[round(value, 2) for value in diagram_box],
                            page=page_index,
                            source=relpath(copied_source, output_dir),
                            confidence=0.45,
                            provenance={
                                "parser": self.name,
                                "parser_version": "pdfplumber",
                                "adapter": "ctl-core-basic-pdf",
                                "created_at": utc_now(),
                            },
                        )
                    )

                for image_index, image in enumerate(page.images, start=1):
                    image_box = self.image_bbox(image)
                    if not image_box:
                        continue
                    image_count += 1
                    record_id = f"pdf-p{page_index:03d}-image-{image_index:04d}"
                    asset_path = ""
                    try:
                        asset_path = self.save_page_crop(page, output_dir, image_box, record_id)
                    except Exception:
                        asset_path = ""
                    image_text = "Embedded PDF image asset"
                    records.append(
                        CtlRecord(
                            id=record_id,
                            type="figure",
                            text=image_text,
                            html=(
                                f"<figure><img src=\"{escape(asset_path)}\" alt=\"{escape(image_text)}\">"
                                f"<figcaption>{escape(image_text)}</figcaption></figure>"
                            ),
                            asset=asset_path,
                            bbox=[round(value, 2) for value in image_box],
                            page=page_index,
                            source=relpath(copied_source, output_dir),
                            confidence=0.5,
                            provenance={
                                "parser": self.name,
                                "parser_version": "pdfplumber",
                                "adapter": "ctl-core-basic-pdf",
                                "created_at": utc_now(),
                            },
                        )
                    )

                text = page.extract_text() or ""
                line_index = 0
                for line in text.splitlines():
                    clean_line = re.sub(r"\s+", " ", line).strip()
                    if not clean_line or clean_line in skip_lines:
                        continue
                    line_index += 1
                    if line_index == 1 or clean_line in {"Summary", "Adoption Signals"}:
                        record_type = "heading"
                        html = f"<h2>{escape(clean_line)}</h2>" if line_index != 1 else f"<h1>{escape(clean_line)}</h1>"
                    else:
                        record_type = "paragraph"
                        html = f"<p>{escape(clean_line)}</p>"
                    records.append(
                        CtlRecord(
                            id=f"pdf-p{page_index:03d}-text-{line_index:04d}",
                            type=record_type,
                            text=clean_line,
                            html=html,
                            page=page_index,
                            source=relpath(copied_source, output_dir),
                            confidence=0.55,
                            provenance={
                                "parser": self.name,
                                "parser_version": "pdfplumber",
                                "adapter": "ctl-core-basic-pdf",
                                "created_at": utc_now(),
                            },
                        )
                    )

        raw = {
            "page_count": page_count,
            "record_count": len(records),
            "table_count": table_count,
            "diagram_count": diagram_count,
            "image_count": image_count,
            "extractor": "pdfplumber",
        }
        return records, raw

    def records_with_pypdf(self, source: Path, output_dir: Path, copied_source: Path) -> tuple[list[CtlRecord], dict]:
        from pypdf import PdfReader

        reader = PdfReader(str(source))
        records: list[CtlRecord] = []
        for page_index, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n|(?<=\.)\s{2,}", page_text) if chunk.strip()]
            for chunk_index, chunk in enumerate(chunks[:100], start=1):
                text = re.sub(r"\s+", " ", chunk).strip()
                if not text:
                    continue
                records.append(
                    CtlRecord(
                        id=f"pdf-p{page_index:03d}-{chunk_index:04d}",
                        type="paragraph",
                        text=text,
                        html=f"<p>{escape(text)}</p>",
                        page=page_index,
                        source=relpath(copied_source, output_dir),
                        confidence=0.45,
                        provenance={
                            "parser": self.name,
                            "parser_version": "pypdf",
                            "adapter": "ctl-core-basic-pdf",
                            "created_at": utc_now(),
                        },
                    )
                )

        raw = {
            "page_count": len(reader.pages),
            "record_count": len(records),
            "extractor": "pypdf",
        }
        return records, raw

    def run(self, source: Path, output_dir: Path, copied_source: Path) -> AdapterResult:
        if source.suffix.lower() != ".pdf":
            return AdapterResult(self.name, "skipped", [], {"reason": "not a PDF file"}, [])

        try:
            records, raw = self.records_with_pdfplumber(source, output_dir, copied_source)
        except ImportError:
            try:
                records, raw = self.records_with_pypdf(source, output_dir, copied_source)
            except ImportError:
                return AdapterResult(
                    self.name,
                    "skipped",
                    [],
                    {"reason": "pdfplumber or pypdf is not installed"},
                    ["Install pdfplumber or pypdf to enable the basic PDF text adapter."],
                )

        warnings = []
        if not records:
            warnings.append("No extractable text found. The PDF may be scanned or image-only.")
        return AdapterResult(self.name, "ok", records, raw, warnings)


ADAPTERS: dict[str, Adapter] = {
    "fileinfo": FileInfoAdapter(),
    "basic-html": BasicHtmlAdapter(),
    "basic-json": BasicJsonAdapter(),
    "basic-text": BasicTextAdapter(),
    "basic-pdf": BasicPdfAdapter(),
}


def select_adapters(adapter_names: Iterable[str]) -> list[Adapter]:
    selected = []
    for name in adapter_names:
        if name == "all":
            return list(ADAPTERS.values())
        if name not in ADAPTERS:
            raise SystemExit(f"Unknown adapter: {name}. Known adapters: {', '.join(ADAPTERS)}")
        selected.append(ADAPTERS[name])
    return selected


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_review_html(output_dir: Path, source_id: str, source_name: str, results: list[AdapterResult], records: list[CtlRecord]) -> None:
    documents_dir = output_dir / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for result in results:
        rows.append(
            "<tr>"
            f"<td>{escape(result.adapter)}</td>"
            f"<td>{escape(result.status)}</td>"
            f"<td>{len(result.records)}</td>"
            f"<td>{escape('; '.join(result.warnings))}</td>"
            "</tr>"
        )

    record_items = []
    for order, record in enumerate(records[:250], start=1):
        label = escape(record.text[:220])
        record_items.append(
            f"<li><strong>{escape(record.type)}</strong> "
            f"<a href=\"#{escape(record.id)}\"><code>{escape(record.id)}</code></a> {label}</li>"
        )
    record_sections = []
    for order, record in enumerate(records[:250], start=1):
        html_fragment = record.html or f"<p>{escape(record.text)}</p>" if record.text else ""
        asset_link = ""
        if record.asset:
            asset_link = f"<p>Asset: <a href=\"../{escape(record.asset)}\">{escape(record.asset)}</a></p>"
        record_sections.append(
            f"<section class=\"ctl-record\" id=\"{escape(record.id)}\" data-ctl-record-id=\"{escape(record.id)}\" "
            f"data-ctl-type=\"{escape(record.type)}\" data-ctl-order=\"{order}\">"
            f"<h3>{escape(record.type)} <code>{escape(record.id)}</code></h3>"
            f"{html_fragment}"
            f"{asset_link}"
            f"</section>"
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CTL Parser Lab - {escape(source_name)}</title>
</head>
<body>
  <article class="ctl-document parser-lab-report">
    <header class="ctl-header">
      <h1 class="ctl-title">Parser Lab Report</h1>
      <p class="ctl-paragraph">Source: <code>{escape(source_name)}</code></p>
      <p class="ctl-paragraph">Source id: <code>{escape(source_id)}</code></p>
    </header>

    <section class="ctl-section" id="adapter-results">
      <h2 class="ctl-heading">Adapter Results</h2>
      <table class="ctl-table">
        <thead>
          <tr><th>Adapter</th><th>Status</th><th>Records</th><th>Warnings</th></tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </section>

    <section class="ctl-section" id="draft-records">
      <h2 class="ctl-heading">Draft CTL Records</h2>
      <ol>
        {''.join(record_items)}
      </ol>
    </section>

    <section class="ctl-section" id="record-details">
      <h2 class="ctl-heading">Record Details</h2>
      {''.join(record_sections)}
    </section>
  </article>
</body>
</html>
"""
    (documents_dir / "parser-lab-report.html").write_text(html, encoding="utf-8")


def run_parser_lab(source: Path, output_dir: Path, adapters: list[Adapter]) -> None:
    source = source.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_id = slugify(source.stem)
    original_dir = output_dir / "assets" / "original"
    intermediate_dir = output_dir / "intermediate"
    original_dir.mkdir(parents=True, exist_ok=True)
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    copied_source = original_dir / source.name
    shutil.copy2(source, copied_source)

    results: list[AdapterResult] = []
    records: list[CtlRecord] = []
    for adapter in adapters:
        result = adapter.run(source, output_dir, copied_source)
        results.append(result)
        records.extend(result.records)
        write_json(
            intermediate_dir / adapter.name / "result.json",
            {
                "adapter": result.adapter,
                "status": result.status,
                "warnings": result.warnings,
                "raw": result.raw,
                "records": [
                    record_to_json(record, source_id, order)
                    for order, record in enumerate(result.records, start=1)
                ],
            },
        )

    canonical_records = [
        record_to_json(record, source_id, order)
        for order, record in enumerate(records, start=1)
    ]
    write_json(output_dir / "assets" / "tables" / "ctl-records.json", canonical_records)
    provenance = {
        "created_at": utc_now(),
        "source_id": source_id,
        "source": relpath(copied_source, output_dir),
        "source_sha256": sha256_file(source),
        "source_of_truth": "Original source file and CTL package files remain authoritative; indexes and database exports are replaceable.",
        "adapters": [
            {
                "name": result.adapter,
                "status": result.status,
                "record_count": len(result.records),
                "warnings": result.warnings,
            }
            for result in results
        ],
    }
    write_json(output_dir / "manifests" / "provenance.json", provenance)
    write_json(
        output_dir / "manifest.json",
        {
            "ctl_version": CTL_VERSION,
            "ctl_schema_version": "0.1",
            "created_at": utc_now(),
            "source_id": source_id,
            "source": relpath(copied_source, output_dir),
            "source_sha256": sha256_file(source),
            "adapters": [
                {
                    "name": result.adapter,
                    "status": result.status,
                    "record_count": len(result.records),
                    "warnings": result.warnings,
                }
                for result in results
            ],
            "record_count": len(records),
            "source_of_truth": "CTL package files are the durable data layer. Database indexes are optional and rebuildable.",
        },
    )
    write_json(
        output_dir / "search.json",
        [
            {"id": record.id, "type": record.type, "text": record.text, "source": record.source}
            for record in records
            if record.text
        ],
    )
    write_review_html(output_dir, source_id, source.name, results, records)
    export_okf(output_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ctl-core parser-lab adapters.")
    parser.add_argument("source", type=Path, help="Source file to inspect.")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output directory.")
    parser.add_argument(
        "--adapter",
        action="append",
        default=["all"],
        help="Adapter to run. Repeatable. Use 'all' for built-ins.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.source.exists():
        raise SystemExit(f"Source file not found: {args.source}")
    adapters = select_adapters(args.adapter)
    run_parser_lab(args.source, args.output, adapters)
    print(f"Wrote parser lab package to {args.output}")
    print(f"Open {args.output / 'documents' / 'parser-lab-report.html'}")


if __name__ == "__main__":
    main()
