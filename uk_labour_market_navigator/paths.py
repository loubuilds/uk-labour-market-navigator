"""Reject links consistently, including Windows junctions on Python 3.11."""

import stat
from pathlib import Path


def linked(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or getattr(info, "st_reparse_tag", 0) in (
        0xA0000003,  # IO_REPARSE_TAG_MOUNT_POINT (junction)
        0xA000000C,  # IO_REPARSE_TAG_SYMLINK
    )
