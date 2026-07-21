"""Run CTL-Core public smoke tests.

The default tests avoid network access and heavy optional dependencies.
Use `--network` to test public source intake against GitHub metadata.
Use `--pdf` to test the optional PDF demo dependencies.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
SMOKE_ROOT = f"output/smoke-{RUN_ID}"


def run(command: list[str], *, optional: bool = False) -> bool:
    print(f"== {' '.join(command)}")
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode == 0:
        return True
    if optional:
        print(f"optional check skipped/failed with exit code {result.returncode}")
        return False
    raise SystemExit(result.returncode)


def exists(path: str) -> None:
    target = ROOT / path
    if not target.exists():
        raise SystemExit(f"Expected file not found: {target}")


def smoke_output(name: str) -> str:
    return f"{SMOKE_ROOT}/{name}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CTL-Core public smoke tests.")
    parser.add_argument("--network", action="store_true", help="Run public network source-intake smoke test.")
    parser.add_argument("--pdf", action="store_true", help="Run optional PDF demo smoke test.")
    args = parser.parse_args()

    run(
        [
            PYTHON,
            "-m",
            "py_compile",
            "scripts/ctl_parser_lab.py",
            "scripts/ctl_okf_export.py",
            "scripts/ctl_source_intake.py",
            "scripts/ctl_codebase_adapter.py",
            "scripts/ctl_schema.py",
            "scripts/check_release_safety.py",
            "scripts/build_demo_pdf.py",
            "ctl_core/cli.py",
            "ctl_core/__main__.py",
            "ctl_core/adapters/database/sqlite_index.py",
            "ctl_core/adapters/database/sqlite_vec_index.py",
            "ctl_core/adapters/database/kuzu_index.py",
        ]
    )

    html_output = smoke_output("html")
    run([PYTHON, "scripts/ctl_parser_lab.py", "samples/simple-source/market-snapshot.html", "-o", html_output])
    exists(f"{html_output}/documents/parser-lab-report.html")
    exists(f"{html_output}/okf/index.md")
    run([PYTHON, "-m", "ctl_core", "inspect", html_output])
    run([PYTHON, "-m", "ctl_core", "validate", html_output])
    run([PYTHON, "-m", "ctl_core", "search", html_output, "HTML"])
    run([PYTHON, "-m", "ctl_core", "index-sqlite", html_output])
    exists(f"{html_output}/indexes/sqlite/ctl-index.sqlite")
    exists(f"{html_output}/indexes/sqlite/index-manifest.json")
    run([PYTHON, "-m", "ctl_core", "query-sqlite", html_output, "HTML"])

    codebase_output = smoke_output("codebase")
    run([PYTHON, "scripts/ctl_codebase_adapter.py", ".", "-o", codebase_output, "--name", "ctl-core-smoke"])
    exists(f"{codebase_output}/documents/codebase-report.html")
    exists(f"{codebase_output}/graph/ctl-code-graph.json")
    exists(f"{codebase_output}/okf/index.md")
    run([PYTHON, "-m", "ctl_core", "validate", codebase_output])

    if args.network:
        github_output = smoke_output("github")
        run(
            [
                PYTHON,
                "scripts/ctl_source_intake.py",
                "https://github.com/python/cpython",
                "-o",
                github_output,
                "--kind",
                "github",
                "--limit",
                "5",
            ]
        )
        exists(f"{github_output}/documents/source-intake-report.html")
        exists(f"{github_output}/okf/index.md")

    if args.pdf:
        run([PYTHON, "scripts/build_demo_pdf.py"], optional=True)
        pdf_output = smoke_output("pdf")
        pdf_ok = run(
            [
                PYTHON,
                "scripts/ctl_parser_lab.py",
                "samples/simple-source/market-snapshot.pdf",
                "-o",
                pdf_output,
            ],
            optional=True,
        )
        if pdf_ok:
            exists(f"{pdf_output}/documents/parser-lab-report.html")
            exists(f"{pdf_output}/okf/index.md")

    print("Smoke tests passed.")


if __name__ == "__main__":
    main()
