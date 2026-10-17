import io
import unittest
from pathlib import Path
from PIL import Image
from arc_runtime.frame_hints import fingerprint,hint,load_prototypes


def image_bytes(color):
    b=io.BytesIO()
    im=Image.new('RGB',(709,1536),color)
    im.save(b,format='JPEG',quality=75)
    return b.getvalue()

class VisualHintsTest(unittest.TestCase):
    def test_matching_color(self):
        red=fingerprint(image_bytes((190,20,20)))
        blue=fingerprint(image_bytes((20,20,190)))
        result=hint(image_bytes((185,22,22)),{'red':[red],'blue':[blue]})
        self.assertEqual(result['scene_hint'],'red')
    def test_abstains_on_ambiguous(self):
        rgb=image_bytes((100,100,100))
        f=fingerprint(rgb)
        out=hint(rgb,{'both-a':[f],'both-b':[f]})
        self.assertEqual(out['scene_hint'],'unknown')
    def test_reject_bad_shape(self):
        out=io.BytesIO(); Image.new('RGB',(400,400),'red').save(out,format='JPEG')
        with self.assertRaises(ValueError):fingerprint(out.getvalue())
    def test_actual_signatures_file_is_valid(self):
        p=Path(__file__).resolve().parents[1]/'arc_runtime'/'visual_hints.json'
        signatures=load_prototypes(p)
        self.assertIn('live_table',signatures)
        self.assertEqual(len(signatures['live_table'][0]),12*24*3)
