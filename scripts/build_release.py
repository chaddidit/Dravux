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
EXCLUDED_PARTS = {".git", "__pycache__", "__MACOSX", ".DS_Store", "out", "build", "dist"}
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def package_version():
    value = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not SEMVER.fullmatch(value):
        raise SystemExit(f"VERSION is not strict semantic versioning: {value}")
    return value


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def should_exclude(relative):
    if any(part in EXCLUDED_PARTS or part.startswith("._") for part in relative.parts):
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
        mode = stat.S_IMODE(path.stat().st_mode)
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
        "operational_contract_version": "1.0.0",
        "archive_root": f"Dravux-{version}",
        "manifest_self_excluded": True,
        "files": entries,
    }
    MANIFEST.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_zip(destination, archive_root, files, relative_to):
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        root_info = zipfile.ZipInfo(f"{archive_root}/", FIXED_TIME)
        root_info.create_system = 3
        root_info.external_attr = (stat.S_IFDIR | 0o755) << 16
        archive.writestr(root_info, b"")
        for path in files:
            relative = path.relative_to(relative_to).as_posix()
            mode = stat.S_IMODE(path.stat().st_mode)
            info = zipfile.ZipInfo(f"{archive_root}/{relative}", FIXED_TIME)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(info, path.read_bytes())


def subtree_files(root):
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and not path.is_symlink()),
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
    build_zip(engineering, archive_root, release_files(include_manifest=True), ROOT)
    skill_root = ROOT / "plugins" / "dravux" / "skills" / "dravux"
    build_zip(claude, "dravux", subtree_files(skill_root), skill_root)
    build_openai_source(openai)
    archives = (engineering, claude, openai)
    checksum_text = "".join(f"{sha256(path)}  {path.name}\n" for path in archives)
    (output / "SHA256SUMS.txt").write_text(checksum_text, encoding="utf-8")
    for path in archives:
        print(f"BUILT: {path}")
        print(f"SHA-256: {sha256(path)}")


if __name__ == "__main__":
    main()
