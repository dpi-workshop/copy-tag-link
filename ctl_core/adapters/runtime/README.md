# Runtime Adapters

Runtime adapters run tools for CTL without making those tools part of CTL-Core.

They may:

- run small trusted local processes
- run heavy parser containers
- run sandboxed WebAssembly/WASI workers
- enforce input/output mount paths
- capture logs, exit codes, and produced files

They must not:

- own CTL package data
- bypass job permissions
- read secrets unless explicitly granted
- silently install tools into the host system

Examples:

- local process runtime
- Docker runtime
- WebAssembly/WASI runtime
- remote worker runtime
