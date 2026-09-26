#!/usr/bin/env python3
"""Deterministic offline checks for the unpacked Dravux release tree."""

import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from collections import Counter
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
EXPECTED_STRICT_JSON_REJECTIONS = {
    "fixtures/hostile/duplicate-json-keys.invalid.json": "duplicate JSON key",
}
BUILDER_PATH = ROOT / "scripts" / "build_release.py"
if not BUILDER_PATH.is_file():
    raise SystemExit("FAIL: required release file(s) missing: scripts/build_release.py")
sys.dont_write_bytecode = True
try:
    _builder_spec = importlib.util.spec_from_file_location("dravux_release_builder", str(BUILDER_PATH))
    if _builder_spec is None or _builder_spec.loader is None:
        raise ImportError("no import loader was available")
    BUILD_RELEASE = importlib.util.module_from_spec(_builder_spec)
    _builder_spec.loader.exec_module(BUILD_RELEASE)
    SHIPPED_FILES = BUILD_RELEASE.SHIPPED_FILES
    if (
        not isinstance(SHIPPED_FILES, tuple)
        or not all(isinstance(item, str) for item in SHIPPED_FILES)
        or len(SHIPPED_FILES) != len(set(SHIPPED_FILES))
        or list(SHIPPED_FILES) != sorted(SHIPPED_FILES)
    ):
        raise ValueError("SHIPPED_FILES must be a sorted unique tuple of strings")
except Exception as exc:
    raise SystemExit(
        "FAIL: could not load scripts/build_release.py: " + json.dumps(str(exc))
    )
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 512
MAX_ARCHIVE_MEMBER_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_EXPANSION_RATIO = 100
ALLOWED_ARCHIVE_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
RUN_CONTRACT_PATTERN = re.compile(r'^RUN_CONTRACT_VERSION\s*=\s*"([^"]+)"', re.MULTILINE)
try:
    PACKAGE_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
except OSError as exc:
    raise SystemExit(f"FAIL: required release file missing or unreadable: VERSION ({exc.strerror})")


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


_CONTRACT_MODULE = None


def load_release_json(path, label=None):
    """Use the bundled bounded strict loader for every release-control JSON file."""
    global _CONTRACT_MODULE
    contract_path = SKILL / "scripts" / "dravux_contract.py"
    if _CONTRACT_MODULE is None:
        require(contract_path.is_file(), "required release file(s) missing: plugins/dravux/skills/dravux/scripts/dravux_contract.py")
        try:
            spec = importlib.util.spec_from_file_location("dravux_bounded_contract", str(contract_path))
            if spec is None or spec.loader is None:
                raise ImportError("no import loader was available")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _CONTRACT_MODULE = module
        except Exception as exc:
            raise SystemExit(
                "FAIL: could not load bundled JSON validator: " + json.dumps(str(exc))
            )
    display = label
    if display is None:
        try:
            display = _quoted(path.relative_to(ROOT).as_posix())
        except ValueError:
            display = _quoted(path.name)
    try:
        return _CONTRACT_MODULE.load_json_path(path)
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise SystemExit(f"FAIL: invalid JSON in {display}: {_quoted(exc)}")


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


def verify_required_files():
    """Every declared release file must exist before anything reads it.

    Absence is reported as a plain FAIL naming the file, never as a traceback from
    whichever later check happened to open it first.
    """
    require(len(set(SHIPPED_FILES)) == len(SHIPPED_FILES), "declared shipped-file list contains a duplicate")
    colliding = BUILD_RELEASE.inventory_collisions(SHIPPED_FILES)
    require(
        not colliding,
        "declared shipped-file list has case- or normalization-colliding paths: "
        + "; ".join(", ".join(_quoted(item) for item in group) for group in colliding),
    )
    missing = sorted(relative for relative in SHIPPED_FILES if not (ROOT / relative).is_file())
    require(not missing, "required release file(s) missing: " + ", ".join(_quoted(path) for path in missing))
    require(MANIFEST.is_file(), "required release file missing: RELEASE_MANIFEST.json")


