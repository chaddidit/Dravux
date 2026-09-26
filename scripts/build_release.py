#!/usr/bin/env python3
"""Build a deterministic Dravux ZIP, manifest, and checksum."""

import argparse
import hashlib
import json
import os
import re
import stat
import unicodedata
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = (2026, 7, 20, 0, 0, 0)
MANIFEST = ROOT / "RELEASE_MANIFEST.json"
SKILL = ROOT / "plugins" / "dravux" / "skills" / "dravux"
# Operating-system metadata that Finder/Explorer create beside real files. Release
# archives contain zero such entries, at any depth.
OS_METADATA_NAMES = {".DS_Store", ".AppleDouble", "__MACOSX", "Thumbs.db", "desktop.ini"}
EXCLUDED_PARTS = {".git", "__pycache__", "out", "build", "dist"} | OS_METADATA_NAMES
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
RUN_CONTRACT_PATTERN = re.compile(r'^RUN_CONTRACT_VERSION\s*=\s*"([^"]+)"', re.MULTILINE)
INSTALLER_PROJECTIONS = (
    ("INSTALLERS/Claude-Chat-Cowork/dravux.zip", "dravux.zip"),
    ("INSTALLERS/Codex-ChatGPT/Dravux-OpenAI-Plugin-Source.zip", "Dravux-OpenAI-Plugin-Source.zip"),
)
# Archive-only marker distinguishing a built release from a source checkout. It exists solely as
# an injected member of the engineering archive — never on disk in a source tree — so the verifier
# keys its installer-archive requirements off this file, not off which archives survive deletion.
ATTESTATION_NAME = "RELEASE_ATTESTATION.json"

