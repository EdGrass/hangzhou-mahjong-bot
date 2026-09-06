"""SpeedX2（候选 C002）语义测试：与 SpeedE 仅在「听牌等待扣已见」上有差异。

生成法：随机赢形(4组+对) − 1 张 = 必听 13 张 → + 非胡 junk = 14 张，
河内耗尽某等待牌 → 触发死等场景（实测命中率 ~11%/次）。
性质断言：
- 空河：x2 与 E 决策完全一致；
- 非空河分歧 ⇒ 同向听档、x2 的活等待更多、E 的候选含死等、x2 原始等待 ≤ E 的。
确定性 fixture（种子 20260909 搜索所得）另行钉死。
"""
import random
import unittest

from bot.speede import SpeedE
from bot.speedx2 import SpeedX2
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

SUITS = ["%d%s" % (n, s) for s in "wbt" for n in range(1, 10)]
HON = ["东", "南", "西", "北", "中", "发", "白"]
ALL = SUITS + HON
HONORS = set(HON)


def _win14(rng):
    gs = []
    for _ in range(4):
        if rng.random() < 0.5:
            s = rng.choice("wbt")
            n = rng.randint(1, 7)
            gs += ["%d%s" % (n, s), "%d%s" % (n + 1, s), "%d%s" % (n + 2, s)]
        else:
            gs += [rng.choice(ALL)] * 3
    p = rng.choice(ALL)
    return gs + [p, p]


def _view(hand, river):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "drawn_tile": hand[-1], "my_hand": list(hand), "god": {},
            "scores": None, "melds": [], "offer_tile": None, "can_gang": True,
            "river": list(river)}


def _counts(hand, river):
    seen = {}
    for t in list(hand) + river:
        seen[t] = seen.get(t, 0) + 1
    return seen


def _raw_w(hand13):
    return len(waits(hand13, exposed_melds=0, gangs=0))


def _live_w(hand13, seen):
    return sum(1 for t in waits(hand13, exposed_melds=0, gangs=0)
               if seen.get(t, 0) < 4)


def _rem_of(hand, d):
    out = list(hand)
    out.remove(d)
    return out


def _sample_state(rng):
    """返回 (hand14, river) 或 None（可能触发死等分歧的构造）。"""
    for _ in range(60):
        w = _win14(rng)
        if any(w.count(t) > 4 for t in set(w)):
            continue
        h13 = list(w)
        h13.pop(rng.randrange(14))
        wset = waits(h13, exposed_melds=0, gangs=0)
        cand = [t for t in ALL if h13.count(t) < 4 and t not in wset]
        if not cand:
            continue
        drawn = rng.choice(cand)
        hand = sorted(h13 + [drawn])
        target = rng.choice(sorted(wset))
        need = 4 - hand.count(target)
        if need <= 0:
            continue
        river = [target] * need + \
            [rng.choice(ALL) for _ in range(rng.randint(0, 3))]
        rng.shuffle(river)
        return hand, river
    return None


class TestSpeedX2(unittest.TestCase):
    def test_empty_river_identical_to_E(self):
        """空河等价：x2 退化为 SpeedE（含 x1 fixture 的 tie 场景）。"""
        rng = random.Random(20260907)
        E, X2 = SpeedE(), SpeedX2()
        states = [
            (["白", "中", "东", "4t", "8b", "6w", "4t", "5b", "2w", "1t",
              "1w", "9w", "北", "发"], []),
        ]
        for _ in range(80):
            st = _sample_state(rng)
            if st:
                states.append((st[0], []))
        for hand, river in states:
            v = _view(list(hand), river)
            aE, aX = E.decide(v), X2.decide(v)
            self.assertEqual(aE, aX, "空河必须与 E 一致: %s" % (hand,))

    def test_fixture_dead_wait_differs(self):
        """确定性 fixture：7t 已成对且河见 2 → 死等，E 弃 8t、x2 弃 7t。"""
        hand = ["1b", "1w", "2b", "2w", "3b", "3w", "4b", "4t", "4t",
                "5b", "6b", "7t", "7t", "8t"]
        river = ["7t", "7t"]        # 7t: 手 2 + 河 2 = 4 → 等待 7t 已死
        v = _view(hand, river)
        aE = SpeedE().decide(v)
        aX = SpeedX2().decide(v)
        self.assertEqual(aE["tile"], "8t", "E 保留原等待结构")
        self.assertEqual(aX["tile"], "7t", "x2 应弃死等结构")
        seen = _counts(hand, river)
        self.assertGreater(_live_w(_rem_of(hand, aX["tile"]), seen),
                           _live_w(_rem_of(hand, aE["tile"]), seen))

    def test_property_diffs_only_by_dead_waits(self):
        """分歧 ⇒ 同向听档、x2 活等待更多、E 候选含死等、x2 原始等待 ≤ E。"""
        rng = random.Random(20260909)
        E, X2 = SpeedE(), SpeedX2()
        diffs = 0
        for _ in range(400):
            st = _sample_state(rng)
            if not st:
                continue
            hand, river = st
            v = _view(hand, river)
            aE, aX = E.decide(v), X2.decide(v)
            if not (aE and aX and aE["action"] == "discard"
                    and aX["action"] == "discard"):
                continue
            tE, tX = aE["tile"], aX["tile"]
            if tE == tX:
                continue
            diffs += 1
            seen = _counts(hand, river)

            def s_after(d):
                return exact_shanten(_rem_of(hand, d), qidui=True,
                                     exposed_melds=0, gangs=0)
            self.assertEqual(s_after(tE), s_after(tX),
                             "差异必须同向听档: %s r=%s" % (hand, river))
            liveE = _live_w(_rem_of(hand, tE), seen)
            liveX = _live_w(_rem_of(hand, tX), seen)
            rawE = _raw_w(_rem_of(hand, tE))
            rawX = _raw_w(_rem_of(hand, tX))
            self.assertGreaterEqual(liveX, liveE,
                                    "x2 按活等待最大化: %s r=%s" % (hand, river))
            self.assertGreaterEqual(rawE, rawX,
                                    "E 按原始等待最大化: %s r=%s" % (hand, river))
            self.assertGreater(rawE, liveE,
                               "E 的候选必须含死等才可能分歧: %s r=%s" % (hand, river))
            self.assertTrue(rawE > rawX or liveX > liveE,
                            "分歧必须至少一项严格: %s r=%s" % (hand, river))
        self.assertGreaterEqual(diffs, 3, "结构化样本应覆盖到差异场景")


if __name__ == "__main__":
    unittest.main()
