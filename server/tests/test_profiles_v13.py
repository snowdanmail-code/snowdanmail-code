import cv2
from pathlib import Path
import unittest
from arc_vision.combined_observer import CompositeObserver
from arc_vision.money_reader import MoneyReadError

ROOT=Path(__file__).resolve().parents[2]
class CaptureProfileRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.im=cv2.imread(str(ROOT/'datasets/cards_gold/cards_1307.jpg'))
        cls.im[638:705,300:412]=cv2.imread(str(ROOT/'datasets/money_gold/bank_1307.png'))
        cls.engine=CompositeObserver()
    def processed(self,edge,quality):
        scale=edge/max(self.im.shape[:2]);sz=(round(self.im.shape[1]*scale),round(self.im.shape[0]*scale))
        crop=cv2.resize(self.im,sz,interpolation=cv2.INTER_AREA)
        ok,jpg=cv2.imencode('.jpg',crop,[cv2.IMWRITE_JPEG_QUALITY,quality])
        self.assertTrue(ok)
        return self.engine.read(jpg.tobytes(),screen_state='live_table')
    def test_full_size_moderate_quality(self):
        r=self.processed(1536,75)
        self.assertEqual(r['cards']['quality'],'complete')
        self.assertEqual(r['amounts']['pot']['cents'],30)
        self.assertEqual(r['cards']['hero_cards'],['4d','Qd'])
    def test_small_presets_are_not_counted_as_verified(self):
        for long_edge,q in ((720,55),(960,75)):
            with self.subTest(edge=long_edge),self.assertRaises(MoneyReadError):
                self.processed(long_edge,q)
        r=self.processed(1280,88)
        self.assertNotEqual(r['cards']['quality'],'complete')
    def test_low_jpeg_quality_not_same_as_low_resolution(self):
        r=self.processed(1536,55)
        self.assertEqual(r['cards']['quality'],'complete')

if __name__=='__main__':unittest.main()
