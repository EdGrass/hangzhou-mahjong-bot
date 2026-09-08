# -*- coding: utf-8 -*-
"""SpeedK 单测（C007 实施）—— K1 一步有效牌 tie + K2 副露 ukeire 判据。

对照父类 SpeedE（真机窗口 A/B 工具链下仅当"同向听后进张更佳"才产生行为差）。
含：纯函数数 pin、K1 弃牌 tie 语义（与 SpeedE 仅在 tie 处分化）、K2 各副露分支
（提速要 / 同速更佳要 / 同速更差不要 / 已听比较 / chi / 白宝 offer 拒绝）、与
SpeedE 一致性随机冒烟。
"""
import random
import unittest

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

import bot.speedk as k
from bot.speede import SpeedE, _best_discard_honor

HONOR = set("东南西北中发白")

# ---------------------------------------------------------------------------
# 参考（非实现，仅用于数值锚定 / 键序推导）
# ---------------------------------------------------------------------------
H19 = ["4w", "4b", "9w", "2b", "3w", "2b", "4w", "4w",
       "东", "白", "东", "中", "东", "中"]   # 14 张，draw 后局面（e=g=0)


def _mk_view(hand14, drawn, phase="draw", turn=0, melds=None, offer=None,
             responding_seats=(), catch=False):
    return {
        "seat": 0, "phase": phase, "turn": turn,
        "responding_seats": list(responding_seats),
        "drawn_tile": drawn,
        "my_hand": list(hand14),
        "melds": list(melds or []),
        "offer_tile": offer,
        "god": {"catch_play": catch},
        "scores": None,
    }


def _udiscard(hand14, discard, exposed=0, gangs=0):
    """弃 1 张后 rem 的进程 ukeire：s==0 用 waits，否则 effective_tiles。"""
    rm = list(hand14)
    rm.remove(discard)
    s = exact_shanten(rm, qidui=(exposed == 0 and gangs == 0),
                      exposed_melds=exposed, gangs=gangs)
    if s == 0:
        return len(waits(rm, exposed_melds=exposed, gangs=gangs))
    return k.effective_tiles(rm, exposed, gangs)


class TestPure(unittest.TestCase):
    def test_candidate_covers_neighbors_honors(self):
        c = k._candidate_tiles(["5w"])
        self.assertIn("5w", c)
        self.assertIn("4w", c)               # ±1
        self.assertIn("7w", c)               # ±2
        self.assertNotIn("0w", k._candidate_tiles(["1w"]))   # 界内无 0
        # 字牌（含白）永远入列
        ck = k._candidate_tiles(["东", "白"])
        self.assertIn("东", ck)
        self.assertIn("白", ck)
        self.assertIn("中", ck)              # 未持有也全量入列

    def test_effective_tiles_distinguishes_ukeire(self):
        # 同一 14 张一手，弃不同候选保留各自的 1-向听手，有效类不同：
        # 弃 9w 保留的高分 > 弃 2b 保留的中分：有效牌能区分保留形态优劣
        for d, expect in (("9w", 14), ("2b", 11), ("3w", 13)):
            self.assertEqual(_udiscard(H19, d), expect,
                             "discard=%s" % d)
        self.assertGreater(_udiscard(H19, "9w"),
                           _udiscard(H19, "2b"))

    def test_effective_tiles_bad_len_safe(self):
        self.assertEqual(k.effective_tiles(["1w", "2w"], 0, 0), 0)   # 非 13 张
        # 副露口径长度不符（如只给 11 张但声 e=1 需 10 张）也安全 0
        self.assertEqual(k.effective_tiles(["1w"] * 11, 1, 0), 0)

    def test_no_white_draw_of_white_counts_as_ukeire(self):
        # 无白手牌，cur=2。手牌不含白，但白在 exact_shanten 中是财神（万能牌）：
        # 抽白可与孤张(西/发/中散字)补对/组块而降向听(弃 西→向听 1)。
        # 旧实现 _plausible_draw 把"抽首张白"预过滤掉 → 有效牌低估 1（8）：
        # 修正后白无条件列为候选、内层 exact 判定把关，得实测值 9。
        hand = ["3w", "4w", "5w", "4w", "5w", "6w", "6b", "7b", "8b",
                "3b", "西", "发", "中"]        # cur=2（含白则 9 类一步有效）
        self.assertNotIn("白", hand)
        self.assertEqual(exact_shanten(hand, qidui=True), 2)
        self.assertTrue(k._plausible_draw(hand)("白"))    # 不再被 gate
        self.assertEqual(k.effective_tiles(hand, 0, 0), 9)   # 数值固化（曾 8）

    def test_ukeire_zero_for_tenpai(self):
        # 已听(tenpai)进程用 waits，effective_tiles 应 0（不做二次筛选）
        tenpai = ["1t", "1w", "1w", "2t", "3t", "3w", "3w", "3w",
                  "6t", "6t", "6t", "8t", "9t"]     # 上方已听样例
        self.assertEqual(exact_shanten(tenpai, qidui=True,
                                       exposed_melds=0, gangs=0), 0)
        self.assertEqual(k.effective_tiles(tenpai, 0, 0), 0)
        # 而其 ukeire（waits 数）> 0
        self.assertEqual(k._ukeire(tenpai, 0, 0),
                         len(waits(tenpai, exposed_melds=0, gangs=0)))


