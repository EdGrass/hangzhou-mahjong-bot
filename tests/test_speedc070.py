# -*- coding: utf-8 -*-
import os, unittest
import numpy as np
from mahjong.sim import make_view
import bot.speedc070 as m

HAND = ["1w","2w","3w","5b","5b","6b","7b","1t","2t","3t","东","东","南"]
class T(unittest.TestCase):
 def test_falls_back_without_meld_model(self):
  st = m.C070Policy(model_path=os.path.join('var','__no1__'), meld_path=os.path.join('var','__no2__'))
  self.assertIsNone(st.meld_model)
  v = make_view(0, 'response_peng', 3, HAND, melds=[], offer='5b', river=['5b'], responding=[0],
                all_melds=[[],[],[],[]], dealer=0)
  a = st.decide(v)
  self.assertIn(a.get('action'), ('peng','pass'))
 def test_meld_rows_shape(self):
  p = os.path.join('var','c070_meld_net.pt')
  if not os.path.exists(p): self.skipTest('model absent')
  st = m.C070Policy(model_path=os.path.join('var','__no1__'), meld_path=p)
  self.assertIsNotNone(st.meld_model)
  v = make_view(0, 'response_peng', 3, HAND, melds=[], offer='5b', river=['5b'], responding=[0],
                all_melds=[[],[],[],[]], dealer=0)
  rows, base, ok, hand, offer, mc = st._meld_rows(v, 'peng')
  self.assertEqual(len(rows), 2); self.assertEqual(len(rows[0]), m.ROW_DIM); self.assertTrue(ok)
 def test_chi_policy_runs(self):
  p = os.path.join('var','c070_meld_net.pt')
  if not os.path.exists(p): self.skipTest('model absent')
  st = m.C070Policy(model_path=os.path.join('var','c068_bc_lo0_net.pt'), meld_path=p)
  v = make_view(0, 'response_chi', 3, HAND, melds=[], offer='5b', river=['5b'], responding=[0],
                all_melds=[[],[],[],[]], dealer=0)
  a = st.decide(v); self.assertIn(a.get('action'), ('chi','pass'))
if __name__ == '__main__': unittest.main()
