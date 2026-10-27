import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from tests import test_e1_runtime as helpers
from tests.blackbox import ROOT
from zzy.native import sketch_patterns as patterns
from zzy.values import Value, freeze


class PatternTests(unittest.TestCase):
    inspect=helpers.SketchRuntimeTests.inspect
    call=helpers.SketchRuntimeTests.call
    error=helpers.SketchRuntimeTests.error

    def test_snapshot_immutable_shared_and_stamp_transform_pen_unchanged(self):
        def check(r,c,p,n):
            drawing=self.call(r,n,'capture',c);first=c.objects[0]
            self.assertIs(drawing.blocks[0],first)
            self.call(r,n,'forward',p,5);state=p.state
            identity=self.call(r,n,'stamp',c,drawing,10,20,2,90)
            self.assertEqual(identity.data,3);self.assertEqual(p.state,state)
            self.assertEqual(len(drawing.blocks),1)
            leaf=c.objects[-1].geometry.children[0]
            for actual,expected in zip(leaf.strokes[0].points,((10,20),(10,40))):
                self.assertAlmostEqual(actual[0],expected[0]);self.assertAlmostEqual(actual[1],expected[1])
            self.assertEqual(leaf.strokes[0].width,2.)
            xml=self.call(r,n,'svg_text',c).data[1].data
            self.assertEqual(len(ET.fromstring(xml).findall('.//{http://www.w3.org/2000/svg}path')),3)
            self.call(r,n,'undo',c);self.assertEqual(len(c.objects),2)
            self.call(r,n,'redo',c);self.assertEqual(len(c.objects),3)
            self.error('E208',lambda:self.call(r,n,'stamp',c,drawing,0,0,0,0))
            self.assertEqual(len(c.objects),3)
            freeze(c,r,n);self.error('E203',lambda:self.call(r,n,'stamp',c,drawing,0,0,1,0))
        self.inspect('sketch.forward(p,10);',check)

    def test_schema_roundtrip_rejects_corruption_and_native_json(self):
        def check(r,c,p,n):
            d=self.call(r,n,'capture',c);text=self.call(r,n,'drawing_text',d).data[1].data
            decoded=self.call(r,n,'drawing_from_json',Value('String',text))
            self.assertTrue(decoded.data[0])
            self.assertEqual(self.call(r,n,'drawing_text',decoded.data[1]).data[1].data,text)
            original=json.loads(text)
            invalid=['{"schema_version":1,"schema_version":1,"kind":"zzy-drawing","objects":[]}',text.replace('1.0','NaN'),text+'x']
            for key,value in [('schema_version',True),('schema_version',2),('kind','wrong'),('objects',{}),('extra',1)]:
                data=dict(original);data[key]=value;invalid.append(json.dumps(data))
            data=json.loads(text);data['objects'][0]['strokes'][0]['width']=False;invalid.append(json.dumps(data))
            for bad in invalid:
                result=self.call(r,n,'drawing_from_json',Value('String',bad))
                self.assertFalse(result.data[0],bad)
            self.assertEqual(len(c.objects),1)
        self.inspect('sketch.forward(p,1);',check)

    def test_function_export_real_frontend_import_and_lazy_decode_once(self):
        with tempfile.TemporaryDirectory(prefix='ZZY 图案 library ') as tmp:
            path=Path(tmp)/'pattern.zzy'
            def check(r,c,p,n):
                drawing=self.call(r,n,'capture',c)
                for name in ('', 'a b','io','(for)','x;io.print(1);'):
                    path.write_bytes(b'old')
                    self.assertFalse(self.call(r,n,'save_function',drawing,str(path),name).data[0])
                    self.assertEqual(path.read_bytes(),b'old')
                result=self.call(r,n,'save_function',drawing,str(path),'flower')
                self.assertTrue(result.data[0],result.data[1].data)
            self.inspect('sketch.text(p,"[OoO][OoO]n [OoO]q &",12);sketch.forward(p,1);',check)
            entry=Path(tmp)/'main.zzy'
            entry.write_text('(use) "pattern.zzy" (as) lib;(zno)c:=sketch.canvas(100,100,"x");(zno)p:=sketch.pen(c,"caller");io.print(lib.flower(c,0,0,1,0));io.print(lib.flower(c,10,20,2,90));io.print(sketch.position(p));',encoding='utf-8')
            for mode,expected in [('check',b''),('run',b'(^_^)(1)\n(^_^)(2)\nsketch.Position::{x: 0.0, y: 0.0}\n')]:
                result=subprocess.run([sys.executable,'-X','utf8','-m','zzy',mode,str(entry)],cwd=ROOT,capture_output=True,timeout=20)
                self.assertEqual((result.returncode,result.stdout,result.stderr),(0,expected,b''))
            # Same real module preparation, with a count around the decode entry.
            from zzy.source import SourceLoader
            from zzy.resources import ResourcePolicy,ResourceMeter
            from zzy.diagnostics import Phase
            from zzy.prepare import prepare
            from zzy.interpreter import Interpreter
            from zzy.output import Output
            import io
            meter=ResourceMeter(ResourcePolicy(),Phase.FRONTEND)
            original=patterns.invoke;calls=[]
            def counted(r,op,args,n):
                if op=='drawing_from_json':calls.append(op)
                return original(r,op,args,n)
            with patch.object(patterns,'invoke',counted),SourceLoader(meter) as loader:
                program=prepare(loader.read(entry),meter,loader)
                self.assertEqual(calls,[])
                runtime=Interpreter(program,Output(io.StringIO(),io.StringIO(),meter))
                runtime.run();self.assertEqual(calls,['drawing_from_json'])
                runtime.run();self.assertEqual(calls,['drawing_from_json']*2)


if __name__=='__main__':unittest.main()