def verify_inventory():
    """The tree must ship exactly the declared files, no more and no fewer.

    RELEASE_MANIFEST.json is regenerated from the tree at build time, so a file deleted or added
    before the build passes the manifest check; only the declared list can catch that.
    """
    actual = {path.relative_to(ROOT).as_posix() for path in manifest_files()}
    colliding = BUILD_RELEASE.inventory_collisions(sorted(actual))
    require(
        not colliding,
        "release tree has case- or normalization-colliding paths: "
        + "; ".join(", ".join(_quoted(item) for item in group) for group in colliding),
    )
    declared = set(SHIPPED_FILES)
    detail = ""
    missing = sorted(declared - actual)
    unexpected = sorted(actual - declared)
    if missing:
        detail += "; missing: " + ", ".join(_quoted(path) for path in missing)
    if unexpected:
        detail += "; unexpected: " + ", ".join(_quoted(path) for path in unexpected)
    require(actual == declared, f"release inventory differs from the declared shipped-file list{detail}")


def verify_manifest():
    payload = load_release_json(MANIFEST, "RELEASE_MANIFEST.json")
    require(isinstance(payload, dict), "release manifest must be a JSON object")
    require(payload.get("package") == "dravux", "release manifest package mismatch")
    require(payload.get("package_version") == PACKAGE_VERSION, "release manifest package version mismatch")
    require(payload.get("report_contract_version") == "0.2.0", "release manifest contract version mismatch")
    require(payload.get("preflight_contract_version") == "1.0.0", "release manifest preflight version mismatch")
    require(
        payload.get("operational_contract_version") == run_contract_version(),
        "release manifest operational version mismatch",
    )
    require(payload.get("archive_root") == f"Dravux-{PACKAGE_VERSION}", "release manifest archive root mismatch")
    files = payload.get("files")
    require(isinstance(files, list), "release manifest files must be an array")
    paths = []
    for index, item in enumerate(files):
        require(isinstance(item, dict), f"release manifest files[{index}] must be an object")
        require(isinstance(item.get("path"), str), f"release manifest files[{index}].path must be a string")
        paths.append(item["path"])
    duplicate_paths = sorted(path for path, count in Counter(paths).items() if count > 1)
    require(
        not duplicate_paths,
        "release manifest contains duplicate file path(s): "
        + ", ".join(_quoted(path) for path in duplicate_paths),
    )
    listed = {item["path"]: item for item in files}
    actual = {path.relative_to(ROOT).as_posix(): path for path in manifest_files()}
    unexpected = sorted(set(actual) - set(listed))
    missing = sorted(set(listed) - set(actual))
    detail = ""
    if unexpected:
        detail += "; unexpected: " + ", ".join(_quoted(path) for path in unexpected)
    if missing:
        detail += "; missing: " + ", ".join(_quoted(path) for path in missing)
    require(set(listed) == set(actual), f"release manifest path set differs from the release tree{detail}")
    for relative, path in actual.items():
        item = listed[relative]
        require(item.get("sha256") == digest(path), f"release manifest hash mismatch: {_quoted(relative)}")
        require(item.get("size") == path.stat().st_size, f"release manifest size mismatch: {_quoted(relative)}")
        require(item.get("mode") == format(canonical_mode(path), "04o"), f"release manifest mode mismatch: {_quoted(relative)}")


def _is_irregular_member(item):
    """True for a member whose recorded Unix file type is neither a regular file nor a directory.

    A symlink member lets an extracted tree point outside itself; no Dravux archive contains one.
    Members with no recorded type bits (Windows-created, or Python's default 0o600) are ordinary files.
    """
    if item.create_system != 3:
        return False
    kind = stat.S_IFMT(item.external_attr >> 16)
    return kind not in (0, stat.S_IFREG, stat.S_IFDIR)


def _has_unsafe_mode(item):
    """True for a Unix-created member that would extract setuid, setgid, sticky, or group/world-writable."""
    if item.create_system != 3:
        return False
    return bool(stat.S_IMODE(item.external_attr >> 16) & 0o7022)


WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def _quoted(value):
    """Render an attacker-controlled archive name on one diagnostic line."""
    return json.dumps(str(value), ensure_ascii=True)


def _member_name_problem(name):
    """Return a cross-platform extraction hazard for a ZIP member name, if any."""
    if not isinstance(name, str) or not name:
        return "empty name"
    if "\\" in name:
        return "backslash or UNC separator"
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        return "absolute, drive-letter, or UNC path"
    if any(unicodedata.category(character) in {"Cc", "Cf", "Cs"} for character in name):
        return "control or invisible character"
    parts = name[:-1].split("/") if name.endswith("/") else name.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return "empty or dot path segment"
    for part in parts:
        if ":" in part:
            return "colon in path segment"
        if part.endswith((".", " ")):
            return "path segment ends in a dot or space"
        if part.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
            return "Windows reserved device name"
    return None