# Authoritative source-tree inventory. RELEASE_MANIFEST.json is intentionally self-excluded;
# installer archives and RELEASE_ATTESTATION.json are injected build outputs.
SHIPPED_FILES = (
    ".agents/plugins/marketplace.json",
    ".claude-plugin/marketplace.json",
    ".gitattributes",
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/docs.yml",
    ".github/ISSUE_TEMPLATE/feature.yml",
    ".github/workflows/ci.yml",
    ".gitignore",
    "CHANGELOG.md",
    "INSTALLERS/Claude-Chat-Cowork/README.md",
    "INSTALLERS/Codex-ChatGPT/README.md",
    "INSTALLERS/README.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "START_HERE.md",
    "THIRD_PARTY_NOTICES.md",
    "VERSION",
    "adapters/chatgpt/README.md",
    "adapters/claude/README.md",
    "adapters/codex/README.md",
    "adapters/github-copilot/README.md",
    "adapters/github-copilot/copilot-instructions.md",
    "config/local-paths.example.json",
    "demos/github/.github/copilot-instructions.md",
    "demos/github/.github/pull_request_template.md",
    "demos/github/.github/workflows/dravux-demo.yml",
    "demos/github/README.md",
    "demos/github/broken/index.html",
    "demos/github/expected-results.md",
    "demos/github/expected/broken-report.json",
    "demos/github/expected/repaired-report.json",
    "demos/github/live/index.html",
    "demos/github/manual-verification-checklist.md",
    "demos/github/offline-fallback.md",
    "demos/github/optional-accessibility-scanner.md",
    "demos/github/repair.diff",
    "demos/github/repaired/index.html",
    "demos/github/reset-instructions.md",
    "demos/github/reset_demo.py",
    "demos/github/runbook-5-7-minutes.md",
    "demos/github/shared/synthetic-product.svg",
    "demos/live-site/README.md",
    "demos/live-site/acquisition-evidence-template.md",
    "demos/live-site/offline-fallback.md",
    "demos/live-site/runbook-3-5-minutes.md",
    "demos/shared/demo-preflight.md",
    "demos/shared/evidence-card-template.md",
    "docs/capabilities.md",
    "docs/manual-verification-checklist.md",
    "docs/portability.md",
    "docs/quickstart.md",
    "docs/release-checklist.md",
    "docs/tracked-work.md",
    "fixtures/ambiguous/advisory-only.json",
    "fixtures/ambiguous/ambiguous-evidence.json",
    "fixtures/ambiguous/missing-evidence.json",
    "fixtures/ambiguous/unsupported-input.json",
    "fixtures/failing/known-fail.json",
    "fixtures/failing/manual-fail-after-automation-pass.json",
    "fixtures/hostile/advisory-fail.invalid.json",
    "fixtures/hostile/duplicate-ids.invalid.json",
    "fixtures/hostile/duplicate-json-keys.invalid.json",
    "fixtures/hostile/duplicate-manual-checks.invalid.json",
    "fixtures/hostile/empty-manual-checks.invalid.json",
    "fixtures/hostile/error-to-verified-pass.invalid.json",
    "fixtures/hostile/invalid-audit-id.invalid.json",
    "fixtures/hostile/invalid-finding-id.invalid.json",
    "fixtures/hostile/invalid-semver.invalid.json",
    "fixtures/hostile/invalid-timestamp.invalid.json",
    "fixtures/hostile/invalid-uri.invalid.json",
    "fixtures/hostile/malformed-output.invalid.json",
    "fixtures/hostile/pass-with-pending-manual.invalid.json",
    "fixtures/hostile/prompt-injection.json",
    "fixtures/hostile/semantic-counterexamples.json",
    "fixtures/hostile/top-level-array.invalid.json",
    "fixtures/hostile/unknown-property.invalid.json",
    "fixtures/hostile/unsupported-contract-version.invalid.json",
    "fixtures/manifest.json",
    "fixtures/operational/README.md",
    "fixtures/operational/acquired-false-execution-complete.invalid.json",
    "fixtures/operational/decorative-spacer.svg",
    "fixtures/operational/execution-complete-with-error.invalid.json",
    "fixtures/operational/execution-failure-claims-pass.invalid.json",
    "fixtures/operational/genuine-not-applicable.run.json",
    "fixtures/operational/post-acquisition-interaction-failure.run.json",
    "fixtures/operational/unsupported-input.preflight.json",
    "fixtures/operational/validator-unavailable.preflight.json",
    "fixtures/passing/automation-pass-manual-incomplete.json",
    "fixtures/passing/false-positive-resistance.json",
    "fixtures/passing/known-pass.json",
    "install.sh",
    "plugins/dravux/.claude-plugin/plugin.json",
    "plugins/dravux/.codex-plugin/plugin.json",
    "plugins/dravux/LICENSE",
    "plugins/dravux/THIRD_PARTY_NOTICES.md",
    "plugins/dravux/skills/dravux/SKILL.md",
    "plugins/dravux/skills/dravux/agents/openai.yaml",
    "plugins/dravux/skills/dravux/assets/preflight-template.json",
    "plugins/dravux/skills/dravux/assets/report-template.json",
    "plugins/dravux/skills/dravux/assets/run-envelope-template.json",
    "plugins/dravux/skills/dravux/fixtures/hostile/unknown-property.invalid.json",
    "plugins/dravux/skills/dravux/fixtures/passing/known-pass.json",
    "plugins/dravux/skills/dravux/references/capability-matrix.md",
    "plugins/dravux/skills/dravux/references/execution-gates.md",
    "plugins/dravux/skills/dravux/references/github-evidence.md",
    "plugins/dravux/skills/dravux/references/input-capabilities.md",
    "plugins/dravux/skills/dravux/references/manual-checks.md",
    "plugins/dravux/skills/dravux/references/surface-modes.md",
    "plugins/dravux/skills/dravux/references/verdict-and-evidence.md",
    "plugins/dravux/skills/dravux/references/wcag-2.2-map.md",
    "plugins/dravux/skills/dravux/schemas/dravux-preflight.schema.json",
    "plugins/dravux/skills/dravux/schemas/dravux-report.schema.json",
    "plugins/dravux/skills/dravux/schemas/dravux-run.schema.json",
    "plugins/dravux/skills/dravux/schemas/finding.schema.json",
    "plugins/dravux/skills/dravux/scripts/dravux_contract.py",
    "plugins/dravux/skills/dravux/scripts/dravux_run.py",
    "schemas/dravux-preflight.schema.json",
    "schemas/dravux-report.schema.json",
    "schemas/dravux-run.schema.json",
    "schemas/finding.schema.json",
    "scripts/audit_demo_html.py",
    "scripts/build_release.py",
    "scripts/run_tests.py",
    "scripts/validate_report.py",
    "scripts/verify_distribution.py",
    "tests/test_contract.py",
    "tests/test_demos.py",
    "tests/test_distribution.py",
    "tests/test_live_site.py",
    "tests/test_operational.py",
    "tests/test_package.py",
    "tests/test_skill_portability.py",
    "verify-install.sh",
    "verify-release.sh",
)


