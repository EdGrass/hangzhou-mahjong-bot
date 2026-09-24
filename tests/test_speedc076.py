# -*- coding: utf-8 -*-
import os, unittest
import numpy as np
from mahjong.sim import make_view
import bot.speedc076 as m

HAND = ["1w","2w","3w","4w","5w","6w","7w","8w","9w","1b","2b","3b","东","南"]
class T(unittest.TestCase):
 def test_fallback_without_value(self):
  st = m.C076Policy(value_path=os.path.join('var','__no__'), base_model=os.path.join('var','__no__'))
  self.assertIsNone(st.model)
  v = make_view(0,'draw',0,HAND,melds=[],river=[],all_melds=[[],[],[],[]],dealer=0)
  a = st.decide(v); self.assertEqual(a.get('action'),'discard'); self.assertIn(a.get('tile'), HAND)
 def test_feature_dim_matches_net(self):
  p = os.path.join('var','c076_value_net.pt')
  if not os.path.exists(p): self.skipTest('value net absent')
  st = m.C076Policy(value_path=p, base_model=os.path.join('var','__no__'))
  v = make_view(0,'draw',0,HAND,melds=[],river=['1t','2t'],all_melds=[[],[],[],[]],dealer=0)
  st._visible(v)
  rows = st._features(HAND, ['南','东'], '南', 0, 0)
  self.assertEqual(len(rows), 2); self.assertEqual(len(rows[0]), 47)
  sc = st.model.score(rows); self.assertEqual(len(sc), 2)
if __name__ == '__main__': unittest.main()
