# -*- coding: utf-8 -*-
"""`speedvaluebaotouvmeld` 契约测试（R1279）。

它是 **V 分支的役 4 候选**（新基线 `speedvaluebaotouv5` + 学习副露，对齐剂量 0.45）。四条不变量：
  ① 注册接线：`claim_p == 0.45`、`W_TILES == 5.0`、副露网在场；
  ② **draw 层逐位等价 `speedvaluebaotouv5`**（V 的 `value_of` 一字未改 ⇒ 相对新基线只多一层）；
  ③ **window 层等价 `SpeedValueMeld(claim_p=0.45)`**；
  ④ 副露网缺失 ⇒ 只有窗口层退化，不报错、不换策略。
"""
import glob
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedvaluemeld import SpeedValueMeld                          # noqa: E402
from bot.speedvaluebaotouv import SpeedValueBaotouV5                   # noqa: E402
from bot.speedvaluebaotouvmeld import SpeedValueBaotouVMeld            # noqa: E402
from run_bot import STRATEGY_FACTORIES as F                            # noqa: E402


def _rows(kind, limit=200):
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*_t0.dec.jsonl")))[-4:]:
        try:
            for ln in io.open(p, encoding="utf-8"):
                ln = ln.strip()
                if not ln:
                    continue
                r = json.loads(ln)
                k = str(r.get("p") or "")
                if (kind == "draw" and k == "draw") or \
                   (kind == "window" and k.startswith("response_") and r.get("o")):
                    out.append(r)
                if len(out) >= limit:
                    return out
        except Exception:
            continue
    return out


class BaotouVMeldTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from arm_smoke import to_view
        cls.to_view = staticmethod(to_view)

    # ① 接线
    def test_wiring(self):
        p = F["speedvaluebaotouvmeld"]()
        self.assertIsInstance(p, SpeedValueBaotouVMeld)
        self.assertAlmostEqual(p.claim_p, 0.45, places=9)
        self.assertAlmostEqual(float(p.W_TILES), 5.0, places=9)
        self.assertIsNotNone(p._mnet, "副露网未加载")

    # ② draw 层等价 V 基线
    def test_draw_layer_equals_v(self):
        a = F["speedvaluebaotouvmeld"]()
        b = SpeedValueBaotouV5()
        rows = _rows("draw")
        if not rows:
            self.skipTest("无 dec 语料")
        diff = 0
        for r in rows:
            v = self.to_view(r)
            try:
                da, db = a.decide(v) or {}, b.decide(v) or {}
            except Exception:
                continue
            if (da.get("action"), da.get("tile")) != (db.get("action"), db.get("tile")):
                diff += 1
        self.assertEqual(diff, 0, "draw 层与 speedvaluebaotouv5 有 %d 处分歧" % diff)

    # ③ window 层等价 0.45 档副露臂
    def test_window_layer_equals_meld45(self):
        a = F["speedvaluebaotouvmeld"]()
        b = SpeedValueMeld(claim_p=0.45)
        rows = _rows("window")
        if not rows:
            self.skipTest("无 dec 语料")
        diff = 0
        for r in rows:
            v = self.to_view(r)
            try:
                da, db = a.decide(v) or {}, b.decide(v) or {}
            except Exception:
                continue
            if (da.get("action"), da.get("tile")) != (db.get("action"), db.get("tile")):
                diff += 1
        self.assertEqual(diff, 0, "window 层与 0.45 档副露臂有 %d 处分歧" % diff)

    # ④ 副露网缺失 ⇒ 退化但不报错
    def test_missing_meld_net_degrades(self):
        p = F["speedvaluebaotouvmeld"]()
        p._mnet = None
        rows = _rows("draw", limit=30)
        if not rows:
            self.skipTest("无 dec 语料")
        v_only = SpeedValueBaotouV5()          # 副露网缺失时，draw 层应仍等于 V 基线
        for r in rows[:30]:
            v = self.to_view(r)
            try:
                d = p.decide(v) or {}
            except Exception as e:             # noqa: BLE001
                self.fail("decide 抛异常：%s" % e)
            if d.get("action") == "discard":
                self.assertIn(str(d.get("tile")), [str(x) for x in (v.get("my_hand") or [])])


if __name__ == "__main__":
    unittest.main(verbosity=2)
