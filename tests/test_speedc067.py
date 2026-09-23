# -*- coding: utf-8 -*-
import os, unittest
from mahjong.sim import make_view
import bot.speedc067 as m

HAND=["1w","2w","3w","4w","5w","6w","7w","8w","9w","1b","2b","3b","东","南"]
class T(unittest.TestCase):
 def test_missing_falls_back(self):
  st=m.C067Policy(model_path=os.path.join('var','__no_c067__'))
  v=make_view(0,'draw',0,HAND,melds=[],river=[],all_melds=[[],[],[],[]],dealer=0)
  a=st.decide(v);self.assertEqual(a.get('action'),'discard');self.assertIn(a.get('tile'),HAND)
 def test_feat_shape(self):
  st=m.C067Policy(model_path=os.path.join('var','__no_c067__'))
  self.assertEqual(len(m._state_feat(HAND[:13],0,0,use_ukeire=True)),43)
if __name__=='__main__':unittest.main()