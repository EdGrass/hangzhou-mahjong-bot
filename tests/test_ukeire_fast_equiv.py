# -*- coding: utf-8 -*-
"""`real_ukeire` 下界剪枝版的**逐位等价**回归测试。

背景（2026-09-17）：`real_ukeire` 对每个候选进张 t 都做
`∃d: shanten(H-d+t) < s0`，无用 t 要跑满 |H| 次精确向听 ⇒ 单决策最坏
~2000 次 shanten 调用（实测 p95=585ms、max=2.55s）。正式赛 M=10 是
一个进程内 10 线程共享策略，GIL 把这条尾延迟放大到 >3s（c151 52/500 超时）。

修法（**可证明精确，不是近似**）：先用一次 `_shanten_after_draw(S)` 取
`S = H + [t]` 的下界 s14。因为 `_shanten_counts` 的分解集合包含每个
`S - d` 的分解集合 ⇒ `s14 <= min_d shanten(S-d)`。
于是 `s14 >= s0` ⇒ 该 t **必然不是进张**，整条 ∃ 循环可安全跳过；
只有 `s14 < s0` 时才回落原路径，结果与参考实现完全一致。

本测试锁住：① 两实现逐位相同；② 下界不变式 s14 <= min_d。
"""
import random
import unittest

from bot.ukeire import _shanten_after_draw, real_ukeire, real_ukeire_reference
from mahjong.shanten_exact import shanten

W = "白"


def _full_pool():
    pool = []
    for s in "wbt":
        for n in range(1, 10):
            pool += ["%d%s" % (n, s)] * 4
    return pool + [W] * 4


class TestFixedHands(unittest.TestCase):
    def test_edges(self):
        cases = [
            ["1w", "1w", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "9w", "9w"],
            [W, W, W, "1w", "1w", "2w", "2w", "3w", "3w", "4b", "4b", "5t", "5t"],
            ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "1b", "1b", "1t", W],
            ["东", "南", "西", "北", "中", "发", "1w", "4w", "7w", "1b", "4b", "1t", "7t"],
            ["1w", "1w", "2w", "2w", "3w", "3w", "4w", "4w", "5w", "5w", "6w", "6w", "7w"],
            ["1t", "1t", "1t", "2t", "2t", "3t", "3t", "4t", "4t", "5t", "5t", "白", "白"],
        ]
        for h in cases:
            self.assertEqual(real_ukeire(list(h)), real_ukeire_reference(list(h)),
                             "13 张手牌 %s 两实现不一致" % h)

    def test_melded_paths_match(self):
        # exposed>0 时七对分支关闭、手牌张数变短，走的是另一条计数路径
        pool = _full_pool()
        rng = random.Random(20260917)
        for e, n in ((1, 10), (2, 7)):
            for _ in range(8):
                h = rng.sample(pool, n)
                self.assertEqual(
                    real_ukeire(list(h), exposed=e),
                    real_ukeire_reference(list(h), exposed=e),
                    "副露 %d 手牌 %s 两实现不一致" % (e, h))

    def test_god_meld_off_matches(self):
        pool = _full_pool()
        rng = random.Random(7788)
        for _ in range(8):
            h = rng.sample(pool, 13)
            self.assertEqual(
                real_ukeire(list(h), god_meld=False),
                real_ukeire_reference(list(h), god_meld=False),
                "god_meld=False 手牌 %s 两实现不一致" % h)


class TestRandomSample(unittest.TestCase):
    def test_matches_reference(self):
        pool = _full_pool()
        rng = random.Random(4242)
        for _ in range(24):
            h = rng.sample(pool, 13)
            self.assertEqual(real_ukeire(list(h)), real_ukeire_reference(list(h)),
                             "随机手牌 %s 两实现不一致" % h)


class TestLowerBoundInvariant(unittest.TestCase):
    """剪枝的**安全性前提**：s14 <= min_d shanten(S-d)。

    这条一旦被打破，`s14 >= s0` 的跳过就不再可靠 —— 所以直接对它做属性测试。
    """

    def test_lower_bound_holds(self):
        pool = _full_pool()
        rng = random.Random(99001)
        for _ in range(12):
            rem = rng.sample(pool, 13)
            s0 = shanten(list(rem))
            for t in ("1w", "5w", "9w", "1b", "5t", "东", W):
                cands = []
                for d in set(rem):
                    hh = list(rem)
                    hh.remove(d)
                    hh.append(t)
                    cands.append(shanten(hh))
                s14 = _shanten_after_draw(list(rem) + [t], 0, 0, True)
                self.assertLessEqual(
                    s14, min(cands),
                    "下界被打破：hand=%s t=%s s14=%d min_d=%d" % (rem, t, s14, min(cands)))


if __name__ == "__main__":
    unittest.main()
