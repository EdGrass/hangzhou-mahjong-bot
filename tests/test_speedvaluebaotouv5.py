# -*- coding: utf-8 -*-
"""`bot/speedvaluebaotouv.SpeedValueBaotouV*` 契约测试（R1266）。

为什么必须钉住：它被排进**三臂役（役 3）**，判词要能归因到"爆头可达性 V 加权项"**这一条**变量。
四条不变量必须在起役前被证明：

  ① **零剂量 / 模型异常 ⇒ 零行为变化**（逐位等于 `SpeedValue`）；
  ② **单变量域**：只覆盖 `value_of`；`_pick_discard` 等全部解析到 `SpeedValue` 的同一函数对象；
  ③ **公式精确**：`value_of` = 基线 value_of + `W_TILES × W_UKEIRE[s] × V(弃牌后状态)`；
  ④ **方向不变式（真实局面）**：改动的那一手，V 必须**严格更高**（本臂存在的全部理由）。
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
from bot.speedvaluebaotouv import (SpeedValueBaotouV5, SpeedValueBaotouV10,   # noqa: E402
                                   SpeedValueBaotouV20)
import bot.speedvaluebaotouv as modv                                     # noqa: E402
from bot.baotou_value import value as V                                  # noqa: E402
from bot.ukeire import visible_counts                                    # noqa: E402
from mahjong.shanten_exact import shanten as exact_shanten                # noqa: E402


def _view(hand, drawn=None, melds=None, river=None, all_melds=None, god=None):
    return {"seat": 0, "phase": "draw", "turn": 6, "my_hand": list(hand),
            "drawn_tile": drawn, "offer_tile": None, "melds": list(melds or []),
            "river": list(river or []), "all_melds": list(all_melds or []),
            "god": god or {"baotou": False, "chain_count": 0, "catch_play": False},
            "draw_idx": 6}


HANDA = (['1w', '2w', '3w', '4w', '5w', '6w', '7b', '8b', '1t', '2t', '3t', '5t', '5t'], '9t')
HANDB = (['1w', '1w', '2w', '3w', '5b', '5b', '6b', '7b', '2t', '3t', '4t', '8t', '9t', '白'], None)


class BaotouVContractTest(unittest.TestCase):
    def setUp(self):
        self.sv = SpeedValue()
        self.v = SpeedValueBaotouV5()

    # ② 单变量域：只覆盖 value_of
    def test_only_value_of_overridden(self):
        for name in ("_pick_discard", "decide"):
            self.assertIs(getattr(SpeedValueBaotouV5, name, None),
                          getattr(SpeedValue, name, None),
                          "%s 不应被覆盖" % name)
        self.assertIsNot(SpeedValueBaotouV5.value_of, SpeedValue.value_of)

    # ③ 公式精确
    def test_formula_exact(self):
        hand, drawn = HANDB
        rem = list(hand)
        e = g = 0
        view = _view(hand, drawn)
        vis = visible_counts(rem, river=view.get("river"), all_melds=view.get("all_melds"))
        for sh in (0, 1, 2):
            a = self.sv.value_of(rem, e, g, vis, view, sh)
            b = self.v.value_of(rem, e, g, vis, view, sh)
            if a is None:
                continue
            w = float(self.sv.W_UKEIRE.get(sh, 0.02))
            bv = float(V(list(rem), e, g, view["river"], view["all_melds"], view["god"],
                           view["draw_idx"], vis=vis))
            self.assertAlmostEqual(b - a, self.v.W_TILES * w * bv, places=6)

    # ① 模型异常 ⇒ 返回基线值（不允许冒异常）
    def test_model_exception_returns_base(self):
        hand, drawn = HANDB
        rem = list(hand)
        view = _view(hand, drawn)
        vis = visible_counts(rem, river=[], all_melds=[])
        a = self.sv.value_of(rem, 0, 0, vis, view, 1)
        with mock.patch.object(modv, "_V", side_effect=RuntimeError("boom")):
            b = self.v.value_of(rem, 0, 0, vis, view, 1)
        self.assertEqual(a, b)

    # ①′ 零剂量 ⇒ 逐位等于基线
    def test_zero_dose_is_identical(self):
        zv = SpeedValueBaotouV5()
        zv.W_TILES = 0.0
        for hand, drawn in (HANDA, HANDB):
            view = _view(hand, drawn)
            a = self.sv._pick_discard(list(hand), drawn, 0, 0, view=view)
            b = zv._pick_discard(list(hand), drawn, 0, 0, view=view)
            self.assertEqual(a, b)

    # 剂量档常量
    def test_dose_constants(self):
        self.assertEqual(SpeedValueBaotouV5.W_TILES, 5.0)
        self.assertEqual(SpeedValueBaotouV10.W_TILES, 10.0)
        self.assertEqual(SpeedValueBaotouV20.W_TILES, 20.0)

    # ④ 方向不变式（真实局面；无语料时跳过）
    def test_direction_on_real_states(self):
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            from arm_smoke import to_view          # noqa: E402
            from offline_replay import draws       # noqa: E402
        except Exception:
            self.skipTest("缺 arm_smoke/offline_replay")
        files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*_t0.dec.jsonl")))[-6:]
        if not files:
            self.skipTest("无 dec 语料")
        n = changed = bad = 0
        for rec in draws(files):
            view = to_view(rec)
            try:
                a = self.sv.decide(view) or {}
                b = self.v.decide(view) or {}
            except Exception:
                continue
            ta, tb = str(a.get("tile") or ""), str(b.get("tile") or "")
            if not ta or not tb:
                continue
            n += 1
            if ta == tb:
                continue
            changed += 1
            try:
                vv = view or {}
                e = len(vv.get("melds") or [])
                g = sum(1 for m in (vv.get("melds") or [])
                        if (m.get("type") if isinstance(m, dict) else None) == "gang")
                ha = list(vv["my_hand"]); ha.remove(ta)
                hb = list(vv["my_hand"]); hb.remove(tb)
                va = V(ha, e, g, vv.get("river") or [], vv.get("all_melds") or [],
                       vv.get("god") or {}, int(vv.get("draw_idx") or 0))
                vb = V(hb, e, g, vv.get("river") or [], vv.get("all_melds") or [],
                       vv.get("god") or {}, int(vv.get("draw_idx") or 0))
                if vb <= va:
                    bad += 1
            except Exception:
                continue
            if n >= 400:
                break
        self.assertGreater(n, 50, "样本太少")
        self.assertEqual(bad, 0, "方向不变式破坏：有 %d 手候选的 V 不高于基线" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
