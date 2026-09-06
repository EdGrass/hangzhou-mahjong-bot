"""SpeedX1（候选 C001）语义测试：与 SpeedE 仅在「全 tie 时弃刚摸优先」上有差异。

性质断言（随机牌面）：
- X1 与 E 的弃牌不同 ⇒ E 弃的是刚摸牌、X1 弃的是别的牌，且二者
  (向听, -等待数, 孤字档) 三键全等（真 tie，非评估差异）。
确定性 fixture：seed 20260906 搜索所得（见 docs/iter/reports/C001.md）。
"""
import random
import unittest

from bot.model import my_turn  # noqa: F401
from bot.speede import SpeedE
from bot.speedx1 import SpeedX1
from mahjong.hu import is_win
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

DECK = []
for n in range(1, 10):
    for s in ("w", "b", "t"):
        DECK += ["%d%s" % (n, s)] * 4
for h in ("东", "南", "西", "北", "中", "发", "白"):
    DECK += [h] * 4

HONORS = set("东南西北中发白")

# 确定性 fixture：drawn=发（字牌），弃 发 与弃 东 三键全 tie。
FIX_HAND = ["白", "中", "东", "4t", "8b", "6w", "4t", "5b", "2w",
            "1t", "1w", "9w", "北", "发"]
FIX_DRAWN = "发"


def _view(hand):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "drawn_tile": hand[-1], "my_hand": list(hand), "god": {},
            "scores": None, "melds": [], "offer_tile": None, "can_gang": True}


def _key(hand, d):
    """SpeedE 系弃牌前三键 (向听, -等待数, 孤字档)。"""
    rem = list(hand)
    rem.remove(d)
    s = exact_shanten(rem, qidui=True, exposed_melds=0, gangs=0)
    wcnt = len(waits(rem, exposed_melds=0, gangs=0)) if s == 0 else 0
    return (s, -wcnt, 0 if d in HONORS else 1)


class TestSpeedX1(unittest.TestCase):
    def test_fixture_tie_discards_drawn(self):
        """确定性牌例：E 弃刚摸(发)，X1 弃同档他牌(东)——tie 内弃新张。"""
        v = _view(list(FIX_HAND))
        self.assertEqual(v["drawn_tile"], FIX_DRAWN)
        aE = SpeedE().decide(v)
        aX = SpeedX1().decide(v)
        self.assertEqual(aE["action"], "discard")
        self.assertEqual(aX["action"], "discard")
        self.assertEqual(aE["tile"], FIX_DRAWN)        # E 保留刚摸 → 打的是刚摸
        self.assertNotEqual(aX["tile"], FIX_DRAWN)     # X1 打别的
        self.assertEqual(_key(FIX_HAND, aE["tile"]),
                         _key(FIX_HAND, aX["tile"]))  # 确为真 tie

    def test_property_diffs_only_in_drawn_tie(self):
        """随机牌面性质：弃牌不同 ⇔ E 弃刚摸 且 X1 弃同档他牌。"""
        rng = random.Random(20260906)
        E, X1 = SpeedE(), SpeedX1()
        seen_diff = False
        for _ in range(40):
            while True:
                hand = [rng.choice(DECK) for _ in range(14)]
                if all(hand.count(t) <= 4 for t in set(hand)):
                    break
            if is_win(hand, exposed_melds=0, gangs=0):
                continue
            v = _view(hand)
            aE, aX = E.decide(v), X1.decide(v)
            if not (aE and aX and aE["action"] == "discard"
                    and aX["action"] == "discard"):
                continue
            tE, tX = aE["tile"], aX["tile"]
            if tE == tX:
                continue
            seen_diff = True
            self.assertEqual(tE, v["drawn_tile"],
                             "E 差异侧必须弃刚摸: %s" % (hand,))
            self.assertNotEqual(tX, v["drawn_tile"],
                                "X1 差异侧不得弃刚摸: %s" % (hand,))
            self.assertEqual(_key(hand, tE), _key(hand, tX),
                             "非 tie 不得分道: %s" % (hand,))
        self.assertTrue(seen_diff, "随机样本应覆盖到差异场景")


if __name__ == "__main__":
    unittest.main()