def package_version():
    value = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not SEMVER.fullmatch(value):
        raise SystemExit(f"VERSION is not strict semantic versioning: {value}")
    return value


def run_contract_version():
    """Read the shipped operational contract version from its single source of truth."""
    text = (SKILL / "scripts" / "dravux_run.py").read_text(encoding="utf-8")
    match = RUN_CONTRACT_PATTERN.search(text)
    if match is None:
        raise SystemExit("dravux_run.py does not declare RUN_CONTRACT_VERSION")
    return match.group(1)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_mode(path):
    """Release mode independent of the builder's umask; git tracks only the executable bit."""
    return 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644


def should_exclude(relative):
    if any(part in EXCLUDED_PARTS or part.startswith("._") for part in relative.parts):
        return True
    if relative == Path(ATTESTATION_NAME):
        return True
    if any(part in {".claude", ".codex"} for part in relative.parts):
        return True
    if len(relative.parts) >= 2 and relative.parts[:2] == (".agents", "skills"):
        return True
    if relative == Path("config/local-paths.json"):
        return True
    if relative.parent == Path("config") and relative.name.endswith(".private.json"):
        return True
    if relative.name == ".env" or relative.name.startswith(".env."):
        return True
    if relative.suffix in {".pyc", ".zip", ".log"}:
        return True
    return False


def release_files(include_manifest):
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(ROOT)
        if should_exclude(relative):
            continue
        if relative == Path("RELEASE_MANIFEST.json") and not include_manifest:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def _quoted(value):
    return json.dumps(str(value))


def collision_key(value):
    """Combined key for names that collide on case-insensitive or normalization-insensitive filesystems.

    NFC first so precomposed and decomposed spellings meet, casefold so letter case meets, and NFC
    again because case folding can itself emit decomposed sequences. The archive verifier and the
    inventory checks share this one key so no layer accepts a pair another layer rejects.
    """
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", str(value)).casefold())


def inventory_collisions(paths):
    """Groups of declared or on-disk paths that would land on one file on such a filesystem."""
    grouped = {}
    for path in paths:
        logical = path[:-1] if path.endswith("/") else path
        grouped.setdefault(collision_key(logical), []).append(path)
    return [group for group in grouped.values() if len(group) > 1]


def _format_collisions(groups):
    return "; ".join(", ".join(_quoted(item) for item in group) for group in groups)


def validate_source_inventory():
    if len(SHIPPED_FILES) != len(set(SHIPPED_FILES)):
        raise SystemExit("FAIL: authoritative shipped-file inventory contains a duplicate")
    if list(SHIPPED_FILES) != sorted(SHIPPED_FILES):
        raise SystemExit("FAIL: authoritative shipped-file inventory is not sorted")
    colliding = inventory_collisions(SHIPPED_FILES)
    if colliding:
        raise SystemExit(
            "FAIL: authoritative shipped-file inventory has case- or normalization-colliding paths: "
            + _format_collisions(colliding)
        )
    actual_paths = release_files(include_manifest=False)
    actual = {path.relative_to(ROOT).as_posix() for path in actual_paths}
    colliding = inventory_collisions(sorted(actual))
    if colliding:
        raise SystemExit(
            "FAIL: source tree has case- or normalization-colliding paths: " + _format_collisions(colliding)
        )
    declared = set(SHIPPED_FILES)
    missing = sorted(declared - actual)
    unexpected = sorted(actual - declared)
    details = []
    if missing:
        details.append("missing: " + ", ".join(_quoted(item) for item in missing))
    if unexpected:
        details.append("unexpected: " + ", ".join(_quoted(item) for item in unexpected))
    if details:
        raise SystemExit("FAIL: source tree differs from authoritative shipped-file inventory; " + "; ".join(details))
    return actual_paths


