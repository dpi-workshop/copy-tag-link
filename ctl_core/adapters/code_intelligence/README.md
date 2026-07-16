# Code Intelligence Adapters

Code intelligence adapters explain codebases after CTL has preserved them.

CTL's codebase adapter turns a repository into a human-browsable CTL package:

- source files
- file records
- symbol records
- simple graph JSON
- semantic HTML report
- search records
- provenance

External code-intelligence tools can add deeper analysis:

- CodeGraph for symbol lookup, call paths, and impact analysis
- Graphify for graph outputs such as `graph.html`, `graph.json`, and reports
- Understand Anything for interactive codebase learning and guided tours

They may:

- read a selected repository or CTL package
- write derived graph/report/dashboard assets
- link derived nodes back to CTL records

They must not:

- replace source code
- become the source of truth
- run without explicit user installation/permission
- silently install plugins or hooks
- read secrets or unrelated repositories

Rule:

```text
CTL preserves the repo. Code-intelligence adapters explain the repo.
```
