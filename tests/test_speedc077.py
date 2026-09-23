# -*- coding: utf-8 -*-
import os, unittest
from mahjong.sim import make_view
import bot.speedc077 as m

HAND = ["1w","2w","3w","4w","5w","6w","7w","8w","9w","1b","2b","3b","东","南"]
class T(unittest.TestCase):
 def test_missing_models_fall_back(self):
  st = m.C077Policy(model_path=os.path.join('var','__a__'), value_path=os.path.join('var','__b__'))
  v = make_view(0,'draw',0,HAND,melds=[],river=[],all_melds=[[],[],[],[]],dealer=0)
  a = st.decide(v); self.assertEqual(a.get('action'),'discard'); self.assertIn(a.get('tile'), HAND)
 def test_real_models_decide(self):
  if not (os.path.exists(m.DEFAULT_BC) and os.path.exists(m.DEFAULT_V)): self.skipTest('models absent')
  st = m.C077Policy()
  v = make_view(0,'draw',0,HAND,melds=[],river=['1t'],all_melds=[[],[],[],[]],dealer=0)
  a = st.decide(v); self.assertEqual(a.get('action'),'discard'); self.assertIn(a.get('tile'), HAND)
  self.assertGreaterEqual(st.stats.get('used',0), 0)
if __name__ == '__main__': unittest.main()
