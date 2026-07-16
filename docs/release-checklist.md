# CTL-Core Public Release Checklist

Use this before creating a public GitHub repo.

## Identity

- [ ] GitHub owner/org chosen: `dpi-workshop`
- [ ] Repo name chosen: `ctl-core`
- [ ] Public maintainer name chosen: `Dean Khong`
- [ ] Git author name/email checked
- [ ] GitHub no-reply or project email configured

## Secret Safety

- [ ] No `.env` files
- [ ] No API keys
- [ ] No Oracle/OpenMemory credentials
- [ ] No Google/OpenAI/Anthropic/OpenRouter keys
- [ ] No private SSH keys, `.pem`, `.key`, token dumps, or cookies
- [ ] Secret scanner run before push:

```shell
scripts/scan_secrets.cmd
```

If the external scanners are not installed, install gitleaks and TruffleHog or
set `CTL_SECURITY_SCANNERS` to a folder containing:

```text
gitleaks/gitleaks.exe
trufflehog/trufflehog.exe
```

## Data Safety

- [ ] No private classroom files
- [ ] No paid PDFs
- [ ] No private chat logs
- [ ] No personal downloads
- [ ] Demo source is generated, public domain, or permissively licensed
- [ ] No absolute personal paths in README commands

## License Safety

- [ ] Apache-2.0 license present
- [ ] Third-party copied code audited
- [ ] External parser dependencies listed as optional
- [ ] Parser licenses checked before claiming compatibility
- [ ] Sample assets license-safe

## Technical Sanity

- [ ] Fresh demo command works
- [ ] Python syntax check passes:

```shell
python scripts/run_smoke_tests.py
```

- [ ] Output opens as static HTML
- [ ] Original source is preserved
- [ ] Assets are copied/extracted when possible
- [ ] `manifest.json` exists
- [ ] `manifests/provenance.json` exists
- [ ] `search.json` exists
- [ ] `assets/tables/ctl-records.json` exists
- [ ] `okf/index.md` exists

## Public Message

- [ ] README explains HTML-first vs Markdown-only
- [ ] README explains database-optional design
- [ ] README explains OKF relationship
- [ ] README explains adapter philosophy
- [ ] README says what CTL-Core is not
- [ ] `docs/why-ctl.md` explains the reason for CTL
- [ ] `docs/output-package.md` explains the package layout
- [ ] `docs/demos.md` has working demo commands
