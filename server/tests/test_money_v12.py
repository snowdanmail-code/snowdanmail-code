"""Measured regression. Gold values annotated from original screenshots.

Holdout screens may share a hand with the training atlas; these tests do NOT
establish generalization across layout changes, apps or font updates.
"""
import base64
import http.client
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import cv2
from arc_vision.money_reader import TemplateMoneyReader,MoneyReadError
from arc_vision.combined_observer import CompositeObserver
from server import ApiHandler

ROOT=Path(__file__).resolve().parents[2]
MONEY_GOLD=ROOT/'datasets'/'money_gold'
CARDS_GOLD=ROOT/'datasets'/'cards_gold'
TRAIN={'1263':176,'1273':0,'1283':5,'1287':15,'1299':13,'1307':30,'1313':12,'1315':14,'1291':18,'1295':67}
HOLDOUT={'1267':177,'1269':10,'1271':10,'1279':7,'1281':0,'1285':11,
         '1289':16,'1293':18,'1297':3,'1301':18,'1303':18,'1305':30,
         '1309':0,'1311':3,'1317':14,'1319':3,'1327':7,'1339':14}

class MoneyReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.reader=TemplateMoneyReader()
    def _image(self,name):
        image=cv2.imread(str(CARDS_GOLD/('cards_'+name+'.jpg'))) if (CARDS_GOLD/('cards_'+name+'.jpg')).exists() else None
        if image is None:
            import numpy as np
            image=np.full((1536,709,3),42,dtype=np.uint8)
        crop=cv2.imread(str(MONEY_GOLD/('bank_'+name+'.png')))
        if crop is None:raise AssertionError('fixture_missing')
        image[638:705,300:412]=crop
        if name=='1263':
            image[875:935,300:412]=cv2.imread(str(MONEY_GOLD/'center_1263.png'))
        return image
    def test_training_reference(self):
        for name,cents in TRAIN.items():
            with self.subTest(name=name):
                result=self.reader.read_pot(self._image(name))
                self.assertEqual(result['status'],'recognized')
                self.assertEqual(result['cents'],cents)
                self.assertFalse(result['confidence_calibrated'])
    def test_holdout_reference(self):
        for name,cents in HOLDOUT.items():
            with self.subTest(name=name):
                result=self.reader.read_pot(self._image(name))
                self.assertEqual(result['status'],'recognized')
                self.assertEqual(result['cents'],cents)
    def test_overlay_abstains(self):
        image=self._image('1299')
        self.assertEqual(self.reader.read_pot(image,screen_state='replay')['status'],'abstain')
        image[642:706,300:414]//=6
        self.assertEqual(self.reader.read_pot(image)['status'],'abstain')
    def test_disconnected_screenshot_abstains(self):
        image=self._image('1319')
        image[638:705,300:412]//=7
        self.assertEqual(self.reader.read_pot(image)['status'],'abstain')
    def test_geometry_errors(self):
        with self.assertRaises(MoneyReadError):self.reader.read_pot(cv2.imread(__file__))
        with self.assertRaises(MoneyReadError):self.reader.read(b'wrong')
    def test_central_chip_never_claimed_to_be_bet(self):
        image=self._image('1263')
        # Center pile text 1.68 != total pot 1.76: never add as action amount.
        self.assertEqual(self.reader.read_central_chips(image)['cents'],168)
        self.assertEqual(self.reader.read_pot(image)['cents'],176)

class CompositeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.reader=CompositeObserver()
    def _read(self,name,state='live_table'):
        image=cv2.imread(str(CARDS_GOLD/('cards_'+name+'.jpg')))
        if image is None:self.skipTest('card fixture not included')
        image[638:705,300:412]=cv2.imread(str(MONEY_GOLD/('bank_'+name+'.png')))
        ok,jpg=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,96])
        return self.reader.read(jpg.tobytes(),screen_state=state)
    def test_known_made_hand(self):
        x=self._read('1307')
        self.assertEqual(x['quality'],'measured')
        self.assertEqual(x['cards']['hero_cards'],['4d','Qd'])
        self.assertEqual(x['amounts']['pot']['cents'],30)
        self.assertEqual(x['known_made_hand']['category'],'three_of_a_kind')
        self.assertFalse(x['money_actions_enabled'])
        self.assertIsNone(x['action'])
    def test_overlay_no_inference(self):
        x=self._read('1307','replay')
        self.assertEqual(x['quality'],'abstain')
        self.assertIsNone(x['known_made_hand'])
    def test_partial_card_no_faked_hand(self):
        x=self._read('1291')
        self.assertIsNone(x['known_made_hand'])
        self.assertEqual(x['amounts']['pot']['cents'],18)

class HttpMeasureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),ApiHandler)
        cls.t=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.t.start()
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close()
    def _call(self,payload,token='token-vision-test-v12'):
        con=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=15)
        con.request('POST','/vision/measure',json.dumps(payload).encode('utf-8'),
            {'Content-Type':'application/json','X-Device-Token':token})
        r=con.getresponse();data=json.loads(r.read()); status=r.status;con.close()
        return status,data
    def test_measure_auth_and_read_only(self):
        image=cv2.imread(str(CARDS_GOLD/'cards_1307.jpg'))
        image[638:705,300:412]=cv2.imread(str(MONEY_GOLD/'bank_1307.png'))
        ok,jpeg=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,96])
        payload={'request':'vision_measure','screen_state':'live_table',
                 'image_base64':base64.b64encode(jpeg.tobytes()).decode()}
        with patch.dict(os.environ,{'ARC_DEVICE_TOKEN':'token-vision-test-v12'}):
            status,data=self._call(payload)
            self.assertEqual(status,200)
            self.assertEqual(data['amounts']['pot']['cents'],30)
            self.assertEqual(data['known_made_hand']['category'],'three_of_a_kind')
            self.assertIsNone(data['action']);self.assertFalse(data['can_place_wager'])
            self.assertEqual(self._call(payload,'wrong')[0],401)
            self.assertEqual(self._call({**payload,'extra':'bad'})[0],400)

class VideoMoneyGold(unittest.TestCase):
    def test_video_crop_gold(self):
        import numpy as np
        root=ROOT/'datasets'/'video_money_checks'
        labels=json.loads((root/'gold.json').read_text())['labels']
        reader=TemplateMoneyReader()
        self.assertGreaterEqual(len(labels),12)
        for row in labels:
            with self.subTest(frame=row['file']):
                canvas=np.full((1536,709,3),42,dtype=np.uint8)
                patch=cv2.imread(str(root/row['file']))
                self.assertEqual(patch.shape,(67,112,3))
                canvas[638:705,300:412]=patch
                value=reader.read_pot(canvas)
                self.assertEqual(value['cents'],row['cents'])

class CompressionV12(unittest.TestCase):
    def test_bank_text_at_jpeg_profiles(self):
        import numpy as np
        f=ROOT/'datasets'/'money_gold'/'bank_1307.png'
        image=np.full((1536,709,3),42,dtype=np.uint8)
        image[638:705,300:412]=cv2.imread(str(f))
        reader=TemplateMoneyReader()
        for quality in (55,75,88):
            with self.subTest(q=quality):
                ok,data=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,quality])
                decoded=cv2.imdecode(data,cv2.IMREAD_COLOR)
                self.assertEqual(reader.read_pot(decoded)['cents'],30)
