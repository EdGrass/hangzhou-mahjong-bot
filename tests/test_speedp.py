# -*- coding: utf-8 -*-
"""SpeedP（打点/弃胡财飘）单测——TDD：先钉期望行为。

覆盖：
1. decide 层：爆头态摸白 → 弃白飘；链满/末盘 → 收胡；非白爆头 → 胡；
   非胡局面与 E 一致；
2. 模拟器端到端：定制造牌山（seat0 = 4面子+白，墙顶两张白 + 任意胡牌），
   SpeedP 连续两飘后三飘胡 —— fan = 平胡1 ×2^2(链) ×爆头2 = 8（E 首巡即胡
   fan=2），得分/守恒/0 违规断言（引擎链计番已与服务器 fan-calc 黄金集对齐，
   本测试验证【策略触发 + 全流程合法性】）。
"""
import unittest

from mahjong.sim import SimGame
from bot.speede import SpeedE
from bot.speedp import SpeedP

W = "白"


def mk_view(hand14, drawn, baotou=False, chain=0, catch_play=False, river=None,
            piao=0):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "drawn_tile": drawn, "my_hand": list(hand14), "melds": [],
            "god": {"baotou": baotou, "chain_count": chain,
                    "catch_play": catch_play, "piao_count": piao},
            "offer_tile": None, "river": list(river or [])}


MELDS14 = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
           "1b", "2b", "3b", W]      # 12 + 白（摸前爆头）


class TestDecidePiao(unittest.TestCase):
    def test_baotou_drawn_white_piao(self):
        # 爆头态摸白：13+白 = 可胡；应弃刚摸的白（财飘），而非胡
        p = SpeedP()
        v = mk_view(MELDS14 + [W], W, baotou=True)
        self.assertEqual(p.decide(v), {"action": "discard", "tile": W})

    def test_speedE_hus_in_same_spot(self):
        e = SpeedE()
        v = mk_view(MELDS14 + [W], W, baotou=True)
        self.assertEqual(e.decide(v), {"action": "hu", "tile": ""})

    def test_chain_at_max_hus(self):
        p = SpeedP()
        v = mk_view(MELDS14 + [W], W, baotou=True, chain=3)   # max_chain=3
        self.assertEqual(p.decide(v), {"action": "hu", "tile": ""})

    def test_late_river_hus(self):
        p = SpeedP()
        v = mk_view(MELDS14 + [W], W, baotou=True, river=["1w"] * 60)
        self.assertEqual(p.decide(v), {"action": "hu", "tile": ""})

    def test_baotou_drawn_nonwhite_hus(self):
        # 爆头态摸非白：只能胡（弃非白不回爆头态）
        p = SpeedP()
        v = mk_view(MELDS14 + ["4t"], "4t", baotou=True)
        self.assertEqual(p.decide(v), {"action": "hu", "tile": ""})

    def test_not_baotou_drawn_white_hus(self):
        # 非爆头态摸白：正常胡（不飘）
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "1b", "1b", "1b", "东", W]
        p = SpeedP()
        v = mk_view(hand, W, baotou=False)
        self.assertEqual(p.decide(v), {"action": "hu", "tile": ""})

    def test_no_hu_falls_back_to_speedE_discard(self):
        # 非胡局面：与 E 同张（孤字 tie 语义继承）
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "东", "南", "北", "中", "发"]
        p, e = SpeedP(), SpeedE()
        v = mk_view(hand, "发", baotou=False)
        self.assertEqual(p.decide(v), e.decide(v))
        self.assertEqual((p.decide(v) or {}).get("action"), "discard")


def _deck_for_piao_scenario():
    """构造定制造牌山：seat0=4面子+白；摸牌序（座序 0,1,2,3 轮换，
    seat0 抽第 0/4/8 张）：白 →(s1,s2,s3 垃圾摸) → 白 →(垃圾×3) → 5w(胡)。"""
    s0 = list(MELDS14)
    s1 = ["东", "南", "西", "北", "中", "发", "1w", "1b", "1t",
          "2w", "2b", "2t", "9w"]
    s2 = ["东", "南", "西", "北", "中", "发", "3w", "3b", "3t",
          "5w", "5b", "5t", "9b"]
    s3 = ["东", "南", "西", "北", "中", "发", "6w", "6b", "6t",
          "8w", "8b", "8t", "9t"]
    scripted = [W, "3w", "3b", "3t", W, "4w", "4b", "4t", "5w"]
    used = {}
    for t in s0 + s1 + s2 + s3 + scripted:
        used[t] = used.get(t, 0) + 1
    assert used[W] == 3 and all(v <= 4 for v in used.values())
    rest = []
    codes = ["%d%s" % (n, s) for s in "wbt" for n in range(1, 10)] + \
            ["东", "南", "西", "北", "中", "发", W]
    for c in codes:
        left = 4 - used.get(c, 0)
        rest += [c] * left
    return s0 + s1 + s2 + s3 + scripted + rest


class TestPiaoSimEndToEnd(unittest.TestCase):
    def test_double_piao_then_hu_scores_chain_x4(self):
        deck = _deck_for_piao_scenario()
        r = SimGame([SpeedP(), SpeedE(), SpeedE(), SpeedE()],
                    rounds=1, seed=0, deck=deck).run()
        st = r["stats"]
        self.assertEqual(st["violations"], 0)
        self.assertEqual(st["hu_count"][0], 1)
        # 链 2（两飘）+ 爆头 → fan=8；庄胡：8×8×3=192
        self.assertEqual(r["totals"][0], 192)
        self.assertEqual(sum(r["totals"]), 0)
        # 链动作确有发生（stats.chain_hu +1；piao 属链）
        self.assertGreaterEqual(st["chain_hu"], 1)

    def test_speedE_baseline_hus_first_white(self):
        deck = _deck_for_piao_scenario()
        r = SimGame([SpeedE(), SpeedE(), SpeedE(), SpeedE()],
                    rounds=1, seed=0, deck=deck).run()
        st = r["stats"]
        self.assertEqual(st["hu_count"][0], 1)
        # E 首巡即胡：爆头 ×2 → fan=2 → 48
        self.assertEqual(r["totals"][0], 48)
        self.assertEqual(sum(r["totals"]), 0)


if __name__ == "__main__":
    unittest.main()
