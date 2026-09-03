"""弃胡财飘路径测试（首版目标：触发全部动作路径）。

场景：庄家(座0)起手 4 面子 + 白（爆头态），墙首为白板 →
  摸白可胡但应弃胡打白（财飘 chain+1）→ 抓打圈开启 →
  一圈后座0任意再摸 → 爆头胡（chain_hu=1，链 ×2 番计入）。
"""
import unittest
from collections import Counter

from bot.heuristic import HeuristicA
from mahjong.hu import is_baotou, is_win
from mahjong.sim import SimGame, make_view

W = "白"
KINDS = ["%d%s" % (i, s) for s in "wbt" for i in range(1, 10)] + \
        ["东", "南", "西", "北", "中", "发", W]
FOUR_MELDS_PLUS_W = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                     "1b", "1b", "1b", W]     # 13 张：4 面子 + 单钓白（爆头态）
JUNK_13 = ["东", "南", "西", "北", "中", "发", "1t", "3t", "5t", "7t",
           "2b", "4b", "6b"]                  # 13 张互不相同（极难成胡）


def build_deck(hands4, wall_prefix=()):
    """hands4 每座 13 张；剩余 84 张按余量补齐，墙前缀优先入墙头。"""
    used = Counter()
    for h in hands4:
        used.update(h)
    deck = [t for h in hands4 for t in h]
    rest = []
    for k in KINDS:
        rest.extend([k] * (4 - used[k]))
    assert len(rest) == 84, "剩余牌应为 84: %d" % len(rest)
    prefix = list(wall_prefix)
    for t in prefix:
        rest.remove(t)
    deck += prefix + rest
    assert len(deck) == 136
    return deck


class TestPiaoDecision(unittest.TestCase):
    def test_baotou_draw_white_piaos(self):
        hand14 = FOUR_MELDS_PLUS_W + [W]       # 摸白后 14 张
        self.assertTrue(is_baotou(FOUR_MELDS_PLUS_W))
        self.assertTrue(is_win(hand14))
        view = make_view(0, "draw", 0, hand14, drawn=W, melds=[],
                         god={"baotou": True})
        act = HeuristicA().decide(view)
        self.assertEqual(act, {"action": "discard", "tile": W},
                         "爆头摸白应弃胡打白（财飘）")

    def test_no_piao_without_baotou_flag(self):
        # 直接给原始视图（绕过 make_view 的引擎重算）：baotou=False 且可胡 → 胡
        hand14 = FOUR_MELDS_PLUS_W + [W]
        raw = {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
               "drawn_tile": W, "my_hand": hand14,
               "god": {"baotou": False, "chain_count": 0, "catch_play": False},
               "scores": None, "melds": [], "offer_tile": None,
               "can_gang": True}
        act = HeuristicA().decide(raw)
        self.assertEqual(act, {"action": "hu", "tile": ""},
                         "无爆头标志时不应飘，直接胡")


class TestPiaoEnginePath(unittest.TestCase):
    def test_full_piao_chain_hu_round(self):
        hands = [list(FOUR_MELDS_PLUS_W), list(JUNK_13), list(JUNK_13),
                 list(JUNK_13)]
        deck = build_deck(hands, wall_prefix=[W])
        g = SimGame([HeuristicA()] * 4, rounds=1, base=1, seed=0, deck=deck)
        res = g.run()
        st = res["stats"]
        self.assertEqual(st["rounds_played"], 1)
        self.assertGreaterEqual(st["chain_hu"], 1, "财飘后爆头胡应计 chain_hu")
        self.assertGreaterEqual(st["catch_rounds"], 1, "弃白应开抓打圈")
        self.assertEqual(st["violations"], 0)
        self.assertEqual(st["hu_count"][0], 1, "庄家应自摸胡")
        self.assertGreater(res["totals"][0], 0)


if __name__ == "__main__":
    unittest.main()
