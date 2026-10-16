#!/usr/bin/env python3
"""Bind installer finalization and cleanup to the directories validated before copying."""

import ctypes
import json
import os
import shutil
import stat
import sys
from contextlib import contextmanager


@contextmanager
def held_tree(base, platform, staging):
    """Open each install component without following links; keep all descriptors alive."""
    if platform not in {".agents", ".claude"} or not staging.startswith(".dravux-install.") or "/" in staging:
        raise ValueError("invalid installer path component")
    descriptors = []
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptors.append(os.open(base, flags))
        for component in (platform, "skills", staging):
            descriptor = os.open(component, flags, dir_fd=descriptors[-1])
            descriptors.append(descriptor)
            if stat.S_IMODE(os.fstat(descriptor).st_mode) & 0o022:
                raise OSError("install directory is group/world-writable")
        identities = [[os.fstat(fd).st_dev, os.fstat(fd).st_ino] for fd in descriptors]
        yield descriptors, identities
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


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
    command, base, platform, staging = sys.argv[1:5]
    if command not in {"record", "finalize", "cleanup"}:
        raise ValueError("unknown installer safety command")
    with held_tree(base, platform, staging) as (descriptors, identities):
        if command == "record":
            print(json.dumps(identities, separators=(",", ":")))
            return
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
