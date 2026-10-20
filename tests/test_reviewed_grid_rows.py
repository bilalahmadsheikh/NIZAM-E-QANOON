"""Exact, source-backed grids: 4058 penalty columns and tariff identities.

Column ordering across a page break is not document reordering. The raw block
ledger remains untouched and all source cells must have one explicit owner.
"""
import copy
import pytest
from nizam.corpus.segment import segment, reviewed_grid_row_shape_ok
from nizam.workers.segment import reviewed_structural_overrides

def b(i,text,page=1):
    return dict(id=i,text=text,page_no=page,x0=200.,x1=500.,y0=100.,page_height=842.)

BLOCKS=[b(1,'48. Offences and Penalties. (1) A person committing an offence is liable.'),
        b(2,'(2) The sections in column4 are illustrative only.'),
        b(3,'5\nWhere a person without reasonable cause fails to produce the'),
        b(4,'Such person shall pay a penalty of twenty five thousand rupees'),
        b(5,'30, 32, 53 and 57'),
        b(6,'despite receipt of a notice from the Authority.',2),
        b(7,'for subsequent default.',2),
        b(8,'6\nAny person who knowingly or fraudulently submits a false document.',2),
        b(9,'Such person shall pay a penalty of twenty thousand rupees.',2),
        b(10,'General',2),
        b(11,'53. Power to Summon. (1) An officer may summon any person.',2)]
ROWS=[dict(source_block_id=3,source_prefix='5\nWhere a person',label='5',kind='clause',parent_block_id=2,cells=[[3,6],[4,7],[5]]),
      dict(source_block_id=8,source_prefix='6\nAny person',label='6',kind='clause',parent_block_id=2,cells=[[8],[9],[10]])]

def test_full_cells_cross_pages_without_interleaving_or_changing_raw_source():
    before=copy.deepcopy(BLOCKS)
    seg=segment(BLOCKS,profile='unreleased-v4',structural_overrides={'source_reviewed_grid_rows':ROWS})
    rows=[n for n in seg.flatten() if n.kind=='clause']
    assert [n.label for n in rows]==['5','6']
    assert rows[0].parent.label=='2' and rows[0].parent.parent.label=='48'
    assert rows[0].text_parts==[
        'Where a person without reasonable cause fails to produce the despite receipt of a notice from the Authority.',
        'Such person shall pay a penalty of twenty five thousand rupees for subsequent default.',
        '30, 32, 53 and 57']
    assert (rows[0].first_page,rows[0].last_page)==(1,2)
    assert rows[0].blocks==[3,6,4,7,5]
    assert [n.label for n in seg.flatten() if n.kind=='section']==['48','53']
    assert all(seg.block_roles[i][1] is rows[0] for i in (3,4,5,6,7))
    assert BLOCKS==before

def test_source_printed_tariffs_and_rates_cannot_become_sections_or_change_parents():
    blocks=[b(1,'FIRST SCHEDULE\nClassification of Services'),b(2,'98.03 Transportation or travelling of passengers.'),
            b(3,'803.1000 Travelling of passengers by road, rail, aircraft and ship whether in, from or to Balochistan.'),
            b(4,'9803.2000 Travelling of passengers by road, rail, aircraft and ship embarking for international journey from Balochistan.'),
            b(5,'SECOND SCHEDULE\nTaxable Services',2),
            b(7,'9812.9500 Services provided by vehicle tracking companies.',2),b(8,'19.5%',2)]
    spec=[dict(source_block_id=2,source_prefix='98.03 Transportation',label='98.03',kind='section',parent_block_id=1,cells=[[2]]),
          dict(source_block_id=3,source_prefix='803.1000 Travelling',label='803.1000',kind='clause',parent_block_id=2,cells=[[3]]),
          dict(source_block_id=4,source_prefix='9803.2000 Travelling',label='9803.2000',kind='clause',parent_block_id=2,cells=[[4]]),
          dict(source_block_id=7,source_prefix='9812.9500 Services',label='9812.9500',kind='section',parent_block_id=5,cells=[[7],[8]])]
    seg=segment(blocks,profile='unreleased-v4',structural_overrides={'source_schedule_heading_blocks':[1,5],'source_reviewed_grid_rows':spec})
    by={n.first_block:n for n in seg.flatten()}
    assert by[3].label=='803.1000' and by[3].parent is by[2] # no invented leading9
    assert by[4].parent is by[2]
    assert by[7].parent is by[5] and by[7].text.endswith('19.5%')
    assert not any(n.label=='19' for n in seg.flatten())

