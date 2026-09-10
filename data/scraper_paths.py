"""Filesystem-safe names for scraper staging files.

Legal titles remain in the manifest.  They must not be used as filesystem
identity: long Punjab/KP rule titles exceeded Windows path limits and left five
otherwise successful official downloads as missing ``.part`` files.
"""

from __future__ import annotations

import hashlib


def short_pdf_filename(source_key: str) -> str:
    """Return a stable, collision-resistant ASCII staging name.

    ``source_key`` is normally the official URL.  Content identity is still the
    SHA-256 of downloaded bytes; this name only gets those bytes safely through
    the temporary filesystem.
    """

    digest = hashlib.sha256(source_key.encode("utf-8")).hexdigest()
    return f"download-{digest[:24]}.pdf"
