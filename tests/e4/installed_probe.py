"""Run with the freshly installed interpreter and -I, outside the checkout.

The caller copies studio.zzy beside this probe. This is explicit real GUI
acceptance, never a dependency of the default headless test discovery.
"""
import gc
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time
from unittest.mock import patch

import zzy


def main():
    root = Path.cwd()
    assert root != Path(zzy.__file__).resolve().parent.parent
    assert Path(zzy.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    records = []

    def cli(*args, expected=b''):
        command = [sys.executable, '-I', '-X', 'utf8', '-m', 'zzy', *args]
        result = subprocess.run(command, capture_output=True, timeout=30)
        records.append(dict(command=command, cwd=str(root), exit_code=result.returncode,
                            stdout=result.stdout.decode('utf-8'), stderr=result.stderr.decode('utf-8')))
        assert (result.returncode, result.stdout, result.stderr) == (0, expected, b''), records[-1]

    cli('check', 'studio.zzy')
    assert not list(root.glob('*.svg')) and not list(root.glob('*.zzysketch'))
    # Check cannot import runtime geometry or GUI. Headless run must not load Tk.
    for command in ('check', 'run'):
        code = ("import sys; from zzy.cli import main; "
                f"sys.argv=['zzy','{command}','studio.zzy']; status=main(); "
                "assert 'tkinter' not in sys.modules; " +
                ("assert 'zzy.native.sketch' not in sys.modules; " if command == 'check' else '') +
                "raise SystemExit(status)")
        result = subprocess.run([sys.executable, '-I', '-X', 'utf8', '-c', code], capture_output=True, timeout=30)
        records.append(dict(command=[sys.executable, '-I', '-X', 'utf8', '-c', code],
                            exit_code=result.returncode, stdout=result.stdout.decode('utf-8'), stderr=result.stderr.decode('utf-8')))
        assert result.returncode == 0 and not result.stderr, records[-1]
        if command == 'run':assert b'--gui' in result.stdout
    assert (root/'little-flower.svg').exists() and (root/'flower.zzy').exists()
    assert not (root/'little-flower.zzysketch').exists()

    from zzy.diagnostics import Phase
    from zzy.output import Output
    from zzy.prepare import prepare
    from zzy.resources import ResourceMeter, ResourcePolicy
    from zzy.source import Source
    from zzy.native.sketch_gui import run_gui
    meter = ResourceMeter(ResourcePolicy(), Phase.FRONTEND)
    program = prepare(Source.from_bytes(root/'studio.zzy', (root/'studio.zzy').read_bytes()), meter)
    output = Output(io.StringIO(), io.StringIO(), meter)
    windows = []
    workers = []
    lines = []

    def probe(view, worker):
        assert threading.current_thread() is threading.main_thread()
        assert worker.ident != threading.get_ident()
        entry = dict(main_thread=threading.get_ident(), worker_thread=worker.ident,
                     tk=view.root.tk.call('info', 'patchlevel'))
        windows.append(entry)
        workers.append(worker)
        deadline = time.monotonic()+10

        def finish():
            if (view.scene is None or not view.render_complete or not view.area.winfo_ismapped()
                    or view.area.winfo_width()<=1 or view.area.winfo_height()<=1):
                assert time.monotonic() < deadline, 'installed GUI render timeout'
                view.window.after(10, finish)
                return
            entry['rendered_objects'] = len(view.scene.geometries)
            entry['viewport'] = [view.area.winfo_width(),view.area.winfo_height()]
            assert entry['rendered_objects'] == 8
            view.close()
        view.window.after(10, finish)

    with patch.object(output, 'write', lines.append):run_gui(program, output, probe=probe)
    gc.collect()
    assert len(windows) == 1 and all(meter.used(k) == 0 for k in ('runtime_objects','runtime_slots','runtime_payload_bytes'))
    assert workers and all(not t.is_alive() for t in workers)
    assert (root/'little-flower.zzysketch').exists()
    restart = '''(use) "flower.zzy" (as) flowers;
(?_?)sketch.load_project("little-flower.zzysketch"){
(^_^)(c)=>{io.print(sketch.layer_info(c)[0].count);io.print(sketch.undo(c));
io.print(sketch.layer_info(c)[0].count);io.print(flowers.draw_flower(c,0,0,1,0));
io.print(sketch.save_svg(c,"restarted.svg"));}
(T_T)(m)=>{io.print(m);}}
'''
    (root/'restart.zzy').write_text(restart, encoding='utf-8')
    cli('check','restart.zzy')
    cli('run','restart.zzy', expected=b'8\ntrue\n7\n(^_^)(9)\n(^_^)(null)\n')
    report = dict(passed=True, python=sys.version, executable=sys.executable, installed_package=zzy.__file__,
                  platform=platform.platform(), commands=records, gui=windows, gui_output=lines,
                  files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()
                         if p.suffix in {'.zzy','.svg','.zzysketch'}})
    (root/'installed-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':main()
