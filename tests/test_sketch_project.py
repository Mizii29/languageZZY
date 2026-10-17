import copy
import gc
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from tests import test_e1_runtime as helpers
from zzy.values import Value
from tests.blackbox import ROOT
from tests.test_p05_integration import quote


class ProjectTests(unittest.TestCase):
    inspect=helpers.SketchRuntimeTests.inspect
    call=helpers.SketchRuntimeTests.call
    error=helpers.SketchRuntimeTests.error

    def test_real_cli_save_restart_load_undo_and_library_reuse(self):
        with tempfile.TemporaryDirectory(prefix='ZZY 重启 恢复 ') as tmp:
            root=Path(tmp);project=root/'saved.zzysketch';library=root/'flower.zzy'
            first=root/'save.zzy';second=root/'load.zzy'
            first.write_text('(zno)c:=sketch.canvas(100,100,"restart");(zno)p:=sketch.pen(c,"pen");sketch.forward(p,10);sketch.copy_object(c,1);io.print(sketch.save_project(c,'+quote(project)+'));io.print(sketch.save_function(sketch.capture(c),'+quote(library)+',"flower"));',encoding='utf-8')
            second.write_text('(use) "flower.zzy" (as) lib;(?_?)sketch.load_project('+quote(project)+'){(^_^)(c)=>{io.print(sketch.layer_info(c)[0].count);io.print(sketch.undo(c));io.print(sketch.layer_info(c)[0].count);io.print(lib.flower(c,10,20,1,0));io.print(sketch.layer_info(c)[0].count);}(T_T)(m)=>{io.print(m);}}',encoding='utf-8')
            check=subprocess.run([sys.executable,'-X','utf8','-m','zzy','check',str(first)],cwd=ROOT,capture_output=True,timeout=20)
            self.assertEqual((check.returncode,check.stdout,check.stderr),(0,b'',b''));self.assertFalse(project.exists());self.assertFalse(library.exists())
            for file,expected in [(first,'(^_^)(null)\n(^_^)(null)\n'),(second,'2\ntrue\n1\n(^_^)(3)\n2\n')]:
                result=subprocess.run([sys.executable,'-X','utf8','-m','zzy','run',str(file)],cwd=ROOT,capture_output=True,timeout=20)
                self.assertEqual((result.returncode,result.stdout,result.stderr),(0,expected.encode(),b''))

    def test_roundtrip_geometry_layers_pens_history_redo_and_high_water(self):
        with tempfile.TemporaryDirectory(prefix='ZZY 项目 ') as tmp:
            path=Path(tmp)/'project.zzysketch'
            def check(r,c,p,n):
                self.call(r,n,'copy_object',c,1)
                self.call(r,n,'translate_object',c,2,20,30)
                self.call(r,n,'undo',c)
                expected=self.call(r,n,'svg_text',c).data[1].data
                result=self.call(r,n,'save_project',c,str(path));self.assertTrue(result.data[0])
                data=json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(data['next_id'],3)
                self.assertNotIn('callbacks',data)
                result=self.call(r,n,'load_project',Value('String',str(path)))
                self.assertTrue(result.data[0],result.data[1].data)
                loaded=result.data[1]
                self.assertIsNot(loaded,c)
                self.assertEqual(self.call(r,n,'svg_text',loaded).data[1].data,expected)
                self.assertEqual(loaded.pens['笔'].state,p.state)
                self.assertTrue(self.call(r,n,'redo',loaded).data)
                self.assertEqual(loaded.objects[-1].geometry.strokes[0].points,((20.,30.),(30.,30.)))
                self.call(r,n,'undo',loaded);self.call(r,n,'undo',loaded)
                self.assertEqual(len(loaded.objects),1)
                self.assertEqual(self.call(r,n,'copy_object',loaded,1).data,3)
                self.assertEqual(len(c.objects),2)
                self.assertEqual(self.call(r,n,'svg_text',c).data[1].data,expected)
            self.inspect('sketch.forward(p,10);',check)

    def test_rejects_corrupt_history_schema_refs_and_keeps_old_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.zzysketch'
            def check(r,c,p,n):
                self.call(r,n,'save_project',c,str(path));original=json.loads(path.read_text())
                bad=[]
                for key,value in [('schema_version',True),('kind','wrong'),('next_id',1),('objects',[1000]),('extra',1),('layer_order',[])]:
                    data=copy.deepcopy(original);data[key]=value;bad.append(json.dumps(data))
                data=copy.deepcopy(original);data['history'][0]['deltas'][0]['attrs'][0]['after']=999;bad.append(json.dumps(data))
                data=copy.deepcopy(original);data['history'][0]['deltas'][0]['added'][0][0]=1;bad.append(json.dumps(data))
                data=copy.deepcopy(original);data['objects']=[0,0];bad.append(json.dumps(data))
                bad+=['{"kind":"zzy-project","kind":"zzy-project"}', 'NaN', '{']
                blocks=tuple(c.objects);state=p.state;canvases=len(r.native_canvases)
                for text in bad:
                    path.write_text(text,encoding='utf-8')
                    result=self.call(r,n,'load_project',Value('String',str(path)))
                    self.assertFalse(result.data[0],text)
                    self.assertEqual(tuple(c.objects),blocks);self.assertEqual(p.state,state)
                    self.assertEqual(len(r.native_canvases),canvases)
                    del result;gc.collect()
            self.inspect('sketch.forward(p,10);',check)

    def test_atomic_save_failure_and_group_state_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'old.zzysketch'
            def check(r,c,p,n):
                path.write_bytes(b'old')
                with patch('zzy.native.files.os.replace',side_effect=OSError('replace failure')):
                    self.assertFalse(self.call(r,n,'save_project',c,str(path)).data[0])
                self.assertEqual(path.read_bytes(),b'old');self.assertEqual(list(Path(tmp).glob('.zzy-*')),[])
                self.call(r,n,'begin_group',c,'group')
                self.error('E214',lambda:self.call(r,n,'save_project',c,str(path)))
                self.error('E214',lambda:self.call(r,n,'save_png',c,str(path)))
                self.call(r,n,'end_group',c)
                self.assertFalse(self.call(r,n,'save_png',c,str(path)).data[0])
                self.assertEqual(path.read_bytes(),b'old')
            self.inspect('sketch.forward(p,10);',check)


if __name__=='__main__':unittest.main()
