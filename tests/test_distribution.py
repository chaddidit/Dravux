import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugins" / "dravux" / "skills" / "dravux"
SCRIPTS = ROOT / "scripts"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def copy_release_tree(destination):
    """Copy only the shipped files into destination so builds never mutate the working tree."""
    sys.path.insert(0, str(SCRIPTS))
    from build_release import release_files

    for path in release_files(include_manifest=True):
        target = destination / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return destination


def extract_release(archive_path, destination):
    """Extract preserving recorded modes, the way an ordinary unzip does."""
    with zipfile.ZipFile(archive_path) as archive:
        for item in archive.infolist():
            target = Path(archive.extract(item, destination))
            mode = (item.external_attr >> 16) & 0o7777
            if mode:
                os.chmod(target, mode)
    return destination


def tree_digest(root):
    values = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_file() and not path.is_symlink():
            values.append((relative, hashlib.sha256(path.read_bytes()).hexdigest()))
        else:
            values.append((relative + "/", ""))
    return values


class DistributionTests(unittest.TestCase):
    def test_end_user_docs_match_raw_and_plugin_routes(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        claude_adapter = (ROOT / "adapters" / "claude" / "README.md").read_text(encoding="utf-8")
        codex_adapter = (ROOT / "adapters" / "codex" / "README.md").read_text(encoding="utf-8")

        for expected in (
            "/dravux:dravux",
            "$dravux:dravux",
            'cp -R fixtures "$DRAVUX_TEST_PROJECT/fixtures"',
            "claude plugin uninstall dravux@dravux",
            "codex plugin remove dravux@dravux",
            "## Troubleshooting",
        ):
            self.assertIn(expected, readme)
        self.assertIn("/dravux:dravux", claude_adapter)
        self.assertIn("$dravux:dravux", codex_adapter)
        self.assertIn('cd "$DRAVUX_COPY"', claude_adapter)
        self.assertIn('cd "$DRAVUX_COPY"', codex_adapter)
        self.assertIn("plugins/dravux/skills/dravux", claude_adapter)
        self.assertIn("plugins/dravux/skills/dravux", codex_adapter)
        quickstart = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")
        operational_readme = (ROOT / "fixtures" / "operational" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("skill/dravux/", quickstart)
        self.assertNotIn("skill/dravux/", operational_readme)
        self.assertIn("plugins/dravux/skills/dravux/", quickstart)

        marketplace = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        self.assertEqual(entry["category"], "Productivity")

    def test_archive_builder_excludes_local_and_private_state(self):
        import sys

        sys.path.insert(0, str(SCRIPTS))
        from build_release import should_exclude

        excluded = (
            Path("config/local-paths.json"),
            Path("config/example.private.json"),
            Path(".env"),
            Path(".env.local"),
            Path(".claude/settings.local.json"),
            Path(".claude/skills/dravux/SKILL.md"),
            Path(".codex/config.toml"),
            Path(".agents/skills/dravux/SKILL.md"),
            Path("out/generated.json"),
            Path("session.log"),
            Path("dist-release/SHA256SUMS.txt"),
            Path("dravux-1.0.2.tgz"),
            Path("node_modules/example/package.json"),
            Path("plugins/dravux/skills/dravux/references/.DS_Store"),
            Path("plugins/dravux/skills/dravux/Thumbs.db"),
            Path("notes.tmp"),
            Path("README.md~"),
        )
        for path in excluded:
            with self.subTest(path=path):
                self.assertTrue(should_exclude(path))
        self.assertFalse(should_exclude(Path(".agents/plugins/marketplace.json")))
        self.assertFalse(should_exclude(Path(".claude-plugin/marketplace.json")))

    def run_script(self, name, *args, cwd=None, home=None):
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if home is not None:
            env["HOME"] = str(home)
        return subprocess.run(
            ["sh", str(ROOT / name), *map(str, args)],
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_all_raw_install_destinations_and_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory(prefix="dravux install space ") as tmp:
            base = Path(tmp)
            unrelated = base / "unrelated Ω directory"
            unrelated.mkdir()
            project = base / "Project With Spaces Ω"
            project.mkdir()
            home = base / "Home With Spaces Ω"
            home.mkdir()
            cases = (
                ("--claude", "--project-dir", project, project / ".claude/skills/dravux"),
                ("--codex", "--project-dir", project, project / ".agents/skills/dravux"),
                ("--claude", "--personal", None, home / ".claude/skills/dravux"),
                ("--codex", "--personal", None, home / ".agents/skills/dravux"),
            )
            for platform, scope, scope_value, destination in cases:
                with self.subTest(platform=platform, scope=scope):
                    args = [platform, scope]
                    if scope_value is not None:
                        args.append(scope_value)
                    installed = self.run_script("install.sh", *args, cwd=unrelated, home=home)
                    self.assertEqual(installed.returncode, 0, installed.stderr)
                    self.assertTrue(destination.is_dir())
                    self.assertEqual(tree_digest(SOURCE), tree_digest(destination))
                    before = tree_digest(destination)
                    verified = self.run_script("verify-install.sh", *args, cwd=unrelated, home=home)
                    self.assertEqual(verified.returncode, 0, verified.stderr)
                    self.assertIn("VERIFIED: installed Dravux", verified.stdout)
                    self.assertEqual(before, tree_digest(destination), "verification must be read-only")

    def test_existing_destinations_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cases = ("file", "directory", "symlink", "broken-symlink")
            for kind in cases:
                with self.subTest(kind=kind):
                    project = base / kind
                    project.mkdir()
                    destination = project / ".claude/skills/dravux"
                    destination.parent.mkdir(parents=True)
                    if kind == "file":
                        destination.write_text("keep", encoding="utf-8")
                    elif kind == "directory":
                        destination.mkdir()
                        (destination / "keep.txt").write_text("keep", encoding="utf-8")
                    elif kind == "symlink":
                        target = project / "target"
                        target.mkdir()
                        destination.symlink_to(target, target_is_directory=True)
                    else:
                        destination.symlink_to(project / "missing", target_is_directory=True)
                    marker = os.readlink(destination) if destination.is_symlink() else (
                        destination.read_text(encoding="utf-8") if destination.is_file() else tree_digest(destination)
                    )
                    result = self.run_script("install.sh", "--claude", "--project-dir", project)
                    self.assertEqual(result.returncode, 4, result.stderr)
                    current = os.readlink(destination) if destination.is_symlink() else (
                        destination.read_text(encoding="utf-8") if destination.is_file() else tree_digest(destination)
                    )
                    self.assertEqual(marker, current)

    def test_second_install_refuses_and_preserves_first_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            args = ("--codex", "--project-dir", project)
            first = self.run_script("install.sh", *args)
            self.assertEqual(first.returncode, 0, first.stderr)
            destination = project / ".agents/skills/dravux"
            before = tree_digest(destination)
            second = self.run_script("install.sh", *args)
            self.assertEqual(second.returncode, 4, second.stderr)
            self.assertEqual(before, tree_digest(destination))

    def test_invalid_scope_preflight_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            missing = base / "missing"
            result = self.run_script("install.sh", "--claude", "--project-dir", missing)
            self.assertEqual(result.returncode, 3)
            self.assertFalse(missing.exists())

            for home in ("", "relative-home", "/"):
                with self.subTest(home=home):
                    result = self.run_script("install.sh", "--codex", "--personal", home=home)
                    self.assertEqual(result.returncode, 3)

    def test_verifier_rejects_tampered_and_extra_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            args = ("--claude", "--project-dir", project)
            self.assertEqual(self.run_script("install.sh", *args).returncode, 0)
            destination = project / ".claude/skills/dravux"
            (destination / "SKILL.md").write_text("tampered", encoding="utf-8")
            tampered = self.run_script("verify-install.sh", *args)
            self.assertEqual(tampered.returncode, 5)

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            args = ("--codex", "--project-dir", project)
            self.assertEqual(self.run_script("install.sh", *args).returncode, 0)
            destination = project / ".agents/skills/dravux"
            (destination / "unexpected.txt").write_text("extra", encoding="utf-8")
            extra = self.run_script("verify-install.sh", *args)
            self.assertEqual(extra.returncode, 5)

    def test_release_scripts_are_executable_but_work_through_sh(self):
        for name in ("install.sh", "verify-install.sh", "verify-release.sh"):
            self.assertTrue(os.access(ROOT / name, os.X_OK), name)

    def test_release_verifier_detects_manifest_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = copy_release_tree(Path(tmp) / f"Dravux-{VERSION}")
            built = subprocess.run(
                [sys.executable, "-B", str(copied / "scripts" / "build_release.py"), "--output-dir", str(Path(tmp) / "artifacts")],
                cwd=copied,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            readme = copied / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            proc = subprocess.run(
                ["python3", "-B", str(copied / "scripts" / "verify_distribution.py")],
                cwd=copied,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("release manifest hash mismatch: README.md", proc.stdout + proc.stderr)

    def build_verifiable_tree(self, base):
        """Copy the shipped files and regenerate their manifest so the verifier has a current tree."""
        tree = copy_release_tree(base / f"Dravux-{VERSION}")
        built = subprocess.run(
            [sys.executable, "-B", str(tree / "scripts" / "build_release.py"), "--output-dir", str(base / "artifacts")],
            cwd=tree,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(built.returncode, 0, built.stderr)
        return tree

    def run_distribution_verifier(self, tree):
        return subprocess.run(
            [sys.executable, "-B", str(tree / "scripts" / "verify_distribution.py")],
            cwd=tree,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_root_git_checkout_is_tolerated_but_nested_git_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tree = self.build_verifiable_tree(base)

            (tree / ".git" / "objects").mkdir(parents=True)
            (tree / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            tolerated = self.run_distribution_verifier(tree)
            self.assertEqual(tolerated.returncode, 0, tolerated.stdout + tolerated.stderr)

            nested = tree / "docs" / ".git"
            nested.mkdir(parents=True)
            (nested / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            rejected = self.run_distribution_verifier(tree)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("excluded path present: docs/.git", rejected.stdout + rejected.stderr)

    def test_build_output_is_ignored_only_in_a_source_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = self.build_verifiable_tree(Path(tmp))
            output = tree / "dist-release"
            output.mkdir()
            (output / "stray.txt").write_text("local build output\n", encoding="utf-8")
            rejected = self.run_distribution_verifier(tree)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("release manifest path set differs", rejected.stdout + rejected.stderr)
            (tree / ".git").mkdir()
            accepted = self.run_distribution_verifier(tree)
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

    def test_builder_creates_deterministic_engineering_and_surface_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = copy_release_tree(Path(tmp) / "tree")
            outputs = []
            for name in ("first", "second"):
                destination = Path(tmp) / name
                proc = subprocess.run(
                    [sys.executable, "-B", str(tree / "scripts" / "build_release.py"), "--output-dir", str(destination)],
                    cwd=tree,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                outputs.append(destination)

            expected = (
                f"Dravux-{VERSION}.zip",
                "dravux.zip",
                "Dravux-OpenAI-Plugin-Source.zip",
                "SHA256SUMS.txt",
            )
            for name in expected:
                self.assertEqual((outputs[0] / name).read_bytes(), (outputs[1] / name).read_bytes(), name)

            checksums = dict(
                reversed(line.split("  ", 1))
                for line in (outputs[0] / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
            )
            self.assertEqual(len(checksums), 6)
            for name in (
                f"Dravux-{VERSION}.zip",
                "dravux.zip",
                "Dravux-OpenAI-Plugin-Source.zip",
                f"Dravux-{VERSION}/RELEASE_ATTESTATION.json",
            ):
                self.assertIn(name, checksums)
            for member, standalone in (
                (f"Dravux-{VERSION}/INSTALLERS/Claude-Chat-Cowork/dravux.zip", "dravux.zip"),
                (
                    f"Dravux-{VERSION}/INSTALLERS/Codex-ChatGPT/Dravux-OpenAI-Plugin-Source.zip",
                    "Dravux-OpenAI-Plugin-Source.zip",
                ),
            ):
                self.assertEqual(checksums[member], checksums[standalone], member)

            with zipfile.ZipFile(outputs[0] / f"Dravux-{VERSION}.zip") as archive:
                names = archive.namelist()
                self.assertTrue(all(name.startswith(f"Dravux-{VERSION}/") for name in names))
            with zipfile.ZipFile(outputs[0] / "dravux.zip") as archive:
                names = archive.namelist()
                self.assertIn("dravux/SKILL.md", names)
                self.assertIn("dravux/fixtures/passing/known-pass.json", names)
                self.assertIn("dravux/fixtures/hostile/unknown-property.invalid.json", names)
                self.assertTrue(all(name.startswith("dravux/") for name in names))
            with zipfile.ZipFile(outputs[0] / "Dravux-OpenAI-Plugin-Source.zip") as archive:
                names = archive.namelist()
                self.assertIn("Dravux-OpenAI-Plugin-Source/.agents/plugins/marketplace.json", names)
                self.assertIn("Dravux-OpenAI-Plugin-Source/plugins/dravux/.codex-plugin/plugin.json", names)

            for archive_path in outputs[0].glob("*.zip"):
                with zipfile.ZipFile(archive_path) as archive:
                    for name in archive.namelist():
                        parts = Path(name).parts
                        self.assertNotIn("..", parts)
                        self.assertNotIn(".DS_Store", parts)
                        self.assertNotIn("__MACOSX", parts)
                        self.assertNotIn(".git", parts)

    def test_installers_projection_is_reachable_and_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = copy_release_tree(Path(tmp) / "tree")
            destination = Path(tmp) / "artifacts"
            proc = subprocess.run(
                [sys.executable, "-B", str(tree / "scripts" / "build_release.py"), "--output-dir", str(destination)],
                cwd=tree,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

            root = f"Dravux-{VERSION}"
            projected = {
                f"{root}/INSTALLERS/Claude-Chat-Cowork/dravux.zip": destination / "dravux.zip",
                f"{root}/INSTALLERS/Codex-ChatGPT/Dravux-OpenAI-Plugin-Source.zip": destination
                / "Dravux-OpenAI-Plugin-Source.zip",
            }
            with zipfile.ZipFile(destination / f"{root}.zip") as archive:
                names = set(archive.namelist())
                for guide in (
                    "INSTALLERS/README.md",
                    "INSTALLERS/Claude-Chat-Cowork/README.md",
                    "INSTALLERS/Codex-ChatGPT/README.md",
                ):
                    self.assertIn(f"{root}/{guide}", names)
                self.assertIn(f"{root}/START_HERE.md", names)
                for member, standalone in projected.items():
                    self.assertIn(member, names)
                    payload = archive.read(member)
                    self.assertEqual(payload, standalone.read_bytes(), member)
                    # At most two navigation steps below the archive root.
                    self.assertLessEqual(len(Path(member).relative_to(root).parts) - 1, 2)
                    with zipfile.ZipFile(io.BytesIO(payload)) as inner:
                        inner_names = inner.namelist()
                    if standalone.name == "dravux.zip":
                        self.assertIn("dravux/SKILL.md", inner_names)
                        self.assertTrue(all(name.startswith("dravux/") for name in inner_names))
                    else:
                        self.assertTrue(
                            all(name.startswith("Dravux-OpenAI-Plugin-Source/") for name in inner_names)
                        )

            manifest = json.loads((tree / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
            listed = {item["path"] for item in manifest["files"]}
            self.assertIn("INSTALLERS/README.md", listed)
            self.assertIn("START_HERE.md", listed)
            self.assertFalse(
                [path for path in listed if path.endswith(".zip")],
                "built archives must never be indexed as manifest source files",
            )

    def test_shipped_installer_archive_cannot_be_swapped_for_a_tampered_one(self):
        """The archive a newcomer uploads is a build product, so the manifest cannot cover it."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tree = self.build_verifiable_tree(base)

            source_checkout = self.run_distribution_verifier(tree)
            self.assertEqual(source_checkout.returncode, 0, source_checkout.stdout + source_checkout.stderr)
            self.assertNotIn("shipped installer archive", source_checkout.stdout)

            extracted = extract_release(base / "artifacts" / f"Dravux-{VERSION}.zip", base / "extracted")
            release = extracted / f"Dravux-{VERSION}"
            shipped = release / "INSTALLERS" / "Claude-Chat-Cowork" / "dravux.zip"
            self.assertTrue(shipped.is_file())

            pristine = self.run_distribution_verifier(release)
            self.assertEqual(pristine.returncode, 0, pristine.stdout + pristine.stderr)
            self.assertIn("shipped installer archive(s) match this package's own files", pristine.stdout)

            # Same root shape, no operating-system metadata, one byte of one member changed.
            with zipfile.ZipFile(shipped) as original:
                entries = [(item, original.read(item.filename)) for item in original.infolist()]
            with zipfile.ZipFile(shipped, "w", compression=zipfile.ZIP_DEFLATED) as rewritten:
                for item, payload in entries:
                    if item.filename == "dravux/SKILL.md":
                        payload = payload.replace(b"# Dravux", b"# DravuX", 1)
                    rewritten.writestr(item, payload)

            with zipfile.ZipFile(shipped) as swapped:
                self.assertTrue(all(name.startswith("dravux/") for name in swapped.namelist()))

            caught = self.run_distribution_verifier(release)
            output = caught.stdout + caught.stderr
            self.assertNotEqual(caught.returncode, 0, output)
            self.assertIn("INSTALLERS/Claude-Chat-Cowork/dravux.zip does not match the files in this package", output)
            self.assertIn("do not upload it", output)
            self.assertIn("re-download the release", output)

    def test_extracted_release_requires_both_installer_archives(self):
        """Built-release state comes from the attestation, so deleting an installer cannot skip the check."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self.build_verifiable_tree(base)
            extracted = extract_release(base / "artifacts" / f"Dravux-{VERSION}.zip", base / "extracted")
            release = extracted / f"Dravux-{VERSION}"
            attestation = release / "RELEASE_ATTESTATION.json"
            claude_zip = release / "INSTALLERS" / "Claude-Chat-Cowork" / "dravux.zip"
            codex_zip = release / "INSTALLERS" / "Codex-ChatGPT" / "Dravux-OpenAI-Plugin-Source.zip"
            self.assertTrue(attestation.is_file(), "built release must carry the attestation")

            for doomed in ([codex_zip], [claude_zip], [claude_zip, codex_zip]):
                with self.subTest(deleted=[path.name for path in doomed]):
                    saved = [(path, path.read_bytes()) for path in doomed]
                    for path, _ in saved:
                        path.unlink()
                    caught = self.run_distribution_verifier(release)
                    output = caught.stdout + caught.stderr
                    self.assertNotEqual(caught.returncode, 0, output)
                    self.assertIn("missing its installer archive(s)", output)
                    self.assertIn("re-download", output)
                    for path, payload in saved:
                        path.write_bytes(payload)

            restored = self.run_distribution_verifier(release)
            self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)
            self.assertIn("2 shipped installer archive(s)", restored.stdout)

            # Stripping only the attestation while archives remain is inconsistent, not a source checkout.
            attestation.unlink()
            stripped = self.run_distribution_verifier(release)
            output = stripped.stdout + stripped.stderr
            self.assertNotEqual(stripped.returncode, 0, output)
            self.assertIn("RELEASE_ATTESTATION.json is missing", output)

    def test_os_metadata_is_excluded_warned_about_and_rejected_inside_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tree = self.build_verifiable_tree(base)
            for relative in (".DS_Store", "plugins/dravux/.DS_Store", "docs/Thumbs.db", "._hidden"):
                (tree / relative).write_bytes(b"finder metadata")

            rebuilt = Path(tmp) / "with-metadata"
            proc = subprocess.run(
                [sys.executable, "-B", str(tree / "scripts" / "build_release.py"), "--output-dir", str(rebuilt)],
                cwd=tree,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

            manifest = json.loads((tree / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
            listed = {item["path"] for item in manifest["files"]}
            for relative in (".DS_Store", "plugins/dravux/.DS_Store", "docs/Thumbs.db", "._hidden"):
                self.assertNotIn(relative, listed)
            for archive_path in rebuilt.glob("*.zip"):
                with zipfile.ZipFile(archive_path) as archive:
                    for name in archive.namelist():
                        parts = Path(name).parts
                        self.assertNotIn(".DS_Store", parts, archive_path.name)
                        self.assertNotIn("Thumbs.db", parts, archive_path.name)
                        self.assertFalse(any(part.startswith("._") for part in parts), archive_path.name)

            warned = self.run_distribution_verifier(tree)
            output = warned.stdout + warned.stderr
            self.assertEqual(warned.returncode, 0, output)
            self.assertIn("WARNING: operating-system metadata found", output)
            self.assertIn("plugins/dravux/.DS_Store", output)
            self.assertIn("safe to delete", output)

            clean = rebuilt / f"Dravux-{VERSION}.zip"
            checked = subprocess.run(
                [sys.executable, "-B", str(tree / "scripts" / "verify_distribution.py"), str(clean)],
                cwd=tree,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

            tampered = base / "tampered.zip"
            shutil.copy2(clean, tampered)
            with zipfile.ZipFile(tampered, "a") as archive:
                archive.writestr(f"Dravux-{VERSION}/docs/.DS_Store", b"finder metadata")
            rejected = subprocess.run(
                [sys.executable, "-B", str(tree / "scripts" / "verify_distribution.py"), str(tampered)],
                cwd=tree,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("operating-system metadata inside archive", rejected.stdout + rejected.stderr)

    def test_unexpected_non_metadata_file_still_fails_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = self.build_verifiable_tree(Path(tmp))
            (tree / "docs" / "leftover-notes.md").write_text("stray file\n", encoding="utf-8")
            failed = self.run_distribution_verifier(tree)
            output = failed.stdout + failed.stderr
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("release manifest path set differs", output)
            self.assertIn("docs/leftover-notes.md", output)

    def test_version_surfaces_match_version_file(self):
        manifest = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
        claude = json.loads((ROOT / "plugins/dravux/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
        codex = json.loads((ROOT / "plugins/dravux/.codex-plugin/plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["package_version"], VERSION)
        self.assertEqual(manifest["archive_root"], f"Dravux-{VERSION}")
        self.assertEqual(claude["version"], VERSION)
        self.assertEqual(codex["version"], VERSION)
        self.assertEqual(marketplace["plugins"][0]["version"], VERSION)


if __name__ == "__main__":
    unittest.main()
