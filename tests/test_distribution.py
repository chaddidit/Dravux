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

    def test_installed_modes_are_normalized_and_verified(self):
        import stat

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            args = ("--claude", "--project-dir", project)
            # A restrictive umask must not leak into the installed copy: the installer sets the modes itself.
            installed = subprocess.run(
                ["sh", "-c", 'umask 077; sh "$0" "$@"', str(ROOT / "install.sh"), *map(str, args)],
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), check=False, capture_output=True, text=True,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            destination = project / ".claude/skills/dravux"
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE((destination / "SKILL.md").stat().st_mode), 0o644)
            self.assertEqual(stat.S_IMODE((destination / "scripts").stat().st_mode), 0o755)
            self.assertEqual(self.run_script("verify-install.sh", *args).returncode, 0)

            (destination / "SKILL.md").chmod(0o666)
            writable = self.run_script("verify-install.sh", *args)
            self.assertEqual(writable.returncode, 5, writable.stderr)
            self.assertIn("group- or world-writable", writable.stderr)
            (destination / "SKILL.md").chmod(0o644)

            (destination / "scripts" / "dravux_run.py").chmod(0o755)
            drifted = self.run_script("verify-install.sh", *args)
            self.assertEqual(drifted.returncode, 5, drifted.stderr)
            self.assertIn("executable bits differ", drifted.stderr)
            (destination / "scripts" / "dravux_run.py").chmod(0o644)
            self.assertEqual(self.run_script("verify-install.sh", *args).returncode, 0)

    def test_installer_rejects_platform_and_skills_parent_symlinks_without_writing_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for component in ("platform", "skills"):
                with self.subTest(component=component):
                    project = base / component
                    project.mkdir()
                    redirected = project / "redirected"
                    redirected.mkdir()
                    platform = project / ".agents"
                    if component == "platform":
                        platform.symlink_to(redirected, target_is_directory=True)
                    else:
                        platform.mkdir()
                        (platform / "skills").symlink_to(redirected, target_is_directory=True)
                    before = sorted(redirected.iterdir())
                    rejected = self.run_script("install.sh", "--codex", "--project-dir", project)
                    self.assertEqual(rejected.returncode, 4, rejected.stderr)
                    self.assertEqual(sorted(redirected.iterdir()), before)
                    self.assertNotIn("Traceback", rejected.stderr)

    def test_installer_creates_private_parents_and_preserves_existing_safe_modes(self):
        import stat

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            fresh = base / "fresh"
            fresh.mkdir()
            installed = self.run_script("install.sh", "--codex", "--project-dir", fresh)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            self.assertEqual(stat.S_IMODE((fresh / ".agents").stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((fresh / ".agents" / "skills").stat().st_mode), 0o700)

            existing = base / "existing"
            skills = existing / ".agents" / "skills"
            skills.mkdir(parents=True)
            (existing / ".agents").chmod(0o755)
            skills.chmod(0o755)
            before = (stat.S_IMODE((existing / ".agents").stat().st_mode), stat.S_IMODE(skills.stat().st_mode))
            installed = self.run_script("install.sh", "--codex", "--project-dir", existing)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            after = (stat.S_IMODE((existing / ".agents").stat().st_mode), stat.S_IMODE(skills.stat().st_mode))
            self.assertEqual(after, before, "installer changed pre-existing parent modes")

    def test_installer_and_verifier_reject_unsafe_or_aliased_parent_chains(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            unsafe = base / "unsafe"
            platform = unsafe / ".agents"
            platform.mkdir(parents=True)
            platform.chmod(0o777)
            rejected = self.run_script("install.sh", "--codex", "--project-dir", unsafe)
            self.assertEqual(rejected.returncode, 4, rejected.stderr)
            self.assertFalse((platform / "skills").exists())

            project = base / "installed"
            project.mkdir()
            args = ("--codex", "--project-dir", project)
            installed = self.run_script("install.sh", *args)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            skills = project / ".agents" / "skills"
            skills.chmod(0o777)
            verified = self.run_script("verify-install.sh", *args)
            self.assertEqual(verified.returncode, 5, verified.stderr)
            self.assertIn("group/world-writable", verified.stderr)
            skills.chmod(0o700)

            physical = project / ".agents-real"
            (project / ".agents").rename(physical)
            (project / ".agents").symlink_to(physical, target_is_directory=True)
            verified = self.run_script("verify-install.sh", *args)
            self.assertEqual(verified.returncode, 4, verified.stderr)
            self.assertIn("symlink", verified.stderr)

    def test_shell_entry_points_never_write_bytecode_into_the_working_directory(self):
        """Every python3 call carries -B (or the env var); a relative HOME must leave the cwd untouched.

        Apple's python3 resolves its bytecode cache under HOME, so a relative HOME once made the
        version probe write a cache tree into whatever directory the script was run from.
        """
        for name in ("install.sh", "verify-install.sh", "verify-release.sh"):
            for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith(("#", "printf")) or "command -v python3" in stripped or "python3 " not in stripped:
                    continue
                with self.subTest(script=name, line=stripped):
                    self.assertTrue("python3 -B" in stripped or "PYTHONDONTWRITEBYTECODE=1 python3" in stripped, stripped)
        env = {key: value for key, value in os.environ.items() if key != "PYTHONDONTWRITEBYTECODE"}
        env["HOME"] = "relative-home"
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("install.sh", "verify-install.sh"):
                proc = subprocess.run(
                    ["sh", str(ROOT / name), "--codex", "--personal"], cwd=tmp, env=env, check=False, capture_output=True, text=True
                )
                self.assertEqual(proc.returncode, 3, proc.stderr)
            self.assertEqual(sorted(Path(tmp).rglob("*")), [], "a shell entry point wrote into the working directory")

    def test_personal_home_symlink_is_canonicalized_before_destination_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            physical = Path(tmp) / "private" / "var"
            physical.mkdir(parents=True)
            physical_resolved = Path(os.path.realpath(physical))
            alias = Path(tmp) / "var"
            alias.symlink_to(physical, target_is_directory=True)
            first = self.run_script("install.sh", "--codex", "--personal", home=alias)
            self.assertEqual(first.returncode, 0, first.stderr)
            destination = physical_resolved / ".agents" / "skills" / "dravux"
            self.assertTrue(destination.is_dir())
            self.assertIn(f"Destination: {destination}", first.stdout)
            before = sorted(path.relative_to(physical_resolved).as_posix() for path in physical_resolved.rglob("*"))
            second = self.run_script("install.sh", "--codex", "--personal", home=alias)
            self.assertEqual(second.returncode, 4, second.stderr)
            after = sorted(path.relative_to(physical_resolved).as_posix() for path in physical_resolved.rglob("*"))
            self.assertEqual(after, before, "a rejected personal install created parent-directory side effects")
            verified = self.run_script("verify-install.sh", "--codex", "--personal", home=alias)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertIn(f"Destination: {destination}", verified.stdout)

    def test_release_scripts_are_executable_but_work_through_sh(self):
        for name in ("install.sh", "verify-install.sh", "verify-release.sh"):
            self.assertTrue(os.access(ROOT / name, os.X_OK), name)

    def test_release_gate_verifies_distribution_before_running_tests(self):
        lines = (ROOT / "verify-release.sh").read_text(encoding="utf-8").splitlines()
        distribution = next(index for index, line in enumerate(lines) if "scripts/verify_distribution.py" in line)
        unit_tests = next(index for index, line in enumerate(lines) if "unittest discover" in line)
        self.assertLess(distribution, unit_tests)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", lines[distribution])
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", lines[unit_tests])
        self.assertIn("python3 -B", lines[distribution])
        self.assertIn("python3 -B", lines[unit_tests])

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
                [sys.executable, "-B", str(copied / "scripts" / "verify_distribution.py")],
                cwd=copied,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('release manifest hash mismatch: "README.md"', proc.stdout + proc.stderr)

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
            self.assertIn('excluded path present: "docs/.git"', rejected.stdout + rejected.stderr)

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
                self.assertIn(f"RECORDED: Dravux-{VERSION}/RELEASE_ATTESTATION.json", proc.stdout)
                self.assertNotIn("ATTESTED:", proc.stdout)
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
            self.assertIn('"INSTALLERS/Claude-Chat-Cowork/dravux.zip" does not match the files in this package', output)
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

    def test_release_attestation_rejects_duplicate_installer_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self.build_verifiable_tree(base)
            extracted = extract_release(base / "artifacts" / f"Dravux-{VERSION}.zip", base / "extracted")
            release = extracted / f"Dravux-{VERSION}"
            attestation_path = release / "RELEASE_ATTESTATION.json"
            attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
            attestation["installer_archives"].append(dict(attestation["installer_archives"][0]))
            attestation_path.write_text(json.dumps(attestation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            rejected = self.run_distribution_verifier(release)
            output = rejected.stdout + rejected.stderr
            self.assertNotEqual(rejected.returncode, 0, output)
            self.assertIn("release attestation contains duplicate installer path", output)
            self.assertNotIn("Traceback", output)

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

    def test_hostile_tree_path_cannot_forge_verifier_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = self.build_verifiable_tree(Path(tmp))
            hostile_name = "note\nPASS: forged\nVERIFIED: forged\x1b.md"
            (tree / "docs" / hostile_name).write_text("unexpected\n", encoding="utf-8")
            rejected = self.run_distribution_verifier(tree)
            output = rejected.stdout + rejected.stderr
            self.assertNotEqual(rejected.returncode, 0, output)
            self.assertIn("release manifest path set differs", output)
            self.assertIn("\\nPASS: forged\\nVERIFIED: forged\\u001b", output)
            self.assertFalse(any(line in {"PASS: forged", "VERIFIED: forged"} for line in output.splitlines()))
            self.assertNotIn("Traceback", output)

    def test_declared_inventory_matches_the_shipped_tree(self):
        sys.path.insert(0, str(SCRIPTS))
        from build_release import SHIPPED_FILES, release_files
        from verify_distribution import SHIPPED_FILES as verifier_inventory

        shipped = [path.relative_to(ROOT).as_posix() for path in release_files(include_manifest=False)]
        self.assertEqual(len(SHIPPED_FILES), len(set(SHIPPED_FILES)), "declared inventory repeats a path")
        self.assertEqual(sorted(SHIPPED_FILES), shipped, "declared inventory and build selection differ")
        self.assertEqual(list(SHIPPED_FILES), sorted(SHIPPED_FILES), "declared inventory must stay sorted")
        self.assertEqual(verifier_inventory, SHIPPED_FILES, "verifier must consume the builder-owned inventory")

    def test_file_deleted_before_the_build_is_still_caught(self):
        """The manifest is regenerated from the tree, so only the declared inventory can notice this."""
        with tempfile.TemporaryDirectory() as tmp:
            tree = copy_release_tree(Path(tmp) / "tree")
            doomed = (
                "plugins/dravux/skills/dravux/agents/openai.yaml",
                "CHANGELOG.md",
                "tests/test_live_site.py",
                "VERSION",
            )
            for relative in doomed:
                (tree / relative).unlink()
            manifest_before = (tree / "RELEASE_MANIFEST.json").read_bytes()
            output_dir = Path(tmp) / "artifacts"
            built = subprocess.run(
                [sys.executable, "-B", str(tree / "scripts" / "build_release.py"), "--output-dir", str(output_dir)],
                cwd=tree,
                check=False,
                capture_output=True,
                text=True,
            )
            output = built.stdout + built.stderr
            self.assertNotEqual(built.returncode, 0, output)
            self.assertIn("source tree differs from authoritative shipped-file inventory", output)
            for relative in doomed:
                self.assertIn(relative, output)
            self.assertNotIn("Traceback", output)
            self.assertFalse(output_dir.exists())
            self.assertEqual((tree / "RELEASE_MANIFEST.json").read_bytes(), manifest_before)

    def test_file_added_before_the_build_is_still_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = copy_release_tree(Path(tmp) / "tree")
            (tree / "docs" / "notes.md").write_text("not a shipped file\n", encoding="utf-8")
            manifest_before = (tree / "RELEASE_MANIFEST.json").read_bytes()
            output_dir = Path(tmp) / "artifacts"
            built = subprocess.run(
                [sys.executable, "-B", str(tree / "scripts" / "build_release.py"), "--output-dir", str(output_dir)],
                cwd=tree,
                check=False,
                capture_output=True,
                text=True,
            )
            output = built.stdout + built.stderr
            self.assertNotEqual(built.returncode, 0, output)
            self.assertIn("source tree differs from authoritative shipped-file inventory", output)
            self.assertIn('unexpected: "docs/notes.md"', output)
            self.assertNotIn("Traceback", output)
            self.assertFalse(output_dir.exists())
            self.assertEqual((tree / "RELEASE_MANIFEST.json").read_bytes(), manifest_before)

    def test_missing_required_file_is_a_plain_failure_not_a_traceback(self):
        for relative, expected in (
            ("LICENSE", 'required release file(s) missing: "LICENSE"'),
            ("schemas/finding.schema.json", 'required release file(s) missing: "schemas/finding.schema.json"'),
            ("VERSION", "required release file missing or unreadable: VERSION"),
            ("RELEASE_MANIFEST.json", "required release file missing: RELEASE_MANIFEST.json"),
            ("scripts/build_release.py", "required release file(s) missing: scripts/build_release.py"),
        ):
            with self.subTest(deleted=relative):
                with tempfile.TemporaryDirectory() as tmp:
                    tree = self.build_verifiable_tree(Path(tmp))
                    (tree / relative).unlink()
                    caught = self.run_distribution_verifier(tree)
                    output = caught.stdout + caught.stderr
                    self.assertNotEqual(caught.returncode, 0, output)
                    self.assertIn(expected, output)
                    self.assertNotIn("Traceback", output)

    def test_corrupt_manifest_is_a_plain_failure_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = self.build_verifiable_tree(Path(tmp))
            (tree / "RELEASE_MANIFEST.json").write_text("{not json", encoding="utf-8")
            caught = self.run_distribution_verifier(tree)
            output = caught.stdout + caught.stderr
            self.assertNotEqual(caught.returncode, 0, output)
            self.assertIn("invalid JSON in", output)
            self.assertIn("RELEASE_MANIFEST.json", output)
            self.assertNotIn("Traceback", output)

    def test_release_manifest_rejects_duplicate_json_keys_and_file_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = self.build_verifiable_tree(Path(tmp))
            manifest_path = tree / "RELEASE_MANIFEST.json"
            original = manifest_path.read_text(encoding="utf-8")
            duplicate_key = original.replace('"package": "dravux",', '"package": "decoy",\n  "package": "dravux",', 1)
            manifest_path.write_text(duplicate_key, encoding="utf-8")
            rejected = self.run_distribution_verifier(tree)
            output = rejected.stdout + rejected.stderr
            self.assertNotEqual(rejected.returncode, 0, output)
            self.assertIn("duplicate JSON key", output)
            self.assertNotIn("Traceback", output)

            payload = json.loads(original)
            payload["files"].append(dict(payload["files"][0]))
            manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            rejected = self.run_distribution_verifier(tree)
            output = rejected.stdout + rejected.stderr
            self.assertNotEqual(rejected.returncode, 0, output)
            self.assertIn("release manifest contains duplicate file path", output)
            self.assertNotIn("Traceback", output)

    def test_structurally_malformed_release_control_json_fails_on_one_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = self.build_verifiable_tree(Path(tmp))
            control = tree / "plugins" / "dravux" / ".codex-plugin" / "plugin.json"
            control.write_text("[]\n", encoding="utf-8")
            rejected = self.run_distribution_verifier(tree)
            output = rejected.stdout + rejected.stderr
            self.assertNotEqual(rejected.returncode, 0, output)
            self.assertIn("FAIL: release verification safely rejected malformed control data", output)
            self.assertEqual(len([line for line in output.splitlines() if line]), 1)
            self.assertNotIn("Traceback", output)

            control.write_bytes(b" " * (4 * 1024 * 1024 + 1))
            rejected = self.run_distribution_verifier(tree)
            output = rejected.stdout + rejected.stderr
            self.assertNotEqual(rejected.returncode, 0, output)
            self.assertIn("4194304-byte limit", output)
            self.assertEqual(len([line for line in output.splitlines() if line]), 1)
            self.assertNotIn("Traceback", output)

    def test_builder_bootstrap_shape_failure_is_plain_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = self.build_verifiable_tree(Path(tmp))
            builder = tree / "scripts" / "build_release.py"
            text = builder.read_text(encoding="utf-8").replace("SHIPPED_FILES = (", "REMOVED_SHIPPED_FILES = (", 1)
            builder.write_text(text, encoding="utf-8")
            rejected = self.run_distribution_verifier(tree)
            output = rejected.stdout + rejected.stderr
            self.assertNotEqual(rejected.returncode, 0, output)
            self.assertIn("could not load scripts/build_release.py", output)
            self.assertEqual(len([line for line in output.splitlines() if line]), 1)
            self.assertNotIn("Traceback", output)

    def test_archive_verifier_rejects_symlink_and_special_members(self):
        import stat

        def member(name, mode, payload=b""):
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = mode << 16
            return info, payload

        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.zip"
            with zipfile.ZipFile(clean, "w") as archive:
                for info, payload in (member("dravux/", stat.S_IFDIR | 0o755), member("dravux/SKILL.md", stat.S_IFREG | 0o644, b"# x\n")):
                    archive.writestr(info, payload)
            accepted = subprocess.run(
                [sys.executable, "-B", str(SCRIPTS / "verify_distribution.py"), str(clean)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

            for kind, mode, payload in (
                ("symlink", stat.S_IFLNK | 0o777, b"../../etc/passwd"),
                ("fifo", stat.S_IFIFO | 0o644, b""),
                ("world-writable", stat.S_IFREG | 0o666, b"x"),
                ("setuid", stat.S_IFREG | 0o4755, b"x"),
            ):
                with self.subTest(kind=kind):
                    tampered = Path(tmp) / f"{kind}.zip"
                    with zipfile.ZipFile(tampered, "w") as archive:
                        for info, data in (member("dravux/SKILL.md", stat.S_IFREG | 0o644, b"# x\n"), member("dravux/link", mode, payload)):
                            archive.writestr(info, data)
                    rejected = subprocess.run(
                        [sys.executable, "-B", str(SCRIPTS / "verify_distribution.py"), str(tampered)],
                        check=False, capture_output=True, text=True,
                    )
                    output = rejected.stdout + rejected.stderr
                    self.assertNotEqual(rejected.returncode, 0, output)
                    self.assertIn("archive member", output)
                    self.assertIn("dravux/link", output)
                    self.assertNotIn("Traceback", output)

            unsafe_names = (
                ("newline", ["dravux/x\nPASS: forged\nVERIFIED: forged"]),
                ("tab", ["dravux/x\tfile"]),
                ("escape", ["dravux/x\x1bfile"]),
                ("colon", ["dravux/x:file"]),
                ("trailing-dot", ["dravux/file."]),
                ("trailing-space", ["dravux/file "]),
                ("windows-reserved", ["dravux/CON.txt"]),
                ("backslash", ["dravux\\..\\evil"]),
                ("drive", ["C:/evil"]),
                ("dot-segment", ["dravux/./evil"]),
                ("exact-collision", ["dravux/a", "dravux/a"]),
                ("casefold-collision", ["dravux/a", "dravux/A"]),
                ("unicode-collision", ["dravux/caf\u00e9", "dravux/cafe\u0301"]),
                ("combined-collision", ["dravux/\u00c5.txt", "dravux/a\u030a.txt"]),
            )
            for kind, names in unsafe_names:
                with self.subTest(kind=kind):
                    tampered = Path(tmp) / f"unsafe-{kind}.zip"
                    with zipfile.ZipFile(tampered, "w") as archive:
                        for name in names:
                            info, data = member(name, stat.S_IFREG | 0o644, b"x")
                            archive.writestr(info, data)
                    rejected = subprocess.run(
                        [sys.executable, "-B", str(SCRIPTS / "verify_distribution.py"), str(tampered)],
                        check=False, capture_output=True, text=True,
                    )
                    output = rejected.stdout + rejected.stderr
                    self.assertNotEqual(rejected.returncode, 0, output)
                    self.assertIn("archive member", output)
                    self.assertNotIn("Traceback", output)
                    self.assertFalse(any(line in {"PASS: forged", "VERIFIED: forged"} for line in output.splitlines()))

    def test_combined_collision_key_is_shared_by_archive_and_inventory_checks(self):
        import stat

        sys.path.insert(0, str(SCRIPTS))
        from build_release import SHIPPED_FILES, collision_key, inventory_collisions

        precomposed = "Å.txt"
        decomposed = "å.txt"
        self.assertNotEqual(precomposed, decomposed)
        self.assertNotEqual(precomposed.casefold(), decomposed.casefold(), "case folding alone must not be enough")
        self.assertEqual(collision_key(precomposed), collision_key(decomposed))
        self.assertEqual(collision_key("Docs/README.MD"), collision_key("docs/readme.md"))
        self.assertNotEqual(collision_key("docs/a.txt"), collision_key("docs/b.txt"))
        self.assertEqual(
            inventory_collisions(["docs/" + precomposed, "docs/b.txt", "docs/" + decomposed]),
            [["docs/" + precomposed, "docs/" + decomposed]],
        )
        self.assertEqual(inventory_collisions(SHIPPED_FILES), [], "the shipped inventory must be collision-free everywhere")

        def member(name):
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            return info

        def verify(path):
            return subprocess.run(
                [sys.executable, "-B", str(SCRIPTS / "verify_distribution.py"), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )

        with tempfile.TemporaryDirectory() as tmp:
            safe = Path(tmp) / "safe.zip"
            with zipfile.ZipFile(safe, "w") as archive:
                for name in ("dravux/" + precomposed, "dravux/b.txt", "dravux/café.txt"):
                    archive.writestr(member(name), b"x")
            accepted = verify(safe)
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

            colliding = Path(tmp) / "colliding.zip"
            with zipfile.ZipFile(colliding, "w") as archive:
                for name in ("dravux/" + precomposed, "dravux/" + decomposed):
                    archive.writestr(member(name), b"x")
            rejected = verify(colliding)
            output = rejected.stdout + rejected.stderr
            self.assertNotEqual(rejected.returncode, 0, output)
            self.assertIn("colliding archive member name", output)
            self.assertIn("combined Unicode NFC + casefold", output)
            self.assertNotIn("Traceback", output)

    def test_inventory_collisions_are_refused_by_builder_and_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = self.build_verifiable_tree(Path(tmp))
            builder = tree / "scripts" / "build_release.py"
            text = builder.read_text(encoding="utf-8")
            # "README.MD" sorts before "README.md" and collides with it on a case-insensitive filesystem.
            patched = text.replace('    "README.md",\n', '    "README.MD",\n    "README.md",\n', 1)
            self.assertNotEqual(patched, text)
            builder.write_text(patched, encoding="utf-8")

            built = subprocess.run(
                [sys.executable, "-B", str(builder), "--output-dir", str(Path(tmp) / "refused")],
                cwd=tree,
                check=False,
                capture_output=True,
                text=True,
            )
            output = built.stdout + built.stderr
            self.assertNotEqual(built.returncode, 0, output)
            self.assertIn("case- or normalization-colliding paths", output)
            self.assertIn('"README.MD"', output)
            self.assertNotIn("Traceback", output)
            self.assertFalse((Path(tmp) / "refused").exists())

            verified = self.run_distribution_verifier(tree)
            output = verified.stdout + verified.stderr
            self.assertNotEqual(verified.returncode, 0, output)
            self.assertIn("declared shipped-file list has case- or normalization-colliding paths", output)
            self.assertNotIn("Traceback", output)

    def test_archive_verifier_enforces_resource_and_metadata_limits_before_crc(self):
        import stat

        def write_zip(path, members, compression=zipfile.ZIP_DEFLATED, create_system=3):
            with zipfile.ZipFile(path, "w", compression=compression) as archive:
                for name, payload in members:
                    info = zipfile.ZipInfo(name)
                    info.create_system = create_system
                    info.compress_type = compression
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    archive.writestr(info, payload)

        def verify(path):
            return subprocess.run(
                [sys.executable, "-B", str(SCRIPTS / "verify_distribution.py"), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            boundary = base / "512-members.zip"
            write_zip(boundary, [(f"dravux/{index:03d}", b"") for index in range(512)], zipfile.ZIP_STORED)
            accepted = verify(boundary)
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

            too_many = base / "513-members.zip"
            write_zip(too_many, [(f"dravux/{index:03d}", b"") for index in range(513)], zipfile.ZIP_STORED)
            cases = [(too_many, "512-member limit")]

            oversized_archive = base / "oversized-archive.zip"
            oversized_archive.write_bytes(b"x" * (16 * 1024 * 1024 + 1))
            cases.append((oversized_archive, "16777216-byte archive limit"))

            oversized_member = base / "oversized-member.zip"
            write_zip(oversized_member, [("dravux/large", b"0" * (16 * 1024 * 1024 + 1))])
            cases.append((oversized_member, "16777216-byte limit"))

            aggregate = base / "aggregate.zip"
            write_zip(aggregate, [(f"dravux/{index}", b"0" * (13 * 1024 * 1024 + 1)) for index in range(5)])
            cases.append((aggregate, "67108864-byte aggregate uncompressed limit"))

            ratio = base / "ratio.zip"
            write_zip(ratio, [("dravux/ratio", b"0" * (1024 * 1024))])
            cases.append((ratio, "100:1 expansion limit"))

            unsupported = base / "unsupported.zip"
            write_zip(unsupported, [("dravux/bzip2", b"x")], zipfile.ZIP_BZIP2)
            cases.append((unsupported, "unsupported archive compression method"))

            non_unix = base / "non-unix.zip"
            write_zip(non_unix, [("dravux/file", b"x")], zipfile.ZIP_STORED, create_system=0)
            cases.append((non_unix, "non-Unix archive member metadata"))

            for path, expected in cases:
                with self.subTest(case=path.name):
                    rejected = verify(path)
                    output = rejected.stdout + rejected.stderr
                    self.assertNotEqual(rejected.returncode, 0, output)
                    self.assertIn(expected, output)
                    self.assertNotIn("Traceback", output)

    def test_archive_verifier_rejects_encryption_zero_size_crc_and_malformed_zip_cleanly(self):
        import stat

        def plain_archive(path, payload=b"payload"):
            info = zipfile.ZipInfo("dravux/file")
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(info, payload)

        def verify(path):
            return subprocess.run(
                [sys.executable, "-B", str(SCRIPTS / "verify_distribution.py"), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            encrypted = base / "encrypted.zip"
            plain_archive(encrypted)
            data = bytearray(encrypted.read_bytes())
            local = data.index(b"PK\x03\x04")
            central = data.index(b"PK\x01\x02")
            data[local + 6:local + 8] = (int.from_bytes(data[local + 6:local + 8], "little") | 1).to_bytes(2, "little")
            data[central + 8:central + 10] = (int.from_bytes(data[central + 8:central + 10], "little") | 1).to_bytes(2, "little")
            encrypted.write_bytes(data)

            zero_size = base / "zero-size.zip"
            plain_archive(zero_size, b"x")
            data = bytearray(zero_size.read_bytes())
            local = data.index(b"PK\x03\x04")
            central = data.index(b"PK\x01\x02")
            data[local + 18:local + 22] = b"\0" * 4
            data[central + 20:central + 24] = b"\0" * 4
            zero_size.write_bytes(data)

            crc = base / "crc.zip"
            plain_archive(crc, b"x")
            data = bytearray(crc.read_bytes())
            local = data.index(b"PK\x03\x04")
            name_length = int.from_bytes(data[local + 26:local + 28], "little")
            extra_length = int.from_bytes(data[local + 28:local + 30], "little")
            payload_offset = local + 30 + name_length + extra_length
            data[payload_offset] ^= 1
            crc.write_bytes(data)

            malformed = base / "bad\nPASS-forged.zip"
            malformed.write_bytes(b"not a zip")

            for path, expected in (
                (encrypted, "encrypted archive member"),
                (zero_size, "nonempty zero-compressed archive member"),
                (crc, "CRC"),
                (malformed, "could not verify archive"),
            ):
                with self.subTest(case=path.name):
                    rejected = verify(path)
                    output = rejected.stdout + rejected.stderr
                    self.assertNotEqual(rejected.returncode, 0, output)
                    self.assertIn(expected, output)
                    self.assertNotIn("Traceback", output)
                    self.assertFalse(any(line == "PASS-forged.zip" for line in output.splitlines()))

    def test_public_entry_points_never_write_bytecode_into_the_tree(self):
        """Stock CPython writes __pycache__ beside imported modules unless told not to.

        Apple's python3 redirects bytecode to a cache outside the tree, which would make this test
        pass for the wrong reason, so the runner forces stock behaviour with sys.pycache_prefix = None.
        """
        runner = (
            "import runpy, sys; sys.pycache_prefix = None; script = sys.argv[1]; sys.argv = sys.argv[1:]; "
            "runpy.run_path(script, run_name='__main__')"
        )
        env = {key: value for key, value in os.environ.items() if key != "PYTHONDONTWRITEBYTECODE"}
        with tempfile.TemporaryDirectory() as tmp:
            tree = copy_release_tree(Path(tmp) / "tree")
            report = Path(tmp) / "demo-report.json"
            commands = (
                ["scripts/validate_report.py", "fixtures/passing/known-pass.json"],
                ["scripts/audit_demo_html.py", "demos/github/broken/index.html", "--state", "broken", "--output", str(report)],
                ["scripts/verify_distribution.py"],
            )
            for command in commands:
                with self.subTest(command=command[0]):
                    proc = subprocess.run(
                        [sys.executable, "-c", runner, str(tree / command[0]), *command[1:]],
                        cwd=tree, env=env, check=False, capture_output=True, text=True,
                    )
                    self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            leftovers = sorted(str(path.relative_to(tree)) for path in tree.rglob("*") if path.name == "__pycache__" or path.suffix == ".pyc")
            self.assertEqual(leftovers, [], "documented commands wrote bytecode into the verified tree")

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
