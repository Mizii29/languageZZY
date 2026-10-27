import unittest
from unittest.mock import patch
from tests import test_e1_runtime as helpers
from zzy.native.sketch_session import Session, QUEUE_LIMIT, QUEUE_BYTES


class ObjectTests(unittest.TestCase):
    inspect=helpers.SketchRuntimeTests.inspect
    call=helpers.SketchRuntimeTests.call
    error=helpers.SketchRuntimeTests.error

    def test_pick_translate_copy_delete_and_undo_with_lock(self):
        def check(r,c,p,n):
            identity=self.call(r,n,'pick',c,5,0).data;self.assertEqual(identity,1)
            self.assertEqual(self.call(r,n,'pick',c,50,50).kind,'Null')
            self.call(r,n,'translate_object',c,1,10,20)
            self.assertEqual(c.objects[0].geometry.strokes[0].points,((10.,20.),(20.,20.)))
            self.assertEqual(self.call(r,n,'copy_object',c,1).data,2)
            self.assertEqual(self.call(r,n,'pick',c,15,20).data,2)
            self.call(r,n,'delete_object',c,2);self.assertEqual(len(c.objects),1)
            self.call(r,n,'undo',c);self.assertEqual([b.geometry.id for b in c.objects],[1,2])
            self.call(r,n,'undo',c);self.call(r,n,'undo',c)
            self.assertEqual(c.objects[0].geometry.strokes[0].points,((0.,0.),(10.,0.)))
            self.call(r,n,'lock_layer',c.layer,True)
            self.assertEqual(self.call(r,n,'pick',c,5,0).data,1)
            self.error('E203',lambda:self.call(r,n,'delete_object',c,1))
            self.error('E204',lambda:self.call(r,n,'delete_object',c,999))
        self.inspect('sketch.forward(p,10);',check)

    def test_input_queue_capacity_bytes_and_close_independent(self):
        session=Session()
        for _ in range(QUEUE_LIMIT):session.send(('callback','key','a'))
        self.assertFalse(session.failed.is_set())
        session.send(('callback','key','b'))
        self.assertTrue(session.failed.is_set());self.assertTrue(session.closed.is_set())
        self.assertEqual(session.failure,('sketch.input_queue',QUEUE_LIMIT,QUEUE_LIMIT+1))
        session.cleanup();self.assertEqual(session.bytes,0)
        session=Session()
        with patch('zzy.native.sketch_session.QUEUE_BYTES',32):session.send(('callback','key','oversized'))
        self.assertEqual(session.failure[0],'sketch.queue_bytes')
        self.assertTrue(session.events.empty())


if __name__=='__main__':unittest.main()
