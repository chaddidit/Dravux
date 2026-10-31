#!/usr/bin/env python3
"""Build a deterministic Dravux ZIP, manifest, and checksum."""

import argparse
import hashlib
import json
import os
import re
import stat
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


def write_manifest(version):
    entries = []
    for path in release_files(include_manifest=False):
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
        "report_contract_version": "0.1.0",
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
    output.mkdir(parents=True, exist_ok=True)
    version = package_version()
    archive_root = f"Dravux-{version}"
    write_manifest(version)
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
    print(f"ATTESTED: {archive_root}/{ATTESTATION_NAME}")


if __name__ == "__main__":
    main()
