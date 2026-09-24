# -*- coding: utf-8 -*-
import os, unittest
import numpy as np
from mahjong.sim import make_view
import bot.speedc069 as m

HAND = ["1w","2w","3w","4w","5w","6w","7w","8w","9w","1b","2b","3b","东","南"]
class T(unittest.TestCase):
 def test_feature_dim_matches_model(self):
  p = os.path.join('var','c069_bc_net.pt')
  if not os.path.exists(p): self.skipTest('model absent')
  import torch
  blob = torch.load(p, map_location='cpu', weights_only=False)
  st = m.C069Policy(model_path=p)
  rows = st._features(HAND, ['南','东'], '南', 0, 0)
  self.assertEqual(len(rows[0]), int(blob['din']))
  self.assertEqual(len(rows[0]), 198)
 def test_candidate_feat_matches_trainer(self):
  import importlib.util
  spec = importlib.util.spec_from_file_location('c069t', os.path.join('var','_c069_discard_train.py'))
  mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
  a = np.asarray(m.cand_feat(HAND, '南', 0, 0), dtype=np.float32)
  b = np.asarray(mod.feat(HAND, '南', 0, 0), dtype=np.float32)
  self.assertTrue(np.allclose(a, b))
 def test_missing_model_falls_back(self):
  st = m.C069Policy(model_path=os.path.join('var','__no__'))
  v = make_view(0,'draw',0,HAND,melds=[],river=[],all_melds=[[],[],[],[]],dealer=0)
  a = st.decide(v); self.assertEqual(a.get('action'),'discard'); self.assertIn(a.get('tile'), HAND)
if __name__ == '__main__': unittest.main()
