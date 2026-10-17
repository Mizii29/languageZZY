"""Real Tk acceptance, explicitly separate from headless discovery. No skips."""
import argparse
import json
from pathlib import Path
import platform
import time
from threading import get_ident, main_thread
import unittest
from unittest.mock import patch

from tests.__main__ import execute
from tests.test_interpreter import prepared
from zzy.native.sketch_gui import run_gui, View


class GUIAcceptance(unittest.TestCase):
    def test_drag_buffer_limit_stops_session_without_partial_stroke(self):
        from zzy.diagnostics import ResourceExceeded
        program,output=prepared('(zno)c:=sketch.canvas(100,100,"drag bound");sketch.show(c);')
        views=[]
        def probe(view,thread):
            views.append(view)
            def drag():
                view.points=[(0.,0.)]*10000
                view.area.event_generate('<B1-Motion>',x=50,y=50)
            view.window.after(60,drag)
        with self.assertRaises(ResourceExceeded) as error:run_gui(program,output,probe=probe)
        self.assertEqual(error.exception.key,'sketch.batch_points')
        self.assertEqual(len(views[0].points),10000)
        self.assertFalse(views[0].scene.geometries)

    def test_stale_queued_layer_action_is_diagnostic_not_python_exception(self):
        from zzy.diagnostics import DiagnosticError
        program,output=prepared('(zno)c:=sketch.canvas(100,100,"stale layer");sketch.add_layer(c,"temporary");sketch.show(c);')
        def probe(view,thread):
            view.session.send(('history','undo'))
            view.session.send(('layer','lock_layer',1,True))
        with self.assertRaises(DiagnosticError) as error:run_gui(program,output,probe=probe)
        self.assertEqual(error.exception.diagnostic.code,'E203')

    def test_windows_pixels_confirm_evenodd_fill_and_clip(self):
        source='''(zno)c:=sketch.canvas(200,200,"evenodd pixels");(zno)p:=sketch.pen(c,"p");sketch.hide_cursor(p);
sketch.fill_color(p,sketch.rgb(255,0,0));sketch.jump_to(p,-60,-20);sketch.begin_fill(p);sketch.polyline(p,[[-20,-20],[-20,20],[-60,20],[-60,-20]]);sketch.end_fill(p);
sketch.jump_to(p,20,-20);sketch.begin_fill(p);sketch.polyline(p,[[60,-20],[60,20],[20,20],[20,-20],[60,-20],[60,20],[20,20],[20,-20]]);sketch.end_fill(p);sketch.show(c);'''
        program,output=prepared(source);observed=[]
        def probe(view,thread):
            deadline=time.monotonic()+3
            def read():
                if view.scene is None or not view.render_complete:
                    if time.monotonic()>deadline:self.fail('render timeout')
                    view.window.after(20,read);return
                import ctypes
                user=ctypes.WinDLL('user32',use_last_error=True);gdi=ctypes.WinDLL('gdi32',use_last_error=True)
                user.GetDC.argtypes=[ctypes.c_void_p];user.GetDC.restype=ctypes.c_void_p
                user.ReleaseDC.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
                gdi.GetPixel.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int];gdi.GetPixel.restype=ctypes.c_uint32
                hwnd=view.area.winfo_id();dc=user.GetDC(hwnd)
                try:
                    for point in ((-40,0),(40,0),(110,0)):
                        x,y=view.screen(point);observed.append(gdi.GetPixel(dc,round(x),round(y)))
                finally:user.ReleaseDC(hwnd,dc)
                view.close()
            view.window.after(180,read)
        run_gui(program,output,probe=probe)
        self.assertEqual(observed,[0x0000ff,0xffffff,0xdddddd])

    def test_callback_error_is_original_diagnostic_and_nested_show_rejected(self):
        from zzy.diagnostics import DiagnosticError
        for body,code in [('io.print(1/0);','E205'),('sketch.show(c);','E214')]:
            program,output=prepared('(zno)c:=sketch.canvas(100,100,"callback error");(addnew) key(k){'+body+'}sketch.on_key(c,key);sketch.show(c);')
            def probe(view,thread):view.window.after(60,lambda:view.session.send(('callback','key','x')))
            with self.assertRaises(DiagnosticError) as error:run_gui(program,output,probe=probe)
            self.assertEqual(error.exception.diagnostic.code,code)

    def test_real_callbacks_timer_key_and_close_cleanup(self):
        source='''(zno)c:=sketch.canvas(200,200,"events");
(zyes)t:=0;
(addnew) click(x,y,b){io.print(b);}
(addnew) key(k){io.print(k);}
(addnew) tick(){io.print("tick");sketch.cancel_timer(c,t);}
sketch.on_click(c,click);sketch.on_key(c,key);t<-sketch.every(c,1::ms,tick);
sketch.show(c);io.print(sketch.cancel_timer(c,t));io.print("closed");'''
        program,output=prepared(source);lines=[]
        def probe(view,thread):
            def send():
                view.area.event_generate('<ButtonPress-3>',x=80,y=90)
                view.area.event_generate('<ButtonRelease-3>',x=80,y=90)
                view.area.focus_force()
                view.area.event_generate('<KeyPress>',keysym='Escape')
                view.window.after(150,view.close)
            view.window.after(80,send)
        with patch.object(output,'write',lines.append):run_gui(program,output,probe=probe)
        self.assertEqual(lines.count('tick\n'),1)
        self.assertIn('3\n',lines);self.assertIn('Escape\n',lines)
        self.assertEqual(lines[-2:],['false\n','closed\n'])

    def test_close_interrupts_long_callback_and_continues_script(self):
        program,output=prepared('(zno)c:=sketch.canvas(100,100,"long callback");(addnew) key(k){(while)(true){}}sketch.on_key(c,key);sketch.show(c);io.print("continued");')
        lines=[];threads=[]
        def probe(view,thread):
            threads.append(thread)
            view.window.after(50,lambda:view.session.send(('callback','key','a')))
            view.window.after(150,view.close)
        with patch.object(output,'write',lines.append):run_gui(program,output,probe=probe)
        self.assertEqual(lines,['continued\n']);self.assertFalse(threads[0].is_alive())

    def test_real_queue_overflow_aborts_long_callback(self):
        program,output=prepared('(zno)c:=sketch.canvas(100,100,"overflow");(addnew) key(k){(while)(true){}}sketch.on_key(c,key);sketch.show(c);')
        from zzy.diagnostics import ResourceExceeded
        def probe(view,thread):
            view.window.after(50,lambda:view.session.send(('callback','key','a')))
            def flood():
                for _ in range(5000):view.session.send(('callback','key','b'))
            view.window.after(120,flood)
        with self.assertRaises(ResourceExceeded) as error:run_gui(program,output,probe=probe)
        self.assertEqual(error.exception.key,'sketch.input_queue')

    def test_real_history_controls_seek_step_and_edit_exit(self):
        program,output=prepared('(zno)c:=sketch.canvas(200,200,"replay");(zno)p:=sketch.pen(c,"p");sketch.forward(p,1);sketch.forward(p,1);sketch.forward(p,1);sketch.show(c);io.print(sketch.layer_info(c)[0].count);io.print(sketch.position(p));')
        lines=[]
        def probe(view,thread):
            def wait(predicate,action,deadline=None):
                deadline=deadline or time.monotonic()+3
                if predicate():action()
                elif time.monotonic()>deadline:self.fail("GUI state did not arrive before deadline")
                else:view.window.after(20,lambda:wait(predicate,action,deadline))
            def start():
                view.session.send(('replay','seek',1))
                wait(lambda:view.scene.playback_position==1,step)
            def step():
                self.assertEqual(len(view.scene.geometries),1)
                view.session.send(('replay','step'))
                wait(lambda:view.scene.playback_position==2,edit)
            def edit():
                self.assertEqual(len(view.scene.geometries),2)
                view.session.send(('history','undo'))
                wait(lambda:view.scene.playback_position==-1 and len(view.scene.geometries)==2,finish)
            def finish():
                self.assertEqual(view.scene.playback_position,-1)
                self.assertEqual(len(view.scene.geometries),2)
                view.close()
            view.window.after(70,start)
        with patch.object(output,'write',lines.append):run_gui(program,output,probe=probe)
        self.assertEqual(lines,['2\n','sketch.Position::{x: 2.0, y: 0.0}\n'])

    def test_real_window_tools_zoom_close_continue_and_reshow(self):
        source='''(zno)c:=sketch.canvas(400,300,"真实窗口验收");
(zno)p:=sketch.pen(c,"first");sketch.forward(p,20);
io.print(sketch.show(c));io.print(sketch.show(c));io.print(sketch.svg_text(c));'''
        program,output=prepared(source)
        observed=[];windows=[];main=get_ident()
        with patch.object(output,'write',lambda s:observed.append((get_ident(),s))):
            def probe(view,thread):
                self.assertEqual(get_ident(),main);self.assertNotEqual(thread.ident,main)
                windows.append(view)
                def act():
                    self.assertIsNotNone(view.scene)
                    before=view.scene
                    view.scale(1.25)
                    self.assertIs(view.scene,before)
                    view.mode.set('rectangle')
                    view.area.event_generate('<ButtonPress-1>',x=100,y=100)
                    view.area.event_generate('<B1-Motion>',x=150,y=150)
                    view.area.event_generate('<ButtonRelease-1>',x=150,y=150)
                    deadline=time.monotonic()+3
                    def finish():
                        if len(view.scene.geometries)==len(before.geometries)+1:view.close()
                        elif time.monotonic()>deadline:self.fail('tool result did not arrive')
                        else:view.window.after(20,finish)
                    view.window.after(20,finish)
                view.window.after(180,act)
            run_gui(program,output,probe=probe)
        self.assertEqual(len(windows),2)
        self.assertTrue(all(tid!=main for tid,_ in observed))
        self.assertEqual([s for _,s in observed[:2]],['(^_^)(null)\n']*2)
        self.assertIn('object-3',observed[-1][1])
        self.assertTrue(all(w.session.closed.is_set() for w in windows))
        self.assertEqual(output.meter.used('runtime_payload_bytes'),0)

    def test_real_window_close_without_edit_and_worker_error_cleanup(self):
        program,output=prepared('(zno)c:=sketch.canvas(100,100,"close");sketch.show(c);io.print(1/0);')
        from zzy.diagnostics import DiagnosticError
        threads=[]
        def probe(view,thread):threads.append(thread);view.window.after(60,view.close)
        with self.assertRaises(DiagnosticError) as error:run_gui(program,output,probe=probe)
        self.assertEqual(error.exception.diagnostic.code,'E205')
        self.assertTrue(all(not t.is_alive() for t in threads))

    def test_missing_tk_is_failure_result(self):
        program,output=prepared('(zno)c:=sketch.canvas(100,100,"missing");io.print(sketch.show(c));')
        import tkinter
        lines=[]
        with patch.object(tkinter,'Tk',side_effect=tkinter.TclError('injected missing display')),patch.object(output,'write',lines.append):
            run_gui(program,output)
        self.assertIn('(T_T)',lines[0]);self.assertIn('injected missing display',lines[0])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    success,report=execute(unittest.defaultTestLoader.loadTestsFromTestCase(GUIAcceptance))
    import tkinter
    report.update(platform=platform.platform(),tk=tkinter.TkVersion,kind='real GUI; explicit desktop run')
    if args.report:args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False));return 0 if success else 1


if __name__=='__main__':raise SystemExit(main())
