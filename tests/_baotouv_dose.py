# -*- coding: utf-8 -*-
"""`SpeedValueBaotouV*` **剂量档**的共享契约用例工厂（R1371）。

背景：`tests/test_speedvaluebaotouv5.py` 的**内容**其实覆盖了 V5/V10/V20（它 import 了三个类并在
`test_dose_constants` 里断言 10.0 / 20.0），但**起役就绪门是按文件名 glob 查的**
（`tests/test_<策略名>*.py`）⇒ `speedvaluebaotouv10` / `speedvaluebaotouv20` 在体检里被判 ❌，
想拿它们当“V 轴第二枪”时会在起役窗口被挡住（§V.50 修过同类问题）。

本模块把“每个剂量档必须自己被钉住的不变量”做成工厂，供 `test_speedvaluebaotouv10.py` /
`test_speedvaluebaotouv20.py` 各自实例化 —— 这样文件名满足门、覆盖也是真的。
"""
import glob
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedvalue import SpeedValue                          # noqa: E402
import bot.speedvaluebaotouv as modv                           # noqa: E402
from bot.baotou_value import value as V                        # noqa: E402
from bot.ukeire import visible_counts                          # noqa: E402

HANDB = (['1w', '1w', '2w', '3w', '5b', '5b', '6b', '7b', '2t', '3t', '4t', '8t', '9t', '白'], None)


def _view(hand, drawn=None):
    return {"seat": 0, "phase": "draw", "turn": 6, "my_hand": list(hand),
            "drawn_tile": drawn, "offer_tile": None, "melds": [], "river": [],
            "all_melds": [], "god": {"baotou": False, "chain_count": 0, "catch_play": False},
            "draw_idx": 6}


def dose_case(cls, dose):
    """生成某个剂量档的 TestCase。"""

    class _DoseContract(unittest.TestCase):
        def setUp(self):
            self.sv = SpeedValue()
            self.arm = cls()

        def test_dose_constant(self):
            self.assertEqual(cls.W_TILES, float(dose))

        def test_single_variable_domain(self):
            # 只覆盖 value_of；出牌/决策必须是 SpeedValue 的同一函数对象
            for name in ("_pick_discard", "decide"):
                self.assertIs(getattr(cls, name, None), getattr(SpeedValue, name, None),
                              "%s 不应被覆盖" % name)
            self.assertIsNot(cls.value_of, SpeedValue.value_of)

        def test_formula_exact(self):
            hand, drawn = HANDB
            rem = list(hand)
            view = _view(hand, drawn)
            vis = visible_counts(rem, river=[], all_melds=[])
            for sh in (0, 1, 2):
                a = self.sv.value_of(rem, 0, 0, vis, view, sh)
                if a is None:
                    continue
                b = self.arm.value_of(rem, 0, 0, vis, view, sh)
                w = float(self.sv.W_UKEIRE.get(sh, 0.02))
                bv = float(V(rem, 0, 0, view["river"], view["all_melds"], view["god"],
                             view["draw_idx"], vis=vis))
                self.assertAlmostEqual(b - a, float(dose) * w * bv, places=6)

        def test_model_exception_returns_base(self):
            hand, drawn = HANDB
            rem = list(hand)
            view = _view(hand, drawn)
            vis = visible_counts(rem, river=[], all_melds=[])
            a = self.sv.value_of(rem, 0, 0, vis, view, 1)
            with mock.patch.object(modv, "_V", side_effect=RuntimeError("boom")):
                b = self.arm.value_of(rem, 0, 0, vis, view, 1)
            self.assertEqual(a, b, "V 算不出必须回退到基线值（不得冒异常）")

        def test_zero_dose_is_identical(self):
            z = cls()
            z.W_TILES = 0.0
            hand, drawn = HANDB
            view = _view(hand, drawn)
            self.assertEqual(self.sv._pick_discard(list(hand), drawn, 0, 0, view=view),
                             z._pick_discard(list(hand), drawn, 0, 0, view=view))

        def test_direction_invariant_on_real_states(self):
            """真实局面上：它改动的那一手，V 必须严格更高（否则本臂不该存在）。无语料则跳过。"""
            try:
                sys.path.insert(0, os.path.join(ROOT, "tools"))
                from arm_smoke import to_view
                from offline_replay import draws
            except Exception:
                self.skipTest("缺 arm_smoke/offline_replay")
            files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*_t0.dec.jsonl")))[-4:]
            if not files:
                self.skipTest("无 dec 语料")
            n = changed = bad = 0
            for rec in draws(files):
                view = to_view(rec)
                try:
                    a = self.sv.decide(view) or {}
                    b = self.arm.decide(view) or {}
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
                    ha = list(vv["my_hand"]); ha.remove(ta)
                    hb = list(vv["my_hand"]); hb.remove(tb)
                    va = V(ha, e, 0, vv.get("river") or [], vv.get("all_melds") or [],
                           vv.get("god") or {}, int(vv.get("draw_idx") or 0))
                    vb = V(hb, e, 0, vv.get("river") or [], vv.get("all_melds") or [],
                           vv.get("god") or {}, int(vv.get("draw_idx") or 0))
                    if vb <= va:
                        bad += 1
                except Exception:
                    continue
                if n >= 300:
                    break
            self.assertEqual(bad, 0, "方向不变式违例 %d/%d（改动了 %d 手）" % (bad, n, changed))

    return _DoseContract
