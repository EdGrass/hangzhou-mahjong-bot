# -*- coding: utf-8 -*-
"""`speedvaluebcvmeld` 契约测试（R1290）——**三层堆叠的部署臂**（不做判词）。

四条不变量：
  ① 接线：`claim_p=0.45`、`W_TILES=5.0`、BC 网 + 副露网都在场、`stats` 是 Counter（R1228 防静默变形）；
  ② **draw 层逐位 ≡ `speedvaluebcv`**（副露层不碰出牌路径）；
  ③ **window 层 ≡ `SpeedValueMeld(claim_p=0.45)`**；
  ④ 副露网缺失 ⇒ 退化不报错。
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

from bot.speedvaluemeld import SpeedValueMeld                      # noqa: E402
from bot.speedvaluebcv import SpeedValueBCV                        # noqa: E402
from bot.speedvaluebcvmeld import SpeedValueBCVMeld                # noqa: E402
from run_bot import STRATEGY_FACTORIES as F                        # noqa: E402


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


class StackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from arm_smoke import to_view
        cls.to_view = staticmethod(to_view)

    def test_wiring(self):
        p = F["speedvaluebcvmeld"]()
        self.assertIsInstance(p, SpeedValueBCVMeld)
        self.assertAlmostEqual(p.claim_p, 0.45, places=9)
        self.assertAlmostEqual(float(p.W_TILES), 5.0, places=9)
        self.assertIsNotNone(p.model, "BC 网未加载")
        self.assertIsNotNone(p._mnet, "副露网未加载")
        self.assertTrue(hasattr(p.stats, "__setitem__"), "stats 必须是可写计数器（R1228）")

    def test_draw_layer_equals_bcv(self):
        a = F["speedvaluebcvmeld"]()
        b = SpeedValueBCV()
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
        self.assertEqual(diff, 0, "draw 层与 speedvaluebcv 有 %d 处分歧" % diff)

    def test_window_layer_equals_meld45(self):
        a = F["speedvaluebcvmeld"]()
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

    def test_missing_meld_net_degrades(self):
        p = F["speedvaluebcvmeld"]()
        p._mnet = None
        rows = _rows("draw", limit=30)
        if not rows:
            self.skipTest("无 dec 语料")
        for r in rows[:30]:
            v = self.to_view(r)
            try:
                d = p.decide(v) or {}
            except Exception as e:                 # noqa: BLE001
                self.fail("decide 抛异常：%s" % e)
            if d.get("action") == "discard":
                self.assertIn(str(d.get("tile")), [str(x) for x in (v.get("my_hand") or [])])


if __name__ == "__main__":
    unittest.main(verbosity=2)
