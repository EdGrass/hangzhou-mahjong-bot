# -*- coding: utf-8 -*-
"""`bot/speedgiveupriver.py` 回归：弃胡 EV 的 p(river) 衰减 + 失败负项。

夹具来自一条**真实决策日志**（2026-09-23 房 a_fb66170740fc 的一手），
只含牌面、无任何隐私字段：14 张（含刚摸）本就是 **fan=1 平胡**，
而弃掉 8b 会留下 **爆头形**（下一摸 ×2）——正是「可胡却弃胡」的场面。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedgiveupriver import SpeedGiveupRiver, SpeedGiveupRiverP   # noqa: E402
from bot.speedvalue import SpeedValue                                  # noqa: E402
from mahjong.fan import calc as calc_fan                               # noqa: E402
from mahjong.hu import is_win                                          # noqa: E402

# 真实记录的牌面（手牌含刚摸 2b；两副露：碰 9w / 吃 2t）
HAND = ["3b", "4b", "8t", "7t", "9t", "白", "8b", "2b"]
MELDS = [("peng", "9w"), ("chi", "2t")]
DRAWN = "2b"


def make_view(river_len):
    """构造 decide() 需要的最小 view（字段名与 game.py 一致）。"""
    return {
        "phase": "draw", "turn": 1, "seat": 1, "responding_seats": [],
        "my_hand": list(HAND), "drawn_tile": DRAWN, "offer_tile": None,
        "melds": [{"type": t, "tile": x} for t, x in MELDS],
        "god": {"baotou": False, "chain_count": 0, "piao_count": 0,
                "catch_play": False},
        "river": [], "river_len": river_len,
    }


class TestGiveupRiver(unittest.TestCase):
    def test_fixture_really_is_a_fan1_win_and_gives_a_baotou_shape(self):
        """先证尺子：这手确实可胡 fan=1，且弃 8b 能进爆头形。"""
        self.assertTrue(is_win(HAND, exposed_melds=2, gangs=0))
        pre = list(HAND)
        pre.remove(DRAWN)
        r = calc_fan(pre, DRAWN, {"count": 0, "piao": 0}, base=1,
                     exposed_melds=2, gangs=0)
        self.assertTrue(r.get("hu"))
        self.assertEqual(r.get("fan"), 1, "夹具应为平胡 fan=1：%s" % (r.get("detail"),))

    def test_p_table_segments(self):
        """p(river)：实测分段 + 末盘先验。"""
        for r, want in ((0, 0.95), (19, 0.95), (20, 0.90), (39, 0.90),
                        (40, 0.67), (54, 0.67), (55, 0.40), (62, 0.40)):
            self.assertAlmostEqual(SpeedGiveupRiverP.p_conv_at(r), want, places=6)

    def test_incumbent_gives_up_on_this_fixture(self):
        """现役（speedvalue）在这手上是**弃胡**（固定 p=0.71 判据）。"""
        act = SpeedValue().decide(make_view(31))
        self.assertEqual(act["action"], "discard")

    def test_early_river_matches_incumbent(self):
        """单变量保真：前盘（p=0.90）取舍与现役一致——不引入无关行为变更。"""
        inc = SpeedValue().decide(make_view(31))
        new = SpeedGiveupRiverP().decide(make_view(31))
        self.assertEqual(new, inc, "前盘应与现役逐位一致")

    def test_endgame_no_longer_gives_up(self):
        """★ 核心修正：末盘（>=55）不再弃胡，改为立即胡。"""
        for river in (55, 60, 62):
            self.assertEqual(SpeedGiveupRiverP().decide(make_view(river))["action"],
                             "hu", "P 版在 river=%d 应胡" % river)
            self.assertEqual(SpeedGiveupRiver().decide(make_view(river))["action"],
                             "hu", "带失败负项版在 river=%d 应胡" % river)

    def test_loss_term_can_only_make_it_stricter(self):
        """失败负项只会让弃胡更保守：把 loss 调大 ⇒ 更早转为胡。"""
        p_only = SpeedGiveupRiverP().decide(make_view(47))
        heavy = SpeedGiveupRiverP(loss_fan=1.2).decide(make_view(47))
        self.assertEqual(p_only["action"], "discard", "loss=0 时后盘仍弃胡")
        self.assertEqual(heavy["action"], "hu", "loss 放大后应转为胡")

    def test_loss_fan_default(self):
        self.assertEqual(SpeedGiveupRiverP().loss_fan, 0.0)
        self.assertEqual(SpeedGiveupRiver().loss_fan, 0.5)


if __name__ == "__main__":
    unittest.main()