class TestK1(unittest.TestCase):
    def test_ukeire_higher_preferred_over_speedE_honor(self):
        # H19 全局最小向听组(s==1)含 9w(ukeire14) 与东(ukeire5)；
        # SpeedK 选 9w；SpeedE 只按孤字优先选东 —— 是 K1 行为面差异演示
        self.assertEqual(k._best_discard_k(H19, "4w", 0, 0), "9w")
        self.assertEqual(_best_discard_honor(H19, "4w", 0, 0), "东")

    def test_no_tie_case_identical_to_speedE(self):
        # 独一最小向听候选的手：SpeedK 与 SpeedE 结果一致
        h14 = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
               "1b", "2b", "3b", "东", "中"]
        self.assertEqual(k._best_discard_k(h14, "中", 0, 0),
                         _best_discard_honor(h14, "中", 0, 0))


def _rand_hand14(seed, honours=True):
    pool = (["%d%s" % (n, s) for s in "wbt" for n in range(1, 10)])
    if honours:
        pool += list("东南西北中发")
    r = random.Random(seed)
    h = []
    while len(h) < 14:
        t = r.choice(pool)
        if h.count(t) < 4:
            h.append(t)
    return h


class TestK1Property(unittest.TestCase):
    def test_agrees_with_speedE_except_genuine_uehire_tie(self):
        # 样本 = 固定含 H19（保证至少出现一次同 s 有效牌 tie）+ 随机 30
        samples = [list(H19)] + [_rand_hand14(seed) for seed in range(30)]
        ties = 0
        for hand in samples:
            ue = k._best_discard_k(hand, None, 0, 0)
            uz = _best_discard_honor(hand, None, 0, 0)
            if ue == uz:
                continue
            # 二者不同 → 必然同为最小向听、只可能差在有效牌比较
            s_k = _s_of_discard(hand, ue)
            s_e = _s_of_discard(hand, uz)
            self.assertEqual(s_k, s_e,
                             "SpeedK 与 SpeedE 不可在最小向听处分化")
            self.assertGreaterEqual(_upeire_of(hand, ue),
                                    _upeire_of(hand, uz))
            ties += 1
        # 至少一次同 s tie（H19 提供），证明分化面确实被覆盖
        self.assertGreaterEqual(ties, 1)


def _s_of_discard(hand14, discard):
    rm = list(hand14)
    rm.remove(discard)
    return exact_shanten(rm, qidui=True, exposed_melds=0, gangs=0)


def _upeire_of(hand14, discard):
    return _udiscard(hand14, discard)


