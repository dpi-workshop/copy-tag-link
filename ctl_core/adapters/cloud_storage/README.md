# Cloud Storage Adapters

Cloud storage adapters sync CTL packages to storage providers.

They may:

- upload/download CTL packages
- mirror static package folders
- verify checksums
- preserve relative paths

They must not:

- parse source documents
- decide what records mean
- alter extracted facts
- run social imports

Examples:

- Cloudflare R2
- S3
- Google Drive
- local filesystem mirror
- rclone external CLI bridge
- AList external WebDAV/service bridge

## Optional External Bridges

### rclone

rclone is useful when a user already wants one tool that can copy, sync, or
mount many cloud providers. A CTL rclone adapter should call the external
`rclone` executable only when the user has installed and configured it.

CTL-Core should not bundle rclone or require it for local package creation.

### AList

AList is useful when a user wants a unified web file browser or WebDAV layer
over many storage providers. A CTL AList adapter should treat AList as an
external service or WebDAV endpoint.

AList is AGPL-3.0. CTL-Core is Apache-2.0. Do not copy AList code into CTL-Core; use
it only as an optional bridge selected by the user.
