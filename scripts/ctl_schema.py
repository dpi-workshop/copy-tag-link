"""Shared CTL record schema for ctl-core parser adapters."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


CTL_SCHEMA_VERSION = "0.1"


@dataclass
class CtlRecord:
    """Canonical record emitted by all CTL parser adapters."""

    id: str
    source_id: str
    type: str
    order: int
    text: str = ""
    html: str = ""
    asset_path: str = ""
    asset_paths: list[str] = field(default_factory=list)
    page: int | None = None
    bbox: list[float] | None = None
    links: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    confidence: float | None = None
    source_path: str = ""
    provenance: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


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


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def records_to_json(records: list[CtlRecord]) -> list[dict]:
    return [asdict(record) for record in records]


def search_entries(records: list[CtlRecord]) -> list[dict]:
    entries = []
    for record in records:
        if not record.text and not record.asset_path:
            continue
        entries.append(
            {
                "id": record.id,
                "source_id": record.source_id,
                "type": record.type,
                "order": record.order,
                "text": record.text,
                "asset_path": record.asset_path,
                "page": record.page,
                "tags": record.tags,
            }
        )
    return entries


def manifest(
    *,
    ctl_version: str,
    source_id: str,
    source_path: str,
    source_sha256: str | None,
    adapters: list[dict],
    record_count: int,
    extra: dict | None = None,
) -> dict:
    data = {
        "ctl_version": ctl_version,
        "ctl_schema_version": CTL_SCHEMA_VERSION,
        "created_at": utc_now(),
        "source_id": source_id,
        "source": source_path,
        "source_sha256": source_sha256,
        "adapters": adapters,
        "record_count": record_count,
    }
    if extra:
        data.update(extra)
    return data
