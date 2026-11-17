-- One line of key=value pairs that identifies a corpus state.  export.sh
-- writes it into the manifest; restore.sh recomputes it after a restore and
-- the two must be equal.  Counts are read, never asserted: this compares two
-- databases, it does not encode today's measurement.
SELECT concat_ws(' ',
  'migrations=' || (SELECT count(*) FROM schema_migration),
  'last_migration=' || (SELECT max(version) FROM schema_migration),
  'documents=' || (SELECT count(*) FROM document),
  'active_instruments=' || (SELECT count(*) FROM instrument WHERE is_active),
  'released_instruments=' || (SELECT count(*) FROM v_release_instrument),
  'active_provisions=' || (SELECT count(*) FROM provision WHERE is_active),
  'provision_versions=' || (SELECT count(*) FROM provision_version),
  'text_blocks=' || (SELECT count(*) FROM text_block),
  'serving_laws=' || (SELECT count(*) FROM mv_instrument_serving),
  'serving_provisions=' || (SELECT count(*) FROM mv_provision_text_known_from));
