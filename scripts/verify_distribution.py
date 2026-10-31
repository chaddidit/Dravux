#!/usr/bin/env python3
"""Deterministic offline checks for the unpacked Dravux release tree."""

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GIT_DIR = ROOT / ".git"
SKILL = ROOT / "plugins" / "dravux" / "skills" / "dravux"
PLUGIN = ROOT / "plugins" / "dravux"
MANIFEST = ROOT / "RELEASE_MANIFEST.json"
IGNORED_PARTS = {"__pycache__", "out", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
# Files that macOS Finder and Windows Explorer create beside real files. They are
# never part of a Dravux release: excluded from every archive, warned about in an
# extracted tree, and treated as tampering when found inside an archive.
OS_METADATA_NAMES = {".DS_Store", ".AppleDouble", "__MACOSX", "Thumbs.db", "desktop.ini"}
OS_METADATA_NOTE = "created by macOS Finder/Windows Explorer; not part of the release; safe to delete"
# Ready-made installer archives injected into the engineering archive at build time. They are build
# products, not manifest sources, so they are expected in an extracted release and nowhere else.
PROJECTED_ARCHIVES = {
    "INSTALLERS/Claude-Chat-Cowork/dravux.zip": "dravux/",
    "INSTALLERS/Codex-ChatGPT/Dravux-OpenAI-Plugin-Source.zip": "Dravux-OpenAI-Plugin-Source/",
}
# Archive-only marker injected by build_release.py into the engineering archive. A source checkout
# never contains it, so it — not the survival of any user-deletable archive — decides whether this
# tree must carry the projected installer archives.
ATTESTATION = ROOT / "RELEASE_ATTESTATION.json"
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
RUN_CONTRACT_PATTERN = re.compile(r'^RUN_CONTRACT_VERSION\s*=\s*"([^"]+)"', re.MULTILINE)
PACKAGE_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def is_os_metadata(relative):
    """True when any path segment is an operating-system metadata entry."""
    return any(part in OS_METADATA_NAMES or part.startswith("._") for part in Path(relative).parts)


def run_contract_version():
    """Read the shipped operational contract version from its single source of truth."""
    match = RUN_CONTRACT_PATTERN.search((SKILL / "scripts" / "dravux_run.py").read_text(encoding="utf-8"))
    require(match is not None, "dravux_run.py does not declare RUN_CONTRACT_VERSION")
    return match.group(1)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_mode(path):
    """Release mode independent of the checking-out umask; git tracks only the executable bit."""
    return 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644


def release_paths():
    """Every path in the tree except the single root-level .git of an ordinary developer checkout."""
    for path in ROOT.rglob("*"):
        if path == GIT_DIR or GIT_DIR in path.parents:
            continue
        if path.relative_to(ROOT).parts[0] == "dist-release" and GIT_DIR.exists():
            continue
        yield path


def os_metadata_in_tree():
    """Every operating-system metadata entry sitting in the extracted tree."""
    found = []
    for path in release_paths():
        relative = path.relative_to(ROOT)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if is_os_metadata(relative):
            found.append(relative.as_posix())
    return sorted(set(found))


def manifest_files():
    files = []
    for path in release_paths():
        if not path.is_file() or path.is_symlink() or path in (MANIFEST, ATTESTATION):
            continue
        relative = path.relative_to(ROOT)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix == ".pyc" or is_os_metadata(relative):
            continue
        if relative.as_posix() in PROJECTED_ARCHIVES:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def verify_manifest():
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(payload["package"] == "dravux", "release manifest package mismatch")
    require(payload["package_version"] == PACKAGE_VERSION, "release manifest package version mismatch")
    require(payload["report_contract_version"] == "0.1.0", "release manifest contract version mismatch")
    require(payload["preflight_contract_version"] == "1.0.0", "release manifest preflight version mismatch")
    require(
        payload["operational_contract_version"] == run_contract_version(),
        "release manifest operational version mismatch",
    )
    require(payload["archive_root"] == f"Dravux-{PACKAGE_VERSION}", "release manifest archive root mismatch")
    listed = {item["path"]: item for item in payload["files"]}
    actual = {path.relative_to(ROOT).as_posix(): path for path in manifest_files()}
    unexpected = sorted(set(actual) - set(listed))
    missing = sorted(set(listed) - set(actual))
    detail = ""
    if unexpected:
        detail += f"; unexpected: {', '.join(unexpected)}"
    if missing:
        detail += f"; missing: {', '.join(missing)}"
    require(set(listed) == set(actual), f"release manifest path set differs from the release tree{detail}")
    for relative, path in actual.items():
        item = listed[relative]
        require(item["sha256"] == digest(path), f"release manifest hash mismatch: {relative}")
        require(item["size"] == path.stat().st_size, f"release manifest size mismatch: {relative}")
        require(item["mode"] == format(canonical_mode(path), "04o"), f"release manifest mode mismatch: {relative}")


def verify_archive(path, expected_root=None):
    """An archive is release output: any OS-metadata entry inside it is a tampering signal."""
    require(path.is_file(), f"archive not found: {path}")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    if expected_root is not None:
        stray = sorted(name for name in names if not name.startswith(expected_root))
        require(not stray, f"archive {path.name} is not rooted at {expected_root}: {', '.join(stray[:5])}")
    polluted = sorted(name for name in names if is_os_metadata(name))
    require(
        not polluted,
        f"operating-system metadata inside archive {path.name}: {', '.join(polluted)}"
        " (release archives must contain none; this archive is not the archive that was built)",
    )
    unsafe = sorted(name for name in names if name.startswith("/") or ".." in Path(name).parts)
    require(not unsafe, f"unsafe archive member path in {path.name}: {', '.join(unsafe)}")
    print(f"PASS: archive {path.name} contains no operating-system metadata and no unsafe member path")


def rebuild_projected_archives(destination):
    """Rebuild the installer archives from this tree's own sources, deterministically."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_release

    require(build_release.ROOT == ROOT, "builder and verifier disagree about the release root")
    claude = destination / "dravux.zip"
    openai = destination / "Dravux-OpenAI-Plugin-Source.zip"
    build_release.build_zip(
        claude, "dravux", build_release.subtree_files(build_release.SKILL), build_release.SKILL
    )
    build_release.build_openai_source(openai)
    return {
        "INSTALLERS/Claude-Chat-Cowork/dravux.zip": claude,
        "INSTALLERS/Codex-ChatGPT/Dravux-OpenAI-Plugin-Source.zip": openai,
    }


def verify_projected_archives():
    """The file a newcomer uploads must be the one this package's own files produce.

    The installer archives are build products, so no manifest entry covers them. Without this check
    a swapped archive with the right root shape would install cleanly and verify cleanly. Whether
    this tree is a built release is decided by the archive-only attestation, never by which
    archives happen to survive in the tree: in an attested release a missing installer archive is
    a hard failure, not a skip.
    """
    shipped = {relative: ROOT / relative for relative in PROJECTED_ARCHIVES if (ROOT / relative).is_file()}
    if not ATTESTATION.is_file():
        require(
            not shipped,
            "installer archive(s) present but RELEASE_ATTESTATION.json is missing; this package is"
            " inconsistent; re-download the release: " + ", ".join(sorted(shipped)),
        )
        return  # a source checkout ships neither the attestation nor built archives
    attested = json.loads(ATTESTATION.read_text(encoding="utf-8"))
    require(attested.get("package") == "dravux", "release attestation package mismatch")
    require(attested.get("package_version") == PACKAGE_VERSION, "release attestation package version mismatch")
    require(
        attested.get("archive_root") == f"Dravux-{PACKAGE_VERSION}",
        "release attestation archive root mismatch",
    )
    entries = attested.get("installer_archives")
    require(isinstance(entries, list) and entries, "release attestation lists no installer archives")
    listed = {}
    for item in entries:
        require(
            isinstance(item, dict) and isinstance(item.get("path"), str),
            "release attestation entry is malformed",
        )
        listed[item["path"]] = item
    require(
        set(listed) == set(PROJECTED_ARCHIVES),
        "release attestation does not list exactly the expected installer archives",
    )
    missing = sorted(set(listed) - set(shipped))
    require(
        not missing,
        "this package is missing its installer archive(s): " + ", ".join(missing)
        + "; the release is incomplete; re-download it",
    )
    with tempfile.TemporaryDirectory() as tmp:
        rebuilt = rebuild_projected_archives(Path(tmp))
        for relative, path in sorted(shipped.items()):
            actual = digest(path)
            require(
                actual == digest(rebuilt[relative]),
                f"{relative} does not match the files in this package; do not upload it;"
                " re-download the release",
            )
            item = listed[relative]
            require(
                item.get("sha256") == actual and item.get("size") == path.stat().st_size,
                f"{relative} does not match the release attestation; do not upload it;"
                " re-download the release",
            )
    print(f"PASS: {len(shipped)} shipped installer archive(s) match this package's own files")


def report_os_metadata(found):
    """Loose Finder/Explorer files are noise, not tampering: say so plainly and continue."""
    if not found:
        return
    print("WARNING: operating-system metadata found in this folder")
    for relative in found:
        print(f"  {relative}")
    print(f"  These files are {OS_METADATA_NOTE}.")
    print("  They are excluded from every Dravux archive and from the release manifest.")


def main():
    archives = [Path(value) for value in sys.argv[1:] if not value.startswith("-")]
    if archives:
        for path in archives:
            verify_archive(path)
        return

    require(SEMVER.fullmatch(PACKAGE_VERSION) is not None, "VERSION is not strict semantic versioning")
    skills = [path for path in release_paths() if path.name == "SKILL.md"]
    require(skills == [SKILL / "SKILL.md"], "release must contain exactly one canonical SKILL.md")

    loose_os_metadata = os_metadata_in_tree()
    forbidden_names = {".git", "preflight"}
    for path in release_paths():
        relative = path.relative_to(ROOT)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if is_os_metadata(relative):
            continue
        require(not any(part in forbidden_names for part in relative.parts), f"excluded path present: {relative}")
        require(not path.is_symlink(), f"symlink present: {relative}")
        mode = path.lstat().st_mode
        require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), f"special file present: {relative}")

    for path in release_paths():
        if path.suffix == ".json" and path.is_file() and not is_os_metadata(path.relative_to(ROOT)):
            json.loads(path.read_text(encoding="utf-8"))

    for name in ("dravux-report.schema.json", "finding.schema.json", "dravux-preflight.schema.json", "dravux-run.schema.json"):
        require(digest(ROOT / "schemas" / name) == digest(SKILL / "schemas" / name), f"schemas drifted: {name}")

    codex = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    claude = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    require(codex["name"] == claude["name"] == "dravux", "plugin names disagree")
    require(codex["version"] == claude["version"] == PACKAGE_VERSION, "plugin versions disagree")
    require(codex["license"] == claude["license"] == "MIT", "plugin licenses disagree")
    require(codex["skills"] == "./skills/", "Codex skill path is not plugin-relative")

    codex_market = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    claude_market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    require(codex_market["name"] == claude_market["name"] == "dravux", "marketplace names disagree")
    require(codex_market["plugins"][0]["name"] == "dravux", "Codex marketplace plugin mismatch")
    require(codex_market["plugins"][0]["source"]["path"] == "./plugins/dravux", "Codex source path mismatch")
    require(claude_market["plugins"][0]["source"] == "./plugins/dravux", "Claude source path mismatch")
    require(claude_market["plugins"][0]["version"] == PACKAGE_VERSION, "Claude marketplace version mismatch")

    require((PLUGIN / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes(), "plugin LICENSE drifted")
    require(
        (PLUGIN / "THIRD_PARTY_NOTICES.md").read_bytes() == (ROOT / "THIRD_PARTY_NOTICES.md").read_bytes(),
        "plugin third-party notices drifted",
    )

    verify_manifest()

    secret_patterns = (
        re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    )
    local_home = "/" + "Users" + "/"
    copyright_line = next(
        line for line in (ROOT / "LICENSE").read_text(encoding="utf-8").splitlines() if line.startswith("Copyright (c) ")
    )
    copyright_holder = re.sub(r"^Copyright \(c\) [0-9]{4} ", "", copyright_line)
    require(bool(copyright_holder), "MIT license copyright holder is missing")
    allowed_name_files = {Path("LICENSE"), Path("plugins/dravux/LICENSE")}
    for path in release_paths():
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".zip"}:
            continue
        relative = path.relative_to(ROOT)
        if is_os_metadata(relative):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        require(local_home not in text, f"absolute local home path present: {relative}")
        if copyright_holder in text:
            require(relative in allowed_name_files, f"personal name outside MIT license: {relative}")
        for pattern in secret_patterns:
            require(pattern.search(text) is None, f"secret-like value present: {relative}")

    install_text = (ROOT / "install.sh").read_text(encoding="utf-8")
    for token in ("curl ", "wget ", "brew ", "pip ", "npm ", "npx ", "sudo ", "eval ", "source "):
        require(token not in install_text, f"installer contains forbidden operation: {token.strip()}")

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    report_check = subprocess.run(
        [sys.executable, "-B", str(SKILL / "scripts" / "dravux_contract.py"), str(SKILL / "assets" / "report-template.json")],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    run_check = subprocess.run(
        [sys.executable, "-B", str(SKILL / "scripts" / "dravux_run.py"), "validate", str(SKILL / "assets" / "run-envelope-template.json")],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    require(report_check.returncode == 0, "bundled report validator self-test failed")
    require(run_check.returncode == 0, "bundled operational validator self-test failed")

    forbidden_version = "1" + "." + "01"
    for path in release_paths():
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".zip"}:
            continue
        if is_os_metadata(path.relative_to(ROOT)):
            continue
        require(forbidden_version not in path.read_text(encoding="utf-8", errors="ignore"), f"literal forbidden version present: {path.relative_to(ROOT)}")

    for name in ("README.md", "INSTALLERS/README.md", "INSTALLERS/Claude-Chat-Cowork/README.md", "INSTALLERS/Codex-ChatGPT/README.md"):
        require((ROOT / name).is_file(), f"required human-facing document missing: {name}")
    require((ROOT / "START_HERE.md").is_file(), "required human-facing document missing: START_HERE.md")

    for relative, expected_root in PROJECTED_ARCHIVES.items():
        candidate = ROOT / relative
        if candidate.is_file():
            verify_archive(candidate, expected_root=expected_root)
    stray_archives = sorted(
        path.relative_to(ROOT).as_posix()
        for path in release_paths()
        if path.is_file() and path.suffix == ".zip" and path.relative_to(ROOT).as_posix() not in PROJECTED_ARCHIVES
    )
    require(not stray_archives, f"unexpected archive in the release tree: {', '.join(stray_archives)}")
    verify_projected_archives()

    report_os_metadata(loose_os_metadata)
    print("PASS: release structure, file manifest, plugin manifests, schemas, privacy, and installer policy")


if __name__ == "__main__":
    main()
