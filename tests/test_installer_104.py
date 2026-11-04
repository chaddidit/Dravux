"""Ownership, private-group, and exclusive-rename regressions for WP-A."""

import ctypes
import errno
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("install_safety_104", ROOT / "scripts/install_safety.py")
safety = importlib.util.module_from_spec(spec)
spec.loader.exec_module(safety)


class Installer104Tests(unittest.TestCase):
    def run_script(self, script, project, platform=".agents", personal=False, hook=""):
        with tempfile.TemporaryDirectory() as tmp:
            wrapper = Path(tmp) / "python3"
            wrapper.write_text(
                "#!" + sys.executable + "\nimport os, sys, runpy, stat, grp, pwd\n"
                + "from types import SimpleNamespace\n" + hook
                + "\nsys.argv = sys.argv[2:]\n"
                + "if sys.argv[0] == '-c':\n"
                + "    code = sys.argv[1]; sys.argv = ['-c'] + sys.argv[2:]\n"
                + "    exec(code, {'__name__': '__main__'})\n"
                + "else:\n    sys.path.insert(0, os.path.dirname(sys.argv[0]))\n"
                + "    runpy.run_path(sys.argv[0], run_name='__main__')\n",
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            return subprocess.run(
                ["sh", str(ROOT / script), "--claude" if platform == ".claude" else "--codex"]
                + (["--personal"] if personal else ["--project-dir", str(project)]),
                env=dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"],
                         HOME=str(project), PYTHONDONTWRITEBYTECODE="1"),
                capture_output=True, text=True, timeout=30,
            )

    def changed_status(self, target, field, value, held_only=False):
        return """
target = os.stat({target!r})
def changed(status):
    if (status.st_dev, status.st_ino) == (target.st_dev, target.st_ino):
        values = list(status); values[{field}] = {value}
        return os.stat_result(values)
    return status
real_fstat = os.fstat
os.fstat = lambda *a, **kw: changed(real_fstat(*a, **kw))
{lstat}
""".format(target=str(target), field=field, value=value, lstat="" if held_only else """
real_lstat = os.lstat
os.lstat = lambda *a, **kw: changed(real_lstat(*a, **kw))
""")

    def test_foreign_owned_parents_refused_before_creating_anything(self):
        for platform in (".agents", ".claude"):
            for component in (platform, platform + "/skills"):
                for personal in (False, True):
                    with self.subTest(component=component, personal=personal), tempfile.TemporaryDirectory() as tmp:
                        project = Path(tmp).resolve()
                        target = project / component
                        target.mkdir(parents=True)
                        before = sorted(project.rglob("*"))
                        result = self.run_script("install.sh", project, platform, personal,
                                                 self.changed_status(target, 4, os.getuid() + 10000))
                        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
                        self.assertIn("owner", result.stderr)
                        self.assertEqual(sorted(project.rglob("*")), before)

    def test_held_descriptors_recheck_owner_and_return_exit_four(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            target = project / ".agents/skills"
            target.mkdir(parents=True)
            result = self.run_script("install.sh", project,
                                     hook=self.changed_status(target, 4, os.getuid() + 10000, held_only=True))
            self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
            self.assertEqual(list(target.iterdir()), [])

    def test_root_owned_nonwritable_parents_are_allowed(self):
        for platform in (".claude", ".agents"):
            for component in (platform, platform + "/skills"):
                for personal in (False, True):
                    with self.subTest(component=component, personal=personal), tempfile.TemporaryDirectory() as tmp:
                        project = Path(tmp).resolve()
                        target = project / component
                        target.mkdir(parents=True)
                        hook = self.changed_status(target, 4, 0)
                        for script in ("install.sh", "verify-install.sh"):
                            result = self.run_script(script, project, platform, personal, hook)
                            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_owner_refusal_names_owner_and_required_ownership(self):
        foreign = os.getuid() + 10000
        for installed in (False, True):
            for owner in ({foreign} if not installed else {foreign, 0} - {os.getuid()}):
                with self.subTest(installed=installed, owner=owner):
                    status = SimpleNamespace(st_uid=owner, st_mode=stat.S_IFDIR | 0o755)
                    with self.assertRaises(safety.UnsafeDirectoryError) as raised:
                        safety.check_entry(status, "/test/entry", installed=installed)
                    message = str(raised.exception)
                    self.assertIn("owned by uid " + str(owner), message)
                    self.assertIn("must belong to the current user (uid " + str(os.getuid()) + ")", message)
                    self.assertEqual("or root (uid 0)" in message, not installed)
                    self.assertNotIn("chmod", message)

    def test_owner_refusal_shell_summaries_keep_the_helper_reason(self):
        for phase in ("initial", "created", "final", "verify"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp).resolve()
                target = project / ".agents"
                target.mkdir()
                skills = target / "skills"
                if phase == "verify":
                    result = self.run_script("install.sh", project)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                condition = {
                    "initial": "True",
                    "created": "os.path.isdir({!r})".format(str(skills)),
                    "final": "os.path.isdir({0!r}) and any(n.startswith('.dravux-install.') for n in os.listdir({0!r}))".format(str(skills)),
                    "verify": "True",
                }[phase]
                command = "verify-parents" if phase == "verify" else "parents"
                hook = "if len(sys.argv) > 3 and sys.argv[3] == {!r} and {}:\n".format(command, condition)
                hook += "\n".join("    " + line for line in self.changed_status(target, 4, os.getuid() + 10000).splitlines())
                result = self.run_script("verify-install.sh" if phase == "verify" else "install.sh",
                                         project, hook=hook)
                self.assertEqual(result.returncode, 5 if phase == "verify" else 4, result.stdout + result.stderr)
                self.assertIn("owned by uid " + str(os.getuid() + 10000), result.stderr)
                self.assertIn("has an unsafe owner, group or mode", result.stderr)
                self.assertNotIn("escap", result.stderr)
                self.assertNotIn("group/world-writable", result.stderr)
                self.assertNotIn("chmod", result.stderr)
                if phase != "verify":
                    self.assertFalse((skills / "dravux").exists())

    def test_private_primary_group_parents_install_and_verify(self):
        hook = ("grp.getgrgid = lambda gid: SimpleNamespace(gr_mem=[pwd.getpwuid(os.getuid()).pw_name])\n"
                "pwd.getpwall = lambda: [pwd.getpwuid(os.getuid())]\n")
        for platform in (".claude", ".agents"):
            for personal in (False, True):
                with self.subTest(platform=platform, personal=personal), tempfile.TemporaryDirectory() as tmp:
                    project = Path(tmp).resolve()
                    skills = project / platform / "skills"
                    skills.mkdir(parents=True)
                    for parent in (skills.parent, skills):
                        parent.chmod(0o775)
                    for script in ("install.sh", "verify-install.sh"):
                        result = self.run_script(script, project, platform, personal, hook)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(stat.S_IMODE(skills.stat().st_mode), 0o775)

    def test_unsafe_writable_parents_explain_refusal_and_remedy(self):
        private = ("grp.getgrgid = lambda gid: SimpleNamespace(gr_mem=[])\n"
                   "pwd.getpwall = lambda: [pwd.getpwuid(os.getuid())]\n")
        cases = (
            (0o775, "grp.getgrgid = lambda gid: SimpleNamespace(gr_mem=['another-account'])\n", "member"),
            (0o775, private + "os.getgid = lambda: -1\n", "primary group"),
            (0o775, private, "owner"),
            (0o777, private, "world-writable"),
            (0o775, "def missing_group(gid): raise KeyError(gid)\ngrp.getgrgid = missing_group\n", "group"),
            (0o775, private + "pwd.getpwall = lambda: [SimpleNamespace(pw_gid=os.getgid(), pw_uid=-1)]\n", "member"),
        )
        for platform in (".claude", ".agents"):
            for component in (platform, platform + "/skills"):
                for mode, hook, reason in cases:
                    with self.subTest(component=component, reason=reason), tempfile.TemporaryDirectory() as tmp:
                        project = Path(tmp).resolve()
                        target = project / component
                        target.mkdir(parents=True)
                        target.chmod(mode)
                        if reason == "owner":
                            hook += self.changed_status(target, 4, 0 if os.getuid() else 10000)
                        result = self.run_script("install.sh", project, platform, hook=hook)
                        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
                        self.assertIn(reason, result.stderr)
                        self.assertIn("chmod " + ("o-w " if mode & 0o002 else "g-w ") + str(target), result.stderr)
                        self.assertFalse((project / platform / "skills/dravux").exists())

    def test_unavailable_linux_rename_installs_nothing_and_cleans_staging(self):
        for condition in ("ENOSYS", "EINVAL", "architecture", "missing-syscall", "cannot-run"):
            with self.subTest(condition=condition), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp).resolve()
                hook = """
if len(sys.argv) > 3 and sys.argv[2].endswith('install_safety.py') and sys.argv[3] == 'finalize':
    import ctypes, errno, platform
    from unittest.mock import Mock
    sys.platform = 'linux'
    platform.machine = lambda: 'unknown-cpu' if CONDITION == 'architecture' else 'x86_64'
    libc = SimpleNamespace()
    if CONDITION != 'missing-syscall':
        libc.syscall = Mock(return_value=-1, side_effect=TypeError('cannot run') if CONDITION == 'cannot-run' else None)
    ctypes.CDLL = lambda *a, **kw: libc
    ctypes.get_errno = lambda: getattr(errno, CONDITION, errno.ENOSYS)
""".replace("CONDITION", repr(condition))
                result = self.run_script("install.sh", project, hook=hook)
                self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
                self.assertIn("exclusive rename", result.stderr)
                self.assertEqual(list((project / ".agents/skills").iterdir()), [])
                self.assertNotIn("INSTALLED:", result.stdout)

    def test_verifier_rejects_foreign_owners_and_all_special_mode_bits(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            installed = self.run_script("install.sh", project)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            destination = project / ".agents/skills/dravux"
            for relative in (".", "scripts", "SKILL.md"):
                target = destination / relative
                for owner in {0, os.getuid() + 10000} - {os.getuid()}:
                    with self.subTest(relative=relative, owner=owner):
                        result = self.run_script("verify-install.sh", project,
                                                 hook=self.changed_status(target, 4, owner))
                        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
                        self.assertIn("owner", result.stderr)
                mode = target.stat().st_mode
                for bit in (stat.S_ISUID, stat.S_ISGID, stat.S_ISVTX):
                    with self.subTest(relative=relative, bit=oct(bit)):
                        target.chmod(stat.S_IMODE(mode) | bit)
                        try:
                            # Some macOS volumes strip setuid/setgid even after a successful chmod.
                            hook = "" if target.lstat().st_mode & bit else self.changed_status(target, 0, mode | bit)
                            result = self.run_script("verify-install.sh", project, hook=hook)
                            self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
                            self.assertIn("setuid, setgid or sticky", result.stderr)
                        finally:
                            target.chmod(stat.S_IMODE(mode))


class ExclusiveRename104Tests(unittest.TestCase):
    def rename(self, libc, machine="x86_64"):
        with patch.object(safety.sys, "platform", "linux"), \
                patch("platform.machine", return_value=machine), \
                patch.object(safety.ctypes, "CDLL", return_value=libc):
            safety.exclusive_rename(42, ".dravux-install.test")

    def test_libc_symbol_keeps_noreplace(self):
        rename = Mock(return_value=0)
        syscall = Mock()
        self.rename(SimpleNamespace(renameat2=rename, syscall=syscall))
        rename.assert_called_once_with(42, b".dravux-install.test", 42, b"dravux", 1)
        syscall.assert_not_called()

    def test_missing_libc_symbol_uses_each_declared_syscall_number(self):
        for machine, number in (("x86_64", 316), ("aarch64", 276), ("armv7", 382),
                                ("i386", 353), ("ppc64le", 357), ("s390x", 347), ("riscv64", 276)):
            with self.subTest(machine=machine):
                syscall = Mock(return_value=0)
                self.rename(SimpleNamespace(syscall=syscall), machine)
                syscall.assert_called_once_with(number, 42, b".dravux-install.test", 42, b"dravux", 1)
                self.assertEqual(syscall.restype, ctypes.c_long)

    def test_32bit_x86_machine_aliases_use_noreplace_syscall(self):
        for machine in ("i686", "i586"):
            with self.subTest(machine=machine):
                syscall = Mock(return_value=0)
                self.rename(SimpleNamespace(syscall=syscall), machine)
                syscall.assert_called_once_with(353, 42, b".dravux-install.test", 42, b"dravux", 1)

    def test_unsupported_syscall_paths_refuse_without_replacing(self):
        syscall = Mock(return_value=0)
        with self.assertRaisesRegex(OSError, "unsupported.*architecture"):
            self.rename(SimpleNamespace(syscall=syscall), "unknown-cpu")
        syscall.assert_not_called()
        for error in (errno.ENOSYS, errno.EINVAL, errno.EEXIST):
            with self.subTest(error=error), patch.object(safety.ctypes, "get_errno", return_value=error):
                syscall = Mock(return_value=-1)
                with self.assertRaises(OSError) as raised:
                    self.rename(SimpleNamespace(syscall=syscall))
                self.assertEqual(raised.exception.errno, error)
                self.assertIn("exclusive rename", str(raised.exception))
                self.assertEqual(syscall.call_count, 1)
        for libc in (SimpleNamespace(), SimpleNamespace(syscall=Mock(side_effect=TypeError("cannot run")))):
            with self.subTest(libc=libc), self.assertRaisesRegex(OSError, "exclusive rename.*unavailable"):
                self.rename(libc)


if __name__ == "__main__":
    unittest.main()
