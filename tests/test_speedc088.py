# -*- coding: utf-8 -*-
import os, unittest
import numpy as np
from mahjong.sim import make_view
import bot.speedc088 as m

HAND = ["1w","2w","3w","4w","5w","6w","7w","8w","9w","1b","2b","3b","东","南"]
class T(unittest.TestCase):
 def test_tta_runs_and_falls_back(self):
  p = os.path.join('var','c073_orig_w4_net.pt')
  if not os.path.exists(p): self.skipTest('model absent')
  st = m.C088Policy(model_path=p)
  v = make_view(0,'draw',0,HAND,melds=[],river=['1t'],all_melds=[[],[],[],[]],dealer=0)
  a = st.decide(v); self.assertEqual(a.get('action'),'discard'); self.assertIn(a.get('tile'), HAND)
  self.assertGreaterEqual(st.stats.get('used',0), 0)
 def test_permute_shape(self):
  st = m.C088Policy(model_path=os.path.join('var','__no__'))
  rows = [[0.0]*154, [1.0]*154]
  r = st._permute(rows, st.perms[1])
  self.assertEqual(r.shape, (2,154))
if __name__ == '__main__': unittest.main()
