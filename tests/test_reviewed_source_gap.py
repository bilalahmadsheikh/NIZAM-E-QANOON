"""4058 pp79-81: readable52 continuation after covered49-51, never fabricated law.

The source owner chose readable law with explicit gaps. Its existing owner-cited
opener must still fail unless the exact missing sequence and current source-level
record support it. Also test repeated-text table-cell intake (rows7 versus10).
"""
import contextlib
import copy
import pytest
from nizam.corpus.segment import segment, _apply_curation_patches, _owner_cited_label_shape_ok
from nizam.storage import legal_write as LW

def b(i,t,page=1):
    return dict(id=i,text=t,page_no=page,x0=194.5,x1=528.7,y0=100.,page_height=842.)

TAIL='in the prescribed manner, an officer of the Authority shall determine the amount in default and order its recovery in the prescribed manner.'
SPEC=dict(kind='section',printed_label=None,cited_label='52',source_block_id=569940,source_prefix=TAIL,
          owner_decision=dict(export='decision-review.json',document_id=4058,question_id='q1'),
          missing_before=['49','50','51'],source_incompleteness_id=64)
BLOCKS=[b(1,'CONTENTS\n48. Offences and Penalties.\n49. Default Surcharge.\n50. Exemption from Penalty and Default Surcharge.\n51. Compounding of Offences.\n52. Recovery of the Tax not Levied or Short-levied.\n53. Power to Summon Persons.'),
        b(2,'48. Offences and Penalties. (1) If a person commits any offence described in column2 of the Table below.',2),
        b(569940,TAIL,3),b(569941,'(7) For the purpose of this section, the expression relevant date means the time of payment of tax.',3),
        b(569942,'(8) Notwithstanding anything contained in this Act, the Authority shall have powers to regulate.',3),
        b(569948,'53. Power to Summon Persons. (1) An officer may summon any person.',3)]

def run(spec=SPEC,blocks=BLOCKS):
    return segment(blocks,profile='unreleased-v4',structural_overrides={'source_body_start_block':2,'source_owner_cited_labels':[spec]})

def test_source_gap_preserves_visible52_and_subsections_without_inventing49_51():
    s=run();ns=s.flatten();secs=[n for n in ns if n.kind=='section']
    assert [n.label for n in secs]==['48','52','53']
    p=secs[1];assert p.first_block==569940 and p.text==TAIL
    assert [c.label for c in p.children]==['7','8']
    assert p.children[0].first_block==569941 and p.children[1].first_block==569942
    assert p.printed_label_marker is None and p.owner_cited
    assert set(s.missing)=={'49','50','51'}

def test_gap_is_not_an_automatic_sequence_guard_bypass():
    plain={k:v for k,v in SPEC.items() if k not in ('missing_before','source_incompleteness_id')}
    with pytest.raises(ValueError,match='out of sequence'):run(plain)
    wrong=copy.deepcopy(BLOCKS);wrong[1]['text']=wrong[1]['text'].replace('48.','47.',1)
    with pytest.raises(ValueError,match='out of sequence'):run(blocks=wrong)
    wrong=copy.deepcopy(BLOCKS);wrong[0]['text']=wrong[0]['text'].replace('50. Exemption from Penalty and Default Surcharge.\n','')
    with pytest.raises(ValueError,match='lacks contents'):run(blocks=wrong)
    wrong=BLOCKS[:2]+[b(500,'50. Exemption from Penalty and Default Surcharge. This provision is readable.',2)]+BLOCKS[2:]
    with pytest.raises(ValueError,match='has a body node'):run(blocks=wrong)

@pytest.mark.parametrize('change',[{'missing_before':['49','51']},{'missing_before':['50','49','51']},
    {'missing_before':['49','50','51','52']},{'missing_before':[]},{'source_incompleteness_id':True},
    {'source_incompleteness_id':0},{'kind':'clause'},{'printed_label':'52'}])
def test_gap_shape_is_bounded_and_explicit(change):
    assert not _owner_cited_label_shape_ok(dict(SPEC,**change))

def test_record_must_be_current_same_source_and_exactly_bind_the_visible_opener(monkeypatch):
    binding={k:SPEC[k] for k in ('cited_label','source_block_id','source_prefix','missing_before')}
    result=[(64,'no_complete_copy_acquired',{'parser_partial_openers':[binding]})]
    class Cursor:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def execute(self,sql,args):assert args==(4058,1397)
        def fetchone(self):return result[0]
    class Conn:
        def cursor(self):return Cursor()
    @contextlib.contextmanager
    def connect():yield Conn()
    monkeypatch.setattr(LW,'connect',connect)
    over={'source_owner_cited_labels':[SPEC]}
    LW.validate_owner_cited_source_gaps(4058,1397,over)
    for bad in (None,(63,'no_complete_copy_acquired',result[0][2]),
                (64,'superseded_by_complete_copy',result[0][2]),
                (64,'no_complete_copy_acquired',{'parser_partial_openers':[dict(binding,source_block_id=99)]})):
        result[0]=bad
        with pytest.raises(ValueError,match='exactly bound'):LW.validate_owner_cited_source_gaps(4058,1397,over)

def test_exact_table_cell_locator_changes_only_named_repeated_cell():
    text='Such person shall be liable to pay a penalty.\n'
    blocks=[b(7,text+'Further penalty.\n'),b(10,text)]
    patch=dict(page_no=1,match_text=text,before_text=text,after_text='Such person shall be liable to pay\n',
               evidence=dict(exact_block_locator=True,source_block_id=10))
    with pytest.raises(ValueError,match='matched 2'):_apply_curation_patches(blocks,[{**patch,'evidence':{}}])
    out,n=_apply_curation_patches(blocks,[patch])
    assert n==1 and out[0]==blocks[0] and out[1]['text']==patch['after_text']
    assert blocks[1]['text']==text # immutable extraction
    for changes in ({'page_no':2},{'before_text':text.strip()},{'evidence':dict(exact_block_locator=True,source_block_id=99)}):
        with pytest.raises(ValueError):_apply_curation_patches(blocks,[{**patch,**changes}])
