#!/usr/bin/env python3
"""Bind installer finalization and cleanup to the directories validated before copying."""

import ctypes
import json
import os
import shutil
import stat
import sys
import tempfile
import unicodedata
from contextlib import contextmanager


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
        for component in (platform, "skills") + ((staging,) if staging is not None else ()):
            descriptor = os.open(component, flags, dir_fd=descriptors[-1])
            descriptors.append(descriptor)
            if stat.S_IMODE(os.fstat(descriptor).st_mode) & 0o022:
                raise OSError("install directory is group/world-writable")
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
    if sys.platform.startswith("linux"):
        rename = libc.renameat2
        flags = 1  # Linux RENAME_NOREPLACE
    elif sys.platform == "darwin":
        rename = libc.renameatx_np
        flags = 4  # Darwin RENAME_EXCL
    else:
        raise OSError("atomic exclusive rename is unsupported on this platform")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(parent, os.fsencode(source), parent, b"dravux", flags) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def main():
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
        raise SystemExit(1)