def _collision_groups(names, key):
    grouped = {}
    for name in names:
        logical = name[:-1] if name.endswith("/") else name
        grouped.setdefault(key(logical), []).append(name)
    return [group for group in grouped.values() if len(group) > 1]


def verify_archive(path, expected_root=None):
    """Reject unsafe metadata and budgets before asking zipfile to expand any member for CRC."""
    safe_name = _quoted(path.name)
    require(path.is_file(), f"archive not found: {_quoted(path)}")
    try:
        archive_size = path.stat().st_size
        require(
            archive_size <= MAX_ARCHIVE_BYTES,
            f"archive {safe_name} exceeds the {MAX_ARCHIVE_BYTES}-byte archive limit",
        )
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            require(
                len(entries) <= MAX_ARCHIVE_MEMBERS,
                f"archive {safe_name} exceeds the {MAX_ARCHIVE_MEMBERS}-member limit",
            )
            oversized = sorted(
                item.filename for item in entries if item.file_size > MAX_ARCHIVE_MEMBER_BYTES
            )
            require(
                not oversized,
                f"archive member exceeds the {MAX_ARCHIVE_MEMBER_BYTES}-byte limit in {safe_name}: "
                + ", ".join(_quoted(name) for name in oversized),
            )
            total_size = sum(item.file_size for item in entries)
            require(
                total_size <= MAX_ARCHIVE_TOTAL_BYTES,
                f"archive {safe_name} exceeds the {MAX_ARCHIVE_TOTAL_BYTES}-byte aggregate uncompressed limit",
            )
            unsupported = sorted(
                item.filename for item in entries if item.compress_type not in ALLOWED_ARCHIVE_COMPRESSION
            )
            require(
                not unsupported,
                f"unsupported archive compression method in {safe_name}: "
                + ", ".join(_quoted(name) for name in unsupported),
            )
            encrypted = sorted(item.filename for item in entries if item.flag_bits & 0x1)
            require(
                not encrypted,
                f"encrypted archive member in {safe_name}: "
                + ", ".join(_quoted(name) for name in encrypted),
            )
            zero_compressed = sorted(
                item.filename for item in entries if item.file_size > 0 and item.compress_size == 0
            )
            require(
                not zero_compressed,
                f"nonempty zero-compressed archive member in {safe_name}: "
                + ", ".join(_quoted(name) for name in zero_compressed),
            )
            excessive_ratio = sorted(
                item.filename
                for item in entries
                if item.compress_size > 0
                and item.file_size > MAX_ARCHIVE_EXPANSION_RATIO * item.compress_size
            )
            require(
                not excessive_ratio,
                f"archive member exceeds the {MAX_ARCHIVE_EXPANSION_RATIO}:1 expansion limit in {safe_name}: "
                + ", ".join(_quoted(name) for name in excessive_ratio),
            )
            non_unix = sorted(item.filename for item in entries if item.create_system != 3)
            require(
                not non_unix,
                f"non-Unix archive member metadata in {safe_name}: "
                + ", ".join(_quoted(name) for name in non_unix),
            )

            names = [item.filename for item in entries]
            if expected_root is not None:
                stray = sorted(name for name in names if not name.startswith(expected_root))
                require(
                    not stray,
                    f"archive {safe_name} is not rooted at {_quoted(expected_root)}: "
                    + ", ".join(_quoted(name) for name in stray[:5]),
                )
            polluted = sorted(name for name in names if is_os_metadata(name))
            require(
                not polluted,
                f"operating-system metadata inside archive {safe_name}: "
                + ", ".join(_quoted(name) for name in polluted)
                + " (release archives must contain none; this archive is not the archive that was built)",
            )
            unsafe = sorted(
                (_quoted(name), _member_name_problem(name))
                for name in names
                if _member_name_problem(name) is not None
            )
            require(
                not unsafe,
                f"unsafe archive member path in {safe_name}: "
                + ", ".join(f"{name} ({problem})" for name, problem in unsafe),
            )
            # The combined key (NFC, then casefold, then NFC) is shared with the builder's inventory
            # check: "Å.txt" and "a" + U+030A + ".txt" are one file on a case- and
            # normalization-insensitive filesystem, so they are one collision here too.
            collision_sets = []
            for label, key in (
                ("exact", lambda value: value),
                ("combined Unicode NFC + casefold", BUILD_RELEASE.collision_key),
            ):
                for group in _collision_groups(names, key):
                    collision_sets.append(f"{label}: " + ", ".join(_quoted(name) for name in group))
            require(
                not collision_sets,
                f"colliding archive member name in {safe_name}: " + "; ".join(collision_sets),
            )
            irregular = sorted(item.filename for item in entries if _is_irregular_member(item))
            require(
                not irregular,
                f"symlink or special-file archive member in {safe_name}: "
                + ", ".join(_quoted(name) for name in irregular),
            )
            risky = sorted(item.filename for item in entries if _has_unsafe_mode(item))
            require(
                not risky,
                "unsafe archive member mode (setuid, setgid, sticky, or group/world-writable) "
                f"in {safe_name}: " + ", ".join(_quoted(name) for name in risky),
            )
            bad_crc = archive.testzip()
            require(
                bad_crc is None,
                f"archive member failed CRC verification in {safe_name}: {_quoted(bad_crc)}",
            )
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(f"FAIL: could not verify archive {safe_name}: {_quoted(exc)}")
    print(f"PASS: archive {safe_name} passed metadata, resource, path, mode, and CRC checks")


