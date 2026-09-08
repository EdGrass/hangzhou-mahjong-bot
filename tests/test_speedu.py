# -*- coding: utf-8 -*-
"""SpeedU 单测（C007 修正版）—— SpeedE + K1 一步有效牌 tie（K2 已撤回）。

SpeedU = SpeedE + K1：仅弃牌效率分化；窗口/副露 100% 继承 SpeedE/SpeedCore。
回归钉：
- 弃牌 tie 与 SpeedE 分化（同一 14 张、同 s 两候选 SpeedU 选 effective 高者）；
- 无 tie 弃牌与 SpeedE 逐手一致（随机 30 手性质）；
- 窗口行为逐帧 == SpeedE（K2 撤回：SpeedU 永不落入 SpeedK 式「已听且碰后
  waits 更多 → 也会碰」激进响应）；
- 胡优先 / 抓打圈继承冒烟。
"""
import random
import unittest

import bot.speedk as uk
import bot.speedu as u
from bot.speede import SpeedE, _best_discard_honor

# ---------------------------------------------------------------------------
# 参考 / 复用 SpeedK 单测锚定的 fixture（H19：同 s==1 时 9w 有效牌 14 > 东 5）
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
        "river": [],
        "can_gang": False,
        "scores": None,
    }


def _uke(hand14, discard):
    """弃 1 张后进程 ukeire（SpeedK 同一口径封装）。"""
    rm = list(hand14)
    rm.remove(discard)
    return uk._ukeire(rm, 0, 0)


class TestK1(unittest.TestCase):
    def test_ukeire_higher_preferred_over_speedE_honor(self):
        # H19 全局最小向听组(s==1)含 9w(ukeire14) 与东(ukeire5)：
        # SpeedU(K1) 选 9w；SpeedE 孤字优先选东 —— 弃牌面唯一分化点
        self.assertEqual(u._best_discard_u(H19, "4w", 0, 0), "9w")
        self.assertEqual(_best_discard_honor(H19, "4w", 0, 0), "东")

    def test_pure_discard_reuses_K1_reference(self):
        # 别名复用：_best_discard_u 与 speedk._best_discard_k 同源同语义（K1 已评审钉死）
        self.assertIs(u._best_discard_u, uk._best_discard_k)
        self.assertEqual(u._best_discard_u(H19, None, 0, 0),
                         uk._best_discard_k(H19, None, 0, 0))

    def test_no_tie_case_identical_to_speedE(self):
        h14 = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
               "1b", "2b", "3b", "东", "中"]
        self.assertEqual(u._best_discard_u(h14, "中", 0, 0),
                         _best_discard_honor(h14, "中", 0, 0))


def _rand_hand14(seed):
    pool = (["%d%s" % (n, s) for s in "wbt" for n in range(1, 10)]
            + list("东南西北中发"))
    r = random.Random(seed)
    h = []
    while len(h) < 14:
        t = r.choice(pool)
        if h.count(t) < 4:
            h.append(t)
    return h


class TestNoTieAgreement(unittest.TestCase):
    def test_discard_agrees_with_speedE_no_broken_shanten(self):
        # 30 随机手：SpeedU 弃牌与 SpeedE 要么逐手一致；分化时只允许双方同为
        # 最小向听、且 SpeedU 的进程 ukeire 不劣（K1 严谨性）。
        agree = 0
        for seed in range(30):
            h = _rand_hand14(seed)
            du = u._best_discard_u(h, None, 0, 0)
            de = _best_discard_honor(h, None, 0, 0)
            if du == de:
                agree += 1
                continue
            self.assertEqual(_s_of(h, du), _s_of(h, de),
                             "SpeedU 不可在最小向听处分化")
            self.assertGreaterEqual(_uke(h, du), _uke(h, de))
        # 绝大多数随机手与 SpeedE 一致（同 s 有效牌 tie 本就稀少）
        self.assertGreaterEqual(agree, 25)


def _s_of(hand14, discard):
    rm = list(hand14)
    rm.remove(discard)
    return uk.exact_shanten(rm, qidui=True, exposed_melds=0, gangs=0)


# ---------------------------------------------------------------------------
# 窗口回归钉：SpeedU.response_* 必须逐帧 == SpeedE（K2 撤回的证据）
# ---------------------------------------------------------------------------
class TestWindowEqualsSpeedE(unittest.TestCase):
    def test_peng_boost_same_as_speedE(self):
        # 碰 1b 若能提速 → SpeedE/SpeedU 都响应（K2 撤回不叠加激进，共存提速）
        E = SpeedE()
        U = u.SpeedU()
        h = ["9b", "5t", "1b", "7t", "1w", "6t", "9b", "6b", "1w", "1b",
             "北", "北", "西"]          # 有 2 张 1b → offer 1b 碰提速
        v = _mk_view(h, None, phase="response_peng", turn=2,
                     responding_seats=(0,), offer="1b")
        self.assertEqual(E.decide(v), U.decide(v))

    def test_tenpai_offer_both_pass_differs_from_speedK(self):
        # 已听(tenpai) offer：SpeedE/SpeedU 都不碰（不动听形）；
        # SpeedK 因"碰后 waits 更多 → 会碰"，SpeedU 拒绝该激进覆盖（K2 撤回钉）。
        t_more = ["1t", "1w", "1w", "2t", "3t", "3w", "3w", "3w",
                  "6t", "6t", "6t", "8t", "9t"]     # sb=0, 碰 1w 后 waits 更多
        # 证实这是 SpeedK 会响应的样例
        self.assertTrue(uk.want_claim_k(t_more, "1w", "peng", 0, 0))
        E = SpeedE()
        U = u.SpeedU()
        v = _mk_view(t_more, None, phase="response_peng", turn=2,
                     responding_seats=(0,), offer="1w")
        e_act = E.decide(v)
        u_act = U.decide(v)
        self.assertEqual(e_act, u_act)                 # 窗口逐帧 == SpeedE
        self.assertEqual(u_act, {"action": "pass", "tile": ""})


class TestDecide(unittest.TestCase):
    def test_non_myturn_delegates_to_super(self):
        # 无 offer 的非窗口他人回合 → 空（继承）
        U = u.SpeedU()
        E = SpeedE()
        view = _mk_view([], None, phase="draw", turn=1)
        self.assertIsNone(U.decide(view))
        self.assertIsNone(E.decide(view))

    def test_hu_priority_inherited(self):
        # 已是和牌形（可直接胡，拆法见 test_speed.py）→ 直接 hu，不做弃牌
        U = u.SpeedU()
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "1b", "2b", "3b", "东", "东"]
        view = _mk_view(hand, "东", phase="draw", turn=0)
        act = U.decide(view)
        self.assertEqual(act["action"], "hu")
        self.assertEqual(act["tile"], "")

    def test_catch_play_chain_inherited(self):
        # 抓打圈命中 → 强制打刚摸
        U = u.SpeedU()
        view = _mk_view(H19, "中", phase="draw", turn=0, catch=True)
        act = U.decide(view)
        self.assertEqual(act["action"], "discard")
        self.assertEqual(act["tile"], "中")

    def test_discard_uses_U_key(self):
        # 本回合弃牌走 _best_discard_u（K1）：H19 → 打 9w
        U = u.SpeedU()
        view = _mk_view(H19, "4w", phase="draw", turn=0)
        act = U.decide(view)
        self.assertEqual(act["action"], "discard")
        self.assertEqual(act["tile"], "9w")


if __name__ == "__main__":
    unittest.main()
