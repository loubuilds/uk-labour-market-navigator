"""Local provider input boundaries; no account reads or external dependencies."""

import json
import re
from pathlib import Path

from .paths import linked
from .workflow import public_text


def public_context(value, field):
    clean = public_text(value, 120)
    if (
        clean != value
        or " ".join(clean.split()) != clean
        or re.search(r"[<>]|\b(?:employer|client|employee)\s*[:=]", clean, re.I)
    ):
        raise ValueError("Use a short public role/place without private fields or markup.")
    if re.search(
        r"(?<!\w)(?:\+44\s?|0)[127](?:[\d ()-]){8,13}(?!\d)|/(?:Users|home)/|bearer\s+\S+|sk-(?:ant-|proj-)?[A-Za-z0-9_-]{10,}|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|(?:token|api[_-]?key|password|secret)\s*[=:]",
        clean,
        re.I,
    ):
        raise ValueError("Remove contact details and private access information.")
    return clean


def unlinked(path):
    path = Path(path)
    if any(linked(p) for p in (path, *path.parents)):
        raise ValueError("Linked private-state paths are not supported.")
    return path


def read_json(path):
    return json.loads(unlinked(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = unlinked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = unlinked(path.with_name("." + path.name + ".tmp"))
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)
