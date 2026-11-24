-- 0131  A judgment's citation is linked to every copy of the provision it names (DECISION-LOG D-136).
--
-- judgment_statute_reference.alternates holds the same provision in the law's other copies: a Lahore judgment
-- citing s.302 PPC is linked to the federal Code and, as an alternate, to the Punjab Code's s.302, where the two
-- units are the same provision (nizam.storage.judgment_linking.same_provision). 'Cases on this section' and the
-- precedent search read the alternates as links, so the Punjab copy finds the judgment too. This index serves the
-- overlap test (alternates && <the section and its sub-units>). The table is derived and small (56 MB).

BEGIN;
CREATE INDEX IF NOT EXISTS ix_jsr_alternates ON judgment_statute_reference USING gin (alternates);
COMMIT;
