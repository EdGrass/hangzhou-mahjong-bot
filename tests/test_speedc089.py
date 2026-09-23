# -*- coding: utf-8 -*-
import os, unittest
from mahjong.sim import make_view
import bot.speedc089 as m

HAND = ["1w","2w","3w","4w","5w","6w","7w","8w","9w","1b","2b","3b","东","南"]
class T(unittest.TestCase):
 def test_falls_back_without_ranker(self):
  st = m.C089Policy(model_path=os.path.join('var','c073_orig_w4_net.pt'),
                    order_path=os.path.join('var','__no__'))
  self.assertIsNone(st.ranker)
  v = make_view(0,'draw',0,HAND,melds=[],river=['1t'],all_melds=[[],[],[],[]],dealer=0)
  a = st.decide(v); self.assertEqual(a.get('action'),'discard'); self.assertIn(a.get('tile'), HAND)
 def test_with_ranker(self):
  p = os.path.join('var','c089_ranker_net.pt')
  if not os.path.exists(p): self.skipTest('ranker absent')
  st = m.C089Policy(model_path=os.path.join('var','c073_orig_w4_net.pt'), order_path=p)
  self.assertIsNotNone(st.ranker)
  v = make_view(0,'draw',0,HAND,melds=[],river=['1t'],all_melds=[[],[],[],[]],dealer=0)
  a = st.decide(v); self.assertEqual(a.get('action'),'discard')
if __name__ == '__main__': unittest.main()
