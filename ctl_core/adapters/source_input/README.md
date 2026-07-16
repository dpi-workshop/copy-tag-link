# Source Input Adapters

Source input adapters collect public source signals and turn them into CTL
packages.

They may:

- read public RSS/Atom feeds
- read public web pages
- read public GitHub repository metadata
- read public YouTube feed or video metadata
- read public Reddit JSON endpoints

They must not:

- bypass paywalls
- evade platform rate limits
- use hidden credentials
- scrape private accounts
- treat social/signal data as verified fact
- alter CTL source-of-truth records after import

The first public tool is `scripts/ctl_source_intake.py`. It is intentionally
small, conservative, and dependency-free.

Examples:

```shell
python scripts/ctl_source_intake.py https://example.com/feed.xml -o output/feed-demo --kind rss
python scripts/ctl_source_intake.py https://github.com/dpi-workshop/ctl-core -o output/github-demo
python scripts/ctl_source_intake.py r/python -o output/reddit-python --kind reddit --limit 10
```
