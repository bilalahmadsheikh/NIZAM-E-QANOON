"""ab_openers.py : A/B for a parser change touching reviewed printed rule openers -- every released document whose
recorded patches carry source_printed_rule_openers is re-segmented in memory with the current segment.py and compared
with its stored tree as a multiset of (kind, label, text length). Prints SAME / DIFF per document. Read-only."""
import collections, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.corpus import segment as S
from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.workers.segment import reviewed_structural_overrides
import os, re
if os.environ.get("NEUTRAL"):   # baseline: rule reviewed_series_regulation disabled (its label pattern matches nothing)
    S._SERIES_LABEL = re.compile(r"(?!x)x")
ONLY = {int(x) for x in os.environ.get("ONLY", "").split(",") if x}
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT DISTINCT i.document_id, i.source_observation_id FROM instrument i
                    JOIN v_release_instrument r ON r.id=i.id
                    JOIN segmentation_curation_patch p ON p.source_observation_id=i.source_observation_id AND p.retired_at IS NULL
                   WHERE p.evidence::text LIKE '%%source_printed_rule_openers%%' AND i.expression_role='primary'""")
    docs = cur.fetchall()
    same = diff = fail = 0
    for doc, obs in sorted(docs):
        if ONLY and doc not in ONLY:
            continue
        cur.execute("""SELECT p.kind::text, p.label, length(coalesce(v.text_en,'')) FROM provision p
                        JOIN instrument i ON i.id=p.instrument_id AND i.is_active AND i.duplicate_of IS NULL
                        LEFT JOIN provision_version v ON v.provision_id=p.id
                       WHERE i.document_id=%s AND p.is_active AND nlevel(p.path) > 3""", (doc,))
        stored = collections.Counter(cur.fetchall())
        try:
            prof = legal_write.segmentation_profile_for(obs)
            patches = legal_write.segmentation_patches_for(obs)
            res = legal_write.structural_resolutions_for(doc)
            seg = S.segment(legal_write.blocks_for(doc), curation_patches=patches,
                            toc_dispositions=legal_write.toc_dispositions_for(obs), structural_resolutions=res,
                            structural_overrides=reviewed_structural_overrides(res, patches) or None,
                            **({} if prof == "default" else {"profile": prof}))
        except Exception as x:
            fail += 1; print(f"{doc} FAIL {type(x).__name__}: {str(x)[:100]}"); continue
        now = collections.Counter((n.kind, n.label, len(n.text or "")) for n in seg.flatten() if n.parent is not None)
        if now == stored:
            same += 1
        else:
            diff += 1; print(f"{doc} DIFF stored-only {sum((stored - now).values())} now-only {sum((now - stored).values())}")
    print(f"{len(docs)} documents: SAME {same}, DIFF {diff}, FAIL {fail}")
