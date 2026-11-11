"""An ordinary replay cannot turn identity-only drafts into released laws."""
import sys,unittest
from unittest.mock import patch
from tools import materialize_multi_instrument as materializer
from tools.materialize_multi_instrument import require_whole_plan_review
class PartialReviewTests(unittest.TestCase):
 def plan(self,qualified):return dict(expressions=[dict(ordinal=0),dict(ordinal=1)],qualified_expression_ordinals=qualified)
 def test_identity_only_sibling_blocks_whole_plan_publication(self):
  with self.assertRaisesRegex(ValueError,'whole-plan --apply refused'):require_whole_plan_review(self.plan([1]))
 def test_every_expression_reviewed_allows_whole_plan(self):require_whole_plan_review(self.plan([0,1]))
 def test_legacy_full_review_plan_unchanged(self):require_whole_plan_review(dict(expressions=[dict(ordinal=0)]));require_whole_plan_review(None)
 def test_malformed_or_foreign_qualifications_fail(self):
  for values in [None,'all',[1,1],[2],[True]]:
   with self.subTest(values=values),self.assertRaises(ValueError):require_whole_plan_review(self.plan(values))
 def test_apply_refuses_partial_plan_before_any_database_build(self):
  with patch.object(sys,'argv',['materializer','--document','9361','--apply']),patch.object(materializer,'load_plan',return_value=self.plan([1])),patch.object(materializer,'prepare')as prepare,patch.object(materializer,'same_blob_observation_problem')as same_blob:
   with self.assertRaisesRegex(ValueError,'whole-plan --apply refused'):materializer.main()
   prepare.assert_not_called();same_blob.assert_not_called()
if __name__=='__main__':unittest.main()
