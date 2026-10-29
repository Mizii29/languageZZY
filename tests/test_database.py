import tempfile,sqlite3,unittest,threading
from pathlib import Path
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from zzy.embedding import load_module
from zzy.diagnostics import DiagnosticError,Cancelled,ResourceExceeded
from zzy.resources import CancellationToken,ResourcePolicy

class DatabaseTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.db=self.root/'data.sqlite3'
  self.path=self.root/'app.zzy'
  self.path.write_text('''(addnew) work(sql,params,ok) {
   (addnew) callback() {
    db.query("CREATE TABLE IF NOT EXISTS items (value TEXT)",[]);
    (zno) rows := db.query(sql,params);
    (zif?:) ok { (return) (^_^)(rows); }
    (return) (T_T)("rollback");
   }
   (?_?) db.transaction("PATH",callback) {
    (^_^)(value) => { (return) value; }
    (T_T)(message) => { (return) message; }
   }
  }'''.replace('PATH',self.db.as_posix()),encoding='utf-8')
  self.module=load_module(self.path)
 def tearDown(self):self.module.close();self.tmp.cleanup()
 def test_commit_binding_rollback_and_reopen(self):
  text="x'); DROP TABLE items; --"
  self.module.call('work','INSERT INTO items VALUES (?)',[text],True)
  self.module.call('work','INSERT INTO items VALUES (?)',['bad'],False)
  self.assertEqual(self.module.call('work','SELECT value FROM items',[],True).value,[[text]])
  with load_module(self.path) as other:self.assertEqual(other.call('work','SELECT count(*) FROM items',[],True).value,[[1]])
 def test_failures_cleanup_and_recovery(self):
  connections=[];original=sqlite3.connect
  def observed(*a,**kw):
   c=original(*a,**kw);connections.append(c);return c
  with patch('sqlite3.connect',observed):
   for sql,params in [('SELECT ?',[]),('COMMIT',[]),('PRAGMA user_version',[]),('ATTACH DATABASE ? AS x',['x']),('SELECT 1; SELECT 2',[]),('SELECT ?', [True]),('SELECT ?', [2**63]),("SELECT x'ff'",[])]:
    with self.subTest(sql=sql),self.assertRaises(DiagnosticError):self.module.call('work',sql,params,True)
  for c in connections:
   with self.assertRaises(sqlite3.ProgrammingError):c.execute('SELECT 1')
  self.assertEqual(self.module.call('work','SELECT ?', [7],True).value,[[7]])
 def test_parallel_requests(self):
  with ThreadPoolExecutor(4) as pool:list(pool.map(lambda i:self.module.call('work','INSERT INTO items VALUES (?)',[str(i)],True),range(12)))
  self.assertEqual(self.module.call('work','SELECT count(*) FROM items',[],True).value,[[12]])
 def test_cancel_and_resource_rollback(self):
  token=CancellationToken();timer=threading.Timer(.05,token.cancel);timer.start()
  sql='WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT sum(x) FROM n'
  try:
   with self.assertRaises(Cancelled):self.module.call('work',sql,[],True,cancellation=token)
  finally:timer.cancel();timer.join()
  with load_module(self.path,policy=ResourcePolicy({'container_items':2})) as small:
   with self.assertRaises(ResourceExceeded):small.call('work','SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3',[],True)
  self.assertEqual(self.module.call('work','SELECT count(*) FROM items',[],True).value,[[0]])
 def test_check_never_opens_database(self):
  import subprocess,sys
  r=subprocess.run([sys.executable,'-m','zzy','check',str(self.path)],capture_output=True)
  self.assertEqual((r.returncode,r.stdout,r.stderr),(0,b'',b''));self.assertFalse(self.db.exists())

 def test_write_then_exception_rolls_back_and_lock_timeout(self):
  source=self.path.read_text().replace('(zno) rows := db.query(sql,params);','db.query("INSERT INTO items VALUES (?)",["pending"]); (zno) rows := db.query(sql,params);')
  self.path.write_text(source)
  with load_module(self.path) as module:
   with self.assertRaises(DiagnosticError):module.call('work','bad sql',[],True)
  with closing(sqlite3.connect(self.db)) as c:self.assertEqual(c.execute("SELECT name FROM sqlite_master WHERE name='items'").fetchall(),[])
  self.module.call('work','SELECT 1',[],True)
  c=sqlite3.connect(self.db);c.execute('BEGIN IMMEDIATE')
  try:
   with self.assertRaises(DiagnosticError):self.module.call('work','SELECT 1',[],True)
  finally:c.rollback();c.close()
  self.assertEqual(self.module.call('work','SELECT count(*) FROM items',[],True).value,[[0]])
