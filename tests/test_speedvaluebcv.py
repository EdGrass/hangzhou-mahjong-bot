# -*- coding: utf-8 -*-
"""`speedvaluebcv` 契约测试（R1267）—— **部署候选臂**（BC+V，21.8% 改动面）。

不变量：
  ① **单变量域**：相对 `SpeedValueBC` 只覆盖 `value_of`（`_pick_discard` 必须是同一函数对象）；
  ② **V 项公式**：`value_of` = `SpeedValue.value_of` + `W_TILES × W_UKEIRE[s] × V`；
  ③ 模型异常 ⇒ 返回基线值（不冒异常）；剂量常量 = 5.0；
  ④ 真实局面 smoke：决策落在手里、无异常（不要求方向，顺序组合下方向由 BC 决定）。
"""
import glob
import io
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedvalue import SpeedValue                                    # noqa: E402
from bot.speedvaluebc import SpeedValueBC                                # noqa: E402
from bot.speedvaluebcv import SpeedValueBCV                              # noqa: E402
import bot.speedvaluebcv as modbcv                                       # noqa: E402
from bot.baotou_value import value as V                                  # noqa: E402
from bot.ukeire import visible_counts                                    # noqa: E402

HAND = (['1w', '2w', '3w', '4w', '5w', '6w', '7b', '8b', '1t', '2t', '3t', '5t', '5t'], '9t')


def _view(hand, drawn=None):
    return {"seat": 0, "phase": "draw", "turn": 6, "my_hand": list(hand), "drawn_tile": drawn,
            "offer_tile": None, "melds": [], "river": [], "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False}, "draw_idx": 6}


class BCVContractTest(unittest.TestCase):
    # ① 只覆盖 value_of
    def test_only_value_of_overridden(self):
        self.assertIs(SpeedValueBCV._pick_discard, SpeedValueBC._pick_discard)
        self.assertIsNot(SpeedValueBCV.value_of, SpeedValueBC.value_of)
        self.assertEqual(SpeedValueBCV.W_TILES, 5.0)

    # ② 公式精确
    def test_formula_exact(self):
        hand, drawn = HAND
        rem = list(hand)
        view = _view(hand, drawn)
        vis = visible_counts(rem, river=[], all_melds=[])
        sv = SpeedValue()
        bcv = SpeedValueBCV()
        for sh in (1, 2):
            a = sv.value_of(rem, 0, 0, vis, view, sh)
            b = bcv.value_of(rem, 0, 0, vis, view, sh)
            if a is None:
                continue
            bv = float(V(list(rem), 0, 0, [], [], view["god"], 6, vis=vis))
            self.assertAlmostEqual(b - a, bcv.W_TILES * float(sv.W_UKEIRE.get(sh, 0.02)) * bv, places=6)

    # ③ 模型异常 ⇒ 基线值
    def test_model_exception_returns_base(self):
        hand, drawn = HAND
        rem = list(hand)
        view = _view(hand, drawn)
        vis = visible_counts(rem, river=[], all_melds=[])
        sv = SpeedValue()
        bcv = SpeedValueBCV()
        a = sv.value_of(rem, 0, 0, vis, view, 1)
        with mock.patch.object(modbcv, "_V", side_effect=RuntimeError("boom")):
            b = bcv.value_of(rem, 0, 0, vis, view, 1)
        self.assertEqual(a, b)

    # ④ 真实局面 smoke
    def test_real_state_smoke(self):
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            from arm_smoke import to_view
            from offline_replay import draws
        except Exception:
            self.skipTest("缺 arm_smoke/offline_replay")
        files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*_t0.dec.jsonl")))[-3:]
        if not files:
            self.skipTest("无 dec 语料")
        bcv = SpeedValueBCV()
        n = 0
        for rec in draws(files):
            v = to_view(rec)
            try:
                d = bcv.decide(v) or {}
            except Exception as e:                     # noqa: BLE001
                self.fail("decide 抛异常：%s" % e)
            if d.get("action") == "discard":
                self.assertIn(str(d.get("tile")), [str(x) for x in v["my_hand"]])
            n += 1
            if n >= 120:
                break
        self.assertGreater(n, 20, "样本太少")


if __name__ == "__main__":
    unittest.main(verbosity=2)
