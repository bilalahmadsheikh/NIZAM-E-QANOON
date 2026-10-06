"""Pin a source observation to a segmentation profile.

docs/SEGMENTATION-PROFILES.md. A pin is how a blocked document is parsed with
rules the released corpus has not been reviewed under: every later build of
the observation -- the worker, the multi-instrument materializer, the stale-
tree and fingerprint tools -- reads the pin and parses under that profile.

WHAT IT REFUSES, before the database trigger would:

  * a non-default profile for an observation with a released instrument. That
    would re-parse a released tree under unreviewed rules;
  * returning a RELEASED observation to 'default' unless --allow-released is
    given. A document released under a profile loses the repair that released
    it; that is a released-tree correction and needs its own review;
  * a pin identical to the observation's current one.

Preview first, pin second:

    python -m nizam.workers.segment --documents 1014 --redo --dry-run \\
        --profile unreleased-v1
    python tools/pin_segmentation_profile.py --documents 1014 \\
        --profile unreleased-v1 --reason "contents one off from body; ..."
    python tools/pin_segmentation_profile.py ... --apply

Append-only: a new pin supersedes the observation's latest one and leaves it
in place (migration 0056).
"""
from __future__ import annotations

import argparse
import json
import sys

from nizam.corpus.segment import SEGMENTATION_PROFILES
from nizam.storage.db import connect
from nizam.workers.segment import SEGMENTER

PINNED_BY = "claude.segmentation-profile-pin/1"

OBSERVATIONS = """
SELECT DISTINCT i.document_id, i.source_observation_id
  FROM instrument i
 WHERE i.is_active AND i.document_id = ANY(%s)
 ORDER BY 1, 2
"""

STATE = """
SELECT (SELECT p.id FROM v_segmentation_profile_latest p
         WHERE p.source_observation_id = %(obs)s),
       (SELECT p.profile FROM v_segmentation_profile_latest p
         WHERE p.source_observation_id = %(obs)s),
       EXISTS (SELECT 1 FROM v_release_instrument r
                WHERE r.source_observation_id = %(obs)s)
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--documents", required=True,
                    help="comma- or space-separated document ids")
    ap.add_argument("--observation", type=int,
                    help="pin only this observation of a shared document")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--evidence",
                    help="JSON object stored with every pin, or @FILE holding one")
    ap.add_argument("--allow-released", action="store_true",
                    help="permit returning a released observation to 'default'")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--pinned-by", default=PINNED_BY,
                    help="reviewer identifier stored with this profile pin")
    a = ap.parse_args()

    if a.profile not in SEGMENTATION_PROFILES:
        ap.error(f"unknown profile {a.profile!r}; one of "
                 f"{sorted(SEGMENTATION_PROFILES)}")
    if len(a.reason.strip()) < 20:
        ap.error("--reason must say what the pin is for")
    raw = a.evidence or ""
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8-sig") as handle:
            raw = handle.read()
    extra = json.loads(raw) if raw else {}
    if not isinstance(extra, dict):
        ap.error("--evidence must be a JSON object")
    documents = sorted({int(v) for v in a.documents.replace(",", " ").split()})

    planned, refused = [], []
    with connect() as conn, conn.cursor() as cur:
        cur.execute(OBSERVATIONS, (documents,))
        pairs = cur.fetchall()
        found = {doc for doc, _ in pairs}
        for doc in sorted(set(documents) - found):
            refused.append((f"doc {doc}", "no active instrument"))
        for doc, obs in pairs:
            where = f"doc {doc} obs {obs}"
            if a.observation is not None and obs != a.observation:
                continue
            cur.execute(STATE, {"obs": obs})
            latest_id, latest_profile, released = cur.fetchone()
            current = latest_profile or "default"
            if released and a.profile != "default":
                refused.append((where, "has a released instrument; a profile "
                                "pin cannot re-parse it"))
                continue
            if released and not a.allow_released:
                refused.append((where, "is released; returning it to 'default' "
                                "is a released-tree correction "
                                "(--allow-released)"))
                continue
            if current == a.profile:
                refused.append((where, f"already parsed under {current!r}"))
                continue
            planned.append({"document_id": doc, "observation": obs,
                            "from": current, "supersedes": latest_id,
                            "released": released})

        print(f"documents   : {len(documents)}")
        print(f"  will pin  : {len(planned)} -> {a.profile}")
        print(f"  refused   : {len(refused)}")
        for where, why in refused:
            print(f"    {where}: {why}")
        for p in planned:
            print(f"    doc {p['document_id']} obs {p['observation']}: "
                  f"{p['from']} -> {a.profile}")
        if not a.apply:
            print("\ndry run -- pass --apply to record these pins")
            return 0

        for p in planned:
            evidence = {"tool": "tools/pin_segmentation_profile.py",
                        "segmenter": SEGMENTER,
                        "document_id": p["document_id"],
                        "released_at_pin": p["released"],
                        **extra}
            cur.execute("""
                INSERT INTO segmentation_profile_pin
                    (source_observation_id, profile, reason, evidence,
                     pinned_by, supersedes_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (p["observation"], a.profile, a.reason.strip(),
                  json.dumps(evidence, ensure_ascii=False), a.pinned_by,
                  p["supersedes"]))
        conn.commit()
        print(f"\npinned {len(planned)} observation(s); replay them with "
              "python -m nizam.workers.segment --documents ... --redo")
    return 0 if not refused or planned else 1


if __name__ == "__main__":
    sys.exit(main())
