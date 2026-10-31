# Release Checklist

- [x] Full offline test suite passes twice
- [ ] Skill creator validation passes — blocked locally because the provided validator's Python environment lacks PyYAML; no install was authorized
- [x] All schemas and JSON files parse
- [x] Fixture manifest covers every required case, including manual normative failure after automated `PASS`
- [x] GitHub demo reproduces FAIL -> repair -> PASS with final `INCOMPLETE`
- [x] Supported inputs are limited to portable standard artifact types; no product-specific design-tool support is claimed
- [x] Public package contains no private path, secret, local config, or nested Git repository
- [x] No support is claimed for proprietary native design files
- [x] No automated result is represented as complete accessibility
- [x] Website evidence-mode downgrades require explicit user acknowledgement before acquisition
- [x] A bare report cannot satisfy the operational run contract
- [x] Ordinary Chat attachments are not described as native installation
- [x] Claude custom-skill ZIP and OpenAI plugin-source distribution are documented separately
- [x] Third-party notices match the package references; final originality/similarity review remains an owner release check
- [x] MIT License and copyright holder match `LICENSE`
- [x] Release archives contain zero operating-system metadata at any depth (`.DS_Store`, `._*`, `__MACOSX`, `Thumbs.db`, `desktop.ini`)
- [x] Loose operating-system metadata in an extracted tree produces an explicit warning and still verifies; the same entry inside an archive is a hard failure
- [x] `INSTALLERS/` is present at the archive root, is reachable in at most two steps, and its injected archives are byte-identical to the standalone `dravux.zip` and `Dravux-OpenAI-Plugin-Source.zip`
- [x] `SHA256SUMS.txt` lists the standalone archives and the injected copies, and the paired hashes match
- [x] `START_HERE.md` is present at the top level and names all four routes before any architecture
- [ ] Manual accessibility review of docs/demo assets is complete
- [ ] Publication target and external actions are separately approved

## Quick self-test (about 10 seconds)

From the extracted release root, run:

```bash
sh verify-release.sh
```

Fully offline; no credentials, network access, or package installs are required. Exit code `0` is success, and the expected final line is:

```
VERIFIED: Dravux 1.0.2 release tree passed all offline checks
```

## Truthful release claims

State only what the package actually enforces.

- Contract string fields reject control characters and Unicode line/paragraph separators, so free text cannot forge lines in the run receipt.
- Universal string-length bounds are NOT a shipped guarantee. No `maxLength` is enforced anywhere in the published schemas or validators; bounding string length remains future hardening and must not be described as a current control.
- Reconcile the release inventory against `git status` before committing. The release manifest is built from the working tree, so intentional untracked shipped files must be included in the commit or the pushed tree will not match the manifest.
