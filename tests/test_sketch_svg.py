"""Parsed SVG geometry and atomic publication, plus real CLI no-GUI checks."""
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from tests.blackbox import ROOT
from tests import test_e1_runtime as helpers
from zzy.diagnostics import Cancelled, Phase, ResourceExceeded
from zzy.values import freeze

NS = {'s': 'http://www.w3.org/2000/svg'}


class SVGTests(unittest.TestCase):
    inspect = helpers.SketchRuntimeTests.inspect
    call = helpers.SketchRuntimeTests.call
    error = helpers.SketchRuntimeTests.error

    def xml(self, r, c, n):
        result = self.call(r,n,'svg_text',c)
        self.assertTrue(result.data[0])
        return ET.fromstring(result.data[1].data)

    def test_coordinates_clip_background_dot_and_xml_injection(self):
        def check(r,c,p,n):
            c.title = '<script a="&">中文</script>'
            root = self.xml(r,c,n)
            self.assertEqual(root.attrib['viewBox'],'0 0 200 100')
            self.assertEqual(root.find('s:title',NS).text,c.title)
            self.assertIsNone(root.find('.//s:script',NS))
            self.assertEqual(root.find('s:defs/s:clipPath/s:rect',NS).attrib,dict(width='200',height='100'))
            self.assertEqual(root.find('s:g',NS).attrib['clip-path'],'url(#canvas-clip)')
            self.assertEqual(root.find('s:g/s:g',NS).attrib['transform'],'translate(100.0 50.0)')
            self.assertEqual(root.find('.//s:path',NS).attrib['d'],'M0 0 L10.0 -20.0')
            dot=root.find('.//s:circle',NS)
            self.assertEqual((dot.attrib['cx'],dot.attrib['cy'],dot.attrib['r']),('10.0','-20.0','2.0'))
            freeze(c,r,n)
            self.assertTrue(self.call(r,n,'svg_text',c).data[0])
        self.inspect('sketch.move_to(p,10,20);sketch.dot(p,4);',check)

    def test_fill_closes_only_fill_and_curves_use_canonical_points(self):
        def check(r,c,p,n):
            paths=self.xml(r,c,n).findall('.//s:path',NS)
            self.assertEqual(paths[0].attrib,dict(d='M0 0 L10.0 0 L10.0 -10.0 Z',fill='#000000',**{'fill-rule':'evenodd','stroke':'none'}))
            self.assertTrue(all('Z' not in path.attrib['d'] for path in paths[1:]))
            # Parse exported numeric coordinates independently of SVG formatter.
            for path, block in zip(paths[-2:],c.objects[-2:]):
                values=path.attrib['d'].replace('M','').replace('L','').split()
                points=tuple((float(values[i]),-float(values[i+1])) for i in range(0,len(values),2))
                self.assertEqual(points,block.geometry.strokes[0].points)
        self.inspect('sketch.begin_fill(p);sketch.move_to(p,10,0);sketch.move_to(p,10,10);sketch.end_fill(p);sketch.circle(p,-10,90);sketch.bezier_to(p,0,30,20,30,20,20);',check)

    def test_draft_invalid_xml_and_clear(self):
        def check(r,c,p,n):
            self.call(r,n,'begin_fill',p)
            self.error('E214',lambda:self.call(r,n,'svg_text',c))
            self.call(r,n,'cancel_fill',p)
            c.title='\0'
            self.assertFalse(self.call(r,n,'svg_text',c).data[0])
            c.title='ok';self.call(r,n,'clear',c)
            self.assertFalse(self.xml(r,c,n).findall('.//s:path',NS))
        self.inspect('sketch.forward(p,5);',check)

    def test_atomic_file_failures_cancel_and_budget_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='SVG 中文 ') as tmp:
            target=Path(tmp)/'作品.svg'
            def check(r,c,p,n):
                target.write_bytes(b'old')
                baseline=dict(r.meter._used)
                with patch('zzy.native.files.os.replace',side_effect=OSError('injected replace')):
                    result=self.call(r,n,'save_svg',c,str(target))
                    self.assertFalse(result.data[0])
                self.assertEqual(target.read_bytes(),b'old')
                self.assertEqual(list(Path(tmp).glob('.zzy-*')),[])
                del result;gc.collect()
                self.assertEqual(dict(r.meter._used),baseline)
                with patch('zzy.native.files.os.replace',side_effect=Cancelled):
                    with self.assertRaises(Cancelled):self.call(r,n,'save_svg',c,str(target))
                self.assertEqual(target.read_bytes(),b'old')
                self.assertEqual(list(Path(tmp).glob('.zzy-*')),[])
                original=r.check
                def bounded(key,count,node):
                    if key=='text_codepoints' and count>300:raise ResourceExceeded(key,300,count,Phase.EXECUTION)
                    original(key,count,node)
                with patch.object(r,'check',bounded):
                    with self.assertRaises(ResourceExceeded):self.call(r,n,'save_svg',c,str(target))
                gc.collect();self.assertEqual(dict(r.meter._used),baseline)
                self.assertEqual(target.read_bytes(),b'old')
                self.assertTrue(self.call(r,n,'save_svg',c,str(target)).data[0])
                self.assertEqual(ET.parse(target).getroot().tag,'{'+NS['s']+'}svg')
                self.assertFalse(self.call(r,n,'save_svg',c,str(Path(tmp)/'missing'/'x')).data[0])
            self.inspect('sketch.forward(p,10);',check)

    def test_real_cli_check_and_export_never_load_gui(self):
        script='''
import sys
class NoGUI:
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'tkinter','turtle'}:raise AssertionError('GUI import')
sys.meta_path.insert(0,NoGUI())
from zzy.cli import main
assert main(['check',sys.argv[1]])==0
assert 'zzy.native.sketch' not in sys.modules
from pathlib import Path
assert not Path('picture.svg').exists()
assert main(['run',sys.argv[1]])==0
assert Path('picture.svg').is_file()
'''
        with tempfile.TemporaryDirectory(prefix='SVG CLI 中文 ') as tmp:
            file=Path(tmp)/'export.zzy'
            file.write_text('(zno)c:=sketch.canvas(200,100,"hello");(zno)p:=sketch.pen(c,"p");sketch.forward(p,10);io.print(sketch.save_svg(c,"picture.svg"));',encoding='utf-8')
            result=subprocess.run([sys.executable,'-X','utf8','-c',script,str(file)],cwd=tmp,
                env=dict(os.environ,PYTHONPATH=str(ROOT)),capture_output=True,timeout=20)
            self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'(^_^)(null)\n',b''))


if __name__=='__main__':unittest.main()
