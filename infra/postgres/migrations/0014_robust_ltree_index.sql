-- The default ltree GiST signature is only 8 bytes.  At corpus scale, with
-- preserved expression revisions sharing stable paths, it repeatedly reached
-- `failed to add item to index page` even for a measured 66-byte path.  A wider
-- signature reduces lossy collisions while leaving every provision row and the
-- exact per-instrument btree uniqueness constraint untouched.
DROP INDEX IF EXISTS provision_path_gist;
CREATE INDEX provision_path_gist
    ON provision USING gist (path gist_ltree_ops(siglen=64));
