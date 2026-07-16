"""Source intake adapters for public web, RSS, GitHub, YouTube, and Reddit.

This is a conservative CTL-Core intake tool:

- no login
- no paywall bypass
- no scraping tricks
- no browser automation
- no writes outside the selected CTL output package

It turns public source signals into ordinary CTL records so they can be browsed,
indexed, exported to OKF, or handed to CTL-Suite later.
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ctl_okf_export import export_okf


CTL_SOURCE_INTAKE_VERSION = "0.1-source-intake"
USER_AGENT = "CTL-Core source intake/0.1 (+https://github.com/dpi-workshop/ctl-core)"


@dataclass
class SourceRecord:
    id: str
    type: str
    text: str = ""
    html: str = ""
    asset_path: str = ""
    source_path: str = ""
    links: list[dict[str, str]] | None = None
    tags: list[str] | None = None
    confidence: float | None = None
    provenance: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class BlockHtmlParser(html.parser.HTMLParser):
    BLOCK_TAGS = {"title", "h1", "h2", "h3", "p", "li", "figcaption", "caption"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current_tag: str | None = None
        self.current_text: list[str] = []
        self.blocks: list[tuple[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag in self.BLOCK_TAGS:
            self.flush()
            self.current_tag = tag
        if tag == "a" and attr_map.get("href"):
            self.links.append({"href": attr_map["href"], "text": ""})
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

    def handle_data(self, data: str) -> None:
        text = clean_text(data)
        if not text:
            return
        if self.current_tag:
            self.current_text.append(text)
        if self.links:
            self.links[-1]["text"] = clean_text(f"{self.links[-1]['text']} {text}")

    def flush(self) -> None:
        if self.current_tag and self.current_text:
            text = clean_text(" ".join(self.current_text))
            if text:
                self.blocks.append((self.current_tag, text))
        self.current_tag = None
        self.current_text = []

    def close(self) -> None:
        self.flush()
        super().close()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "source"


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fetch_text(url: str, timeout: int = 30) -> tuple[str, dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        headers = {key.lower(): value for key, value in response.headers.items()}
        return response.read().decode(charset, errors="replace"), headers


def absolute_url(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, href)


def item_text(item: ET.Element, names: list[str]) -> str:
    for name in names:
        found = item.find(name)
        if found is not None and found.text:
            return clean_text(found.text)
    return ""


def item_link(item: ET.Element) -> str:
    link = item.find("link")
    if link is not None:
        if link.text:
            return clean_text(link.text)
        href = link.attrib.get("href")
        if href:
            return href
    return ""


def rss_records(url: str, limit: int) -> tuple[list[SourceRecord], dict[str, Any], str]:
    text, headers = fetch_text(url)
    root = ET.fromstring(text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//atom:entry", ns)

    records: list[SourceRecord] = []
    for index, item in enumerate(items[:limit], start=1):
        title = item_text(item, ["title", "{http://www.w3.org/2005/Atom}title"]) or f"Feed item {index}"
        summary = item_text(
            item,
            [
                "description",
                "summary",
                "{http://www.w3.org/2005/Atom}summary",
                "{http://www.w3.org/2005/Atom}content",
            ],
        )
        link = item_link(item)
        published = item_text(
            item,
            ["pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"],
        )
        records.append(
            SourceRecord(
                id=f"rss-item-{index:04d}",
                type="feed_item",
                text=clean_text(f"{title}. {summary}"),
                html=f"<article><h2>{escape(title)}</h2><p>{escape(summary)}</p></article>",
                links=[{"href": link, "rel": "source"}] if link else [],
                tags=["ctl", "source-intake", "rss"],
                confidence=0.7,
                provenance=provenance("source-intake-rss", url),
                metadata={"published": published, "source_url": url},
            )
        )
    raw = {"adapter": "rss", "url": url, "content_type": headers.get("content-type", ""), "item_count": len(items)}
    return records, raw, text


def web_records(url: str, limit: int) -> tuple[list[SourceRecord], dict[str, Any], str]:
    text, headers = fetch_text(url)
    parser = BlockHtmlParser()
    parser.feed(text)
    parser.close()

    records: list[SourceRecord] = []
    for index, (tag, block_text) in enumerate(parser.blocks[:limit], start=1):
        record_type = "heading" if tag in {"title", "h1", "h2", "h3"} else "paragraph"
        records.append(
            SourceRecord(
                id=f"web-block-{index:04d}",
                type=record_type,
                text=block_text,
                html=f"<{tag}>{escape(block_text)}</{tag}>",
                links=[],
                tags=["ctl", "source-intake", "website"],
                confidence=0.45,
                provenance=provenance("source-intake-web", url),
                metadata={"source_url": url, "tag": tag},
            )
        )

    for index, image in enumerate(parser.images[:limit], start=1):
        src = absolute_url(url, image.get("src", ""))
        label = image.get("alt") or image.get("title") or "Website image"
        records.append(
            SourceRecord(
                id=f"web-image-{index:04d}",
                type="figure",
                text=label,
                html=f"<figure><img src=\"{escape(src)}\" alt=\"{escape(label)}\"><figcaption>{escape(label)}</figcaption></figure>",
                links=[{"href": src, "rel": "image-source"}] if src else [],
                tags=["ctl", "source-intake", "website", "figure"],
                confidence=0.3,
                provenance=provenance("source-intake-web", url),
                metadata={"source_url": url, "src": src},
            )
        )

    raw = {
        "adapter": "website",
        "url": url,
        "content_type": headers.get("content-type", ""),
        "block_count": len(parser.blocks),
        "link_count": len(parser.links),
        "image_count": len(parser.images),
        "links": parser.links[:limit],
    }
    return records, raw, text


def github_repo_url(url: str) -> tuple[str, str]:
    match = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", url)
    if not match:
        raise SystemExit("GitHub intake expects a public repo URL such as https://github.com/owner/repo")
    return match.group(1), match.group(2).removesuffix(".git")


def github_records(url: str, limit: int) -> tuple[list[SourceRecord], dict[str, Any], str]:
    owner, repo = github_repo_url(url)
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    text, headers = fetch_text(api_url)
    data = json.loads(text)
    fields = {
        "description": data.get("description") or "",
        "language": data.get("language") or "",
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "open_issues": data.get("open_issues_count"),
        "license": (data.get("license") or {}).get("spdx_id") or "",
        "default_branch": data.get("default_branch") or "",
        "updated_at": data.get("updated_at") or "",
    }
    body = "\n".join(f"- {key}: {value}" for key, value in fields.items())
    records = [
        SourceRecord(
            id="github-repo-summary",
            type="repo_summary",
            text=clean_text(f"{owner}/{repo}. {fields['description']}"),
            html=f"<article><h1>{escape(owner)}/{escape(repo)}</h1><pre>{escape(body)}</pre></article>",
            links=[{"href": data.get("html_url") or url, "rel": "source"}],
            tags=["ctl", "source-intake", "github", "repo"],
            confidence=0.85,
            provenance=provenance("source-intake-github", url),
            metadata={"source_url": url, **fields},
        )
    ]
    topics = data.get("topics") or []
    for index, topic in enumerate(topics[:limit], start=1):
        records.append(
            SourceRecord(
                id=f"github-topic-{index:04d}",
                type="tag",
                text=str(topic),
                html=f"<p>{escape(str(topic))}</p>",
                tags=["ctl", "source-intake", "github", "topic"],
                confidence=0.75,
                provenance=provenance("source-intake-github", url),
                metadata={"source_url": url},
            )
        )
    raw = {"adapter": "github", "url": url, "api_url": api_url, "rate_remaining": headers.get("x-ratelimit-remaining", "")}
    return records, raw, text


def youtube_feed_url(value: str) -> str:
    if value.startswith("UC") and "/" not in value:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={value}"
    if "feeds/videos.xml" in value:
        return value
    if "youtube.com/watch" in value or "youtu.be/" in value:
        encoded = urllib.parse.quote(value, safe="")
        return f"https://www.youtube.com/oembed?url={encoded}&format=json"
    raise SystemExit(
        "YouTube intake expects a channel_id, a YouTube RSS feed URL, or a specific video URL. "
        "Handle URLs may need a separate lookup step."
    )


def youtube_records(url: str, limit: int) -> tuple[list[SourceRecord], dict[str, Any], str]:
    source_url = youtube_feed_url(url)
    text, headers = fetch_text(source_url)
    if "oembed" in source_url:
        data = json.loads(text)
        title = data.get("title") or "YouTube video"
        author = data.get("author_name") or ""
        records = [
            SourceRecord(
                id="youtube-video",
                type="video",
                text=clean_text(f"{title}. {author}"),
                html=f"<article><h1>{escape(title)}</h1><p>{escape(author)}</p></article>",
                links=[{"href": url, "rel": "source"}],
                tags=["ctl", "source-intake", "youtube", "video"],
                confidence=0.7,
                provenance=provenance("source-intake-youtube", url),
                metadata={"source_url": url, "author": author},
            )
        ]
        return records, {"adapter": "youtube", "url": url, "mode": "oembed"}, text
    records, raw, _ = rss_records(source_url, limit)
    for record in records:
        record.tags = ["ctl", "source-intake", "youtube", "feed_item"]
        record.provenance = provenance("source-intake-youtube", url)
    raw["adapter"] = "youtube"
    raw["input_url"] = url
    raw["feed_url"] = source_url
    return records, raw, text


def reddit_json_url(value: str, limit: int) -> str:
    if "reddit.com" in value:
        parsed = urllib.parse.urlparse(value)
        path = parsed.path.rstrip("/")
        if path.endswith(".json"):
            return value
        return urllib.parse.urlunparse(parsed._replace(path=f"{path}.json", query=f"limit={limit}"))
    subreddit = value.strip().lstrip("r/")
    if not subreddit:
        raise SystemExit("Reddit intake expects a subreddit name or public reddit.com URL.")
    return f"https://www.reddit.com/r/{urllib.parse.quote(subreddit)}/top.json?t=month&limit={limit}"


def reddit_records(url: str, limit: int) -> tuple[list[SourceRecord], dict[str, Any], str]:
    source_url = reddit_json_url(url, limit)
    text, headers = fetch_text(source_url)
    data = json.loads(text)
    children = (((data.get("data") or {}).get("children")) or [])[:limit]
    records: list[SourceRecord] = []
    for index, child in enumerate(children, start=1):
        post = child.get("data") or {}
        title = post.get("title") or f"Reddit post {index}"
        permalink = absolute_url("https://www.reddit.com", post.get("permalink") or "")
        selftext = clean_text(post.get("selftext") or "")
        records.append(
            SourceRecord(
                id=f"reddit-post-{index:04d}",
                type="social_signal",
                text=clean_text(f"{title}. {selftext}"),
                html=f"<article><h2>{escape(title)}</h2><p>{escape(selftext)}</p></article>",
                links=[{"href": permalink, "rel": "source"}] if permalink else [],
                tags=["ctl", "source-intake", "reddit", "signal", "unverified"],
                confidence=0.35,
                provenance=provenance("source-intake-reddit", url),
                metadata={
                    "source_url": source_url,
                    "score": post.get("score"),
                    "num_comments": post.get("num_comments"),
                    "subreddit": post.get("subreddit"),
                    "created_utc": post.get("created_utc"),
                    "truth_status": "unverified signal",
                },
            )
        )
    raw = {"adapter": "reddit", "url": url, "json_url": source_url, "post_count": len(children), "content_type": headers.get("content-type", "")}
    return records, raw, text


def provenance(adapter: str, url: str) -> dict[str, Any]:
    return {
        "parser": "ctl-source-intake",
        "parser_version": CTL_SOURCE_INTAKE_VERSION,
        "adapter": adapter,
        "source_url": url,
        "created_at": utc_now(),
    }


def detect_kind(url: str, explicit: str) -> str:
    if explicit != "auto":
        return explicit
    lowered = url.lower()
    if "github.com/" in lowered:
        return "github"
    if "youtube.com/" in lowered or "youtu.be/" in lowered or url.startswith("UC"):
        return "youtube"
    if "reddit.com/" in lowered or re.fullmatch(r"r/[a-z0-9_]+|[a-z0-9_]+", lowered):
        return "reddit"
    if lowered.endswith(".xml") or "rss" in lowered or "feed" in lowered:
        return "rss"
    return "website"


def record_to_json(record: SourceRecord, source_id: str, order: int) -> dict[str, Any]:
    data = asdict(record)
    data["source_id"] = source_id
    data["order"] = order
    data.setdefault("links", [])
    data.setdefault("tags", [])
    data.setdefault("metadata", {})
    return {key: value for key, value in data.items() if value not in (None, "", [])}


def write_review_html(output_dir: Path, source_id: str, source_url: str, records: list[SourceRecord], raw: dict[str, Any]) -> None:
    documents_dir = output_dir / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    record_sections = []
    for order, record in enumerate(records, start=1):
        fragment = record.html or f"<p>{escape(record.text)}</p>"
        link_items = "".join(
            f"<li><a href=\"{escape(link.get('href', ''))}\">{escape(link.get('rel', 'link'))}</a></li>"
            for link in (record.links or [])
            if link.get("href")
        )
        links_html = f"<ul>{link_items}</ul>" if link_items else ""
        record_sections.append(
            f"<section id=\"{escape(record.id)}\" data-ctl-record-id=\"{escape(record.id)}\" data-ctl-type=\"{escape(record.type)}\">"
            f"<h3>{escape(record.type)} <code>{escape(record.id)}</code></h3>{fragment}{links_html}</section>"
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CTL Source Intake - {escape(source_id)}</title>
</head>
<body>
  <article class="ctl-document source-intake-report">
    <header>
      <h1>Source Intake Report</h1>
      <p>Source: <a href="{escape(source_url)}">{escape(source_url)}</a></p>
      <p>Source id: <code>{escape(source_id)}</code></p>
      <p>Adapter: <code>{escape(str(raw.get("adapter", "")))}</code></p>
    </header>
    <section>
      <h2>Records</h2>
      {''.join(record_sections)}
    </section>
  </article>
</body>
</html>
"""
    (documents_dir / "source-intake-report.html").write_text(html, encoding="utf-8")


