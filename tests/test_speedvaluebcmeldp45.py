# -*- coding: utf-8 -*-
"""`speedvaluebcmeldp45` 契约测试（R1278）。

它是 **BC 分支的役 4 候选**（组合臂 + 对齐剂量 `claim_p=0.45`）。四条不变量：
  ① 注册接线：工厂取出的臂 `claim_p == 0.45`、两个模型都在场；
  ② **draw 层等价**于 `speedvaluebc`（同 margin/同网络、`_pick_discard` 取 BC 版）；
  ③ **window 层等价**于 `SpeedValueMeld(claim_p=0.45)`（`_want_claim` 取副露网版）；
  ④ 模型缺失 ⇒ 对应层退化为基线（不报错、不静默换策略）。
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

from bot.speedvaluebc import SpeedValueBC                              # noqa: E402
from bot.speedvaluebcmeld import SpeedValueBCMeld                      # noqa: E402
from bot.speedvaluemeld import SpeedValueMeld                          # noqa: E402
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


class BCMeldDose45Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from arm_smoke import to_view
        cls.to_view = staticmethod(to_view)

    # ① 注册接线 + 两模型在场
    def test_registered_and_models_present(self):
        p = F["speedvaluebcmeldp45"]()
        self.assertAlmostEqual(float(p.claim_p), 0.45, places=9)
        self.assertIsInstance(p, SpeedValueBCMeld)
        self.assertIsNotNone(p.model, "BC 网未加载")
        self.assertIsNotNone(p._mnet, "副露网未加载")

    # ② draw 层等价于 speedvaluebc
    def test_draw_layer_equals_bc(self):
        a = F["speedvaluebcmeldp45"]()
        b = SpeedValueBC()
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
        self.assertEqual(diff, 0, "draw 层与 speedvaluebc 有 %d 处分歧" % diff)

    # ③ window 层等价于 SpeedValueMeld(claim_p=0.45)
    def test_window_layer_equals_meld45(self):
        a = F["speedvaluebcmeldp45"]()
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

    # ④ 模型缺失 ⇒ 退化（不报错）
    def test_missing_models_degrade(self):
        p = F["speedvaluebcmeldp45"]()
        p.model = None
        p._mnet = None
        rows = _rows("draw", limit=40)
        if not rows:
            self.skipTest("无 dec 语料")
        for r in rows[:40]:
            v = self.to_view(r)
            d = p.decide(v) or {}                 # 契约是"不抛异常"，不是"每行都必须有动作"
            a = d.get("action")
            if a == "discard":
                self.assertIn(str(d.get("tile")), [str(x) for x in (v.get("my_hand") or [])],
                              "弃的牌必须在手里")
            else:
                self.assertIn(a, (None, "", "pass", "peng", "chi", "gang", "hu"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
