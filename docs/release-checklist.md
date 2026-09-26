# Release Checklist

Every box is a release-time gate. Do not inherit a check mark from an earlier source tree or from the
builder's own review; record fresh evidence after the final edit and require independent verification.

## Artifact order and authenticity

Canonical policy: [SECURITY.md](../SECURITY.md). Release gates below must stay consistent with it.

- [ ] Before extracting, uploading, installing, or running any downloaded archive, calculate its SHA-256 digest and compare it with the exact matching entry in the accompanying `SHA256SUMS.txt`; stop on mismatch
- [ ] Confirm the same-channel checksum, embedded manifest, and internal release record are described only as corruption/internal-consistency checks, never publisher authentication
- [ ] Record that Dravux 1.0.2 has no cryptographic publisher signature
- [ ] Record this disclosure for every route without an independently trusted digest, signature, or provenance: Publisher authenticity was not independently verified.
- [ ] Only after the outer archive digest matches, extract it and run `sh verify-release.sh` before any embedded installer is uploaded, installed, or run
- [ ] Confirm the source checkout contains guides but no installer ZIPs; only a built engineering release injects them

## Package gates

- [ ] Final full offline test and distribution gates pass after the last source edit; an independent verifier records certification
- [ ] Skill creator validation passes, or the missing sanctioned dependency is recorded without installing it
- [ ] All schemas and JSON files parse
- [ ] Fixture manifest covers every required case, including manual normative failure after automated `PASS`
- [ ] GitHub demo reproduces FAIL -> repair -> PASS with final `INCOMPLETE`
- [ ] Supported inputs are limited to portable standard artifact types; no product-specific design-tool support is claimed
- [ ] Public package contains no private path, secret, local config, or nested Git repository
- [ ] No support is claimed for proprietary native design files
- [ ] No automated result is represented as complete accessibility
- [ ] Website evidence-mode downgrades require explicit user acknowledgement before acquisition
- [ ] A bare report cannot satisfy the operational run contract
- [ ] Ordinary Chat attachments are not described as native installation
- [ ] Claude custom-skill ZIP and OpenAI plugin-source distribution are documented separately
- [ ] Third-party notices match the package references; final originality/similarity review remains an owner release check
- [ ] MIT License and copyright holder match `LICENSE`
- [ ] Release archives contain zero operating-system metadata at any depth (`.DS_Store`, `._*`, `__MACOSX`, `Thumbs.db`, `desktop.ini`)
- [ ] Loose operating-system metadata in an extracted tree produces an explicit warning and still verifies; the same entry inside an archive is a hard failure
- [ ] `INSTALLERS/` is present at the built archive root, is reachable in at most two steps, and its injected archives are byte-identical to the standalone `dravux.zip` and `Dravux-OpenAI-Plugin-Source.zip`
- [ ] `SHA256SUMS.txt` lists the standalone archives and the injected copies, and the paired hashes match
- [ ] `START_HERE.md` is present at the top level and names all four routes before any architecture
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

- Contract string fields reject control characters and Unicode line/paragraph separators, so free text cannot forge lines in the run receipt. Directional-override and other invisible formatting codepoints (for example U+202E) are NOT rejected, so a free-text value can still be visually reordered within its own line by a bidi-aware terminal; some C1 controls are also outside the rejected set. The `--json` output is the authoritative form, and validator diagnostics render untrusted text as escaped ASCII literals. See [SECURITY.md](../SECURITY.md).
- Bounded JSON ingress is a shipped operational control: input is capped at 4 MiB, each decoded string and object key at 262,144 characters, and numeric tokens at 128 characters, with additional depth, item, and structural-token limits. The schemas do not publish `maxLength`, so schema inspection alone does not describe these loader limits.
- Reconcile the release inventory against `git status` before committing. The release manifest is built from the working tree, so intentional untracked shipped files must be included in the commit or the pushed tree will not match the manifest.
