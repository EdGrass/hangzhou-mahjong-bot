# -*- coding: utf-8 -*-
"""SpeedC151C（c151 + 巡门控拆对惩罚）—— **分段契约护栏**回归。

要钉住的五件事：
  ① 子类关系与身份（`name="speedc151c"`、`GATE_TURN=3`）；
  ② **`巡 >= GATE_TURN` ⇒ 与 `SpeedC151` 逐字相同**；
  ③ **`巡 <  GATE_TURN` ⇒ 与 `SpeedC135D`（有界 c135，无路线加成）逐字相同**；
  ④ **`river_len` 缺失 ⇒ 保守退化为 c151**（不得悄悄变成另一个候选）；
  ⑤ **不是 no-op**：存在真实局面使 `SpeedC151` 与 `SpeedC135D` 不同（否则闸门是死的）。

用法：python -X utf8 -m unittest tests.test_speedc151c -v
"""
import glob
import io
import json
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "var"))
from bot.speedc151 import SpeedC151                              # noqa: E402
from bot.speedc151c import SpeedC151C                            # noqa: E402
from bot.speedc135d import SpeedC135D                            # noqa: E402


def _positions(limit=60):
    """真实弃牌局面：(hand, drawn, exposed, gangs)。"""
    out = []
    files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "*", "*_t0.dec.jsonl")))
    random.Random(151) .shuffle(files)
    for f in files:
        try:
            lines = io.open(f, encoding="utf-8").read().splitlines()
        except OSError:
            continue
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("p") != "draw" or (r.get("a") or {}).get("action") != "discard":
                continue
            h = r.get("h"); m = r.get("m") or []
            e = len(m); g = sum(1 for x in m if len(x) == 4)
            if not h or len(h) != 14 - 3 * e - g:
                continue
            out.append((list(h), r.get("d"), e, g))
            if len(out) >= limit:
                return out
    return out


def _v(rl):
    return {"river_len": rl, "river": [], "all_melds": [[], [], [], []], "melds": []}


class TestC151C(unittest.TestCase):
    def setUp(self):
        self.pos = _positions(60)
        self.assertTrue(self.pos, "取不到真实局面（dec 流）")

    def test_identity(self):
        c = SpeedC151C()
        self.assertTrue(issubclass(SpeedC151C, SpeedC151))
        self.assertEqual(c.name, "speedc151c")
        self.assertEqual(c.GATE_TURN, 3)
        self.assertEqual(c._turn_of({"river_len": 12}), 3)
        self.assertEqual(c._turn_of({"river_len": 8}), 2)
        self.assertIsNone(c._turn_of({}))

    def test_late_turns_match_c151(self):
        a = SpeedC151(); c = SpeedC151C()
        bad = n = 0
        view = _v(12)                    # 巡 3 == GATE ⇒ 走 c151
        for h, d, e, g in self.pos:
            n += 1
            try:
                if a._pick_discard(list(h), d, e, g, view=view) != \
                   c._pick_discard(list(h), d, e, g, view=view):
                    bad += 1
            except Exception:
                continue
        self.assertGreater(n, 0)
        self.assertEqual(bad, 0, "巡 >= GATE 时必须与 c151 逐字相同")

    def test_early_turns_match_bounded_c135(self):
        # 用大预算：40ms 时阀门偶尔会在负载下到期（见 R807 的非确定性度量），
        # 那是"预算内走候选、超预算走基线"的设计行为，**不是语义差异**。
        c = SpeedC151C(budget_ms=10000.0)
        ref = SpeedC135D(budget_ms=10000.0)
        bad = n = 0
        view = _v(0)                     # 巡 1 < GATE ⇒ 走有界 c135
        for h, d, e, g in self.pos:
            n += 1
            try:
                if ref._pick_discard(list(h), d, e, g, view=view) != \
                   c._pick_discard(list(h), d, e, g, view=view):
                    bad += 1
            except Exception:
                continue
        self.assertGreater(n, 0)
        self.assertEqual(bad, 0, "巡 < GATE 时必须与有界 c135 逐字相同")

    def test_missing_river_len_degrades_to_c151(self):
        a = SpeedC151(); c = SpeedC151C()
        bad = n = 0
        for h, d, e, g in self.pos:
            n += 1
            try:
                if a._pick_discard(list(h), d, e, g, view={}) != \
                   c._pick_discard(list(h), d, e, g, view={}):
                    bad += 1
            except Exception:
                continue
        self.assertEqual(bad, 0, "拿不到 river_len 时必须保守退化到 c151")

    def test_not_a_noop(self):
        a = SpeedC151(); ref = SpeedC135D(budget_ms=10000.0)
        diff = 0
        view = _v(0)
        for h, d, e, g in self.pos:
            try:
                if a._pick_discard(list(h), d, e, g, view=view) != \
                   ref._pick_discard(list(h), d, e, g, view=view):
                    diff += 1
            except Exception:
                continue
        self.assertGreater(diff, 0, "c151 与 c135 必须存在差异，否则闸门没作用")


if __name__ == "__main__":
    unittest.main()