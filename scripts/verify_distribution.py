#!/usr/bin/env python3
"""Deterministic offline checks for the unpacked Dravux release tree."""

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "dravux" / "skills" / "dravux"
PLUGIN = ROOT / "plugins" / "dravux"
MANIFEST = ROOT / "RELEASE_MANIFEST.json"
IGNORED_PARTS = {"__pycache__", "out", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
PACKAGE_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_files():
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.is_symlink() or path == MANIFEST:
            continue
        relative = path.relative_to(ROOT)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix == ".pyc" or path.name in {".DS_Store"} or path.name.startswith("._"):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def verify_manifest():
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(payload["package"] == "dravux", "release manifest package mismatch")
    require(payload["package_version"] == PACKAGE_VERSION, "release manifest package version mismatch")
    require(payload["report_contract_version"] == "0.1.0", "release manifest contract version mismatch")
    require(payload["preflight_contract_version"] == "1.0.0", "release manifest preflight version mismatch")
    require(payload["operational_contract_version"] == "1.0.0", "release manifest operational version mismatch")
    require(payload["archive_root"] == f"Dravux-{PACKAGE_VERSION}", "release manifest archive root mismatch")
    listed = {item["path"]: item for item in payload["files"]}
    actual = {path.relative_to(ROOT).as_posix(): path for path in manifest_files()}
    require(set(listed) == set(actual), "release manifest path set differs from the release tree")
    for relative, path in actual.items():
        item = listed[relative]
        require(item["sha256"] == digest(path), f"release manifest hash mismatch: {relative}")
        require(item["size"] == path.stat().st_size, f"release manifest size mismatch: {relative}")
        require(item["mode"] == format(stat.S_IMODE(path.stat().st_mode), "04o"), f"release manifest mode mismatch: {relative}")


def main():
    require(SEMVER.fullmatch(PACKAGE_VERSION) is not None, "VERSION is not strict semantic versioning")
    require(PACKAGE_VERSION == "1.0.1", "VERSION is not 1.0.1")
    skills = list(ROOT.rglob("SKILL.md"))
    require(skills == [SKILL / "SKILL.md"], "release must contain exactly one canonical SKILL.md")

    forbidden_names = {".git", "__MACOSX", ".DS_Store", ".AppleDouble", "preflight"}
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        require(not any(part in forbidden_names for part in relative.parts), f"excluded path present: {relative}")
        require(not path.is_symlink(), f"symlink present: {relative}")
        mode = path.lstat().st_mode
        require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), f"special file present: {relative}")
        require(not path.name.startswith("._"), f"AppleDouble file present: {relative}")

    for path in ROOT.rglob("*.json"):
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
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".zip"}:
            continue
        relative = path.relative_to(ROOT)
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
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".zip"}:
            continue
        require(forbidden_version not in path.read_text(encoding="utf-8", errors="ignore"), f"literal forbidden version present: {path.relative_to(ROOT)}")

    print("PASS: release structure, file manifest, plugin manifests, schemas, privacy, and installer policy")


if __name__ == "__main__":
    main()
