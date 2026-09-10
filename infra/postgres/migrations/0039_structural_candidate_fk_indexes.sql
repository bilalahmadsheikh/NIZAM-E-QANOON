-- Deleting an archived provision asks every referencing foreign key whether a
-- live row still points at it.  The candidate table was indexed by instrument,
-- but not by the three provision FK columns, turning an offline archive prune
-- into one full candidate-table scan per retired provision.
BEGIN;

CREATE INDEX structural_candidate_candidate_provision
    ON segmentation_structural_candidate(candidate_provision_id);
CREATE INDEX structural_candidate_canonical_provision
    ON segmentation_structural_candidate(canonical_provision_id);
CREATE INDEX structural_candidate_parent_provision
    ON segmentation_structural_candidate(parent_provision_id)
    WHERE parent_provision_id IS NOT NULL;

COMMIT;
