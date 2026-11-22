-- 0121  Whether a judgment's citation names its law, or takes the law the judgment last named (DECISION-LOG D-123).
--
-- Judgments name a law once ("section 497 of the Code of Criminal Procedure") and then cite its sections bare
-- ("section 497(2)", "the said section 498"). Of 3,800 citations in a 150-judgment dry run, 1,848 named no law. A
-- bare citation takes the law last named for the same kind of unit (section or article) earlier in the same
-- judgment, and is recorded 'inherited' so it is never mistaken for a citation that names its law. With no earlier
-- named law it stays 'no_law_named'. No default law is assumed: a bare "Article 129" may be the Qanun-e-Shahadat's.

BEGIN;
ALTER TABLE judgment_statute_reference
    ADD COLUMN law_basis text NOT NULL DEFAULT 'named' CHECK (law_basis IN ('named', 'inherited')),
    ADD COLUMN inherited_from text;              -- the earlier citation, as printed, whose law it takes
ALTER TABLE judgment_statute_reference
    ADD CONSTRAINT ck_jsr_inherited CHECK ((law_basis = 'inherited') = (inherited_from IS NOT NULL));
COMMIT;