def rebuild_projected_archives(destination):
    """Rebuild the installer archives from this tree's own sources, deterministically."""
    require(BUILD_RELEASE.ROOT == ROOT, "builder and verifier disagree about the release root")
    claude = destination / "dravux.zip"
    openai = destination / "Dravux-OpenAI-Plugin-Source.zip"
    BUILD_RELEASE.build_zip(
        claude, "dravux", BUILD_RELEASE.subtree_files(BUILD_RELEASE.SKILL), BUILD_RELEASE.SKILL
    )
    BUILD_RELEASE.build_openai_source(openai)
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
            " inconsistent; re-download the release: "
            + ", ".join(_quoted(path) for path in sorted(shipped)),
        )
        return  # a source checkout ships neither the attestation nor built archives
    attested = load_release_json(ATTESTATION, "RELEASE_ATTESTATION.json")
    require(isinstance(attested, dict), "release attestation must be a JSON object")
    require(attested.get("package") == "dravux", "release attestation package mismatch")
    require(attested.get("package_version") == PACKAGE_VERSION, "release attestation package version mismatch")
    require(
        attested.get("archive_root") == f"Dravux-{PACKAGE_VERSION}",
        "release attestation archive root mismatch",
    )
    entries = attested.get("installer_archives")
    require(isinstance(entries, list) and entries, "release attestation lists no installer archives")
    listed = {}
    listed_paths = []
    for item in entries:
        require(
            isinstance(item, dict) and isinstance(item.get("path"), str),
            "release attestation entry is malformed",
        )
        listed_paths.append(item["path"])
        listed[item["path"]] = item
    duplicate_paths = sorted(path for path, count in Counter(listed_paths).items() if count > 1)
    require(
        not duplicate_paths,
        "release attestation contains duplicate installer path(s): "
        + ", ".join(_quoted(path) for path in duplicate_paths),
    )
    require(
        set(listed) == set(PROJECTED_ARCHIVES),
        "release attestation does not list exactly the expected installer archives",
    )
    missing = sorted(set(listed) - set(shipped))
    require(
        not missing,
        "this package is missing its installer archive(s): "
        + ", ".join(_quoted(path) for path in missing)
        + "; the release is incomplete; re-download it",
    )
    with tempfile.TemporaryDirectory() as tmp:
        rebuilt = rebuild_projected_archives(Path(tmp))
        for relative, path in sorted(shipped.items()):
            actual = digest(path)
            require(
                actual == digest(rebuilt[relative]),
                f"{_quoted(relative)} does not match the files in this package; do not upload it;"
                " re-download the release",
            )
            item = listed[relative]
            require(
                item.get("sha256") == actual and item.get("size") == path.stat().st_size,
                f"{_quoted(relative)} does not match the release attestation; do not upload it;"
                " re-download the release",
            )
    print(f"PASS: {len(shipped)} shipped installer archive(s) match this package's own files")


def report_os_metadata(found):
    """Loose Finder/Explorer files are noise, not tampering: say so plainly and continue."""
    if not found:
        return
    print("WARNING: operating-system metadata found in this folder")
    for relative in found:
        print(f"  {_quoted(relative)}")
    print(f"  These files are {OS_METADATA_NOTE}.")
    print("  They are excluded from every Dravux archive and from the release manifest.")


