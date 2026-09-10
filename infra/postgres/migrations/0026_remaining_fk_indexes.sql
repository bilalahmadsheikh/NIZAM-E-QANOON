-- PostgreSQL does not index the referencing side of a foreign key.  Revision
-- archival deletes an instrument only after its derived children are removed;
-- without these indexes each FK check scans the surviving table once per
-- retired instrument (9,340 scans in the clean-v5 prune).
BEGIN;

CREATE INDEX block_assignment_instrument
    ON block_assignment_set(instrument_id) WHERE instrument_id IS NOT NULL;
CREATE INDEX instrument_repealed_by
    ON instrument(repealed_by_id) WHERE repealed_by_id IS NOT NULL;
CREATE INDEX instrument_status_assertion_instrument
    ON instrument_status_assertion(instrument_id);
CREATE INDEX provision_version_amended_by
    ON provision_version(amended_by_id) WHERE amended_by_id IS NOT NULL;
CREATE INDEX segmentation_run_instrument
    ON segmentation_run(instrument_id) WHERE instrument_id IS NOT NULL;

COMMIT;