def write_manifest(version, files=None):
    entries = []
    for path in files if files is not None else release_files(include_manifest=False):
        mode = canonical_mode(path)
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "size": path.stat().st_size,
                "mode": format(mode, "04o"),
            }
        )
    payload = {
        "package": "dravux",
        "package_version": version,
        "report_contract_version": "0.2.0",
        "preflight_contract_version": "1.0.0",
        "operational_contract_version": run_contract_version(),
        "archive_root": f"Dravux-{version}",
        "manifest_self_excluded": True,
        "files": entries,
    }
    MANIFEST.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_member(archive, archive_root, relative, payload, mode):
    info = zipfile.ZipInfo(f"{archive_root}/{relative}", FIXED_TIME)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | mode) << 16
    archive.writestr(info, payload)


def build_zip(destination, archive_root, files, relative_to, injected=()):
    """Write a deterministic archive; `injected` adds built artifacts that are not tree files."""
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        root_info = zipfile.ZipInfo(f"{archive_root}/", FIXED_TIME)
        root_info.create_system = 3
        root_info.external_attr = (stat.S_IFDIR | 0o755) << 16
        archive.writestr(root_info, b"")
        for path in files:
            relative = path.relative_to(relative_to).as_posix()
            write_member(archive, archive_root, relative, path.read_bytes(), canonical_mode(path))
        for relative, payload in injected:
            write_member(archive, archive_root, relative, payload, 0o644)


def subtree_files(root):
    """Files of one subtree, under the same exclusion policy as the engineering archive."""
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and not path.is_symlink() and not should_exclude(path.relative_to(ROOT))
        ),
        key=lambda item: item.relative_to(root).as_posix(),
    )


def build_openai_source(destination):
    selected = [ROOT / ".agents" / "plugins" / "marketplace.json"]
    selected.extend(subtree_files(ROOT / "plugins" / "dravux"))
    build_zip(destination, "Dravux-OpenAI-Plugin-Source", selected, ROOT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    source_files = validate_source_inventory()
    version = package_version()
    output.mkdir(parents=True, exist_ok=True)
    archive_root = f"Dravux-{version}"
    write_manifest(version, source_files)
    engineering = output / f"{archive_root}.zip"
    claude = output / "dravux.zip"
    openai = output / "Dravux-OpenAI-Plugin-Source.zip"
    build_zip(claude, "dravux", subtree_files(SKILL), SKILL)
    build_openai_source(openai)
    # The engineering archive carries byte-identical copies of the two installer
    # archives so a tester never has to rebuild anything to install Dravux.
    installer_payloads = tuple((member, (output / name).read_bytes()) for member, name in INSTALLER_PROJECTIONS)
    attestation = {
        "package": "dravux",
        "package_version": version,
        "archive_root": archive_root,
        "installer_archives": [
            {
                "path": member,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
            for member, payload in installer_payloads
        ],
    }
    attestation_payload = (json.dumps(attestation, indent=2, sort_keys=True) + "\n").encode("utf-8")
    injected = installer_payloads + ((ATTESTATION_NAME, attestation_payload),)
    build_zip(engineering, archive_root, release_files(include_manifest=True), ROOT, injected=injected)
    archives = (engineering, claude, openai)
    lines = [f"{sha256(path)}  {path.name}" for path in archives]
    lines.extend(
        f"{hashlib.sha256(payload).hexdigest()}  {archive_root}/{member}" for member, payload in injected
    )
    (output / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for path in archives:
        print(f"BUILT: {path}")
        print(f"SHA-256: {sha256(path)}")
    for member, payload in installer_payloads:
        print(f"PROJECTED: {archive_root}/{member}")
        print(f"SHA-256: {hashlib.sha256(payload).hexdigest()}")
    print(f"RECORDED: {archive_root}/{ATTESTATION_NAME}")


if __name__ == "__main__":
    main()
