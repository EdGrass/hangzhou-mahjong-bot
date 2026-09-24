# -*- coding: utf-8 -*-
import os, unittest
import numpy as np
from mahjong.sim import make_view
import bot.speedc068b as m
import bot.speedc067 as c067

HAND=["1w","2w","3w","4w","5w","6w","7w","8w","9w","1b","2b","3b","东","南"]
class T(unittest.TestCase):
 def test_visible_counts(self):
  st=m.C068bPolicy(model_path=os.path.join('var','__no__'))
  v=make_view(0,'draw',0,HAND,melds=[],river=['1t','9t'],
              all_melds=[[],[{'type':'peng','tile':'5b','tiles':['5b','5b','5b']}],[],[]],dealer=0)
  vis=st._visible(v)
  self.assertEqual(vis.shape,(34,))
  self.assertEqual(float(vis.sum()),5.0)
 def test_features_match_c067_when_no_visibility(self):
  st=m.C068bPolicy(model_path=os.path.join('var','__no__'))
  st._vis=np.zeros(34,dtype=np.float32)
  st2=c067.C067Policy(model_path=os.path.join('var','__no__'))
  a=st._features(HAND,['南','东'],'南',0,0)
  b=st2._features(HAND,['南','东'],'南',0,0)
  self.assertEqual(len(a),2); self.assertEqual(len(a[0]),154)
  self.assertTrue(np.allclose(np.asarray(a,float),np.asarray(b,float)))
 def test_missing_model_falls_back(self):
  st=m.C068bPolicy(model_path=os.path.join('var','__no__'))
  v=make_view(0,'draw',0,HAND,melds=[],river=[],all_melds=[[],[],[],[]],dealer=0)
  a=st.decide(v);self.assertEqual(a.get('action'),'discard');self.assertIn(a.get('tile'),HAND)
if __name__=='__main__':unittest.main()
