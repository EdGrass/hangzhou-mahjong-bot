# -*- coding: utf-8 -*-
import os, unittest
from mahjong.sim import make_view
import bot.speedc068 as m

HAND=["1w","2w","3w","4w","5w","6w","7w","8w","9w","1b","2b","3b","东","南"]
class T(unittest.TestCase):
 def test_defaults_and_range(self):
  st=m.C068Policy(model_path=os.path.join('var','__no_c068__'))
  self.assertEqual(st.shanten_range,(1,2))
  st2=m.C068Policy(model_path=os.path.join('var','__no_c068__'),lo=0,hi=2)
  self.assertEqual(st2.shanten_range,(0,2))
  self.assertGreaterEqual(st2.max_candidates,2)
 def test_missing_falls_back(self):
  st=m.C068Policy(model_path=os.path.join('var','__no_c068__'),lo=0,hi=2)
  v=make_view(0,'draw',0,HAND,melds=[],river=[],all_melds=[[],[],[],[]],dealer=0)
  a=st.decide(v);self.assertEqual(a.get('action'),'discard');self.assertIn(a.get('tile'),HAND)
 def test_real_model_loads(self):
  p=os.path.join('var','c068_bc_net.pt')
  if not os.path.exists(p): self.skipTest('model not built yet')
  st=m.C068Policy(model_path=p)
  self.assertIsNotNone(st.model)
if __name__=='__main__':unittest.main()
