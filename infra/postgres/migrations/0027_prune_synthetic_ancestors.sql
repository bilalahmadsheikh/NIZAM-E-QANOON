-- provision_ancestor accelerates subtree lookup; it is not source evidence.
-- Migration 0018 expanded every ltree prefix, including the three labels that
-- identify the observation (jurisdiction.kind.year_number).  Those prefixes
-- are not provisions and no provision-rooted subtree query can address them.
-- Keep only closure rows whose ancestor_path names a real, active provision in
-- the same instrument.  Canonical provision.path, parent_id, text, and source
-- evidence are untouched.

BEGIN;

DELETE FROM provision_ancestor a
 WHERE NOT EXISTS (
       SELECT 1
         FROM provision child
         JOIN provision ancestor
           ON ancestor.instrument_id = child.instrument_id
          AND ancestor.path = a.ancestor_path
          AND ancestor.is_active
        WHERE child.id = a.provision_id
          AND child.is_active
 );

COMMENT ON TABLE provision_ancestor IS
    'Disposable active-provision closure. Contains self plus real parent_id ancestors only; synthetic ltree identity prefixes are excluded.';

COMMIT;
