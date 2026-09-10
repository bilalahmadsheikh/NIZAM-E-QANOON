-- 0008  a block's provision assignment dies with the provision
--
-- 0006 declared provision_block.provision_id as ON DELETE SET NULL. That fights
-- the role/provision CHECK: re-segmenting deletes the instrument, the cascade
-- tries to null the column on blocks whose role is 'body', and the CHECK -- which
-- requires body text to resolve to a provision -- refuses. Every re-segmentation
-- failed on it.
--
-- SET NULL was the wrong action anyway. A block's assignment to a provision has
-- no meaning once that provision is gone; the row is rebuilt by the next
-- segmentation, along with the tree it describes. CASCADE says exactly that.

BEGIN;

ALTER TABLE provision_block DROP CONSTRAINT provision_block_provision_id_fkey;

ALTER TABLE provision_block
    ADD CONSTRAINT provision_block_provision_id_fkey
    FOREIGN KEY (provision_id) REFERENCES provision(id) ON DELETE CASCADE;

COMMIT;
