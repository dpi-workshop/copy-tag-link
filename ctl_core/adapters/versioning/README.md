# Versioning Adapters

Versioning adapters track package history, forks, diffs, and checkpoints.

They may:

- detect changed CTL files
- create checkpoints
- report diffs
- connect prompts, decisions, outputs, and assets to a history timeline

They must not:

- parse source documents
- replace CTL provenance manifests
- commit secrets
- automatically publish public repositories

Examples:

- Git
- Git LFS for explicitly approved large assets
- archive snapshots

Git is useful for text-heavy CTL records, OKF cards, prompts, scripts, and
decision logs. Large video, audio, image batches, and model files should usually
live in asset storage with checksums and manifests.
