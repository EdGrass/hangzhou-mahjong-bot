# -*- coding: utf-8 -*-
"""SpeedV 单测 —— SpeedE + 真机 river-aware 舍张（河见死等待/死进张剔除）。

SpeedV 与 SpeedE/U(K1) 的唯一差异 = 把〔公开弃牌河〕算进进度度量：等待/有效牌
只在"该牌物理未摸完（已见<4）"时计入。回归钉：
- 活等待纯函数：已见满 4 的死等待从 waits 中剔除；
- 白(财神)进张不特判：河已见满 4 白时白相关降向听路径被 seen 层拦截（即便
  _plausible_draw 无条件放行白）；
- 空河等价：river=[] 时 _best_discard_v == speedk._best_discard_k（空河退化
  K1/SpeedU 语义，非 SpeedE）；
- 死等改变决策：同 s 双候选 A(保留死等)/B(保留活等)，SpeedV 选 B 而 SpeedE 选 A；
- 无 tie/无河见差局面决策与 SpeedE 逐手一致；
- 窗口行为逐帧 == SpeedE（不覆盖）；胡优先 / 抓打圈继承冒烟。
"""
import random
import unittest

import bot.speedk as k
import bot.speedv as v
from bot.speede import SpeedE
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

HONOR = set("东南西北中发白")


# ---------------------------------------------------------------------------
# 参考：复用已评审锚定的进程进张样例（见 test_speedk 的 no_white / t_more）
# ---------------------------------------------------------------------------
# 13 张已听手，raw waits = ['7t','白']（无一在手 <=3；7t 可被河推到 4 成死等）
TENPAI_TMORE = ["1t", "1w", "1w", "2t", "3t", "3w", "3w", "3w",
                "6t", "6t", "6t", "8t", "9t"]

# 白(财神)有效进张手（cur=2，抽白可降向听；见 speedk no_white 数值钉死 9 类）
HAND_WHITE = ["3w", "4w", "5w", "4w", "5w", "6w", "6b", "7b", "8b",
              "3b", "西", "发", "中"]

# 同 s==0 双候选十pai 手（引擎实测，注释见 _dead_tie_fixture 解释）
DEAD_TIE = ["1b", "1b", "2b", "4b", "4b", "8t", "9t", "9t",
            "9w", "9w", "9w", "9w", "西", "西"]

# H19（14 张 draw 后，e=g=0，K1/EmptyV 均 9w）
H19 = ["4w", "4b", "9w", "2b", "3w", "2b", "4w", "4w",
       "东", "白", "东", "中", "东", "中"]


def _mk_view(hand14, drawn, phase="draw", turn=0, melds=None, offer=None,
             responding_seats=(), catch=False, river=()):
    return {
        "seat": 0, "phase": phase, "turn": turn,
        "responding_seats": list(responding_seats),
        "drawn_tile": drawn,
        "my_hand": list(hand14),
        "melds": list(melds or []),
        "offer_tile": offer,
        "god": {"catch_play": catch},
        "river": list(river),
        "can_gang": False,
        "scores": None,
    }


def _dead_tie_fixture():
    """同 s==0 的两种听形（保持哪把牌）：
    弃 2b -> 听 ['8t','白']；弃 8t -> 听 ['2b','白']。
    当河已见满 4×8t：弃 2b 保住的 8t 等待成死等（活=只剩 '白'），而弃 8t
    保住的听 ['2b','白'] 全活 → SpeedV(K1-empty 同 2b)被河逼到弃 8t；SpeedE
    不看河仍弃 2b。数值由引擎实测固化于 _test 断言。"""
    return DEAD_TIE


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


class TestLiveWaits(unittest.TestCase):
    def test_dead_wait_excluded_from_raw(self):
        # 10pai rem，raw waits 含 7t 与白；河 4×7t → seen[7t]=4 → 剔除只剩白
        seen = v._seen([], ["7t"] * 4)
        raw = waits(TENPAI_TMORE, exposed_melds=0, gangs=0)
        self.assertEqual(set(raw), {"白", "7t"})
        self.assertEqual(v._live_waits(TENPAI_TMORE, 0, 0, seen), 1)
        # 7t 河见满被剔；白 seen0 remain live
        self.assertIn("7t", raw)          # raw（不看河）仍含 7t —— 剔除点确在 live

    def test_live_equals_raw_without_river(self):
        # 空河：seen 仅手牌计数；waits() 已排除手牌满 4 → _live == raw 长度
        seen = v._seen(TENPAI_TMORE, [])
        self.assertEqual(v._live_waits(TENPAI_TMORE, 0, 0, seen),
                         len(waits(TENPAI_TMORE, exposed_melds=0, gangs=0)))


class TestWhiteSeenNotSpecial(unittest.TestCase):
    def test_white_seen_full_removes_white_draw_path(self):
        # 白在 speedk._plausible_draw 无条件放行（财神可补任意孤张）；但 V 在 seen
        # 层拦：河 4×白 → 白物理摸不到 → 该有效路径剔除（白不特殊）。
        # 数值：空河 live==K.effective==9；河 4×白 → 降 1（白类进张死）
        self.assertTrue(k._plausible_draw(HAND_WHITE)("白"))   # 修复放行仍在
        seen0 = v._seen(HAND_WHITE, [])
        self.assertEqual(v._live_effective(HAND_WHITE, 0, 0, seen0), 9)
        self.assertEqual(k.effective_tiles(HAND_WHITE, 0, 0), 9)  # 与 K 无河同源
        seen4 = v._seen(HAND_WHITE, ["白"] * 4)
        self.assertEqual(v._live_effective(HAND_WHITE, 0, 0, seen4), 8)


