import pytest
from nizam.workers.segment import reviewed_structural_overrides

def merge(source=2573742,parent=2573737,parent_label='VIII',kind='part'):
    item=dict(source_block_id=source,source_kind='part',source_label='SECOND MATE (FOREIGN-GOING)',parent_block_id=parent,parent_kind='chapter',parent_label=parent_label,kind=kind)
    return reviewed_structural_overrides([], [dict(evidence={'structural_overrides':{'source_reparent_blocks':[item]}})])

def test_reviewed_9617_caption_can_return_to_its_printed_chapter():
    assert merge()['source_reparent_blocks'][0]['source_block_id']==2573742

@pytest.mark.parametrize('kwargs',[{'source':123},{'parent':123},{'parent_label':'VII'},{'kind':'section'}])
def test_unrelated_division_reparent_is_not_admitted(kwargs):
    with pytest.raises(ValueError):merge(**kwargs)
