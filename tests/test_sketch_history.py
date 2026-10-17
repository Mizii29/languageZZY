import unittest
from unittest.mock import patch
from tests import test_e1_runtime as helpers
from zzy.diagnostics import ResourceExceeded
from zzy.native import sketch_history as history
from zzy.native.sketch_replay import Replay


class HistoryTests(unittest.TestCase):
    inspect=helpers.SketchRuntimeTests.inspect
    call=helpers.SketchRuntimeTests.call
    error=helpers.SketchRuntimeTests.error

    def test_multi_pen_group_restores_states_and_geometry_and_high_water(self):
        def check(r,c,p,n):
            q=self.call(r,n,'pen',c,'second');p0=p.state;q0=q.state
            self.call(r,n,'begin_group',c,'two pens')
            self.call(r,n,'forward',p,10);self.call(r,n,'left',q,90);self.call(r,n,'forward',q,5)
            self.error('E214',lambda:self.call(r,n,'undo',c))
            self.error('E214',lambda:self.call(r,n,'svg_text',c))
            self.call(r,n,'end_group',c)
            blocks=tuple(c.objects);self.assertEqual(len(c.history),1)
            self.assertTrue(self.call(r,n,'undo',c).data)
            self.assertEqual((p.state,q.state,c.objects),(p0,q0,[]));self.assertEqual(c.next_id,3)
            self.assertTrue(self.call(r,n,'redo',c).data)
            self.assertEqual(tuple(c.objects),blocks)
            self.assertTrue(all(a is b for a,b in zip(c.objects,blocks)))
            self.call(r,n,'undo',c);self.call(r,n,'forward',p,1)
            self.assertEqual(c.objects[0].geometry.id,3)
            self.assertFalse(self.call(r,n,'redo',c).data)
        self.inspect('',check)

    def test_fill_single_command_and_cancel_no_history(self):
        def check(r,c,p,n):
            initial=p.state
            self.call(r,n,'begin_fill',p);self.call(r,n,'forward',p,10)
            self.call(r,n,'left',p,90);self.call(r,n,'forward',p,10)
            self.call(r,n,'end_fill',p)
            self.assertEqual(len(c.history),1);final=p.state
            self.call(r,n,'undo',c);self.assertEqual(p.state,initial);self.assertFalse(c.objects)
            self.call(r,n,'redo',c);self.assertEqual(p.state,final)
            self.call(r,n,'begin_fill',p);self.call(r,n,'forward',p,1);self.call(r,n,'cancel_fill',p)
            self.assertEqual(len(c.history),1)
        self.inspect('',check)

    def test_history_quota_atomic_and_clear_releases(self):
        def check(r,c,p,n):
            with patch.object(history,'COMMANDS',1):
                self.call(r,n,'forward',p,1);state=p.state;block=c.objects[0]
                with self.assertRaises(ResourceExceeded):self.call(r,n,'forward',p,2)
                self.assertEqual(p.state,state);self.assertEqual(c.objects,[block]);self.assertEqual(c.next_id,2)
                self.call(r,n,'undo',c);self.call(r,n,'forward',p,3)
                self.assertFalse(self.call(r,n,'redo',c).data)
            self.call(r,n,'clear_history',c);self.assertFalse(c.history);self.assertFalse(c.redo_history)
            with patch.object(history,'BYTES',1):
                old=p.state
                with self.assertRaises(ResourceExceeded):self.call(r,n,'left',p,5)
                self.assertEqual(p.state,old)
            self.assertEqual((c.history_bytes,c.history_count),(0,0))
        self.inspect('',check)

    def test_clear_and_layers_undo(self):
        def check(r,c,p,n):
            self.call(r,n,'clear_history',c)
            old=c.objects[0]
            self.call(r,n,'clear',c);self.call(r,n,'undo',c)
            self.assertIs(c.objects[0],old)
            layer=self.call(r,n,'add_layer',c,'layer')
            self.call(r,n,'undo',c);self.assertEqual(len(c.layers),1)
            self.call(r,n,'redo',c);self.assertIs(c.layers[1],layer)
            self.call(r,n,'layer_visible',layer,False);self.call(r,n,'undo',c)
            self.assertTrue(layer.visible)
        self.inspect('sketch.forward(p,10);',check)

    def test_replay_seek_isolated_shared_paths_bounded_checkpoints(self):
        def check(r,c,p,n):
            for _ in range(40):self.call(r,n,'forward',p,1)
            real_state=p.state;real_blocks=tuple(c.objects)
            replay=Replay(r,c,n)
            self.assertEqual(len(replay.scene().geometries),0)
            replay.seek(17)
            self.assertEqual(len(replay.scene().geometries),17)
            self.assertEqual(replay.scene().pens[0][1].position,(17.,0.))
            replay.seek(40);replay.seek(2);replay.seek(40)
            self.assertEqual(replay.scene().geometries,tuple(b.geometry for b in real_blocks))
            self.assertTrue(all(g is b.geometry for g,b in zip(replay.scene().geometries,real_blocks)))
            self.assertLessEqual(len(replay.checkpoints),8)
            self.assertEqual(p.state,real_state);self.assertEqual(tuple(c.objects),real_blocks)
            replay.close()
        self.inspect('',check)


if __name__=='__main__':unittest.main()
