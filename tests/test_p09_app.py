"""Campus business is ZZY; Python supplies fixtures and independent expectations."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tests.blackbox import ROOT
from tests.test_p05_integration import quote
from zzy.diagnostics import Phase
from zzy.interpreter import Interpreter
from zzy.native import files
from zzy.output import Output
from zzy.prepare import prepare
from zzy.process import ProcessTree, run_bounded
from zzy.resources import ResourceMeter, ResourcePolicy
from zzy.source import SourceLoader

APP = ROOT / 'apps/zzy-campus'
CONFIG = APP / 'limits.json'
MAIN = APP / 'main.zzy'
MENU = '1列表 2新增 3编辑 4删除 5完成 6筛选 7排序 8统计 9导出 10保存 11打开 12撤销 13重做 0退出> '
INTRO = 'ZZY 校园任务管家 v1\n1新建 2打开 0退出> '
HEADER = 'id\ttitle\tcategory\tpriority\tdone\n'


def document(tasks=(), next_id=1):
    return dict(schema_version=1, next_id=next_id, tasks=list(tasks))


def task(id=1, title='作业', category='课程', priority=3, done=False):
    return dict(id=id, title=title, category=category, priority=priority, done=done)


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def banner(count, next_id, dirty):
    return f'任务数={count} next_id={next_id} 未保存={str(dirty).lower()}\n'+MENU


class CampusAppTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='ZZY 校园 app ')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def cli(self, source=MAIN, stdin='', mode='run', timeout=30):
        return run_bounded([sys.executable, '-X', 'utf8', '-m', 'zzy', mode, str(source),
                            '--limits', str(CONFIG), '--diagnostic-format', 'json'],
                           cwd=self.root, env=dict(os.environ, PYTHONPATH=str(ROOT)),
                           stdin=stdin.encode('utf-8'), timeout=timeout)

    def run_ok(self, source=MAIN, stdin='', timeout=30):
        status, out, err = self.cli(source, stdin, timeout=timeout)
        self.assertEqual((status, err), (0, b''), err.decode('utf-8'))
        return out.decode('utf-8')

    def write_json(self, name, value):
        path = self.root/name
        path.write_text(compact(value), encoding='utf-8')
        return path

    def program(self, body):
        imports = ''.join(f'(use) {quote(APP/(name+".zzy"))} (as) {name};\n'
                          for name in ('model','validation','tasks','views','storage','session'))
        path = self.root/'probe.zzy'
        path.write_text(imports + body, encoding='utf-8')
        return path

    def test_fixed_startup_eof_and_check(self):
        self.assertEqual(self.run_ok(stdin='0\n'), INTRO+'再见\n')
        self.assertEqual(self.run_ok(), INTRO+'再见\n')
        self.assertEqual(self.run_ok(stdin='1\n'), INTRO+'已新建\n'+banner(0,1,True)+
                         '输入结束：有未保存修改，未自动保存\n再见\n')
        sentinel = self.write_json('existing.json', document())
        original = sentinel.read_bytes()
        self.assertEqual(self.cli(stdin='1\n10\nexisting.json\n1\n',mode='check'), (0,b'',b''))
        self.assertEqual(sentinel.read_bytes(),original)
        self.assertEqual({p.name for p in self.root.iterdir()}, {'existing.json'})

    def test_real_menu_save_restart_and_exact_output(self):
        script = '1\n2\n作业\n课程\n3\n1\n10\ntasks.json\n1\n0\n'
        want = INTRO+'已新建\n'+banner(0,1,True)
        want += '标题> 分类> 优先级1低/2中/3高> 1提交 2重填 0取消> 已更新\n'+banner(1,2,True)
        want += '保存路径> 保存到：tasks.json\n1确认写入(可能覆盖) 0取消> 保存成功\n'+banner(1,2,False)+'再见\n'
        self.assertEqual(self.run_ok(stdin=script),want)
        saved=document([task()],2)
        self.assertEqual((self.root/'tasks.json').read_bytes(),compact(saved).encode())
        want=INTRO+'打开路径> 打开成功\n'+banner(1,2,False)+HEADER+'1\t作业\t课程\t3\tfalse\n共1项\n'+banner(1,2,False)+'再见\n'
        self.assertEqual(self.run_ok(stdin='2\ntasks.json\n1\n0\n'),want)
        self.assertEqual(list(self.root.glob('.zzy-*.tmp')),[])

    def test_crud_filter_sort_stats_and_export(self):
        self.write_json('tasks.json',document([task(),task(2,'读书','生活',1),task(3,'实验','课程',3)],4))
        script=('2\ntasks.json\n3\n2\n阅读\n学习\n2\n1\n5\n1\n1\n4\n3\n1\n'
                '2\n新作业\n课程\n3\n1\n6\n课程\n3\n0\n作业\n7\n2\n1\n9\nreport.tsv\n1\n8\n10\n1\n0\n')
        out=self.run_ok(stdin=script)
        self.assertIn('1\t作业\t课程\t3\ttrue\n4\t新作业\t课程\t3\tfalse\n共2项\n',out)
        self.assertIn('{"total":3,"done":1,"pending":2,"priority":[0,1,2],"categories":{"课程":2,"学习":1}}\n',out)
        self.assertEqual((self.root/'report.tsv').read_text(encoding='utf-8'),HEADER+'1\t作业\t课程\t3\ttrue\n4\t新作业\t课程\t3\tfalse\n')
        self.assertEqual(json.loads((self.root/'tasks.json').read_text(encoding='utf-8')),
                         document([task(done=True),task(2,'阅读','学习',2),task(4,'新作业')],5))
        self.assertNotIn('失败：',out)

    def test_validation_matrix_fixed_independent_errors(self):
        cases=json.loads((ROOT/'tests/p09/validation-cases.json').read_text(encoding='utf-8'))
        self.assertEqual(len(cases),160)
        self.assertEqual(len({c['id'] for c in cases}),160)
        self.write_json('matrix.json',[c['value'] for c in cases])
        actual=self.run_ok(ROOT/'tests/p09/drivers/validate.zzy')
        self.assertEqual(actual,''.join(c['stdout'] for c in cases))

    def test_bad_json_encoding_missing_and_empty_files(self):
        source=ROOT/'tests/p09/drivers/load.zzy'
        for raw in (b'',b'{',b'null x',b'{"schema_version":1,"schema_version":1}',b'NaN',b'1e400',b'"\\ud800"',b'\xff'):
            with self.subTest(raw=raw):
                (self.root/'case.json').write_bytes(raw)
                out=self.run_ok(source)
                self.assertTrue(out.startswith('FAIL:'),out)
                self.assertEqual((self.root/'case.json').read_bytes(),raw)
        (self.root/'case.json').unlink()
        self.assertTrue(self.run_ok(source).startswith('FAIL:I/O failed:'))

    def test_load_commit_is_all_or_nothing_and_success_resets_history(self):
        self.write_json('bad.json',document([task(),task(2,priority=True)],3))
        self.write_json('good.json',document([task(42,'新文件')],43))
        source=self.program('(addnew) run() -> (Result) {\n    (zno) state := model.fresh();\n    session.commit(state, tasks.add(state.document, "old", "c", 1)?);\n    session.save(state, "old.json")?;\n    session.commit(state, tasks.edit(state.document, 1, "edited", "c", 2)?);\n    (?_?) session.load(state, "bad.json") { (T_T)(message) => { io.print(message); } _ => { io.print("WRONG"); } }\n    io.print(storage.encode(state.document)?);\n    io.print([state.path, model.dirty(state), len(state.undo), len(state.redo)]);\n    session.load(state, "good.json")?;\n    io.print(storage.encode(state.document)?);\n    io.print([state.path, model.dirty(state), len(state.undo), len(state.redo)]);\n    (return) (^_^)((null));\n}\nrun();')
        self.assertEqual(self.run_ok(source),'tasks[1].priority: 需要整数\n'+
            compact(document([task(title='edited',category='c',priority=2)],2))+'\n[old.json, true, 2, 0]\n'+
            compact(document([task(42,'新文件')],43))+'\n[good.json, false, 0, 0]\n')

    def test_history_alias_dirty_highwater_and_redo_branch(self):
        source=self.program('(addnew) run() -> (Result) {\n    (zno) state := model.fresh();\n    session.commit(state, tasks.add(state.document, "a", "c", 1)?);\n    session.save(state, "state.json")?;\n    session.commit(state, tasks.edit(state.document, 1, "b", "c", 3)?);\n    session.undo(state)?;\n    io.print([state.document.tasks[0].title, model.dirty(state)]);\n    session.redo(state)?;\n    session.save(state, "state.json")?;\n    session.undo(state)?;\n    io.print([state.document.tasks[0].title, model.dirty(state)]);\n    session.undo(state)?;\n    io.print([len(state.document.tasks), state.document.next_id]);\n    session.commit(state, tasks.add(state.document, "new", "c", 2)?);\n    io.print([state.document.tasks[0].id, state.document.next_id, len(state.redo)]);\n    io.print(session.redo(state));\n    io.print(session.commit(state, tasks.edit(state.document, 2, "new", "c", 2)?));\n    (return) (^_^)((null));\n}\nrun();')
        self.assertEqual(self.run_ok(source),'[a, false]\n[a, true]\n[0, 2]\n[2, 3, 0]\n(T_T)(没有可重做操作)\n没有变化\n')

    def test_history_99_100_101_and_empty_undo(self):
        source=self.program('(addnew) run() -> (Result) {\n    (zno) state := model.fresh();\n    io.print(session.undo(state));\n    (for) index (in) 0..<101 {\n        (zno) message := session.commit(state, tasks.add(state.document, str(index), "c", 1)?);\n        (zif?:) index >= 98 { io.print([len(state.undo), message]); }\n    }\n    (for) index (in) 0..<100 { session.undo(state)?; }\n    io.print([len(state.document.tasks), state.document.next_id, len(state.redo)]);\n    io.print(session.undo(state));\n    (for) index (in) 0..<100 { session.redo(state)?; }\n    io.print([len(state.document.tasks), state.document.next_id, len(state.undo)]);\n    (return) (^_^)((null));\n}\nrun();')
        self.assertEqual(self.run_ok(source,timeout=60),'(T_T)(没有可撤销操作)\n[99, 已更新]\n[100, 已更新]\n[100, 已更新；历史已满，丢弃最旧一步]\n[1, 102, 100]\n(T_T)(没有可撤销操作)\n[101, 102, 100]\n')

    def test_id_exhaustion_delete_save_and_restart(self):
        self.write_json('max.json',document([],2147483647))
        source=self.program('(addnew) run() -> (Result) {\n    (zno) state := model.fresh();\n    session.load(state, "max.json")?;\n    session.commit(state, tasks.add(state.document, "last", "c", 1)?);\n    io.print([state.document.tasks[0].id, state.document.next_id]);\n    io.print(tasks.add(state.document, "no", "c", 1));\n    session.commit(state, tasks.remove(state.document, 2147483647)?);\n    session.save(state, "max.json")?;\n    (return) (^_^)((null));\n}\nrun();')
        self.assertEqual(self.run_ok(source),'[2147483647, 2147483648]\n(T_T)(ID已耗尽)\n')
        self.assertEqual(json.loads((self.root/'max.json').read_text()),document([],2147483648))
        out=self.run_ok(stdin='2\nmax.json\n0\n')
        self.assertIn(banner(0,2147483648,False),out)

    def test_menu_cancel_failed_save_blocks_load_and_eof_no_write(self):
        good=self.write_json('keep.json',document([task()],2));before=good.read_bytes()
        out=self.run_ok(stdin='1\n11\n0\n11\n1\nmissing/path.json\n1\n0\n0\n')
        self.assertNotIn('打开路径>',out)
        self.assertIn('I/O failed:',out)
        self.assertIn('输入结束：有未保存修改，未自动保存',out)
        self.assertEqual(good.read_bytes(),before)
        self.assertFalse((self.root/'missing').exists())
        self.assertEqual(list(self.root.glob('.zzy-*.tmp')),[])

    def test_open_retry_other_path_and_preserve_current(self):
        self.write_json('good.json',document([task()],2))
        out=self.run_ok(stdin='2\nabsent.json\n1\n2\ngood.json\n11\nabsent.json\n0\n1\n0\n')
        self.assertEqual(out.count('打开失败：'),3)
        self.assertIn('打开成功',out)
        self.assertIn('1\t作业\t课程\t3\tfalse',out)
        self.assertNotIn('未自动保存',out)

    def test_every_draft_prompt_eof_is_non_mutating(self):
        original=compact(document([task()],2)).encode()
        drafts=['3','3\n1','3\n1\nnew','3\n1\nnew\nc','3\n1\nnew\nc\n2',
                '4','4\n1','5','5\n1','6','6\nc','6\nc\n1','6\nc\n1\n0','7','9','9\nout.tsv','10']
        for draft in drafts:
            with self.subTest(draft=draft):
                (self.root/'case.json').write_bytes(original)
                out=self.run_ok(stdin='2\ncase.json\n'+draft+'\n')
                self.assertTrue(out.endswith('再见\n'))
                self.assertEqual((self.root/'case.json').read_bytes(),original)
                self.assertFalse((self.root/'out.tsv').exists())
                self.assertNotIn('未自动保存',out)
        out=self.run_ok(stdin='1\n2\na\nc\n1\n1\n10\n')
        self.assertIn('有未保存修改，未自动保存',out)

    def test_view_is_readonly_stable_empty_and_all_sort_modes(self):
        source=self.program('(addnew) run() -> (Result) {\n    (zno) state := model.fresh();\n    session.commit(state, tasks.add(state.document, "b", "c", 2)?);\n    session.commit(state, tasks.add(state.document, "a", "c", 2)?);\n    session.save(state, "data.json")?;\n    (for) sorting (in) 0..<4 {\n        (zno) result := views.select(state.document, model.Filter::{sorting: sorting});\n        io.print(result ?> { (yield): @.id; });\n    }\n    io.print(views.select(state.document, model.Filter::{search: "absent"}));\n    io.print([model.dirty(state), len(state.undo)]);\n    io.print(data.stringify(views.stats(model.Document::{next_id: 1, tasks: []}))?);\n    (return) (^_^)((null));\n}\nrun();')
        self.assertEqual(self.run_ok(source),'[1, 2]\n[1, 2]\n[1, 2]\n[2, 1]\n[]\n[false, 2]\n{"total":0,"done":0,"pending":0,"priority":[0,0,0],"categories":{}}\n')

    def test_save_revalidates_internal_state_before_touching_disk(self):
        self.root.joinpath('old.json').write_bytes(b'unchanged')
        source=self.program('(zno) state := model.fresh();\nstate.document <- model.Document::{next_id: 1, tasks: [model.Task::{id: 1, title: "x", category: "c", priority: 1, done: (false)}]};\nio.print(session.save(state, "old.json"));\nio.print([model.dirty(state), state.path]);')
        self.assertEqual(self.run_ok(source),'(T_T)(next_id: 必须大于所有ID)\n[true, null]\n')
        self.assertEqual((self.root/'old.json').read_bytes(),b'unchanged')

    def test_resource_failure_is_not_recoverable_format_error(self):
        for raw, key in [(b' '*4194305,'io_payload_bytes'),(b'['*65+b'0'+b']'*65,'value_depth')]:
            with self.subTest(key=key):
                (self.root/'case.json').write_bytes(raw)
                status,out,err=self.cli(ROOT/'tests/p09/drivers/load.zzy')
                self.assertEqual((status,out),(1,b''))
                self.assertEqual(json.loads(err)['code'],'E211')
                self.assertIn(key,json.loads(err)['message'])

    def test_app_atomic_write_close_replace_and_permission_failures(self):
        target=self.root/'old.json';real_fdopen=files.os.fdopen
        source=self.program('(addnew) run() -> (Result) {\n    (zno) state := model.fresh();\n    session.commit(state, tasks.add(state.document, "edited", "c", 1)?);\n    (?_?) session.save(state, TARGET) {\n        (T_T)(message) => { io.print("FAIL"); }\n        _ => { io.print("WRONG"); }\n    }\n    io.print([state.document.tasks[0].title, model.dirty(state), state.path, len(state.undo)]);\n    (return) (^_^)((null));\n}\nrun();'.replace('TARGET',quote(target)))
        for failure in ('write','close','replace','permission'):
            with self.subTest(failure=failure):
                target.write_bytes(b'old')
                meter=ResourceMeter(ResourcePolicy.from_file(CONFIG),Phase.FRONTEND)
                with SourceLoader(meter) as loader: program=prepare(loader.read(source),meter,loader)
                output=Output(io.StringIO(),io.StringIO(),meter)
                runtime=Interpreter(program,output)
                class Stream:
                    def __init__(self,fd,mode): self.stream=real_fdopen(fd,mode)
                    def __enter__(self): return self
                    def write(self,raw):
                        if failure=='write': raise OSError('injected write')
                        return self.stream.write(raw)
                    def __exit__(self,*args):
                        self.stream.close()
                        if failure=='close': raise OSError('injected close')
                with patch.object(files.os,'fdopen',Stream):
                    if failure=='replace':
                        with patch.object(files.os,'replace',side_effect=OSError('injected replace')): runtime.run()
                    elif failure=='permission':
                        with patch.object(files.tempfile,'mkstemp',side_effect=PermissionError('injected permission')): runtime.run()
                    else: runtime.run()
                self.assertEqual(output.stdout.getvalue(),'FAIL\n[edited, true, null, 1]\n')
                self.assertEqual(output.stderr.getvalue(),'')
                self.assertEqual(target.read_bytes(),b'old')
                self.assertEqual(list(self.root.glob('.zzy-*.tmp')),[])
                for key in ('runtime_objects','runtime_slots','runtime_payload_bytes'):
                    self.assertEqual(meter.used(key),0)

    def test_task_count_boundaries_real_cli(self):
        source=ROOT/'tests/p09/drivers/load.zzy'
        for count in (9999,10000,10001):
            with self.subTest(count=count):
                self.write_json('case.json',document([task(i+1,'x','c',1) for i in range(count)],count+1))
                want=f'OK:{count+1}:{count}\n' if count<=10000 else 'FAIL:tasks: 最多10000项\n'
                self.assertEqual(self.run_ok(source,timeout=180),want)

    def test_application_file_byte_boundary_including_json_parse(self):
        tail=compact(document()).encode()
        for size in (4194303,4194304):
            with self.subTest(size=size):
                (self.root/'case.json').write_bytes(b' '*(size-len(tail))+tail)
                self.assertEqual(self.run_ok(ROOT/'tests/p09/drivers/load.zzy',timeout=60),'OK:1:0\n')

    def test_exhausted_menu_noop_cancel_and_failed_export(self):
        self.write_json('case.json',document([task(2147483647)],2147483648))
        original=(self.root/'case.json').read_bytes()
        out=self.run_ok(stdin='2\ncase.json\n2\n5\n2147483647\n2\n4\n2147483647\n0\n9\ncase.json\n9\nmissing/out.tsv\n1\n0\n')
        self.assertIn('失败：ID已耗尽',out)
        self.assertNotIn('标题> ',out)
        self.assertIn('没有变化',out)
        self.assertIn('不能导出到当前数据文件',out)
        self.assertIn('I/O failed:',out)
        self.assertNotIn('未保存=true',out)
        self.assertEqual((self.root/'case.json').read_bytes(),original)

    def test_numeric_errors_reenter_fields_and_cancel_preserve_id(self):
        out=self.run_ok(stdin='x\n9\n1\n2\na\nc\n1.0\n4\n2\n2\nb\nc\n3\n0\n1\n0\n2\n')
        self.assertIn('请输入十进制整数',out)
        self.assertIn('选项超出范围',out)
        self.assertIn('已取消',out)
        self.assertIn('共0项',out)
        self.assertNotIn('next_id=2',out)

    def test_app_permission_read_failure_keeps_session(self):
        source=self.program('(addnew) run() -> (Result) {\n    (zno) state := model.fresh();\n    session.commit(state, tasks.add(state.document, "edited", "c", 1)?);\n    (?_?) session.load(state, "denied.json") {\n        (T_T)(message) => { io.print(message); }\n        _ => { io.print("WRONG"); }\n    }\n    io.print([state.document.tasks[0].title, state.document.next_id, model.dirty(state), state.path, len(state.undo)]);\n    (return) (^_^)((null));\n}\nrun();')
        meter=ResourceMeter(ResourcePolicy.from_file(CONFIG),Phase.FRONTEND)
        with SourceLoader(meter) as loader: program=prepare(loader.read(source),meter,loader)
        output=Output(io.StringIO(),io.StringIO(),meter)
        with patch.object(files,'open',side_effect=PermissionError('denied by test'),create=True):
            Interpreter(program,output).run()
        self.assertEqual(output.stdout.getvalue(),'I/O failed: denied by test\n[edited, 2, true, null, 1]\n')
        self.assertEqual(output.stderr.getvalue(),'')

    def test_actual_ctrl_c_during_load_does_not_save_dirty_session(self):
        self.write_json('old.json',document([task()],2))
        original=(self.root/'old.json').read_bytes()
        self.write_json('large.json',document([task(i+1,'x','c',1) for i in range(10000)],10001))
        tree=ProcessTree()
        kwargs={}
        if os.name=='nt':
            startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
            kwargs=dict(creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
        stdout_path=self.root/'console.out';stderr_path=self.root/'console.err'
        with stdout_path.open('wb') as out,stderr_path.open('wb') as err:
            try:
                process=tree.start([sys.executable,'-X','utf8','-m','zzy','run',str(MAIN),
                                    '--limits',str(CONFIG),'--diagnostic-format','json'],
                    cwd=self.root,env=dict(os.environ,PYTHONPATH=str(ROOT)),stdin=subprocess.PIPE,
                    stdout=out,stderr=err,**kwargs)
                process.stdin.write('2\nold.json\n3\n1\nchanged\nc\n1\n1\n11\n2\nlarge.json\n'.encode())
                process.stdin.flush()
                deadline=time.monotonic()+10
                while time.monotonic()<deadline and process.poll() is None:
                    text=stdout_path.read_bytes().decode('utf-8')
                    if text.count('打开路径> ')==2 and '未保存=true' in text: break
                    time.sleep(.01)
                else: self.fail('application never reached dirty load operation')
                if os.name=='nt':
                    script="import ctypes,sys,time; k=ctypes.WinDLL('kernel32'); k.FreeConsole(); assert k.AttachConsole(int(sys.argv[1])); assert k.SetConsoleCtrlHandler(None,True); assert k.GenerateConsoleCtrlEvent(0,0); time.sleep(.2)"
                    signaler=subprocess.run([sys.executable,'-c',script,str(process.pid)],capture_output=True,timeout=5)
                    self.assertEqual(signaler.returncode,0,signaler.stderr)
                else:
                    import signal
                    os.killpg(process.pid,signal.SIGINT)
                self.assertEqual(process.wait(timeout=10),130)
            finally:
                tree.close()
                if tree.process and tree.process.stdin: tree.process.stdin.close()
        records=[json.loads(line) for line in stderr_path.read_bytes().splitlines()]
        self.assertEqual(len(records),1)
        self.assertEqual((records[0]['kind'],records[0]['code']),('cancelled',None))
        self.assertEqual((self.root/'old.json').read_bytes(),original)
        self.assertEqual(list(self.root.glob('.zzy-*.tmp')),[])
