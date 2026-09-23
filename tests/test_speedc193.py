# -*- coding: utf-8 -*-
"""C193：仅做庄时启用 c151 压对数路线，做闲严格回退 speedtugc。"""
import inspect, os, sys, unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0,ROOT)
from bot.speedc151 import SpeedC151
from bot.speedtugc import SpeedTUGC
from bot.speedc193 import SpeedC193
HAND=["9b","2w","7w","7b","1b","2w","东","1w","4w","1b","东","1b","3w","8w"]
DRAWN="8w"
def view(dealer,seat=0):
 return {"seat":seat,"phase":"draw","turn":seat,"my_hand":list(HAND),"melds":[],"drawn_tile":DRAWN,"river":[],"river_len":6,"all_melds":[],"dealer":dealer,"god":{"baotou":False,"chain_count":0,"catch_play":False,"piao_count":0,"god_discarder_seat":-1}}
class TestC193(unittest.TestCase):
 def test_registered_subclass(self):
  from run_bot import STRATEGY_FACTORIES as F
  self.assertIn("speedc193",F); self.assertIsInstance(F["speedc193"](),SpeedC193); self.assertTrue(issubclass(SpeedC193,SpeedTUGC))
 def test_dealer_uses_route(self):
  self.assertEqual(SpeedC151()._pick_discard(HAND,DRAWN,0,0,view=view(0)),SpeedC193()._pick_discard(HAND,DRAWN,0,0,view=view(0)))
 def test_nondealer_uses_speedtugc(self):
  self.assertEqual(SpeedTUGC()._pick_discard(HAND,DRAWN,0,0,view=view(1)),SpeedC193()._pick_discard(HAND,DRAWN,0,0,view=view(1)))
 def test_only_pick_hook(self):
  self.assertIs(SpeedC193.decide,SpeedTUGC.decide)
  self.assertIsNot(SpeedC193._pick_discard,SpeedTUGC._pick_discard)
if __name__=="__main__": unittest.main()
