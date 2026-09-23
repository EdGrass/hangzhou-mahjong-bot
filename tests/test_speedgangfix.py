# -*- coding: utf-8 -*-
"""`speedgangfix` 的护栏单测（R941）。运行：python -X utf8 tests/test_speedgangfix.py

口径提醒：`_pick_discard` 收到的是**弃牌前**手牌 ⇒ e 面子 + g 杠时应有 14-3e-g 张
（g>0 时 ≡ 13-3e+1 张）；而**响应窗口**里手牌是 13-3e 张。
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mahjong.shanten_exact import shanten as SH                       # noqa: E402
from bot.speedc151 import SpeedC151                                    # noqa: E402
from bot.speedroute import SpeedRouteLate                              # noqa: E402
from bot.speedgangfix import SpeedGangFix, SpeedGangFixClaim, SpeedGangFixLate   # noqa: E402

GANG = {"type": "gang", "tile": "1b", "tiles": ["1b"] * 4}

# 弃牌前手牌：e=1, g=1 ⇒ 14-3*1-1 = 10 张？——不是：带杠手牌弃牌前 = 13-3e+1 = 11 张
GANG_HANDS_PRE = [
    ["2b", "2b", "3b", "4b", "5b", "6b", "7b", "1w", "1w", "5t", "东"],
    ["1w", "2w", "3w", "5b", "5b", "7t", "7t", "9b", "9b", "东", "南"],
    ["1b", "1b", "2b", "3b", "4b", "6t", "7t", "8t", "9w", "9w", "北"],
    ["东", "1w", "2w", "3w", "南", "西", "北", "6b", "6b", "6b", "白"],
    ["9w", "9w", "8w", "7w", "6w", "5w", "5w", "2t", "3t", "4t", "东"],
]

# e=0 的**弃牌前**手牌 = 14 张（含刚摸牌）—— 13 张会让 `cands` 为空、
# 两个臂都走兜底而"看起来一致"（我第一版就踩了这个**假绿**）
NON_GANG_HANDS = [
    ["1w", "2w", "3w", "4b", "5b", "6b", "7t", "8t", "9t", "9t", "东", "南", "西", "北"],
    ["2b", "3b", "4b", "5t", "5t", "5t", "7w", "8w", "9w", "1b", "1b", "9b", "白", "东"],
    ["1t", "2t", "3t", "4t", "5t", "6t", "7t", "8t", "9t", "东", "东", "发", "白", "南"],
]


def _sh_gangaware(hand, played, e):
    """修正约定：暗牌 13-3e 张、gangs=0（杠按 3 张计）。"""
    hh = list(hand)
    hh.remove(played)
    if len(hh) != 13 - 3 * e:
        return None
    return SH(hh, qidui=(e == 0), exposed_melds=e, gangs=0)


def _best_sh(hand, e):
    vals = [_sh_gangaware(hand, d, e) for d in sorted(set(hand))]
    vals = [v for v in vals if v is not None]
    return min(vals) if vals else None


class TestGangFix(unittest.TestCase):
    def test_fixture_sanity(self):
        """fixture 数量级自检（防止再次写错规格）。"""
        for hand in GANG_HANDS_PRE:
            self.assertEqual(len(hand), 11, "带杠弃牌前应为 11 张（e=1,g=1）")
        for hand in NON_GANG_HANDS:
            self.assertEqual(len(hand), 14, "非杠弃牌前应为 14 张（e=0，含刚摸牌）")

    def test_gang_fix_preserves_shanten(self):
        """① 带杠手牌：修复臂必须保向听。"""
        fix = SpeedGangFix()
        for hand in GANG_HANDS_PRE:
            best = _best_sh(hand, 1)
            self.assertIsNotNone(best, "样本应在修正约定下可评估：%s" % hand)
            tile = fix._pick_discard(list(hand), None, 1, 1, view=None)
            self.assertIn(tile, hand, "必须返回手里的牌")
            self.assertEqual(_sh_gangaware(hand, tile, 1), best,
                             "带杠手牌必须保向听：hand=%s 选=%s" % (hand, tile))

    def test_old_bug_signature_returns_hand0(self):
        """② 旧实现 `cands` 为空 ⇒ `return hand[0]`。"""
        c151 = SpeedC151()
        hit = sum(1 for hand in GANG_HANDS_PRE
                  if c151._pick_discard(list(hand), None, 1, 1, view=None) == hand[0])
        self.assertGreaterEqual(hit, 1, "旧实现应至少在一个带杠局面上返回 hand[0]")

    def test_non_gang_identical(self):
        """③ 非杠手牌：修复臂与 c151 逐位相同。"""
        c151 = SpeedC151()
        fix = SpeedGangFix()
        for hand in NON_GANG_HANDS:
            a = c151._pick_discard(list(hand), None, 0, 0, view=None)
            b = fix._pick_discard(list(hand), None, 0, 0, view=None)
            self.assertEqual(a, b, "非杠必须逐位一致：hand=%s" % hand)

    def test_gang_claim_is_no_longer_blanket_false(self):
        """④ 带杠手牌：**存在**至少一个窗口，父类因长度检查拒绝、而修复臂接受。"""
        parent = SpeedC151()
        fixed = SpeedGangFixClaim()
        found = 0
        offers = ["5b", "2b", "1w", "9b", "7t", "6b", "3b", "4b", "东", "白", "南", "西"]
        for hand10 in [h[:10] for h in GANG_HANDS_PRE]:
            for off in offers:
                if hand10.count(off) < 2:
                    continue
                view = {"my_hand": list(hand10), "melds": [dict(GANG)], "offer_tile": off,
                        "phase": "response_peng", "river": [], "all_melds": [[], [], [], []]}
                if parent._want_claim(view, "peng") is False and fixed._want_claim(view, "peng") is True:
                    found += 1
        self.assertGreater(found, 0,
                           "修复臂应至少在一个带杠窗口上给出 True（父类全 False）")

    def test_gang_claim_rejects_when_no_pair(self):
        """④-b 反向护栏：手里不足 2 张时不得接受碰。"""
        hand10 = ["1w", "2w", "3w", "5b", "7t", "7t", "9b", "9b", "东", "南"]
        view = {"my_hand": list(hand10), "melds": [dict(GANG)], "offer_tile": "5b",
                "phase": "response_peng", "river": [], "all_melds": [[], [], [], []]}
        self.assertIs(SpeedGangFixClaim()._want_claim(view, "peng"), False)


class TestGangFixLate(unittest.TestCase):
    """组合臂：非杠 == SpeedRouteLate；带杠保向听。"""

    def test_non_gang_equals_route_late(self):
        rl = SpeedRouteLate()
        fl = SpeedGangFixLate()
        for hand in NON_GANG_HANDS:
            a = rl._pick_discard(list(hand), None, 0, 0, view=None)
            b = fl._pick_discard(list(hand), None, 0, 0, view=None)
            self.assertEqual(a, b, "非杠必须与 SpeedRouteLate 逐位一致：hand=%s" % hand)

    def test_gang_preserves_shanten(self):
        fl = SpeedGangFixLate()
        for hand in GANG_HANDS_PRE:
            best = _best_sh(hand, 1)
            self.assertIsNotNone(best)
            tile = fl._pick_discard(list(hand), None, 1, 1, view=None)
            self.assertEqual(_sh_gangaware(hand, tile, 1), best,
                             "组合臂带杠必须保向听：hand=%s 选=%s" % (hand, tile))


if __name__ == "__main__":
    unittest.main(verbosity=2)