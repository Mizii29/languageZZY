"""Real Tk acceptance, explicitly separate from headless discovery. No skips."""
import argparse
import json
from pathlib import Path
import platform
from threading import get_ident, main_thread
import unittest
from unittest.mock import patch

from tests.__main__ import execute
from tests.test_interpreter import prepared
from zzy.native.sketch_gui import run_gui, View


class GUIAcceptance(unittest.TestCase):
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
                    view.window.after(150,view.close)
                view.window.after(80,act)
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
