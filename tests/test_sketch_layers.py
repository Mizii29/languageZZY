import unittest
import xml.etree.ElementTree as ET
from tests import test_e1_runtime as helpers
from zzy.values import freeze


class LayerTests(unittest.TestCase):
    inspect=helpers.SketchRuntimeTests.inspect
    call=helpers.SketchRuntimeTests.call
    error=helpers.SketchRuntimeTests.error

    def test_layers_order_visibility_lock_and_snapshot(self):
        def check(r,c,p,n):
            layer=self.call(r,n,'add_layer',c,'top')
            self.call(r,n,'set_layer',p,layer);self.call(r,n,'move_to',p,10,10)
            self.call(r,n,'lock_layer',layer,True)
            self.error('E203',lambda:self.call(r,n,'forward',p,1))
            self.call(r,n,'lock_layer',layer,False)
            info=self.call(r,n,'layer_info',c)
            self.assertEqual([i.data[1]['count'].data for i in info.data],[1,1])
            self.assertTrue(all(i.frozen for i in info.data))
            self.call(r,n,'rename_layer',layer,'new')
            self.assertEqual(info.data[1].data[1]['name'].data,'top')
            self.error('E208',lambda:self.call(r,n,'rename_layer',layer,'default'))
            self.error('E204',lambda:self.call(r,n,'move_layer',layer,2))
            self.call(r,n,'move_layer',layer,0)
            xml=self.call(r,n,'svg_text',c).data[1].data
            self.assertLess(xml.index('object-2'),xml.index('object-1'))
            self.call(r,n,'layer_visible',layer,False)
            self.assertNotIn('object-2',self.call(r,n,'svg_text',c).data[1].data)
            freeze(layer,r,n)
            self.error('E203',lambda:self.call(r,n,'layer_visible',layer,True))
        self.inspect('sketch.forward(p,10);',check)

    def test_text_is_upright_escaped_ignores_up_and_does_not_move(self):
        def check(r,c,p,n):
            before=p.state
            self.call(r,n,'text',p,'<>&中文',20)
            self.assertEqual(p.state,before)
            xml=self.call(r,n,'svg_text',c).data[1].data
            elem=ET.fromstring(xml).find('.//{http://www.w3.org/2000/svg}text')
            self.assertEqual(elem.text,'<>&中文')
            self.assertEqual(elem.attrib['y'],'-12.0')
            self.assertEqual(elem.attrib['text-anchor'],'end')
            self.assertNotIn('scale(',xml)
            self.error('E208',lambda:self.call(r,n,'text_align',p,'unknown'))
            self.error('E208',lambda:self.call(r,n,'text',p,'bad',0))
            self.assertEqual(len(c.objects),1)
        self.inspect('sketch.jump_to(p,5,12);sketch.pen_up(p);sketch.font(p,"A&B");sketch.text_align(p,"right");',check)


if __name__=='__main__':unittest.main()
