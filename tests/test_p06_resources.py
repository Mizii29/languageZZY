"""Generated CLI boundaries; expectations count bytes/tokens independently."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from tests.blackbox import ROOT
from zzy.process import run_bounded
from zzy.resources import DEFAULT_LIMITS


class ResourceCliTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='ZZY P06 limits ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def cli(self,source,limits=None,mode='check',timeout=60,stdin=b''):
        (self.root/'main.zzy').write_text(source,encoding='utf-8')
        args=[sys.executable,'-X','utf8','-m','zzy',mode,'main.zzy','--diagnostic-format','json']
        if limits is not None:
            (self.root/'limits.json').write_text(json.dumps(dict(policy_version=1,limits=limits)),encoding='utf-8')
            args.extend(['--limits','limits.json'])
        return run_bounded(args,cwd=self.root,env=dict(os.environ,PYTHONPATH=str(ROOT)),timeout=timeout,stdin=stdin,output_limit=2**21,stderr_limit=2**21)

    def boundary(self,result,key,over,mode='check'):
        status,out,err=result
        self.assertEqual(status,(2 if mode=='check' else 1) if over else 0,err)
        if over:
            record=json.loads(err.splitlines()[-1]);self.assertEqual(record['code'],'E211');self.assertIn(key,record['message'])
            self.assertNotIn(b'Traceback',err)
        else:self.assertEqual(err,b'')
        self.assertEqual(out,b'')

    def test_source_graph_and_file_adjacent_limits(self):
        child='1;';(self.root/'child.zzy').write_text(child)
        source='(use) "child.zzy" (as) child;'
        for key,code,demand in (('source_file_bytes','1;',2),('source_total_bytes',source,len(source.encode())+len(child)),('module_count',source,2),('import_depth',source,2)):
            for offset in (-1,0,1):
                with self.subTest(key=key,offset=offset):
                    self.boundary(self.cli(code,{key:demand+offset}),key,offset<0)

    def test_stderr_exact_utf8_adjacent_and_final_reserve(self):
        record=dict(schema_version=1,kind='trace',code=None,file='main.zzy',span=dict(start=dict(line=1,column=7),end=dict(line=1,column=8)),message='1',notes=[])
        expected=(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n').encode()
        for offset in (-1,0,1):
            status,out,err=self.cli('(@_@) 1;',{'stderr_bytes':len(expected)+offset},mode='run')
            self.assertEqual(out,b'')
            if offset<0:
                self.assertEqual(status,1);self.assertLessEqual(len(err),4096)
                self.assertEqual(len(err.splitlines()),1);last=json.loads(err);self.assertEqual(last['code'],'E211');self.assertIn('stderr_bytes',last['message'])
            else:self.assertEqual((status,err),(0,expected))

    def test_default_source_file_and_total_adjacent(self):
        for count in (DEFAULT_LIMITS['source_file_bytes']-1,DEFAULT_LIMITS['source_file_bytes'],DEFAULT_LIMITS['source_file_bytes']+1):
            with self.subTest(file_bytes=count):
                self.boundary(self.cli(' '*count),'source_file_bytes',count>DEFAULT_LIMITS['source_file_bytes'])
        # Nine modules keep each file <=2 MiB while the graph reaches 16 MiB.
        body=''.join(f'(use) "m{i}.zzy" (as) m{i};' for i in range(9))
        total=DEFAULT_LIMITS['source_total_bytes']
        for offset in (-1,0,1):
            remaining=total+offset-len(body)
            for i in range(9):
                size=min(remaining,DEFAULT_LIMITS['source_file_bytes']);remaining-=size
                (self.root/f'm{i}.zzy').write_bytes(b' '*size)
            self.assertEqual(remaining,0)
            with self.subTest(total_bytes=total+offset):self.boundary(self.cli(body),'source_total_bytes',offset>0)

    def test_default_module_and_import_adjacent(self):
        for count in (127,128,129):
            body=''
            for i in range(count-1):
                (self.root/f'm{i}.zzy').write_text('');body+=f'(use) "m{i}.zzy" (as) m{i};'
            with self.subTest(modules=count):self.boundary(self.cli(body),'module_count',count>128)
        for depth in (31,32,33):
            for i in range(1,depth):
                (self.root/f'd{i}.zzy').write_text(f'(use) "d{i+1}.zzy" (as) next;' if i<depth-1 else '')
            with self.subTest(depth=depth):self.boundary(self.cli('(use) "d1.zzy" (as) first;'),'import_depth',depth>32)

    def test_default_numeric_and_integer_and_quantity_adjacent(self):
        for size in (4095,4096,4097):
            with self.subTest(digits=size):self.boundary(self.cli('0'*size+';'),'numeric_digits',size>4096)
        prefix='(zyes)x:=2;(for)i(in)0..<15{x<-x*x;}'
        for divisor in (4,2,1):
            # x=2^32768; x*(x/divisor) needs 65535/65536/65537 bits.
            with self.subTest(divisor=divisor):self.boundary(self.cli(prefix+f'x*(x//{divisor});',mode='run'),'integer_bits',divisor==1,'run')
        for depth in (63,64,65):
            with self.subTest(exponent=depth):self.boundary(self.cli(f'(zyes)x:=1::one;(for)i(in)0..<{depth}{{x<-x*1::m;}}',mode='run'),'quantity_exponent_abs',depth>64,'run')

    def test_default_token_and_ast_adjacent(self):
        limit=DEFAULT_LIMITS['tokens_per_file']
        for count in (limit-1,limit,limit+1):
            source=('0;'*(count//2) if count%2==0 else '0;'*((count-7)//2)+'io.print(0);')
            with self.subTest(tokens=count):self.boundary(self.cli(source),'tokens_per_file',count>limit)
        limit=DEFAULT_LIMITS['ast_nodes_total']
        for count in (limit-1,limit,limit+1):
            # Program=1, literal statement=2, empty block=1.
            source='0;'*((count-1)//2)+('{}' if count%2==0 else '')
            with self.subTest(ast=count):self.boundary(self.cli(source,{'tokens_per_file':1000000},timeout=90),'ast_nodes_total',count>limit)

    def test_check_all_effects_leaves_files_unchanged(self):
        code=(ROOT/'tests/p06/inputs/check-all-effects.zzy').read_text(encoding='utf-8')
        (self.root/'check-module.zzy').write_bytes((ROOT/'tests/p06/inputs/check-module.zzy').read_bytes())
        target=self.root/'check-must-not-write';target.write_bytes(b'original')
        self.assertEqual(self.cli(code,{'runtime_objects':1,'runtime_slots':1,'runtime_payload_bytes':1}),(0,b'',b''))
        self.assertEqual(target.read_bytes(),b'original')
        self.assertFalse(list(self.root.glob('.zzy-*.tmp')))

    def test_default_text_and_io_payload_adjacent(self):
        for key in ('text_codepoints','io_payload_bytes'):
            limit=DEFAULT_LIMITS[key]
            for offset in (-1,0,1):
                count=limit+offset
                if key=='text_codepoints':payload=b'a'*count;limits=None
                else:
                    payload=('😀'*(count//4)+'a'*(count%4)).encode()
                    limits={'text_codepoints':DEFAULT_LIMITS['text_codepoints']+4}
                self.assertEqual(len(payload) if key=='io_payload_bytes' else len(payload.decode()),count)
                (self.root/'x').write_bytes(payload)
                with self.subTest(key=key,offset=offset):
                    self.boundary(self.cli('io.read_text("x");',limits,mode='run'),key,offset>0,'run')

    def test_default_stdout_adjacent(self):
        limit=DEFAULT_LIMITS['stdout_bytes']
        source='(?_?)io.read_text("x"){(^_^)(v)=>{io.print(v);} _=>{(o_o)(false);}}'
        for offset in (-1,0,1):
            content='x'*(limit+offset-1);(self.root/'x').write_text(content)
            status,out,err=self.cli(source,mode='run')
            self.assertEqual(status,1 if offset>0 else 0,err[:200])
            if offset>0:
                self.assertEqual(out,b'');self.assertLessEqual(len(err),4096)
                self.assertEqual(json.loads(err)['code'],'E211');self.assertIn('stdout_bytes',json.loads(err)['message'])
            else:self.assertEqual((out,err),((content+'\n').encode(),b''))

    def test_default_stderr_adjacent(self):
        limit=DEFAULT_LIMITS['stderr_bytes']
        def record(message,line,start,end):
            return dict(schema_version=1,kind='trace',code=None,file='main.zzy',span=dict(start=dict(line=line,column=start),end=dict(line=line,column=end)),message=message,notes=[])
        def encode(value):return (json.dumps(value,separators=(',',':'))+'\n').encode()
        sample='(for)i(in)0..<1000{(@_@)1;}'
        column=sample.index('1;')+1
        first=record('1',1,column,column+1);first_bytes=encode(first)
        count=(limit-1500)//len(first_bytes)
        prefix=f'(for)i(in)0..<{count}{{(@_@)1;}}\n'
        self.assertEqual(prefix.index('1;')+1,column)
        for offset in (-1,0,1):
            target=limit+offset-len(first_bytes)*count
            lengths=[n for n in range(1,4000) if len(encode(record('x'*n,2,7,9+n)))==target]
            self.assertEqual(len(lengths),1)
            length=lengths[0];last=record('x'*length,2,7,9+length)
            status,out,err=self.cli(prefix+'(@_@) "'+'x'*length+'";',mode='run')
            self.assertEqual((status,out),(1 if offset>0 else 0,b''))
            records=err.splitlines(keepends=True)
            self.assertEqual(len(records),count+1)
            self.assertTrue(all(line==first_bytes for line in records[:-1]))
            if offset>0:
                self.assertLessEqual(len(records[-1]),4096)
                self.assertEqual(json.loads(records[-1])['code'],'E211')
                self.assertIn('stderr_bytes',json.loads(records[-1])['message'])
            else:
                self.assertEqual(records[-1],encode(last));self.assertEqual(len(err),limit+offset)