class TestK2(unittest.TestCase):
    # --- 各分支（用具体 13 张暗牌 + offer） ---
    def test_peng_boost_claim(self):
        h = ["9b", "5t", "1b", "7t", "1w", "6t", "9b", "6b", "1w", "1b",
             "北", "北", "西"]
        self.assertTrue(k.want_claim_k(h, "1b", "peng", 0, 0))

    def test_peng_same_s_more_ukeire_claim(self):
        h = ["8b", "1t", "3b", "6b", "1b", "6b", "3b", "9w", "5w", "5b",
             "1t", "2w", "东"]
        self.assertTrue(k.want_claim_k(h, "3b", "peng", 0, 0))

    def test_peng_same_s_worse_not_claim(self):
        # sb==sa==2；wa(14) < wb(15) → 不碰
        h = ["1b", "2b", "3t", "4t", "4w", "6b", "6w", "6w", "7b", "7b",
             "7b", "7w", "8w"]
        self.assertFalse(k.want_claim_k(h, "7b", "peng", 0, 0))

    def test_peng_impossible_returns_false(self):
        hA = ["9b", "5t", "1b", "7t", "1w", "6t", "9b", "6b", "1w", "1b",
              "北", "北", "西"]
        # 仅 2 张 1b → gang_ming(<3)、北 offer <2 直接不行
        self.assertFalse(k.want_claim_k(hA, "1b", "gang_ming", 0, 0))
        self.assertFalse(k.want_claim_k(hA, "西", "peng", 0, 0))

    def test_tenpai_peng_comparison(self):
        # 已听(sb=0)
        t_more = ["1t", "1w", "1w", "2t", "3t", "3w", "3w", "3w",
                  "6t", "6t", "6t", "8t", "9t"]
        t_worse = ["1b", "2b", "3b", "3w", "3w", "6b", "6t", "6w", "7b",
                   "7w", "8b", "8t", "8w"]
        # 已听碰后等待更多 → 要
        self.assertTrue(k.want_claim_k(t_more, "1w", "peng", 0, 0))
        # 已听碰后未更佳 → 不要（不动听形）
        self.assertFalse(k.want_claim_k(t_worse, "3w", "peng", 0, 0))

    def test_white_offer_never(self):
        h = ["9b", "5t", "1b", "7t", "1w", "6t", "9b", "6b", "1w", "1b",
             "北", "北", "西"]
        self.assertFalse(k.want_claim_k(h, "白", "peng", 0, 0))
        self.assertFalse(k.want_claim_k(h, "白", "chi", 0, 0))

    def test_chi_boost_claim(self):
        h = ["1t", "1t", "1w", "2t", "2t", "3b", "3t", "3w", "5w", "7b",
             "8w", "9b", "9t"]
        self.assertTrue(k.want_claim_k(h, "1t", "chi", 0, 0,
                                       chi_pair=["2t", "3t"]))

    def test_chi_bad_pair_false(self):
        h = ["1t", "2t", "3t", "4t", "4t", "5w", "6w", "7w", "8w", "9w",
             "东", "东", "北"]
        self.assertFalse(k.want_claim_k(h, "6w", "chi", 0, 0,
                                        chi_pair=["4w", "5w"]))


class TestDecide(unittest.TestCase):
    def test_non_myturn_delegates_to_super(self):
        kk = k.SpeedK()
        ee = SpeedE()
        # 庄外无事做的普通 draw 非本人回合场景，二者皆应空（None）
        view = _mk_view([], None, phase="draw", turn=1)
        self.assertIsNone(kk.decide(view))
        self.assertIsNone(ee.decide(view))

    def test_falling_catch_playchain(self):
        # 抓打圈命中抓打时强制打刚摸牌（K1 继承父类行为）
        kk = k.SpeedK()
        view = _mk_view(H19, "中", phase="draw", turn=0, catch=True)
        act = kk.decide(view)
        self.assertEqual(act["action"], "discard")
        self.assertEqual(act["tile"], "中")


if __name__ == "__main__":
    unittest.main()