def main():
    archives = [Path(value) for value in sys.argv[1:] if not value.startswith("-")]
    if archives:
        for path in archives:
            verify_archive(path)
        return

    verify_required_files()
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
        require(not any(part in forbidden_names for part in relative.parts), f"excluded path present: {_quoted(relative)}")
        require(not path.is_symlink(), f"symlink present: {_quoted(relative)}")
        mode = path.lstat().st_mode
        require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), f"special file present: {_quoted(relative)}")

    for path in release_paths():
        if path.suffix == ".json" and path.is_file() and not is_os_metadata(path.relative_to(ROOT)):
            relative = path.relative_to(ROOT).as_posix()
            expected_rejection = EXPECTED_STRICT_JSON_REJECTIONS.get(relative)
            if expected_rejection is None:
                load_release_json(path)
                continue
            try:
                load_release_json(path)
            except SystemExit as exc:
                require(
                    expected_rejection in str(exc),
                    f"expected hostile JSON fixture {_quoted(relative)} failed for the wrong reason",
                )
            else:
                require(False, f"expected hostile JSON fixture {_quoted(relative)} was accepted")

    for name in ("dravux-report.schema.json", "finding.schema.json", "dravux-preflight.schema.json", "dravux-run.schema.json"):
        require(digest(ROOT / "schemas" / name) == digest(SKILL / "schemas" / name), f"schemas drifted: {name}")

    codex = load_release_json(PLUGIN / ".codex-plugin" / "plugin.json", "Codex plugin manifest")
    claude = load_release_json(PLUGIN / ".claude-plugin" / "plugin.json", "Claude plugin manifest")
    require(codex["name"] == claude["name"] == "dravux", "plugin names disagree")
    require(codex["version"] == claude["version"] == PACKAGE_VERSION, "plugin versions disagree")
    require(codex["license"] == claude["license"] == "MIT", "plugin licenses disagree")
    require(codex["skills"] == "./skills/", "Codex skill path is not plugin-relative")

    codex_market = load_release_json(ROOT / ".agents" / "plugins" / "marketplace.json", "Codex marketplace manifest")
    claude_market = load_release_json(ROOT / ".claude-plugin" / "marketplace.json", "Claude marketplace manifest")
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
    verify_inventory()

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
        require(local_home not in text, f"absolute local home path present: {_quoted(relative)}")
        if copyright_holder in text:
            require(relative in allowed_name_files, f"personal name outside MIT license: {_quoted(relative)}")
        for pattern in secret_patterns:
            require(pattern.search(text) is None, f"secret-like value present: {_quoted(relative)}")

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
        require(
            forbidden_version not in path.read_text(encoding="utf-8", errors="ignore"),
            f"literal forbidden version present: {_quoted(path.relative_to(ROOT))}",
        )

    for name in ("README.md", "INSTALLERS/README.md", "INSTALLERS/Claude-Chat-Cowork/README.md", "INSTALLERS/Codex-ChatGPT/README.md"):
        require((ROOT / name).is_file(), f"required human-facing document missing: {name}")
    require((ROOT / "START_HERE.md").is_file(), "required human-facing document missing: START_HERE.md")
    require((ROOT / "SECURITY.md").is_file(), "required human-facing document missing: SECURITY.md")
    require((ROOT / "docs" / "portability.md").is_file(), "required human-facing document missing: docs/portability.md")

    for relative, expected_root in PROJECTED_ARCHIVES.items():
        candidate = ROOT / relative
        if candidate.is_file():
            verify_archive(candidate, expected_root=expected_root)
    stray_archives = sorted(
        path.relative_to(ROOT).as_posix()
        for path in release_paths()
        if path.is_file() and path.suffix == ".zip" and path.relative_to(ROOT).as_posix() not in PROJECTED_ARCHIVES
    )
    require(
        not stray_archives,
        "unexpected archive in the release tree: "
        + ", ".join(_quoted(path) for path in stray_archives),
    )
    verify_projected_archives()

    report_os_metadata(loose_os_metadata)
    print("PASS: release structure, file manifest, plugin manifests, schemas, privacy, and installer policy")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(
            "FAIL: release verification safely rejected malformed control data: " + _quoted(exc),
            file=sys.stderr,
        )
        raise SystemExit(1)
