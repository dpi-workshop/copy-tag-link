# Demos

The public MVP includes three small demos.

To run the default non-network smoke tests:

```shell
python scripts/run_smoke_tests.py
```

## HTML Demo

The HTML demo uses only the Python standard library.

```shell
python scripts/ctl_parser_lab.py samples/simple-source/market-snapshot.html -o output/demo-market-snapshot
```

Open:

```text
output/demo-market-snapshot/documents/parser-lab-report.html
```

## PDF Demo

Install optional demo dependencies:

```shell
python -m pip install -r requirements-demo.txt
```

Regenerate the styled sample PDF:

```shell
python scripts/build_demo_pdf.py
```

Parse it:

```shell
python scripts/ctl_parser_lab.py samples/simple-source/market-snapshot.pdf -o output/demo-market-snapshot-pdf
```

Open:

```text
output/demo-market-snapshot-pdf/documents/parser-lab-report.html
```

The PDF demo should preserve the original PDF and extract:

- semantic text records
- a semantic HTML table
- a table crop
- a diagram crop
- an embedded image crop
- OKF-compatible cards

## Source Intake Demo

GitHub public metadata:

```shell
python scripts/ctl_source_intake.py https://github.com/python/cpython -o output/source-intake-github-cpython --kind github --limit 10
```

Reddit public JSON:

```shell
python scripts/ctl_source_intake.py r/python -o output/reddit-python --kind reddit --limit 10
```

Social sources are unverified signal. Use them for discovery, not as proof.

## Codebase Demo

Run CTL on CTL-Core itself:

```shell
python scripts/ctl_codebase_adapter.py . -o output/codebase-ctl-core-public --name ctl-core-public
```

Open:

```text
output/codebase-ctl-core-public/documents/codebase-report.html
```

This produces:

- file records
- symbol records
- a simple code graph
- search JSON
- OKF cards