@pytest.mark.parametrize('change',[{'source_prefix':'6 Wrong prefix'}, {'parent_block_id':999},
    {'cells':[[3,6],[4,7],[5,6]]},{'label':'05'},{'kind':'item'}])
def test_stale_ambiguous_or_invented_source_data_fails_closed(change):
    rows=[dict(ROWS[0],**change),ROWS[1]]
    with pytest.raises(ValueError):segment(BLOCKS,structural_overrides={'source_reviewed_grid_rows':rows})

def test_overlapping_cell_ownership_and_future_parent_fail_closed():
    for rows in ([ROWS[0],dict(ROWS[1],cells=[[8],[9],[5]])],
                 [dict(ROWS[0],parent_block_id=8),ROWS[1]]):
        with pytest.raises(ValueError):segment(BLOCKS,structural_overrides={'source_reviewed_grid_rows':rows})

def test_race_club_rates_remain_with_their_actual_qualifier():
    blocks=[b(1,'SECOND SCHEDULE\nTaxable Services'),b(2,'9831.0000\nRace clubs:'),
            b(3,'(a)\nServices of entry/admissions Rs.200 per entry ticket or entry pass of a person visiting the race events.'),
            b(4,'(b)\nOther services.\n15%'),b(5,'9832.0000\nLabour and manpower supply services.\n15%')]
    rows=[dict(source_block_id=2,source_prefix='9831.0000\nRace clubs:',label='9831.0000',kind='section',parent_block_id=1,cells=[[2]]),
          dict(source_block_id=3,source_prefix='(a)\nServices of entry',label='a',kind='clause',parent_block_id=2,cells=[[3]]),
          dict(source_block_id=4,source_prefix='(b)\nOther services.',label='b',kind='clause',parent_block_id=2,cells=[[4]]),
          dict(source_block_id=5,source_prefix='9832.0000\nLabour',label='9832.0000',kind='section',parent_block_id=1,cells=[[5]])]
    seg=segment(blocks,profile='unreleased-v4',structural_overrides={'source_schedule_heading_blocks':[1],'source_reviewed_grid_rows':rows})
    ns={n.first_block:n for n in seg.flatten()}
    assert ns[3].parent is ns[2] and ns[4].parent is ns[2] and ns[5].parent is ns[1]
    assert 'Rs.200' in ns[3].text and '15%' not in ns[3].text
    assert ns[4].text=='Other services. 15%'

def test_merge_and_intake_keys_preserve_grid_specs():
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import STRUCTURAL_KEYS,GENERIC_STRUCTURAL_KEYS,named_block_ids
    key='source_reviewed_grid_rows'
    assert all(reviewed_grid_row_shape_ok(r) for r in ROWS)
    assert key in STRUCTURAL_PATCH_KEYS and key in STRUCTURAL_KEYS and key in GENERIC_STRUCTURAL_KEYS
    patch=lambda rows:{'evidence':{'structural_overrides':{key:rows}}}
    assert reviewed_structural_overrides([],[patch(ROWS[:1]),patch(ROWS[1:])])[key]==ROWS
    assert named_block_ids({key:ROWS})==set(range(2,11))
    with pytest.raises(ValueError,match='conflicting'):
        reviewed_structural_overrides([],[patch(ROWS),patch([dict(ROWS[0],parent_block_id=1)])])
