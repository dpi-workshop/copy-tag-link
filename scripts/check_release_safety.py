#!/usr/bin/env python
"""Small pre-release safety scanner for ctl-core.

This is not a replacement for gitleaks/trufflehog. It is a local guardrail for
the obvious mistakes: keys, env files, private paths, huge workbench folders,
and generated outputs in the release slice.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    ".venv-kuzu",
    "venv",
    "env",
    "output",
    "handoff",
    "dist",
    "build",
    "node_modules",
}

SUSPICIOUS_NAMES = {
    ".env",
    "secrets",
    "secret",
    "credentials",
    "token",
    "cookies",
}

SECRET_PATTERNS = [
    ("openai-style key", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}")),
    ("google api key", re.compile(r"AIza[0-9A-Za-z_-]{20,}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}")),
    ("generic api assignment", re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]{12,}['\"]")),
    ("windows user path", re.compile(r"C:\\Users\\[^\\\s]+", re.IGNORECASE)),
    ("local ai path", re.compile(r"E:\\AI\\", re.IGNORECASE)),
    ("downloads path", re.compile(r"E:\\Downloads\\|C:\\Users\\[^\\\s]+\\Downloads", re.IGNORECASE)),
]


def should_skip_dir(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def scan_file(path: Path, root: Path) -> list[str]:
    findings = []
    relative = path.relative_to(root).as_posix()
    lower_name = path.name.lower()
    lower_stem = path.stem.lower()
    if lower_name in SUSPICIOUS_NAMES or lower_stem in SUSPICIOUS_NAMES:
        findings.append(f"{relative}: suspicious filename")
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(f"{relative}: {label}")
    return findings


def scan(root: Path) -> list[str]:
    findings = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if should_skip_dir(path.relative_to(root)):
            continue
        findings.extend(scan_file(path, root))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a small ctl-core release safety scan.")
    parser.add_argument("root", type=Path, nargs="?", default=Path("."), help="Repository root to scan.")
    args = parser.parse_args()
    root = args.root.resolve()
    findings = scan(root)
    if findings:
        print("Release safety scan found issues:")
        for finding in findings:
            print(f"- {finding}")
        raise SystemExit(1)
    print("Release safety scan passed.")


if __name__ == "__main__":
    main()