def write_package(url: str, kind: str, records: list[SourceRecord], raw: dict[str, Any], raw_text: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_id = slugify(f"{kind}-{urllib.parse.urlparse(url).netloc or url}-{urllib.parse.urlparse(url).path}")
    original_dir = output_dir / "assets" / "original"
    original_dir.mkdir(parents=True, exist_ok=True)
    source_note = original_dir / "source-url.txt"
    source_note.write_text(f"{url}\n", encoding="utf-8")
    raw_path = output_dir / "intermediate" / kind / "raw.txt"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw_text, encoding="utf-8")

    canonical_records = [record_to_json(record, source_id, order) for order, record in enumerate(records, start=1)]
    write_json(output_dir / "assets" / "tables" / "ctl-records.json", canonical_records)
    write_json(output_dir / "intermediate" / kind / "result.json", {"adapter": kind, "raw": raw, "records": canonical_records})
    provenance_doc = {
        "created_at": utc_now(),
        "source_id": source_id,
        "source": "assets/original/source-url.txt",
        "source_url": url,
        "source_sha256": sha256_text(raw_text),
        "source_of_truth": "Original public URL and CTL package files remain authoritative; indexes are replaceable.",
        "adapters": [{"name": kind, "status": "ok", "record_count": len(records), "warnings": []}],
    }
    write_json(output_dir / "manifests" / "provenance.json", provenance_doc)
    write_json(
        output_dir / "manifest.json",
        {
            "ctl_version": CTL_SOURCE_INTAKE_VERSION,
            "ctl_schema_version": "0.1",
            "created_at": utc_now(),
            "source_id": source_id,
            "source": "assets/original/source-url.txt",
            "source_url": url,
            "source_sha256": sha256_text(raw_text),
            "adapters": [{"name": kind, "status": "ok", "record_count": len(records), "warnings": []}],
            "record_count": len(records),
            "source_of_truth": "CTL package files are the durable data layer. Database indexes are optional and rebuildable.",
        },
    )
    write_json(
        output_dir / "search.json",
        [{"id": record.id, "type": record.type, "text": record.text, "source": url} for record in records if record.text],
    )
    write_review_html(output_dir, source_id, url, records, raw)
    export_okf(output_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a CTL package from public RSS, website, GitHub, YouTube, or Reddit sources.")
    parser.add_argument("source", help="Public source URL, GitHub repo URL, YouTube feed/channel/video, or subreddit name.")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output CTL package directory.")
    parser.add_argument("--kind", choices=["auto", "rss", "website", "github", "youtube", "reddit"], default="auto")
    parser.add_argument("--limit", type=int, default=20, help="Maximum feed/posts/blocks/images to capture.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    kind = detect_kind(args.source, args.kind)
    handlers = {
        "rss": rss_records,
        "website": web_records,
        "github": github_records,
        "youtube": youtube_records,
        "reddit": reddit_records,
    }
    try:
        records, raw, raw_text = handlers[kind](args.source, args.limit)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"{kind} intake failed with HTTP {error.code}: {error.reason}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"{kind} intake failed: {error.reason}") from error
    write_package(args.source, kind, records, raw, raw_text, args.output)
    print(f"Wrote {len(records)} CTL records with {kind} intake.")
    print(f"Open {args.output / 'documents' / 'source-intake-report.html'}")


if __name__ == "__main__":
    main()
