#!/usr/bin/env python3
"""Bind installer finalization and cleanup to the directories validated before copying."""

import ctypes
import grp
import json
import os
import platform
import pwd
import shlex
import shutil
import stat
import sys
import tempfile
import unicodedata
from contextlib import contextmanager


class UnsafeDirectoryError(ValueError):
    """An unsafe install parent must keep the installer's refusal exit code."""


def check_entry(status, path, installed=False, private_group=False):
    owner = os.getuid()
    if status.st_uid not in ({owner} if installed else {owner, 0}):
        required = "the current user (uid " + str(owner) + ")" + ("" if installed else " or root (uid 0)")
        raise UnsafeDirectoryError(path + " is owned by uid " + str(status.st_uid)
                                   + "; must belong to " + required)
    if installed and status.st_mode & 0o7000:
        raise UnsafeDirectoryError("setuid, setgid or sticky bit on " + path)
    if status.st_mode & 0o002:
        raise UnsafeDirectoryError("world-writable install entry: " + path
                                   + "; remove world write with chmod o-w " + shlex.quote(path))
    if status.st_mode & 0o020:
        if not private_group:
            reason = "group-writable entries are not allowed here"
        elif status.st_uid != owner:
            reason = "group-writable entry must have the current user as owner"
        elif status.st_gid != os.getgid():
            reason = "group-writable entry must use the user's primary group"
        else:
            try:
                user = pwd.getpwuid(owner).pw_name
                group = grp.getgrgid(status.st_gid)
                # Primary-group members need not appear in gr_mem.
                shared = any(member != user for member in group.gr_mem) or any(
                    account.pw_gid == status.st_gid and account.pw_uid != owner
                    for account in pwd.getpwall()
                )
            except (KeyError, OSError):
                reason = "could not verify private primary group membership"
            else:
                reason = "primary group has another account as a member" if shared else None
        if reason:
            raise UnsafeDirectoryError(reason + ": " + path
                                       + "; remove group write with chmod g-w " + shlex.quote(path))


def check_chain(base, candidates, installed=False):
    base = os.path.realpath(base)
    for index, candidate in enumerate(candidates):
        try:
            status = os.lstat(candidate)
        except FileNotFoundError:
            if not installed:
                continue
            raise
        if not stat.S_ISDIR(status.st_mode):
            raise UnsafeDirectoryError("install parent is not a directory or is a symlink: " + candidate)
        if os.path.commonpath((base, os.path.realpath(candidate))) != base:
            raise UnsafeDirectoryError("install parent escapes selected base: " + candidate)
        check_entry(status, candidate, installed=installed and index >= 2, private_group=index < 2)


def check_installed_tree(destination):
    def failed(error):
        raise error

    for parent, directories, files in os.walk(destination, onerror=failed, followlinks=False):
        for path in [parent] + [os.path.join(parent, name) for name in directories + files]:
            check_entry(os.lstat(path), path, installed=True)


def _validate_path_text(path):
    for character in path:
        if unicodedata.category(character) in {"Cc", "Cs", "Zl", "Zp"} or character in (
            "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff"
        ):
            raise ValueError("install base path contains U+{:04X}".format(ord(character)))


def resolve_base(path, project):
    _validate_path_text(path)
    if project:
        # Strip trailing slash/dot spellings without resolving a symlink first.
        named = path
        while named not in {"", "/"} and named.endswith(("/", "/.")):
            named = (named[:-2] if named.endswith("/.") else named[:-1]) or "/"
        named = os.path.join(os.getcwd(), named)
        status = os.lstat(named)
        if not stat.S_ISDIR(status.st_mode):
            raise ValueError("project directory must exist and must not be a symlink")
    os.chdir(path)
    if project:
        entered = os.stat(".")
        status = os.lstat(named)
        if not stat.S_ISDIR(status.st_mode) or (entered.st_dev, entered.st_ino) != (status.st_dev, status.st_ino):
            raise ValueError("project directory changed while entering it")
    physical = os.getcwd()
    _validate_path_text(physical)
    print(physical)


