"""Owned geometry invariants that cannot be observed before E1-02 SVG export."""
import gc
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from tests.blackbox import ROOT
from tests.test_interpreter import prepared
from zzy.diagnostics import Cancelled, DiagnosticError, Phase, ResourceExceeded
from zzy.interpreter import Interpreter
from zzy.native import sketch
from zzy.native.catalog import REGISTRY, FUNCTIONS, PURE_CALLS
from zzy.values import Array, Value, freeze

PREFIX = '(zno)c:=sketch.canvas(200,100,"画布");(zno)p:=sketch.pen(c,"笔");'


class SketchRuntimeTests(unittest.TestCase):
    def inspect(self, body, callback, *, tail='', failure=None):
        program, output = prepared(PREFIX + body + 'io.print("inspect");' + tail)
        runtime = Interpreter(program, output)
        def inspect(text):
            c = runtime.bindings[id(program.root.children[0])].value
            p = runtime.bindings[id(program.root.children[1])].value
            callback(runtime, c, p, program.root)
        with patch.object(output, 'write', inspect):
            if failure:
                with self.assertRaises(failure): runtime.run()
            else: runtime.run()
        for key in ('runtime_objects', 'runtime_slots', 'runtime_payload_bytes'):
            self.assertEqual(runtime.meter.used(key), 0, key)
        self.assertFalse(runtime.native_canvases)
        return runtime

    def call(self, r, n, op, handle, *args):
        values = [handle]
        for a in args:
            values.append(a if isinstance(a, Value) else Value(
                'Bool' if type(a) is bool else 'Int' if type(a) is int else 'Float' if type(a) is float else 'String', a))
        return sketch.invoke(r, 'sketch.' + op, values, n)

    def error(self, code, action):
        with self.assertRaises(DiagnosticError) as caught: action()
        self.assertEqual(caught.exception.diagnostic.code, code)

    def test_defaults_clear_and_no_unpublished_apis(self):
        def inspect(r,c,p,n):
            self.assertEqual((c.width,c.height,c.title,c.background),(200,100,'画布',(255,255,255)))
            self.assertEqual((c.layer.name,c.layer.locked,c.layer.visible),('default',False,True))
            self.assertEqual(p.state,sketch.PenState())
            self.call(r,n,'hide_cursor',p);self.assertFalse(p.state.cursor)
            self.call(r,n,'show_cursor',p);self.assertTrue(p.state.cursor)
            self.call(r,n,'width',p,10000);self.assertEqual(p.state.width,10000.)
            self.call(r,n,'width',p,1)
            red=sketch.invoke(r,'sketch.rgb',[Value('Int',255),Value('Int',0),Value('Int',0)],n)
            self.call(r,n,'background',c,red);self.assertEqual(c.background,(255,0,0))
            self.call(r,n,'forward',p,10)
            old=p.state;self.call(r,n,'clear',c)
            self.assertEqual(c.objects,[]);self.assertEqual(c.segments,0)
            self.assertEqual(p.state,old);self.assertEqual(c.next_id,2)
            self.assertNotIn('sketch.undo',FUNCTIONS);self.assertNotIn('sketch.svg_text',FUNCTIONS)
            self.assertNotIn('sketch.show',FUNCTIONS)
            self.assertEqual(set(PURE_CALLS),{f.name for f in FUNCTIONS.values() if f.pure})
            self.assertEqual(len(REGISTRY.extensions['sketch'].types),5)
        self.inspect('',inspect)

    def test_input_copy_and_pen_up_dot_geometry(self):
        body='(zno)a:=[[10,0],[10,10]];sketch.polyline(p,a);a[0][0]<-99;array.pop(a);sketch.pen_up(p);sketch.move_to(p,50,60);sketch.dot(p,4);'
        def inspect(r,c,p,n):
            self.assertEqual(len(c.objects),2)
            path,dot=[b.geometry for b in c.objects]
            self.assertEqual(path.strokes[0].points,((0.,0.),(10.,0.),(10.,10.)))
            self.assertEqual((dot.kind,dot.center,dot.diameter,dot.fill),('dot',(50.,60.),4.,(0,0,0)))
            self.assertFalse(p.state.down)
        self.inspect(body,inspect)

    def test_circle_fixed_geometry_error_and_closed_repeated_turns(self):
        for radius,extent,cx,cy,end in [(10,90,0,10,(10,10)),(-10,90,0,-10,(10,-10)),(10,-90,0,10,(-10,10)),(-10,-90,0,-10,(-10,-10))]:
            def inspect(r,c,p,n):
                pts=c.objects[0].geometry.strokes[0].points
                self.assertEqual(pts[0],(0.,0.))
                self.assertAlmostEqual(pts[-1][0],end[0]);self.assertAlmostEqual(pts[-1][1],end[1])
                for a,b in zip(pts,pts[1:]):
                    self.assertAlmostEqual(math.hypot(a[0]-cx,a[1]-cy),10)
                    mid=((a[0]+b[0])/2,(a[1]+b[1])/2)
                    self.assertLessEqual(10-math.hypot(mid[0]-cx,mid[1]-cy),0.25+1e-12)
            self.inspect(f'sketch.circle(p,{radius},{extent});',inspect)
        self.inspect('sketch.set_heading(p,37);sketch.circle(p,-10,-720);',
            lambda r,c,p,n:self.assertEqual((p.state.position,p.state.heading,c.objects[0].geometry.strokes[0].points[-1]),((0.,0.),37.,(0.,0.))))

    def test_bezier_flattening_independent_dense_sample_and_degenerate(self):
        def inspect(r,c,p,n):
            pts=c.objects[0].geometry.strokes[0].points
            self.assertIn((5.,7.5),pts);self.assertEqual(pts[-1],(10.,0.))
            for i in range(1001):
                t=i/1000
                expected=(30*(1-t)*t*t+10*t**3,30*(1-t)*t)
                # Independent point-to-segment projection, not the implementation helper.
                distances=[]
                for a,b in zip(pts,pts[1:]):
                    v=(b[0]-a[0],b[1]-a[1]);length=v[0]**2+v[1]**2
                    u=max(0,min(1,((expected[0]-a[0])*v[0]+(expected[1]-a[1])*v[1])/length)) if length else 0
                    distances.append(math.hypot(expected[0]-a[0]-u*v[0],expected[1]-a[1]-u*v[1]))
                self.assertLessEqual(min(distances),0.25+1e-12)
            self.call(r,n,'bezier_to',p,10,0,10,0,10,0)
            self.assertEqual(p.state.position,(10.,0.))
        self.inspect('sketch.bezier_to(p,0,10,10,10,10,0);',inspect)

    def test_fill_private_commit_styles_and_no_closing_stroke(self):
        body='sketch.fill_color(p,sketch.rgb(8,9,10));sketch.begin_fill(p);sketch.move_to(p,10,0);sketch.color(p,sketch.rgb(255,0,0));sketch.width(p,3);sketch.move_to(p,10,10);'
        def inspect(r,c,p,n):
            self.assertEqual(c.objects,[]);self.assertEqual(c.next_id,1)
            self.assertEqual(c.draft.segments,2)
            self.call(r,n,'end_fill',p)
            g=c.objects[0].geometry
            self.assertEqual((g.kind,g.fill,g.fill_rule),('fill',(8,9,10),'evenodd'))
            self.assertEqual(g.boundary,((0.,0.),(10.,0.),(10.,10.)))
            self.assertEqual([s.color for s in g.strokes],[(0,0,0),(255,0,0)])
            self.assertEqual([s.width for s in g.strokes],[1.,3.])
            self.assertEqual(c.segments,2);self.assertEqual(p.state.position,(10.,10.))
            self.assertIsNone(c.draft)
        self.inspect(body,inspect)

    def test_fill_cancel_restores_every_state_and_failed_end_retains_draft(self):
        def inspect(r,c,p,n):
            original=p.state
            self.call(r,n,'begin_fill',p)
            self.call(r,n,'forward',p,10);self.call(r,n,'left',p,45);self.call(r,n,'width',p,9)
            self.error('E214',lambda:self.call(r,n,'end_fill',p))
            self.assertIsNotNone(c.draft);self.assertFalse(c.objects)
            self.call(r,n,'cancel_fill',p)
            self.assertEqual(p.state,original);self.assertEqual(c.segments,0)
            self.call(r,n,'begin_fill',p);self.call(r,n,'cancel_fill',p)
        self.inspect('',inspect)

    def test_batch_failure_does_not_change_existing_geometry_or_position(self):
        def inspect(r,c,p,n):
            before=p.state;blocks=tuple(c.objects)
            points=Array(r,n)
            for pair in ((10,20),(30,True)):
                values=Array(r,n)
                for v in pair:values.push(Value('Bool' if type(v) is bool else 'Int',v),r,n)
                points.push(values,r,n)
            self.error('E201',lambda:self.call(r,n,'polyline',p,points))
            self.assertEqual(p.state,before);self.assertEqual(tuple(c.objects),blocks)
            self.assertEqual(c.next_id,2)
        self.inspect('sketch.forward(p,3);',inspect)

    def test_freeze_aliases_canvas_pen_layer_and_wrong_canvas(self):
        def inspect(r,c,p,n):
            q=self.call(r,n,'pen',c,'q')
            wrapper=Array(r,n);wrapper.push(p,r,n);freeze(wrapper,r,n)
            self.error('E203',lambda:self.call(r,n,'forward',p,1))
            self.call(r,n,'forward',q,2)
            self.assertEqual(q.state.position,(2.,0.))
            c.layer.locked=True
            self.error('E203',lambda:self.call(r,n,'forward',q,1))
            self.error('E203',lambda:self.call(r,n,'clear',c))
            c.layer.locked=False;freeze(c.layer,r,n)
            self.error('E203',lambda:self.call(r,n,'forward',q,1))
            c.layer.frozen=False;freeze(c,r,n)
            self.error('E203',lambda:self.call(r,n,'forward',q,1))
            self.error('E203',lambda:self.call(r,n,'pen',c,'another'))
            c.frozen=False
            other=sketch.Canvas(20,20,'other',r,n)
            q.layer=other.layer
            self.error('E203',lambda:self.call(r,n,'forward',q,1))
        self.inspect('',inspect)

    def test_context_thread_and_expired_handle_rejection(self):
        held=[]
        def inspect(r,c,p,n):
            held.extend((c,p,n))
            other=Interpreter(r.program,r.output)
            self.error('E203',lambda:self.call(other,n,'heading',p))
            self.error('E203',lambda:freeze(c,other,n))
            self.assertFalse(c.frozen)
            failures=[]
            def worker():
                try:self.call(r,n,'heading',p)
                except DiagnosticError as error:failures.append(error.diagnostic.code)
                try:sketch.invoke(r,'sketch.canvas',[Value('Int',1),Value('Int',1),Value('String','')],n)
                except DiagnosticError as error:failures.append(error.diagnostic.code)
                try:freeze(c,r,n)
                except DiagnosticError as error:failures.append(error.diagnostic.code)
            thread=Thread(target=worker);thread.start();thread.join(3)
            self.assertFalse(thread.is_alive());self.assertEqual(failures,['E203']*3)
            self.assertFalse(c.frozen)
        runtime=self.inspect('',inspect)
        self.assertFalse(held[0].alive)
        self.error('E203',lambda:self.call(runtime,held[2],'heading',held[1]))

    def test_nonfinite_huge_numbers_and_derived_bounds(self):
        def inspect(r,c,p,n):
            for v in (float('nan'),float('inf'),-float('inf'),10**5000):
                self.error('E208',lambda:self.call(r,n,'forward',p,v))
            self.call(r,n,'jump_to',p,1000000,0)
            before=p.state
            self.error('E208',lambda:self.call(r,n,'forward',p,1))
            self.error('E208',lambda:self.call(r,n,'dot',p,1))
            self.assertEqual(p.state,before);self.assertFalse(c.objects)
        self.inspect('',inspect)

    def test_segment_and_object_limits_fail_before_publish(self):
        def inspect(r,c,p,n):
            with patch.object(sketch,'LIMITS',dict(sketch.LIMITS,path_segments=2,objects=2)):
                self.call(r,n,'forward',p,1);self.call(r,n,'forward',p,1)
                before=p.state
                with self.assertRaises(ResourceExceeded):self.call(r,n,'forward',p,1)
                self.assertEqual((p.state,len(c.objects),c.segments),(before,2,2))
                self.call(r,n,'clear',c);self.call(r,n,'begin_fill',p)
                self.call(r,n,'move_to',p,3,0);self.call(r,n,'move_to',p,3,1)
                with self.assertRaises(ResourceExceeded):self.call(r,n,'move_to',p,4,1)
                self.assertEqual(c.draft.segments,2)
                self.call(r,n,'end_fill',p);self.assertEqual(c.segments,2)
            with patch.object(sketch,'LIMITS',dict(sketch.LIMITS,objects=1)):
                with self.assertRaises(ResourceExceeded):self.call(r,n,'dot',p,1)
        self.inspect('',inspect)

    def test_allocation_failure_at_each_preparation_keeps_state_and_budget(self):
        def inspect(r,c,p,n):
            # Exercise failures inside scratch, geometry payload, and fill commit.
            for op,args in [('forward',(10,)),('circle',(10,90)),('bezier_to',(0,10,10,10,10,0)),('end_fill',())]:
                if op=='end_fill':
                    self.call(r,n,'begin_fill',p);self.call(r,n,'move_to',p,50,0);self.call(r,n,'move_to',p,50,10)
                real=r.reserve
                # Each reserve site in these preparation paths is faulted once.
                count={'forward':2,'circle':3,'bezier_to':2,'end_fill':2}[op]
                for fail_at in range(count):
                    gc.collect();before=p.state;objects=tuple(c.objects);draft=c.draft
                    budget=dict(r.meter._used);counter=0
                    def reserve(*a,**kw):
                        nonlocal counter
                        index=counter;counter+=1
                        if index==fail_at:
                            raise ResourceExceeded('injected',0,1,Phase.EXECUTION)
                        return real(*a,**kw)
                    with patch.object(r,'reserve',reserve):
                        with self.assertRaises(ResourceExceeded):self.call(r,n,op,p,*args)
                    gc.collect()
                    self.assertEqual(p.state,before);self.assertEqual(tuple(c.objects),objects)
                    self.assertIs(c.draft,draft)
                    self.assertEqual({k:r.meter.used(k) for k in budget},budget)
                if op=='end_fill':self.call(r,n,'cancel_fill',p)
        self.inspect('',inspect)

    def test_default_pen_curve_and_document_capacity_boundaries(self):
        def inspect(r,c,p,n):
            for i in range(255):self.call(r,n,'pen',c,'p'+str(i))
            self.assertEqual(len(c.pens),256)
            with self.assertRaises(ResourceExceeded):self.call(r,n,'pen',c,'overflow')
            self.assertEqual(len(c.pens),256)
            # The circular sagitta limit is 0.25 at radius 100. Choose extents
            # halfway inside each ceil interval, avoiding roundoff at the edge.
            step=math.degrees(2*math.acos(1-0.25/100))
            self.call(r,n,'circle',p,100,step*65535.5)
            self.assertEqual(c.objects[0].segments,65536)
            old=p.state
            with self.assertRaises(ResourceExceeded):self.call(r,n,'circle',p,100,step*65536.5)
            self.assertEqual(p.state,old)
            self.call(r,n,'clear',c)
            points=Array(r,n)
            for i in range(10000):
                pair=Array(r,n)
                pair.push(Value('Int',i%2),r,n);pair.push(Value('Int',i%3),r,n)
                points.push(pair,r,n)
            for _ in range(100):self.call(r,n,'polyline',p,points)
            self.assertEqual(c.segments,1000000)
            old=p.state
            with self.assertRaises(ResourceExceeded):self.call(r,n,'forward',p,1)
            self.assertEqual(p.state,old);self.assertEqual(len(c.objects),100)
            self.call(r,n,'clear',c)
            for _ in range(100000):self.call(r,n,'dot',p,1)
            self.assertEqual(len(c.objects),100000)
            with self.assertRaises(ResourceExceeded):self.call(r,n,'dot',p,1)
            self.assertEqual(len(c.objects),100000)
        self.inspect('',inspect)

    def test_cancel_during_curve_and_context_cleanup_restore_fill(self):
        held=[]
        def inspect(r,c,p,n):
            held.extend((c,p));real=r.meter.cancellation.check;count=0
            def cancel():
                nonlocal count
                count+=1
                if count==12:raise Cancelled()
                real()
            with patch.object(r.meter.cancellation,'check',cancel):
                self.call(r,n,'circle',p,100,360)
        self.inspect('sketch.begin_fill(p);sketch.forward(p,10);',inspect,failure=Cancelled)
        c,p=held
        self.assertFalse(c.objects);self.assertIsNone(c.draft);self.assertEqual(p.state,sketch.PenState())

    def test_program_reuse_allocates_fresh_documents_and_resets_ids(self):
        program,output=prepared(PREFIX+'sketch.forward(p,1);io.print("inspect");')
        runtime=Interpreter(program,output);seen=[]
        def observe(text):
            c=runtime.bindings[id(program.root.children[0])].value
            seen.append(c);self.assertEqual(c.next_id,2)
        with patch.object(output,'write',observe):
            runtime.run();runtime.run()
        self.assertIsNot(seen[0],seen[1]);self.assertIsNot(seen[0].context,seen[1].context)
        self.assertTrue(all(not c.alive for c in seen))

    def test_check_does_not_import_geometry_or_tk_or_execute(self):
        script='''
import sys
class BlockGUI:
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'tkinter','turtle'}: raise AssertionError('GUI import')
sys.meta_path.insert(0,BlockGUI())
from zzy.cli import main
assert main(['check',sys.argv[1]])==0
assert 'zzy.native.sketch' not in sys.modules
assert main(['run',sys.argv[2]])==0
assert 'tkinter' not in sys.modules
'''
        with tempfile.TemporaryDirectory(prefix='ZZY sketch 中文 ') as tmp:
            root=Path(tmp)
            (root/'check.zzy').write_text(PREFIX+'io.input("forbidden");io.write_text("sentinel","changed");sketch.circle(p,0,1);',encoding='utf-8')
            (root/'run.zzy').write_text(PREFIX+'sketch.circle(p,10,90);',encoding='utf-8')
            (root/'sentinel').write_bytes(b'old')
            result=subprocess.run([sys.executable,'-X','utf8','-c',script,str(root/'check.zzy'),str(root/'run.zzy')],
                cwd=root,env=dict(os.environ,PYTHONPATH=str(ROOT)),input=b'',capture_output=True,timeout=15)
            self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
            self.assertEqual((root/'sentinel').read_bytes(),b'old')

    def test_real_cli_batch_boundary_and_shared_payload_limit(self):
        with tempfile.TemporaryDirectory(prefix='ZZY sketch boundary ') as tmp:
            file=Path(tmp)/'boundary.zzy'
            for count,code in [(9999,0),(10000,0),(10001,1)]:
                file.write_text(PREFIX+f'(zno)a:=[];(for)i(in)range(0,{count},1){{array.push(a,[i,0]);}}sketch.polyline(p,a);io.print(sketch.position(p).x);',encoding='utf-8')
                result=subprocess.run([sys.executable,'-X','utf8','-m','zzy','run',str(file),'--diagnostic-format','json'],
                    cwd=ROOT,capture_output=True,timeout=30)
                self.assertEqual(result.returncode,code,result.stderr)
                if code:self.assertIn(b'E211',result.stderr);self.assertEqual(result.stdout,b'')
                else:self.assertEqual(result.stdout,f'{count-1}.0\n'.encode());self.assertEqual(result.stderr,b'')
        program,output=prepared(PREFIX+'sketch.circle(p,100,360);',{'runtime_payload_bytes':100000})
        with self.assertRaises(ResourceExceeded):Interpreter(program,output).run()
        self.assertEqual(output.meter.used('runtime_payload_bytes'),0)


if __name__=='__main__':unittest.main()
