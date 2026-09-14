"""Pinned common identities, independently reproduced from source classifications."""

import json

from ._source import RESOURCES, sha256

REFERENCE_HASH = "943cc315a17453e9284a169917fded1860109de9cdd4182621b16ecf8af1087d"


def reference():
    body = (RESOURCES / "identities.json").read_bytes()
    if sha256(body) != REFERENCE_HASH:
        raise ValueError("The common occupation and district identities failed verification.")
    return json.loads(body)
