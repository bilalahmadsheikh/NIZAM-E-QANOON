"""Build the word list the judgment text-quality gate reads (D-130, gate J9).

    python tools/build_judgment_vocab.py

The words (three letters or more, case folded) that occur in at least MIN_DOCS released Supreme Court judgments, read
from typed text layers (nizam.judgment parser, released before 23 Nov 2026). Written to
nizam/corpus/data/judgment_vocab.txt, one word per line, sorted. The file is versioned with the parser: rebuilding it
changes which files pass J9, so it is rebuilt only with a parser version bump.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nizam.storage.db import connect  # noqa: E402

MIN_DOCS = 3
OUT = ROOT / "nizam" / "corpus" / "data" / "judgment_vocab.txt"


def main() -> int:
    df: collections.Counter = collections.Counter()
    with connect() as conn, conn.cursor(name="vocab") as cur:
        cur.itersize = 2000
        cur.execute("""SELECT p.judgment_id, p.text FROM v_release_judgment_paragraph p
                         JOIN judgment j ON j.id = p.judgment_id AND j.decided_on = p.decided_on
                        WHERE j.court_code = 'SC' AND p.kind = 'body' ORDER BY p.judgment_id""")
        current, words = None, set()
        for jid, text in cur:
            if jid != current:
                df.update(words)
                current, words = jid, set()
            words.update(re.findall(r"[a-z]{3,}", text.lower()))
        df.update(words)
    vocab = sorted(w for w, n in df.items() if n >= MIN_DOCS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(vocab) + "\n", encoding="utf-8")
    print(f"{len(vocab):,} words in at least {MIN_DOCS} SC judgments -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
