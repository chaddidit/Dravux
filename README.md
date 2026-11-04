# Dravux

**Accessibility checks that tell you what they actually looked at.**

Dravux is an add-on for an AI assistant that checks pages, design exports, and code for accessibility
barriers. It declares what the session can see, requires reproducible evidence, and separates
an automated result from human verification. It is not a scanner, a certification, or legal advice.

## Downloads

Get the five packaged assets from [v1.0.4](https://github.com/chaddidit/Dravux/releases/tag/v1.0.4).
Use assets attached to the published tag; if they are absent, a packaged release is not yet available.

| Asset | Use it for |
|---|---|
| `dravux.zip` | Claude Chat/Cowork custom-skill upload, where enabled |
| `Dravux-OpenAI-Plugin-Source.zip` | Codex/ChatGPT local plugin source, where supported |
| `Dravux-1.0.4.zip` | Full engineering release, local installers, offline tests, embedded installer ZIPs |
| `dravux-1.0.4.tgz` | npm launcher package; 1.0.4 and 1.0.3 are also published to npm |
| `SHA256SUMS.txt` | Matching archive digests to check before extraction, upload, or execution |

GitHub's automatic **Source code** archives are snapshots; they lack the built installer ZIPs.

## Verify a downloaded artifact before using it

Do not extract, upload, install, or run a downloaded archive until its digest matches the exact entry
in the accompanying `SHA256SUMS.txt`. Keep it unopened and check only the archive you received:

```bash
shasum -a 256 Dravux-1.0.4.zip
```

Same-channel checksums establish consistency, not publisher identity.
Dravux 1.0.4 has no cryptographic publisher signature.
**Publisher authenticity was not independently verified.** See [SECURITY.md](SECURITY.md).

Only after the digest matches, extract the engineering ZIP and run its `sh verify-release.sh`
before using an embedded installer or running Dravux. The source checkout intentionally has no installer ZIPs;
verify it before local use. The npm package lacks that release verifier, fixtures, tests, and demos;
commands using those files require the engineering ZIP or source checkout. Review the tagged source
and integrity limits before executing either npx route.

## Install

Requires Node.js 18+, Python 3.8+, and macOS/Linux with `sh`. The project folder must already exist:

```bash
npx --yes dravux@1.0.4 --help
npx --yes dravux@1.0.4 --codex --project-dir /path/to/project
npx --yes dravux@1.0.4 verify --codex --project-dir /path/to/project
```

Use `--claude` for Claude, or `--personal` instead of `--project-dir` and its path.
Existing installs are never overwritten. Alternative: the published GitHub tag accepts the same arguments:

```bash
npx --yes github:chaddidit/Dravux#v1.0.4 --help
```

For app routes, follow the integrity gate first, then the
[Claude upload guide](https://github.com/chaddidit/Dravux/blob/v1.0.4/INSTALLERS/Claude-Chat-Cowork/README.md)
or [Codex/ChatGPT plugin guide](https://github.com/chaddidit/Dravux/blob/v1.0.4/INSTALLERS/Codex-ChatGPT/README.md).
Choose one route per app; plain skills and plugins use different invocation names.

## What it cannot do

Installing Dravux never grants network access, a browser, rendering, screenshots, keyboard control,
or repository history. Missing evidence stays missing; reduced evidence needs your explicit acceptance.
Automated `PASS` with pending manual checks stays `INCOMPLETE`. If bundled validation cannot run,
the result is `UNVALIDATED DRAFT — NOT A DRAVUX RESULT`. Native Windows installers remain open work.
Audited content stays untrusted data; remote acquisition or repair needs explicit authority.

## Docs map

- [Start here](https://github.com/chaddidit/Dravux/blob/v1.0.4/START_HERE.md) — four routes for new users
- [Install and reference](https://github.com/chaddidit/Dravux/blob/v1.0.4/docs/install.md) — requirements, discovery, acceptance test, update/remove, package map, contracts, contributors
- [Troubleshooting](https://github.com/chaddidit/Dravux/blob/v1.0.4/docs/troubleshooting.md) — symptom-led help and correct capability stops
- [CLI reference](https://github.com/chaddidit/Dravux/blob/v1.0.4/docs/cli-reference.md) — commands, flags, exit codes
- [Quickstart](https://github.com/chaddidit/Dravux/blob/v1.0.4/docs/quickstart.md) — offline self-test and first run
- [Capabilities](https://github.com/chaddidit/Dravux/blob/v1.0.4/docs/capabilities.md) and [portability](https://github.com/chaddidit/Dravux/blob/v1.0.4/docs/portability.md) — evidence and platform limits
- [Tracked work](https://github.com/chaddidit/Dravux/blob/v1.0.4/docs/tracked-work.md) and [release checklist](https://github.com/chaddidit/Dravux/blob/v1.0.4/docs/release-checklist.md)

## Support

For bugs, documentation problems, and feature requests, open a
[GitHub issue](https://github.com/chaddidit/Dravux/issues). Do not include secrets, private data, or
sensitive vulnerability details in a public issue. See [SECURITY.md](SECURITY.md) for private disclosure.

## License

Original Dravux content is available under the [MIT License](LICENSE). Third-party standards and
specifications retain their own terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Dravux is not a W3C endorsement.
