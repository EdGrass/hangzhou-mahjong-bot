# -*- coding: utf-8 -*-
import os, unittest
from mahjong.sim import make_view
import bot.speedc068e as m

HAND=["1w","2w","3w","4w","5w","6w","7w","8w","9w","1b","2b","3b","东","南"]
class T(unittest.TestCase):
 def test_ensemble_loads_and_scores(self):
  missing=[os.path.join('var','__no1__'),os.path.join('var','__no2__')]
  st=m.C068ePolicy(model_paths=missing)
  self.assertIsNone(st.model)
  paths=[p for p in m.DEFAULT_PATHS if os.path.exists(p)]
  if len(paths)<2: self.skipTest('need 2 models')
  st2=m.C068ePolicy(model_paths=paths)
  self.assertEqual(st2.members,len(paths))
  sc=st2.model.score([[0.0]*154]*3)
  self.assertEqual(len(sc),3)
 def test_fallback_without_model(self):
  st=m.C068ePolicy(model_paths=[os.path.join('var','__no__')])
  v=make_view(0,'draw',0,HAND,melds=[],river=[],all_melds=[[],[],[],[]],dealer=0)
  a=st.decide(v);self.assertEqual(a.get('action'),'discard');self.assertIn(a.get('tile'),HAND)
if __name__=='__main__':unittest.main()
