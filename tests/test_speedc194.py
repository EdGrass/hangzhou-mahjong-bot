# -*- coding: utf-8 -*-
"""C194：中盘3+对子、同向听、进张损失<=4 的外科式拆对。"""
import io,os,sys,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0,ROOT)
from bot.speedtugc import SpeedTUGC
from bot.speedc194 import SpeedC194
HAND=["5b","7b","8b","6w","3t","6t","5w","5t","6t","7b","7w","4t","7t","7t"]
DRAWN="7t"; BASE="3t"; C194="7b"
def view(river_len=24):
 river=[]
 # fixture only needs length; contents are public info but route metrics use hand primarily
 river=list(range(river_len))
 return {"seat":0,"phase":"draw","turn":0,"responding_seats":[],"my_hand":list(HAND),"melds":[],"drawn_tile":DRAWN,"offer_tile":None,"river":river,"river_len":river_len,"all_melds":[],"god":{"baotou":False,"chain_count":0,"catch_play":False,"piao_count":0,"god_discarder_seat":-1}}
class TestC194(unittest.TestCase):
 def test_registered_subclass(self):
  from run_bot import STRATEGY_FACTORIES as F
  self.assertIn("speedc194",F); self.assertIsInstance(F["speedc194"](),SpeedC194); self.assertTrue(issubclass(SpeedC194,SpeedTUGC))
 def test_fixture_base_outside_mid(self):
  self.assertEqual((SpeedTUGC().decide(view(0)) or {}).get("tile"),BASE)
  self.assertEqual((SpeedC194().decide(view(0)) or {}).get("tile"),BASE)
 def test_fixture_safe_pair_reduction_midgame(self):
  self.assertEqual((SpeedTUGC().decide(view(24)) or {}).get("tile"),BASE)
  p=SpeedC194(); act=p.decide(view(24)); self.assertEqual(act.get("tile"),C194); self.assertEqual(p.stats["changed"],1)
 def test_source_guardrails(self):
  with io.open(os.path.join(ROOT,"bot","speedc194.py"),encoding="utf-8") as fh: s=fh.read()
  self.assertIn("MAX_PAIRS = 2",s); self.assertIn("MID_LO = 12",s); self.assertIn("MID_HI = 28",s)
if __name__=="__main__": unittest.main()
