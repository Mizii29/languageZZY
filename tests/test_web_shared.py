"""Shared snapshot graph, ownership and ordinary core semantics."""
import io
from pathlib import Path
import tempfile
import unittest
from zzy.web_shared import initialize
from zzy.web import RequestRuntime
from zzy.prepare import prepare
from zzy.source import SourceLoader
from zzy.resources import ResourcePolicy,ResourceMeter,CancellationToken
from zzy.diagnostics import Phase,DiagnosticError
from zzy.output import Output

ROOT=Path(__file__).resolve().parents[1]


def load(path):
    policy=ResourcePolicy()
    meter=ResourceMeter(policy,Phase.FRONTEND)
    with SourceLoader(meter) as loader:program=prepare(loader.read(path),meter,loader)
    return program,policy


def call(program,policy,snapshot,name):
    r=RequestRuntime(program,Output(io.StringIO(),io.StringIO(),ResourceMeter(policy,Phase.EXECUTION)),io.StringIO())
    r.shared_snapshot=snapshot;r.handler=next(n for n in program.root.children if n.token.lexeme==name)
    r.request_text=('{}','null');r.input_valid=False
    try:r.run();return r.result
    finally:
        assert not r.bindings
        assert all(r.meter.used(k)==0 for k in ('runtime_objects','runtime_slots','runtime_payload_bytes'))


class SharedTests(unittest.TestCase):
    def test_nested_writes_and_default_alias_are_frozen(self):
        program,policy=load(ROOT/'tests/p08/shared.zzy');snap=initialize(program,policy,CancellationToken())
        try:
            for name in ('array_write','map_write','shape_write','machine_write','default_write'):
                with self.subTest(name=name),self.assertRaises(DiagnosticError) as error:call(program,policy,snap,name)
                self.assertEqual(error.exception.diagnostic.code,'E203')
            for _ in range(2):self.assertEqual(call(program,policy,snap,'read'),(200,b'[[1,2],[7],"a"]'))
            self.assertEqual(call(program,policy,snap,'iterate'),(200,b'[3,[2,3]]'))
            array=next(value for value,_ in snap.bindings.values() if value.kind=='Array' and len(value.data)==2)
            self.assertEqual(array.active,0)
            self.assertGreater(snap.meter.used('runtime_objects'),0)
        finally:snap.close()
        for key in ('runtime_objects','runtime_slots','runtime_payload_bytes'):self.assertEqual(snap.meter.used(key),0)
        snap.close()

    def test_rejects_lazy_mutable_closure_and_default_capture(self):
        sources=[
            '(zno) x := (zzz)(1);',
            '(zno) x := [(zzz)(1)];',
            '(zyes) x := []; (shape) Box { v := x; }',
            '(addnew) factory() { (zyes) x := 0; (return) (addnew)() => x; } (zno) f := factory();',
            '(zno) ns := array;',
            '(zno) c := sketch.canvas(10,10,"x");',
        ]
        for source in sources:
            with self.subTest(source=source),tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'module.zzy';path.write_text(source,encoding='utf-8')
                program,policy=load(path)
                with self.assertRaises(DiagnosticError) as error:initialize(program,policy,CancellationToken())
                self.assertEqual(error.exception.diagnostic.code,'E303')

    def test_readonly_closure_captures_are_frozen(self):
        source='(shape) Response { status; body; }\n(addnew) factory() { (zno) a := [1]; (return) (addnew)() => a; }\n(zno) f := factory();\n(addnew) read(r) { (return) Response::{status:200,body:f()}; }\n(addnew) write(r) { array.push(f(),2); }\n'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'module.zzy';path.write_text(source,encoding='utf-8');program,policy=load(path)
            snap=initialize(program,policy,CancellationToken())
            try:
                with self.assertRaises(DiagnosticError):call(program,policy,snap,'write')
                self.assertEqual(call(program,policy,snap,'read'),(200,b'[1]'))
            finally:snap.close()

    def test_dependency_defaults_and_failed_initialization_release(self):
        from zzy.web_shared import Initializer
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            (directory/'dep.zzy').write_text('(zno) values := [5]; (shape) Item { a := values; } (addnew) get() { (return) Item::{}; }')
            path=directory/'main.zzy'
            path.write_text('(use) "dep.zzy" (as) dep; (shape) Response { status; body; } (addnew) read(r) { (return) Response::{status:200,body:dep.get().a}; }')
            program,policy=load(path);snap=initialize(program,policy,CancellationToken())
            try:
                self.assertEqual(call(program,policy,snap,'read'),(200,b'[5]'))
                self.assertTrue(snap.modules)
            finally:snap.close()
            (directory/'dep.zzy').write_text('(zno) hidden := (zzz)(1); (addnew) get() { (return) hidden; }')
            program,policy=load(path)
            r=Initializer(program,Output(io.StringIO(),io.StringIO(),ResourceMeter(policy,Phase.EXECUTION)),io.StringIO())
            with self.assertRaises(DiagnosticError):r.run()
            self.assertFalse(hasattr(r,'snapshot'))
            self.assertTrue(all(r.meter.used(k)==0 for k in ('runtime_objects','runtime_slots','runtime_payload_bytes')))

    def test_native_nominal_definition_identity_and_private_namespace_cache(self):
        source='(shape) Response { status; body; } (addnew) accept(v: array.Stats) { (return) v.sum; } (addnew) read(r) { (return) Response::{status:200,body:accept(array.stats([2]))}; }'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'module.zzy';path.write_text(source);program,policy=load(path)
            snap=initialize(program,policy,CancellationToken())
            try:
                for _ in range(2):self.assertEqual(call(program,policy,snap,'read'),(200,b'2'))
            finally:snap.close()
