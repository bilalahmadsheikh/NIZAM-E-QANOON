"""A same-issued-work decision is never a shortcut around source/release checks."""
import copy
import pytest
from tools.expression_source_variants import validate_pair,validate_approval,SCHEMA,METHOD
from tools.materialize_multi_instrument import require_whole_plan_review

def example():
 s=dict(jurisdiction='sindh',kind='act',year=1973,number='VII',document_id=9361,
        source_observation_id=13533,expression_ordinal=3,source_sha256='a'*64,duplicate_of=None)
 t=dict(s,document_id=712,source_observation_id=3285,expression_ordinal=0,source_sha256='b'*64)
 p=dict(schema=SCHEMA,method=METHOD,source=dict(document_id=9361,source_observation_id=13533,
        expression_ordinal=3,metadata=s,source_pdf_sha256=s['source_sha256'],spans=[dict(start_block_id=1,end_block_id=2)]),
        canonical=dict(document_id=712,source_observation_id=3285,expression_ordinal=0,metadata=t,
                       source_pdf_sha256=t['source_sha256'],spans=[dict(start_block_id=3,end_block_id=4)]),
        printed_issued_identity={k:s[k]for k in('jurisdiction','kind','year','number')},
        classification=dict(relation='same_issued_instrument_print_variant',actual_legal_version=False,
                            partial_copy=False,different_commencement=False,comparison_complete_for_issued_identity=True),
        comparison=dict(differences_classified=['inserted/interested'],no_word_equivalence_claim=True,
                        no_current_version_equivalence_claim=True,no_target_text_substitution=True),reviewed_files={'page.png':'c'*64},
        owner_decision=dict(document_id=9361,question_id='q5'))
 return p,s,t

def test_released_and_distinct_provenance_required():
 p,s,t=example()
 validate_pair(p,s,t,copy_released=False,target_released=True)
 for flags in [dict(copy_released=True,target_released=True),dict(copy_released=False,target_released=False),
               dict(copy_released=False,target_released=True,target_historical=True)]:
  with pytest.raises(ValueError):validate_pair(p,s,t,**flags)
 with pytest.raises(ValueError):validate_pair(p,s,dict(t,duplicate_of='another-copy'),copy_released=False,target_released=True)

@pytest.mark.parametrize('change',['jurisdiction','number','partial','historical','commencement','unreviewed','primary'])
def test_identity_metadata_and_legal_version_uncertainty_fail_closed(change):
 p,s,t=example();p=copy.deepcopy(p)
 if change in('jurisdiction','number'):t=dict(t,**{change:'different'})
 elif change=='partial':p['classification']['partial_copy']=True
 elif change=='historical':p['classification']['actual_legal_version']=True
 elif change=='commencement':p['classification']['different_commencement']=True
 elif change=='unreviewed':p['classification']['comparison_complete_for_issued_identity']=False
 else:p['source']['expression_ordinal']=0
 with pytest.raises(ValueError):validate_pair(p,s,t,copy_released=False,target_released=True)

def test_ordinary_replay_refused_even_if_all_marked_qualified():
 plan=dict(expressions=[dict(ordinal=0,source_variant_disposition={'standing':True})],qualified_expression_ordinals=[0])
 with pytest.raises(ValueError,match='source-variant'):require_whole_plan_review(plan)

def test_empty_or_partial_approval_cannot_authorize_apply():
 for approval in [dict(approved=True),dict(approved=True,reviewer='someone',remaining_findings=[],approved_hashes={})]:
  with pytest.raises(ValueError,match='Incomplete'):validate_approval(approval,'matrix.json')

@pytest.mark.parametrize('change',['outer-key','archive-sha','text-substitution','word-equivalence'])
def test_evidence_cannot_change_its_identity_or_be_used_as_text(change):
 p,s,t=example()
 if change=='outer-key':p['canonical']['source_observation_id']=123
 elif change=='archive-sha':p['source']['source_pdf_sha256']='wrong'
 elif change=='text-substitution':p['comparison']['no_target_text_substitution']=False
 else:p['comparison']['no_word_equivalence_claim']=False
 with pytest.raises(ValueError):validate_pair(p,s,t,copy_released=False,target_released=True)
