"""A promoted extraction can be curated before its first successful tree.

Exercise the actual query against PostgreSQL-shaped tables in SQLite, so
same-SHA, activity and released-predecessor refusals test predicates rather
than mocked query text. No corpus database is mutated.
"""
import sqlite3
import pytest
from tools.record_curation_patch import observation_rows_for_patch, patch_observations


class Cursor:
    def __init__(self):
        self.db=sqlite3.connect(':memory:');self.cur=self.db.cursor()
        self.cur.executescript('''
          CREATE TABLE document(id INTEGER,is_active BOOLEAN,supersedes_document_id INTEGER,sha256 TEXT);
          CREATE TABLE instrument(document_id INTEGER,is_active BOOLEAN,source_observation_id INTEGER,source_sha256 TEXT);
          CREATE TABLE source_observation(id INTEGER,sha256 TEXT);
          CREATE TABLE v_release_instrument(source_observation_id INTEGER,document_id INTEGER);
          INSERT INTO document VALUES(1,false,NULL,'a'),(2,true,1,'a');
          INSERT INTO instrument VALUES(1,true,7,'a');
          INSERT INTO source_observation VALUES(7,'a');
        ''')
    def execute(self,sql,args=()):self.cur.execute(sql.replace('%s','?'),args)
    def fetchall(self):return self.cur.fetchall()


def test_promoted_revision_keeps_same_observation_without_bootstrap_tree():
    cur=Cursor()
    assert observation_rows_for_patch(cur,2)==[(7,'a')]
    assert patch_observations(observation_rows_for_patch(cur,2),False)==([7],None)
    assert cur.db.execute('SELECT count(*) FROM instrument').fetchone()==(1,)


@pytest.mark.parametrize('change',[
    "UPDATE document SET sha256='other' WHERE id=2",
    "UPDATE document SET is_active=false WHERE id=2",
    "UPDATE document SET is_active=true WHERE id=1",
    "UPDATE document SET supersedes_document_id=NULL WHERE id=2",
    "UPDATE instrument SET source_sha256='other'",
    "UPDATE source_observation SET sha256='other'",
    "UPDATE instrument SET is_active=false",
    "INSERT INTO v_release_instrument VALUES(7,1)",
    "INSERT INTO v_release_instrument VALUES(99,1)",
])
def test_invalid_or_released_predecessor_cannot_supply_observation(change):
    cur=Cursor();cur.db.execute(change)
    assert observation_rows_for_patch(cur,2)==[]


def test_ordinary_path_wins_and_duplicate_observations_still_checked():
    cur=Cursor();cur.db.executescript("INSERT INTO instrument VALUES(2,true,8,'b'); INSERT INTO source_observation VALUES(8,'b');")
    assert observation_rows_for_patch(cur,2)==[(8,'b')]
    cur.db.executescript("INSERT INTO instrument VALUES(2,true,9,'c'); INSERT INTO source_observation VALUES(9,'c');")
    rows=observation_rows_for_patch(cur,2)
    obs,why=patch_observations(rows,False)
    assert obs==[] and 'different blobs' in why
