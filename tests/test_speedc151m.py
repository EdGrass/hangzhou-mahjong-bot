# -*- coding: utf-8 -*-
"""SpeedC151M（c151 + 副露门控档位放宽）—— **契约护栏**回归。

要钉住的四件事：
  ① 子类关系与身份（`c151m0`/`MILD_UPTO=0`、`make(2).name=="c151m2"`）；
  ② ★ **零档 == `speedc151` 逐例等价**（在真实副露窗口上分歧必须为 0）
     —— 这是"单变量、零档可证明是 no-op"的硬证据；
  ③ **单调性**：`mild_upto` 增大时接受集合只增不减；
  ④ **非 no-op**：`mild_upto=2` 时必须存在与 c151 不同的窗口（否则旋钮是死的）。

用法：python -X utf8 -m unittest tests.test_speedc151m -v
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
from bot.speedc151m import SpeedC151M, make                      # noqa: E402
from bot.speed import _chi_pairs                                 # noqa: E402
from arm_smoke import to_view                                   # noqa: E402


def _windows(limit=400):
    """真实副露窗口：(view, kind, pair)。"""
    out = []
    files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "*", "*.json")))
    random.Random(1511).shuffle(files)
    for f in files:
        try:
            p = json.load(io.open(f, encoding="utf-8"))
        except Exception:
            continue
        for blk in (p.get("blocks") or []):
            sh = blk.get("start_hands")
            if not sh or all(x is None for x in sh):
                continue
            h = list(sh[0] or [])
            if len(h) != 13:
                continue
            base = {"my_hand": list(h), "melds": [], "river": [],
                    "all_melds": [[], [], [], []], "god": None}
            for offer in sorted(set(h)):
                if h.count(offer) >= 2:
                    v = dict(base); v["offer_tile"] = offer; v["phase"] = "response_peng"
                    out.append((v, "peng", None))
                for pr in _chi_pairs(h, offer):
                    v = dict(base); v["offer_tile"] = offer; v["phase"] = "response_chi"
                    out.append((v, "chi", pr))
            if len(out) >= limit:
                return out[:limit]
    return out


def _response_windows(limit=300):
    """真实 `response_peng`/`response_chi` 决策记录（喂给 `decide()` 的端到端样本）。"""
    out = []
    files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "*", "*.dec.jsonl")))
    random.Random(11).shuffle(files)
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
            if r.get("k") != "d" or r.get("p") not in ("response_peng", "response_chi"):
                continue
            out.append(r)
            if len(out) >= limit:
                return out
    return out


class TestC151M(unittest.TestCase):
    def setUp(self):
        self.w = _windows(400)
        self.assertTrue(self.w, "取不到真实副露窗口")

    def test_identity(self):
        self.assertTrue(issubclass(SpeedC151M, SpeedC151))
        self.assertEqual(SpeedC151M().name, "c151m0")
        self.assertEqual(make(2).name, "c151m2")
        self.assertEqual(make(2).MILD_UPTO, 2)

    def test_tier0_equals_c151(self):
        a = SpeedC151()
        b = SpeedC151M(mild_upto=0)
        bad = 0
        for v, kind, pr in self.w:
            if a._want_claim(v, kind, pr) != b._want_claim(v, kind, pr):
                bad += 1
        self.assertEqual(bad, 0, "零档必须与 speedc151 逐例等价（单变量契约）")

    def test_monotone_in_mild_upto(self):
        bad = 0
        for v, kind, pr in self.w:
            prev = SpeedC151M(mild_upto=0)._want_claim(v, kind, pr)
            for k in range(1, 6):
                cur = SpeedC151M(mild_upto=k)._want_claim(v, kind, pr)
                if prev and not cur:
                    bad += 1
                prev = cur
        self.assertEqual(bad, 0, "mild_upto 增大时接受集合只增不减")

    def test_not_a_noop(self):
        a = SpeedC151()
        diff = sum(1 for v, kind, pr in self.w
                   if SpeedC151M(mild_upto=2)._want_claim(v, kind, pr)
                   != a._want_claim(v, kind, pr))
        self.assertGreater(diff, 0, "高档位必须与 c151 有差异（旋钮不是死的）")


    def test_decide_end_to_end_direction(self):
        """`decide()` 端到端：m2 只会**多**副露、绝不**少**副露；且真实窗口上确有新增。"""
        rows = _response_windows(300)
        self.assertTrue(rows, "取不到副露窗口记录")
        a = SpeedC151(); b = SpeedC151M(mild_upto=2)
        n = 0; new = 0; lost = 0; bad = 0
        CLAIM = ("peng", "chi", "gang")
        for r in rows:
            try:
                v = to_view(r)
            except Exception:
                continue
            try:
                x = a.decide(v); y = b.decide(v)
            except Exception:
                bad += 1; continue
            if not x or not y:
                bad += 1; continue
            n += 1
            ax = (x.get("action") or "").lower()
            ay = (y.get("action") or "").lower()
            if ax not in CLAIM and ay in CLAIM:
                new += 1
            elif ax in CLAIM and ay not in CLAIM:
                lost += 1
        self.assertGreater(n, 100, "有效窗口太少")
        self.assertEqual(bad, 0, "decide() 不得抛异常")
        self.assertEqual(lost, 0, "m2 不得减少副露（单向扩展）")
        self.assertGreater(new, 0, "高档位必须在真实窗口上多副露")


if __name__ == "__main__":
    unittest.main()