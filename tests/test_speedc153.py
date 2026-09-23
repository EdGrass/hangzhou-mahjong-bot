# -*- coding: utf-8 -*-
"""speedc153（强制爆头保险臂）单测。

核心断言：**被闸门挡掉时，必须优先走"能变成爆头形"的弃牌**。

⚠ **增量的真实边界（实测更正）**：c148 的 `decide()` 会**先走 C036**（`_best_giveup` 的 EV 判据），
所以"有爆头形且 EV 划算"的场景 c148 **已经**会弃爆头那张。本臂**只多覆盖**：
「**闸门挡 ∧ 有爆头形 ∧ C036 的 EV 判据没过**」（即 §9.25 的 `fan_now=2 且爆头形也只有 2 番` 那类——
此刻我们本来就胡不了，所以"能不能变爆头"与"现在几番"无关）。
夹具是**搜索得到的最小可区分样例**（闸门挡 ∧ 存在爆头形弃牌 ∧ c148 的 _pick_discard 选的是另一张）。
"""
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc148 import SpeedC148                      # noqa: E402
from bot.speedc153 import SpeedC153                      # noqa: E402
from mahjong.hu import is_baotou                          # noqa: E402

# ★ 可区分夹具（搜索得到）：闸门会挡，爆头形弃牌 = 1w，而 c148 的 _pick_discard 选 1b
DISC_HAND = ["2w", "1w", "1w", "6w", "6w", "白", "6w", "1b", "5w", "5w", "白", "2b", "白", "3w"]
DISC_DRAWN = "3w"
# 闸门会挡、但**没有任何**弃牌能变爆头形 ⇒ 两条臂都应退回普通弃牌
PLAIN_HAND = ["白", "1w", "2w", "4w", "5w", "6w", "7b", "8b", "9b", "东", "东", "东", "南", "南"]
PLAIN_DRAWN = "南"
# 爆头 ⇒ 合法，应放行 hu
BAOTOU_PRE = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "1b", "1b", "1b", "白"]
BAOTOU_HAND = BAOTOU_PRE + ["5b"]


def _view(hand, drawn):
    return {"seat": 0, "phase": "draw", "turn": 0, "responding_seats": [],
            "my_hand": list(hand), "melds": [], "drawn_tile": drawn, "offer_tile": None,
            "river": [], "river_len": 6, "all_melds": [], "can_gang": True,
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestForcedBaotou(unittest.TestCase):
    def test_baotou_route_exists_but_fallback_differs(self):
        """先证夹具有效：**爆头路线存在**，且 c148 被挡后用的兜底 `_pick_discard` 选的**不是**它。

        （注意：c148 的 `decide()` 会先走 C036，本夹具上 C036 恰好也会给爆头那张 ⇒
          这里比的是"被挡后的兜底路径"，用于说明**兜底不等于爆头路线**。）
        """
        bd = []
        for d in sorted(set(DISC_HAND)):
            aft = list(DISC_HAND)
            aft.remove(d)
            if is_baotou(aft, allow_qidui=True, exposed_melds=0, gangs=0):
                bd.append(d)
        self.assertIn("1w", bd, "夹具必须存在爆头形弃牌")
        pick148 = SpeedC148()._pick_discard(list(DISC_HAND), DISC_DRAWN, 0, 0,
                                            view=_view(DISC_HAND, DISC_DRAWN))
        self.assertNotIn(pick148, bd, "兜底 _pick_discard 不该等于爆头路线（否则本臂无增量）")

    def test_c153_takes_baotou_route(self):
        act = SpeedC153().decide(_view(DISC_HAND, DISC_DRAWN))
        self.assertEqual(act.get("action"), "discard")
        self.assertEqual(act.get("tile"), "1w", "被闸门挡掉后必须优先走爆头形弃牌")

    def test_blocked_without_baotou_route_still_discards(self):
        for cls in (SpeedC148, SpeedC153):
            act = cls().decide(_view(PLAIN_HAND, PLAIN_DRAWN))
            self.assertEqual(act.get("action"), "discard",
                             "有白平胡被挡后必须弃牌，绝不能返回非法 hu")

    def test_legal_baotou_win_passes_through(self):
        for cls in (SpeedC148, SpeedC153):
            act = cls().decide(_view(BAOTOU_HAND, "5b"))
            self.assertEqual(act.get("action"), "hu", "爆头是合法胡，必须放行")

    def test_source_order_guardrail(self):
        """方向护栏：必须先尝试 `_best_giveup`，**再**退回 `_pick_discard`。"""
        src = inspect.getsource(SpeedC153.decide)
        i_giveup = src.find("self._best_giveup(")     # ⚠ 用调用形式，别匹配到 docstring 里的文字
        i_pick = src.find("self._pick_discard(")
        self.assertGreater(i_giveup, -1, "必须调用 _best_giveup（朝爆头弃牌）")
        self.assertGreater(i_pick, -1, "必须有 _pick_discard 兜底")
        self.assertLess(i_giveup, i_pick, "顺序错了：_best_giveup 必须在 _pick_discard 之前")

    def test_registered_and_flags(self):
        with open(os.path.join(ROOT, "run_bot.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('"speedc153"', src, "必须在 run_bot.STRATEGY_FACTORIES 注册")
        s = SpeedC153()
        self.assertIsInstance(s, SpeedC148)
        self.assertTrue(s.YOU_CAI_BI_KAO, "必须带合法性闸门")


if __name__ == "__main__":
    unittest.main()