@contextmanager
def held_tree(base, platform, staging=None):
    """Open each install component without following links; keep all descriptors alive."""
    if platform not in {".agents", ".claude"} or (
        staging is not None and (not staging.startswith(".dravux-install.") or "/" in staging)
    ):
        raise ValueError("invalid installer path component")
    descriptors = []
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptors.append(os.open(base, flags))
        path = base
        for component in (platform, "skills") + ((staging,) if staging is not None else ()):
            descriptor = os.open(component, flags, dir_fd=descriptors[-1])
            descriptors.append(descriptor)
            path = os.path.join(path, component)
            check_entry(os.fstat(descriptor), path,
                        private_group=component in {platform, "skills"})
        identities = [[os.fstat(fd).st_dev, os.fstat(fd).st_ino] for fd in descriptors]
        yield descriptors, identities
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def record_staging(base, platform):
    with held_tree(base, platform) as (parents, parent_identities):
        os.fchdir(parents[-1])
        staging = os.path.basename(tempfile.mkdtemp(prefix=".dravux-install.", dir="."))
        created = os.stat(staging, dir_fd=parents[-1], follow_symlinks=False)
        try:
            with held_tree(base, platform, staging) as (_, identities):
                if identities != parent_identities + [[created.st_dev, created.st_ino]]:
                    raise OSError("install directory changed while recording staging")
                print(staging, json.dumps(identities, separators=(",", ":")), flush=True)
        except BaseException:
            current = os.stat(staging, dir_fd=parents[-1], follow_symlinks=False)
            if (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
                os.rmdir(staging, dir_fd=parents[-1])
            raise


def exclusive_rename(parent, source):
    """Atomic directory publication, refusing every existing destination type."""
    libc = ctypes.CDLL(None, use_errno=True)
    arguments = (parent, os.fsencode(source), parent, b"dravux", 1)
    argument_types = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    if sys.platform.startswith("linux"):
        try:
            rename = libc.renameat2
        except AttributeError:
            machine = platform.machine()
            number = {"x86_64": 316, "aarch64": 276, "armv7": 382, "armv7l": 382,
                      "i386": 353, "i686": 353, "i586": 353,
                      "ppc64le": 357, "s390x": 347, "riscv64": 276}.get(machine)
            if number is None:
                raise OSError("atomic exclusive rename unsupported on architecture " + machine)
            try:
                rename = libc.syscall
            except AttributeError:
                raise OSError("atomic exclusive rename syscall is unavailable")
            arguments = (number,) + arguments
            argument_types = [ctypes.c_long] + argument_types
    elif sys.platform == "darwin":
        rename = libc.renameatx_np
        arguments = arguments[:-1] + (4,)  # Darwin RENAME_EXCL; Linux uses RENAME_NOREPLACE (1).
    else:
        raise OSError("atomic exclusive rename is unsupported on this platform")
    try:
        rename.argtypes = argument_types
        rename.restype = ctypes.c_long if len(arguments) == 6 else ctypes.c_int
        result = rename(*arguments)
    except (AttributeError, TypeError, ctypes.ArgumentError) as error:
        raise OSError("atomic exclusive rename is unavailable: " + str(error))
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, "atomic exclusive rename failed: " + os.strerror(error))


def main():
    if sys.argv[1] in {"parents", "verify-parents"}:
        check_chain(sys.argv[2], sys.argv[3:], installed=sys.argv[1] == "verify-parents")
        return
    if sys.argv[1] == "verify-tree":
        check_installed_tree(sys.argv[2])
        return
    if sys.argv[1] in {"project", "home"}:
        resolve_base(sys.argv[2], sys.argv[1] == "project")
        return
    if sys.argv[1] == "record":
        record_staging(*sys.argv[2:4])
        return
    command, base, platform, staging = sys.argv[1:5]
    if command not in {"finalize", "cleanup"}:
        raise ValueError("unknown installer safety command")
    with held_tree(base, platform, staging) as (descriptors, identities):
        if identities != json.loads(sys.argv[5]):
            raise OSError("install directory identity changed since staging was created")
        if command == "finalize":
            exclusive_rename(descriptors[-2], staging)
        else:
            # In this short-lived process, a held cwd keeps cleanup inside the verified parent.
            # shutil.rmtree uses its fd-based, symlink-resistant implementation on supported OSes.
            if not shutil.rmtree.avoids_symlink_attacks:
                raise OSError("safe staging cleanup is unsupported on this platform")
            os.fchdir(descriptors[-2])
            shutil.rmtree(staging)


if __name__ == "__main__":
    try:
        main()
    except (OSError, AttributeError, ValueError, NotImplementedError) as error:
        print("Installer safety check failed: " + ascii(str(error)), file=sys.stderr)
        raise SystemExit(4 if isinstance(error, UnsafeDirectoryError) else 1)
