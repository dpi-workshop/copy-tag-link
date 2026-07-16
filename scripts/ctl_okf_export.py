#!/usr/bin/env python
"""Export a CTL package as OKF-compatible Markdown cards.

OKF is treated as the card catalogue. CTL HTML/assets remain the richer shelf.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OKF_EXPORT_VERSION = "0.1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def yaml_scalar(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text:
        return '""'
    if re.fullmatch(r"[A-Za-z0-9_./:@+-]+", text):
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def yaml_list(values: list[Any]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(yaml_scalar(value) for value in values) + "]"


def frontmatter(fields: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{key}: {yaml_list(value)}")
        elif isinstance(value, dict):
            lines.append(f"{key}: {yaml_scalar(json.dumps(value, ensure_ascii=False, sort_keys=True))}")
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def rel_link(target: str, from_dir: Path, package_dir: Path) -> str:
    if not target:
        return ""
    target_path = (package_dir / target).resolve()
    if not target_path.exists() and "://" in target:
        return target
    return Path(os.path.relpath(target_path, from_dir.resolve())).as_posix()


def find_review_document(package_dir: Path) -> str:
    documents_dir = package_dir / "documents"
    if not documents_dir.exists():
        return ""
    candidates = sorted(documents_dir.glob("*.html"))
    if not candidates:
        return ""
    return candidates[0].relative_to(package_dir).as_posix()


def title_for_record(record: dict[str, Any]) -> str:
    text = " ".join(str(record.get("text", "")).split())
    if text:
        return text[:90]
    asset = record.get("asset_path") or ""
    if asset:
        return Path(asset).name
    return record.get("id", "CTL record")


def record_tags(record: dict[str, Any]) -> list[str]:
    tags = ["ctl", f"ctl-type-{record.get('type', 'unknown')}"]
    parser = (record.get("provenance") or {}).get("parser")
    if parser:
        tags.append(f"parser-{parser}")
    for tag in record.get("tags") or []:
        if tag not in tags:
            tags.append(str(tag))
    return tags


def write_source_card(package_dir: Path, okf_dir: Path, manifest: dict[str, Any], review_doc: str) -> Path:
    source_id = manifest.get("source_id") or slugify(Path(str(manifest.get("source", "source"))).stem)
    target = okf_dir / "source.md"
    fields = {
        "type": "CTL Source",
        "title": source_id,
        "description": "Source package exported from CTL semantic HTML/assets.",
        "resource": rel_link(review_doc, okf_dir, package_dir) if review_doc else "",
        "source": manifest.get("source", ""),
        "source_sha256": manifest.get("source_sha256", ""),
        "ctl_schema_version": manifest.get("ctl_schema_version", ""),
        "ctl_version": manifest.get("ctl_version", ""),
        "tags": ["ctl", "source", "okf-export"],
        "timestamp": manifest.get("created_at") or utc_now(),
    }
    body = [
        f"# {source_id}",
        "",
        "This OKF card points to the CTL source package. The rich data remains in the CTL HTML, assets, manifest, and records.",
        "",
    ]
    if review_doc:
        body.append(f"- CTL review HTML: [{review_doc}]({rel_link(review_doc, okf_dir, package_dir)})")
    body.extend(
        [
            f"- Source: `{manifest.get('source', '')}`",
            f"- Record count: `{manifest.get('record_count', '')}`",
        ]
    )
    target.write_text(frontmatter(fields) + "\n".join(body) + "\n", encoding="utf-8")
    return target


def write_parser_card(package_dir: Path, okf_dir: Path, manifest: dict[str, Any]) -> Path:
    target = okf_dir / "parser-decision.md"
    adapters = manifest.get("adapters") or []
    adapter_names = [str(adapter.get("name", "unknown")) for adapter in adapters if isinstance(adapter, dict)]
    fields = {
        "type": "CTL Parser Decision",
        "title": "Parser decision and adapter provenance",
        "description": "Parser/adapter metadata for this CTL package.",
        "resource": "../manifest.json",
        "tags": ["ctl", "parser-decision", *[f"parser-{name}" for name in adapter_names]],
        "timestamp": manifest.get("created_at") or utc_now(),
    }
    body = ["# Parser Decision", ""]
    body.append("Adapters:")
    for adapter in adapters:
        if not isinstance(adapter, dict):
            continue
        body.append(
            f"- `{adapter.get('name', 'unknown')}`: `{adapter.get('status', '')}`, records `{adapter.get('record_count', '')}`"
        )
    body.extend(["", "- Manifest: [manifest.json](../manifest.json)"])
    target.write_text(frontmatter(fields) + "\n".join(body) + "\n", encoding="utf-8")
    return target


def write_record_card(package_dir: Path, records_dir: Path, record: dict[str, Any], review_doc: str) -> Path:
    record_id = record.get("id", "record")
    filename = f"{slugify(str(record_id))}.md"
    target = records_dir / filename
    asset_path = record.get("asset_path") or ""
    source_path = record.get("source_path") or ""
    provenance = record.get("provenance") or {}
    resource = asset_path or review_doc or source_path
    fields = {
        "type": f"CTL {record.get('type', 'Record')}",
        "title": title_for_record(record),
        "description": f"CTL record {record_id} from source {record.get('source_id', '')}.",
        "resource": rel_link(resource, records_dir, package_dir) if resource else "",
        "ctl_record_id": record_id,
        "source_id": record.get("source_id", ""),
        "record_type": record.get("type", ""),
        "order": record.get("order", ""),
        "page": record.get("page", ""),
        "bbox": record.get("bbox") or [],
        "confidence": record.get("confidence", ""),
        "parser": provenance.get("parser", ""),
        "parser_version": provenance.get("parser_version", ""),
        "tags": record_tags(record),
        "timestamp": provenance.get("created_at") or utc_now(),
    }
    body = [f"# {title_for_record(record)}", ""]
    body.append(f"- CTL record id: `{record_id}`")
    body.append(f"- Type: `{record.get('type', '')}`")
    body.append(f"- Source id: `{record.get('source_id', '')}`")
    if asset_path:
        body.append(f"- Asset: [{asset_path}]({rel_link(asset_path, records_dir, package_dir)})")
    if source_path:
        body.append(f"- Source path: `{source_path}`")
    if review_doc:
        body.append(f"- CTL review HTML: [{review_doc}]({rel_link(review_doc, records_dir, package_dir)})")
    if record.get("text"):
        body.extend(["", "## Text", "", str(record["text"])])
    if record.get("html"):
        body.extend(["", "## CTL HTML Fragment", "", "```html", str(record["html"]), "```"])
    target.write_text(frontmatter(fields) + "\n".join(body) + "\n", encoding="utf-8")
    return target


def write_index(okf_dir: Path, manifest: dict[str, Any], record_cards: list[Path]) -> None:
    source_id = manifest.get("source_id") or "source"
    lines = [
        frontmatter(
            {
                "type": "CTL OKF Index",
                "title": f"{source_id} OKF index",
                "description": "Index of OKF cards generated from a CTL package.",
                "resource": "source.md",
                "tags": ["ctl", "okf", "index"],
                "timestamp": utc_now(),
            }
        ).rstrip(),
        "",
        f"# {source_id} OKF Index",
        "",
        "- [Source card](source.md)",
        "- [Parser decision](parser-decision.md)",
        "",
        "## Records",
        "",
    ]
    for card in record_cards:
        lines.append(f"- [{card.stem}]({card.relative_to(okf_dir).as_posix()})")
    (okf_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_okf(package_dir: Path, output_dir: Path | None = None, max_records: int | None = None) -> None:
    package_dir = package_dir.resolve()
    output_dir = (output_dir or package_dir / "okf").resolve()
    records_path = package_dir / "assets" / "tables" / "ctl-records.json"
    manifest_path = package_dir / "manifest.json"
    if not records_path.exists():
        raise SystemExit(f"CTL records not found: {records_path}")
    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    records_dir = output_dir / "records"
    records_dir.mkdir(parents=True, exist_ok=True)

    manifest_data = read_json(manifest_path)
    records = read_json(records_path)
    if max_records is not None:
        records = records[:max_records]
    review_doc = find_review_document(package_dir)

    write_source_card(package_dir, output_dir, manifest_data, review_doc)
    write_parser_card(package_dir, output_dir, manifest_data)
    record_cards = [write_record_card(package_dir, records_dir, record, review_doc) for record in records]
    write_index(output_dir, manifest_data, record_cards)

    summary = {
        "okf_export_version": OKF_EXPORT_VERSION,
        "created_at": utc_now(),
        "package": str(package_dir),
        "okf_dir": str(output_dir),
        "record_card_count": len(record_cards),
        "source_card": "source.md",
        "parser_card": "parser-decision.md",
        "index": "index.md",
    }
    (output_dir / "okf-export.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a CTL package to OKF-compatible Markdown cards.")
    parser.add_argument("package", type=Path, help="CTL package directory containing manifest.json and assets/tables/ctl-records.json.")
    parser.add_argument("-o", "--output", type=Path, default=None, help="OKF output directory. Defaults to <package>/okf.")
    parser.add_argument("--max-records", type=int, default=None, help="Limit record cards for review/testing.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export_okf(args.package, args.output, args.max_records)
    output = args.output or args.package / "okf"
    print(f"Wrote OKF cards to {output}")
    print(f"Open {output / 'index.md'}")


if __name__ == "__main__":
    main()