class TestEmptyRiverDegradesToK(unittest.TestCase):
    def test_empty_river_matches_K1_over_20_hands(self):
        # 空河退化 SpeedU/K1 语义：_best_discard_v(空seen) == _best_discard_k
        for seed in range(20):
            h = _rand_hand14(seed)
            self.assertEqual(
                v._best_discard_v(h, None, 0, 0, v._seen(h, [])),
                k._best_discard_k(h, None, 0, 0), "seed=%d" % seed)

    def test_empty_river_H19_same_as_K(self):
        self.assertEqual(v._best_discard_v(H19, "4w", 0, 0, v._seen(H19, [])),
                         k._best_discard_k(H19, "4w", 0, 0))
        self.assertEqual(k._best_discard_k(H19, "4w", 0, 0), "9w")


class TestDeadWaitChangesDecision(unittest.TestCase):
    def test_SpeedV_keeps_live_waits_SpeedE_dead(self):
        # 同 s==0 双候选：空河二者皆弃 2b；河满 4×8t 后 2b 的 wait-8t 变死等，
        # SpeedV 改保留活听的"弃 8t"；SpeedE 不看河仍弃 2b。
        h = _dead_tie_fixture()
        self.assertEqual(exact_shanten(
            [t for t in h if t != "2b"], qidui=True), 0)
        self.assertEqual(exact_shanten(
            [t for t in h if t != "8t"], qidui=True), 0)
        empty = v._seen(h, [])
        self.assertEqual(v._best_discard_v(h, None, 0, 0, empty), "2b")
        self.assertEqual(k._best_discard_k(h, None, 0, 0), "2b")   # empty==K
        river4 = v._seen(h, ["8t"] * 4)
        self.assertEqual(v._best_discard_v(h, None, 0, 0, river4), "8t")
        # SpeedE 不受河影响仍弃 2b
        from bot.speede import _best_discard_honor
        self.assertEqual(_best_discard_honor(h, None, 0, 0), "2b")

    def test_decide_level_E_vs_V_over_river(self):
        # decide 级（真机 view 带 river 键）：空河 SpeedV==SpeedE 同弃 2b；
        # 河满 8t 后 SpeedV 弃 8t、SpeedE 仍弃 2b。
        h = _dead_tie_fixture()
        E, V = SpeedE(), v.SpeedV()
        ve = _mk_view(h, None, river=[])
        self.assertEqual(E.decide(ve), V.decide(ve))
        self.assertEqual(V.decide(ve), {"action": "discard", "tile": "2b"})
        vf = _mk_view(h, None, river=["8t"] * 4)
        self.assertEqual(V.decide(vf), {"action": "discard", "tile": "8t"})
        self.assertEqual(E.decide(vf), {"action": "discard", "tile": "2b"})


class TestNoTieAgreementWithE(unittest.TestCase):
    def test_prior_noriver_difference_decide_equals_E(self):
        # 无 K1 有效牌 tie、且空河（= 无河见差）的手 → SpeedV 决策逐手 == SpeedE
        E, V = SpeedE(), v.SpeedV()
        agree = 0
        for seed in range(30):
            h = _rand_hand14(seed)
            # 跳过会被 K1 有效牌 tie 拉开的 H19 类无 tie 更常见；逐手核对
            dv = V.decide(_mk_view(h, None, river=[]))
            de = E.decide(_mk_view(h, None, river=[]))
            if dv == de:
                agree += 1
        # 不强迫全等（个别 K1 有效牌 tie 允许分化）；但绝大多数应与 E 一致
        self.assertGreaterEqual(agree, 27)


class TestWindowEqualsE(unittest.TestCase):
    def test_peng_boost_decide_same_as_E(self):
        # 响应窗口（response_peng）：SpeedV 不覆盖 → 动作逐帧 == SpeedE
        h = ["9b", "5t", "1b", "7t", "1w", "6t", "9b", "6b", "1w", "1b",
             "北", "北", "西"]
        E, V = SpeedE(), v.SpeedV()
        view = _mk_view(h, None, phase="response_peng", turn=2,
                        responding_seats=(0,), offer="1b")
        self.assertEqual(E.decide(view), V.decide(view))

    def test_tenpai_offer_both_pass(self):
        t_more = TENPAI_TMORE           # 已听(sb=0)
        E, V = SpeedE(), v.SpeedV()
        view = _mk_view(t_more, None, phase="response_peng", turn=2,
                        responding_seats=(0,), offer="1w")
        self.assertEqual(V.decide(view),
                         {"action": "pass", "tile": ""})
        self.assertEqual(E.decide(view), V.decide(view))


class TestDecideInherit(unittest.TestCase):
    def test_hu_priority_inherited(self):
        V = v.SpeedV()
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "1b", "2b", "3b", "东", "东"]
        act = V.decide(_mk_view(hand, "东", river=[]))
        self.assertEqual(act["action"], "hu")
        self.assertEqual(act["tile"], "")

    def test_catch_play_inherited(self):
        V = v.SpeedV()
        act = V.decide(_mk_view(H19, "中", river=[], catch=True))
        self.assertEqual(act["action"], "discard")
        self.assertEqual(act["tile"], "中")

    def test_non_myturn_delegates_to_super(self):
        E, V = SpeedE(), v.SpeedV()
        view = _mk_view([], None, phase="draw", turn=1)
        self.assertIsNone(V.decide(view))
        self.assertIsNone(E.decide(view))


if __name__ == "__main__":
    unittest.main()
