-- Replace unreliable incremental ltree GiST writes with a deterministic
-- ancestor closure backed by ordinary B-tree equality.
--
-- `provision.path` remains ltree and remains the canonical, immutable lineage.
-- `provision_ancestor` is disposable query acceleration, not source evidence:
-- one row for each path prefix lets `ancestor_path = $1::ltree` fetch an exact
-- active subtree without recursive joins or the GiST page-split failure proven
-- on observation 1397.

BEGIN;

DROP INDEX IF EXISTS provision_active_path_gist;

CREATE TABLE provision_ancestor (
    ancestor_path ltree NOT NULL,
    provision_id  uuid NOT NULL REFERENCES provision(id) ON DELETE CASCADE,
    distance      smallint NOT NULL CHECK (distance >= 0),
    PRIMARY KEY (ancestor_path, provision_id)
);
CREATE INDEX provision_ancestor_provision ON provision_ancestor(provision_id);

INSERT INTO provision_ancestor (ancestor_path,provision_id,distance)
SELECT subpath(p.path,0,n),p.id,(nlevel(p.path)-n)::smallint
  FROM provision p
  CROSS JOIN LATERAL generate_series(1,nlevel(p.path)) AS g(n)
 WHERE p.is_active;

COMMIT;
