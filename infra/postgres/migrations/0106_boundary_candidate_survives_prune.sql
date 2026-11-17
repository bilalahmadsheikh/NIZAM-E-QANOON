-- A boundary candidate outlives the tree it was first recorded against (18 Nov 2026, DECISION-LOG D-071).
--
-- A segmentation_boundary_candidate is source evidence about a document's blocks: "a separate instrument starts at
-- block N", with its source_verified / owner-decided adjudications. It was keyed (NOT NULL, FK) to the instrument
-- that was active when it was recorded. A replay retires that instrument, and the retired-revision prune then
-- deleted the candidate and its adjudications with it (tools/prune_retired_instruments.sql). The 11 Nov prune
-- removed 226 candidates that 99 documents' ACTIVE expression manifests still cite, so 19 reviewed multi-expression
-- plans could no longer be re-materialised ("need a recorded confirmed_split boundary candidate").
--
-- The link to the derived tree becomes optional, as instrument_expression_manifest.materialized_instrument_id
-- already is: the prune severs it instead of deleting the evidence. The candidate keeps its observation, document
-- and block, which is what every reader of it (tools/materialize_multi_instrument.py) matches on.
--
-- REVERSAL: only once no row has a NULL instrument_id: ALTER ... SET NOT NULL.
-- Governing contract: docs/02 (multi-instrument boundaries); migrations 0038, 0063.

ALTER TABLE segmentation_boundary_candidate ALTER COLUMN instrument_id DROP NOT NULL;

COMMENT ON COLUMN segmentation_boundary_candidate.instrument_id IS
  'The instrument active when the candidate was recorded; NULL once that revision is pruned (0106). The candidate '
  'is evidence about the observation''s blocks and is never deleted with a derived tree.';
