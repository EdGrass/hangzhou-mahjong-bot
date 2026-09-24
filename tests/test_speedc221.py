# -*- coding: utf-8 -*-
"""SpeedC221（只在 1 向听用真进张修宽度）—— **方向/语义护栏**回归。

要钉住的五件事（其余全靠战役）：
  ① **单变量**：继承 `SpeedTUGC`，唯一改动的格子是 `s == 1`；
  ② **`s != 1` 时与基线逐字相同**（含 s==0 的 waits 宽度；这是"单变量"的硬证据）；
  ③ **预算为 0 时在 `s == 1` 也干净回退到基线**（`real_ukeire` 返回 (None,None)，**绝不把 None 当 0**）；
  ④ **绝不牺牲向听**：选出的牌留下的向听 = 最小向听；
  ⑤ **不是 no-op**：在 `s == 1` 的真实局面上，至少有一例与基线不同。

用法：python -X utf8 -m unittest tests.test_speedc221 -v
"""
import glob
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "var"))
from bot.speedc221 import SpeedC221, _best_discard_width_at_1sh   # noqa: E402
from bot.speedtugc import SpeedTUGC                               # noqa: E402
from bot.speedt import _best_discard_t as base_choice             # noqa: E402
from mahjong.shanten_exact import shanten as SH                   # noqa: E402


def _positions(limit=60):
    """真实弃牌局面：(hand, drawn, exposed, gangs)。"""
    out = []
    files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "*", "*_t0.dec.jsonl")))[-60:]
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


def _sh(h, e, g):
    return SH(h, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g)


def _min_shanten(hand, e, g):
    best = None
    for d in set(hand):
        hh = list(hand); hh.remove(d)
        try:
            v = _sh(hh, e, g)
        except Exception:
            continue
        if best is None or v < best:
            best = v
    return best


class TestC221(unittest.TestCase):
    def setUp(self):
        self.pos = _positions(60)
        self.assertTrue(self.pos, "取不到真实局面（dec 流）")

    def test_is_single_variable(self):
        self.assertTrue(issubclass(SpeedC221, SpeedTUGC))
        src = io.open(os.path.join(ROOT, "bot", "speedc221.py"), encoding="utf-8").read()
        self.assertIn("_best_discard_t", src)              # 干净回退必须在
        self.assertIn("smin != 1", src)                    # 只改 1 向听那一格

    def test_non_1sh_matches_baseline_exactly(self):
        bad = 0; n = 0
        for h, d, e, g in self.pos:
            smin = _min_shanten(h, e, g)
            if smin == 1 or smin is None:
                continue
            n += 1
            a = _best_discard_width_at_1sh(h, d, e, g, god_meld=True, view=None)
            b = base_choice(h, d, e, g, god_meld=True)
            if a != b:
                bad += 1
        self.assertGreater(n, 0, "样本里应当有非 1 向听的局面")
        self.assertEqual(bad, 0, "s != 1 时必须与基线逐字相同（单变量契约）")

    def test_zero_budget_falls_back_to_baseline(self):
        bad = 0; n = 0
        for h, d, e, g in self.pos:
            if _min_shanten(h, e, g) != 1:
                continue
            n += 1
            a = _best_discard_width_at_1sh(h, d, e, g, god_meld=True, view=None, budget_ms=0.0)
            b = base_choice(h, d, e, g, god_meld=True)
            if a != b:
                bad += 1
        self.assertGreater(n, 0, "样本里应当有 1 向听的局面")
        self.assertEqual(bad, 0, "预算为 0 时必须干净回退（不得把 None 当 0）")

    def test_never_sacrifices_shanten(self):
        bad = 0
        for h, d, e, g in self.pos:
            pick = _best_discard_width_at_1sh(h, d, e, g, god_meld=True, view=None, budget_ms=40.0)
            hh = list(h)
            if pick not in hh:
                bad += 1; continue
            hh.remove(pick)
            smin = _min_shanten(h, e, g)
            try:
                s = _sh(hh, e, g)
            except Exception:
                continue
            if smin is not None and s > smin:
                bad += 1
        self.assertEqual(bad, 0, "绝不允许为了宽度/回退而牺牲向听")

    def test_not_a_noop_on_1sh(self):
        diff = 0; n = 0
        for h, d, e, g in self.pos:
            if _min_shanten(h, e, g) != 1:
                continue
            n += 1
            if _best_discard_width_at_1sh(h, d, e, g, god_meld=True, view=None) != \
                    base_choice(h, d, e, g, god_meld=True):
                diff += 1
        self.assertGreater(n, 0)
        self.assertGreater(diff, 0, "在 1 向听局面上必须至少有一例与基线不同（不是 no-op）")


if __name__ == "__main__":
    unittest.main()
