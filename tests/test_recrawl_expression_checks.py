"""Scoped diagnostics must exclude held siblings and fail on unknown/empty scope."""
import contextlib,io,runpy,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
GOOD='This Act shall come into force at once.'
class Cursor:
 def __init__(self,missing=False,empty=False,blank=False):self.rows=[];self.calls=[];self.missing=missing;self.empty=empty;self.blank=blank
 def __enter__(self):return self
 def __exit__(self,*a):return False
 def execute(self,sql,params):
  self.calls.append((sql,params));scope=len(params)>1 and params[1]is not None
  if 'count(*) FROM instrument'in sql:self.rows=[(0 if self.missing else 1,)]
  elif 'subpath(p.path'in sql:self.rows=[]if self.empty else [('s_1',' ')]if self.blank else [('s_1',GOOD)]if scope else [('s_1',GOOD),('s_bad','GAZETTE head leaked')]
  elif 'SELECT DISTINCT trim'in sql:self.rows=[]
  elif 'string_agg'in sql:self.rows=[]if self.empty else [(68,None),(69,'   ')]if self.blank else [(68,GOOD)]if scope else [(68,GOOD),(1,'nonsensezz '*50)]
  else:raise AssertionError(sql)
 def fetchall(self):return self.rows
 def fetchone(self):return self.rows[0]if self.rows else None
class Connection:
 def __init__(self,c):self.c=c
 def __enter__(self):return self
 def __exit__(self,*a):return False
 def cursor(self):return self.c
class ExpressionCheckTests(unittest.TestCase):
 def run_check(self,name,args,**kw):
  cur=Cursor(**kw);out=io.StringIO();code=0
  with patch('nizam.storage.db.connect',return_value=Connection(cur)),patch.object(sys,'argv',[name,*args]),contextlib.redirect_stdout(out),contextlib.redirect_stderr(out):
   try:runpy.run_path(str(ROOT/'tools/recrawl'/name),run_name='__main__')
   except SystemExit as e:code=e.code
  return code,out.getvalue(),cur
 def test_expression_filters_both_leak_queries(self):
  code,out,c=self.run_check('leakscan.py',['9361','--expression','9'])
  self.assertEqual(code,0);self.assertIn('9361/e9: clean',out)
  self.assertEqual([args for sql,args in c.calls if 'subpath'in sql or 'SELECT DISTINCT trim'in sql],[(9361,9,9)]*2)
 def test_default_leak_scan_still_reports_held_damage(self):
  code,out,_=self.run_check('leakscan.py',['9361']);self.assertEqual(code,1);self.assertIn('FLAGS head',out)
 def test_scoped_text_gate_excludes_held_garble(self):
  code,out,c=self.run_check('textgate.py',['9361','--expression','9'])
  self.assertEqual(code,0);self.assertIn('9361/e9 text PASS',out)
  self.assertEqual(c.calls[-1][1],(9361,9,9))
 def test_default_text_gate_still_reports_held_damage(self):
  code,out,_=self.run_check('textgate.py',['9361']);self.assertEqual(code,1);self.assertIn('text FAIL',out)
 def test_unknown_expression_never_reports_pass(self):
  for name in ['leakscan.py','textgate.py']:
   code,_,_=self.run_check(name,['9361','--expression','99'],missing=True);self.assertNotEqual(code,0)
 def test_empty_scoped_text_never_falls_back_to_whole_raw_document(self):
  code,_,c=self.run_check('textgate.py',['9361','--expression','9'],empty=True)
  self.assertNotEqual(code,0);self.assertFalse(any('FROM text_block'in sql for sql,_ in c.calls))
 def test_empty_scoped_leak_scan_never_reports_clean(self):
  code,_,_=self.run_check('leakscan.py',['9361','--expression','9'],empty=True);self.assertNotEqual(code,0)
 def test_null_and_blank_scoped_version_rows_never_report_pass(self):
  for name in ['leakscan.py','textgate.py']:
   code,_,_=self.run_check(name,['9361','--expression','9'],blank=True);self.assertNotEqual(code,0)
if __name__=='__main__':unittest.main()
