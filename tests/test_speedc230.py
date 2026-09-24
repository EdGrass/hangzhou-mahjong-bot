# -*- coding: utf-8 -*-
"""SpeedC230（吃牌取"最宽搭子"）—— **方向护栏 + 可证占优** 回归。

要钉住的四件事：
  ① **单变量**：`SpeedC230` 是 `SpeedC151` 的子类，只覆盖 `_want_claim`；
  ② **可证占优**：在真实吃牌窗口上，c230 选中的搭子其 `(向听, −live)` **弱优于** c151 的选择
     （c151 的选择一定在 c230 的候选集合里 ⇒ 不可能更差）；且 **不改变"要不要副露"**（None 与 None 对齐）；
  ③ **≤1 个搭子可过门控时严格 no-op**（逐位相同）——保证下行有界；
  ④ **非 no-op**：语料里存在真实窗口使两者不同（否则这个臂是死的）。

用法：python -X utf8 tests/test_speedc230.py -v
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
from arm_smoke import to_view                                   # noqa: E402
from bot.speed import _chi_pairs                                # noqa: E402
from bot.speedc136 import _after_best                           # noqa: E402
from bot.speedc151 import SpeedC151                             # noqa: E402
from bot.speedc230 import SpeedC230                             # noqa: E402
from bot.ukeire import visible_counts                           # noqa: E402


def _chi_windows(limit=300, rooms=25):
    out = []
    dirs = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*")))[-rooms:]
    for dd in dirs:
        for f in sorted(glob.glob(os.path.join(dd, "*_t0.dec.jsonl"))):
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
                if r.get("p") != "response_chi" or not r.get("o"):
                    continue
                v = to_view(r)
                h = list(v["my_hand"])
                melds = v.get("melds") or []
                e = len(melds)
                g = sum(1 for m in melds if m.get("type") == "gang")
                if len(h) != 13 - 3 * e - g:
                    continue
                if not _chi_pairs(h, v["offer_tile"]):
                    continue
                out.append(v)
                if len(out) >= limit:
                    return out
    return out


def _first_pass(pol, v):
    h = list(v["my_hand"])
    melds = v.get("melds") or []
    e = len(melds)
    g = sum(1 for m in melds if m.get("type") == "gang")
    for p in _chi_pairs(h, v["offer_tile"]):
        try:
            if pol._want_claim(v, "chi", p):
                return p
        except Exception:
            return None
    return None


def _key(v, pair):
    """(向听, −live)；pair=None ⇒ 不副露 ⇒ 返回 None。"""
    if pair is None:
        return None
    h = list(v["my_hand"])
    melds = v.get("melds") or []
    e = len(melds)
    g = sum(1 for m in melds if m.get("type") == "gang")
    vis = visible_counts(h, river=v.get("river"), all_melds=v.get("all_melds"))
    aft = _after_best(h, v["offer_tile"], "chi", pair, e, g, vis, True)
    if aft is None:
        return (99, 0.0)
    return (aft[0], -(aft[1] or 0.0))


class TestC230(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = _chi_windows(300, 25)
        cls.a = SpeedC151()
        cls.b = SpeedC230()

    def test_subclass_and_hook(self):
        self.assertTrue(issubclass(SpeedC230, SpeedC151))
        self.assertEqual(SpeedC230().name, "speedc230")
        self.assertIn("_want_claim", SpeedC230.__dict__, "只允许覆盖 _want_claim（单变量）")

    def test_never_worse_and_never_flips_meld(self):
        """核心护栏：目标值弱优 + 不改"要不要副露"。"""
        self.assertTrue(self.win, "取不到真实吃牌窗口")
        worse = 0
        flips = 0
        for v in self.win:
            pa = _first_pass(self.a, v)
            pb = _first_pass(self.b, v)
            if (pa is None) != (pb is None):
                flips += 1
            ka, kb = _key(v, pa), _key(v, pb)
            if ka is not None and kb is not None and kb > ka:
                worse += 1
        self.assertEqual(flips, 0, "c230 不得改变是否副露")
        self.assertEqual(worse, 0, "c230 不得选出比 c151 更差的搭子")

    def test_strict_noop_when_single_option(self):
        """≤1 个搭子能过门控时必须逐位相同（下行有界）。"""
        single = 0
        for v in self.win:
            h = list(v["my_hand"])
            melds = v.get("melds") or []
            e = len(melds)
            g = sum(1 for m in melds if m.get("type") == "gang")
            npass = 0
            for p in _chi_pairs(h, v["offer_tile"]):
                try:
                    if self.a._want_claim(v, "chi", p):
                        npass += 1
                except Exception:
                    pass
            if npass > 1:
                continue
            single += 1
            self.assertEqual(_first_pass(self.a, v), _first_pass(self.b, v))
        self.assertGreater(single, 0, "语料里应存在单选项窗口（否则该护栏没测到东西）")

    def test_is_not_a_noop(self):
        diff = sum(1 for v in self.win if _first_pass(self.a, v) != _first_pass(self.b, v))
        self.assertGreater(diff, 0, "c230 在真实窗口上必须至少改变一次选择")


if __name__ == "__main__":
    unittest.main(verbosity=2)
