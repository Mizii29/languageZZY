"""P11 lazy resource diagnostics: fixed answers and real CLI failure records."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from zzy.diagnostics import Cancelled, Phase, ResourceExceeded, display_path, render
from zzy.interpreter import Interpreter
from zzy.output import Output
from zzy.prepare import prepare
from zzy.resources import ResourceMeter, ResourcePolicy
from zzy.source import Source
from zzy.tokens import Token


def runtime(program=None, **limits):
    if program is None:
        program=prepare(Source.from_bytes(Path('p11.zzy'),b'io.print(1);'),ResourceMeter(ResourcePolicy(),Phase.FRONTEND))
    meter=ResourceMeter(ResourcePolicy(limits),Phase.EXECUTION)
    return Interpreter(program,Output(io.StringIO(),io.StringIO(),meter),io.StringIO())


class LazyLocationTests(unittest.TestCase):
    def test_success_and_cancellation_do_not_evaluate_location(self):
        r=runtime()
        with patch.object(r,'location',side_effect=AssertionError('eager location')):
            r.check('integer_bits',1,object())
            with r.reserve(object(),runtime_slots=1):pass
            r.meter.cancellation.cancel()
            with self.assertRaises(Cancelled):r.check('integer_bits',2,object())
            with self.assertRaises(Cancelled):r.reserve(object(),runtime_slots=1)
        self.assertEqual(r.meter.used('runtime_slots'),0)
        self.assertEqual(r._location_paths,{})

    def test_fixed_unicode_bom_crlf_token_and_eof_records(self):
        r=runtime(integer_bits=1,runtime_slots=1)
        source=Source.from_bytes(Path('中 module.zzy'),b'\xef\xbb\xbf'+ 'zzysay:中😀\r\n1+1;'.encode())
        for start,end,coordinates in [(source.text.index('+'),source.text.index('+')+1,(2,2,2,3)),(len(source.text),len(source.text),(2,5,2,5))]:
            node=SimpleNamespace(token=Token('PLUS',source,start,end),span='not the token range')
            for method in ('check','reserve'):
                with self.assertRaises(ResourceExceeded) as caught:
                    if method=='check':r.check('integer_bits',2,node)
                    else:r.reserve(node,runtime_slots=2)
                e=caught.exception;key='integer_bits' if method=='check' else 'runtime_slots'
                expected={'schema_version':1,'kind':'error','code':'E211','file':display_path(source.path),'span':{'start':{'line':coordinates[0],'column':coordinates[1]},'end':{'line':coordinates[2],'column':coordinates[3]}},'message':f'资源超限：{key}，上限 1，本次需求 2','notes':[]}
                self.assertEqual(e.diagnostic.record(),expected)
                self.assertEqual(json.loads(render(e.diagnostic,'json')),expected)
                self.assertEqual(render(e.diagnostic),f'{expected["file"]}:{coordinates[0]}:{coordinates[1]}: E211 {expected["message"]}\n')
                self.assertEqual((e.key,e.limit,e.requested,e.phase,e.exit_code),(key,1,2,Phase.EXECUTION,1))
        self.assertEqual(r.meter.used('runtime_slots'),0)

    def test_location_failure_preserves_original_quota_abort_and_notes(self):
        r=runtime(integer_bits=1)
        for failure in (OSError('cwd'),MemoryError(),ValueError('span')):
            with patch.object(r,'location',side_effect=failure):
                with self.assertRaises(ResourceExceeded) as caught:r.check('integer_bits',2,r.program.root)
            self.assertEqual((caught.exception.key,caught.exception.limit,caught.exception.requested),('integer_bits',1,2))
            self.assertIsNone(caught.exception.diagnostic.span)
        e=ResourceExceeded('integer_bits',1,2,Phase.EXECUTION)
        e.diagnostic=replace(e.diagnostic,notes=('原始备注',))
        r.locate_resource_error(e,r.program.root)
        self.assertEqual(e.diagnostic.notes,('原始备注',))

    def test_shared_program_concurrent_errors_and_changing_cwd(self):
        r=runtime();program=r.program;node=program.root
        def request(limit):
            local=runtime(program,integer_bits=limit)
            with self.assertRaises(ResourceExceeded) as caught:local.check('integer_bits',limit+1,node)
            return caught.exception.diagnostic.record(),local._location_paths
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(request,range(1,17)))
        for i,(record,paths) in enumerate(results,1):
            self.assertIn(f'上限 {i}，本次需求 {i+1}',record['message'])
            self.assertEqual(record['span'],results[0][0]['span'])
        self.assertEqual(len({id(paths) for _,paths in results}),16)
        original=Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with self.assertRaises(ResourceExceeded) as caught:r.check('integer_bits',65537,node)
                self.assertEqual(caught.exception.diagnostic.file,display_path(node.token.source.path))
            finally:os.chdir(original)

    def test_real_cli_cross_module_notes_and_check_no_execution(self):
        with tempfile.TemporaryDirectory(prefix='ZZY P11 中文 ') as directory:
            root=Path(directory);dep=root/'dep.zzy';entry=root/'main.zzy';limits=root/'limits.json'
            dep.write_bytes(b'\xef\xbb\xbf'+ 'zzysay:😀\r\n(addnew) f(){(return) 1+1;}'.encode())
            entry.write_text('(use) "dep.zzy" (as) d;\nio.print(d.f());',encoding='utf-8')
            limits.write_text(json.dumps({'policy_version':1,'limits':{'integer_bits':1}}),encoding='utf-8')
            base=[sys.executable,'-X','utf8','-m','zzy']
            for mode in ('check','run'):
                result=subprocess.run([*base,mode,str(entry),'--limits',str(limits),'--diagnostic-format','json'],capture_output=True,timeout=10)
                if mode=='check':self.assertEqual(result.returncode,0,result.stderr.decode());continue
                self.assertEqual(result.returncode,1,result.stderr.decode());self.assertEqual(result.stdout,b'')
                record=json.loads(result.stderr)
                self.assertEqual((record['code'],record['file']),('E211',display_path(dep)))
                self.assertEqual(record['span'],{'start':{'line':2,'column':24},'end':{'line':2,'column':25}})
                self.assertEqual(record['notes'],[f'调用 f：{display_path(entry)}:2:13'])


if __name__=='__main__':unittest.main()
