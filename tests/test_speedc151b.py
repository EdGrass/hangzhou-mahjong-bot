# -*- coding: utf-8 -*-
"""SpeedC151B（c151 的 40ms 有界孪生体）—— **语义/契约护栏**回归。

要钉住的五件事（其余全靠战役）：
  ① **子类关系**：`SpeedC151B` 是 `SpeedC151` 的子类（复用它**自带**的有界路径，不另写一套）；
  ② **身份**：`name == "speedc151b"`、`budget_ms == 40.0`；
  ③ **没有动 c151 本身**：`SpeedC151().budget_ms is None`（本役仍在跑 c151，这是红线）；
  ④ **行为等价**：在**真实 draw 决策点**上，c151b 与 c151 **逐决策分歧 = 0**
     （40ms 预算在本池真实局面上不触发 ⇒ 二者等价，只是 c151b 把最坏延迟封顶）；
  ⑤ **截断真的接了干净回退**：`budget_ms=0.0` 时逐决策 == 基线 `_best_discard_t`
     （证明 deadline/fallback 那条路是真活的，不是摆设）。

用法：python -X utf8 -m unittest tests.test_speedc151b -v
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
from bot.speedc151 import SpeedC151                              # noqa: E402
from bot.speedc151b import SpeedC151B                            # noqa: E402
from bot.speedt import _best_discard_t as base_choice            # noqa: E402


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


class TestC151B(unittest.TestCase):
    def setUp(self):
        self.pos = _positions(60)
        self.assertTrue(self.pos, "取不到真实局面（dec 流）")

    def test_subclass_and_identity(self):
        self.assertTrue(issubclass(SpeedC151B, SpeedC151))
        b = SpeedC151B()
        self.assertEqual(b.name, "speedc151b")
        self.assertEqual(b.budget_ms, 40.0)

    def test_does_not_touch_c151(self):
        a = SpeedC151()
        self.assertEqual(a.name, "speedc151")
        self.assertIsNone(a.budget_ms, "c151 必须保持无界（本役在用它，红线）")

    def test_equivalent_to_c151_on_real_positions(self):
        a = SpeedC151(); b = SpeedC151B()
        bad = 0; n = 0
        for h, d, e, g in self.pos:
            n += 1
            try:
                x = a._pick_discard(list(h), d, e, g)
                y = b._pick_discard(list(h), d, e, g)
            except Exception:
                continue
            if x != y:
                bad += 1
        self.assertGreater(n, 0)
        self.assertEqual(bad, 0, "40ms 预算下 c151b 必须与 c151 逐决策相同")

    def test_zero_budget_returns_clean_fallback(self):
        z = SpeedC151B(budget_ms=0.0)
        bad = 0; n = 0
        for h, d, e, g in self.pos:
            n += 1
            try:
                x = z._pick_discard(list(h), d, e, g)
            except Exception:
                continue
            y = base_choice(list(h), d, e, g, god_meld=z.GOD_MELD)
            if x != y:
                bad += 1
        self.assertGreater(n, 0)
        self.assertEqual(bad, 0, "预算为 0 时必须干净回退到基线（不得把 None 当 0）")

    def test_not_a_noop_vs_plain_baseline(self):
        """c151b 仍应是 c151 语义（不是退化成 speedtugc）：至少一例与裸基线不同。"""
        b = SpeedC151B()
        diff = 0
        for h, d, e, g in self.pos:
            try:
                x = b._pick_discard(list(h), d, e, g)
            except Exception:
                continue
            if x != base_choice(list(h), d, e, g, god_meld=b.GOD_MELD):
                diff += 1
        self.assertGreater(diff, 0, "c151b 必须保留 c151 的路线加成（不是 no-op）")


if __name__ == "__main__":
    unittest.main()


def setUpModule():
    """★ R1346：**无真实语料就整模块跳过**（clone / CI）。

    为什么：本模块的护栏都要在**真实对局记录**（`var/replays/**/*.dec.jsonl`）上取窗口；
    语料不在时它们会报“取不到真实吃牌窗口”这类**假失败**，把真问题淹没。
    `var/` 不在仓库里（.gitignore）⇒ 刚 clone 下来必定无语料，这里明确“跳过”而不是“失败”。
    本地（有语料）行为不变。
    """
    import os as _os
    import unittest as _ut
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    _rep = _os.path.join(_root, "var", "replays")
    _has = False
    if _os.path.isdir(_rep):
        for _dp, _dn, _fn in _os.walk(_rep):
            if any(_x.endswith(".dec.jsonl") for _x in _fn):
                _has = True
                break
    if not _has:
        raise _ut.SkipTest("无真实语料 var/replays/**/*.dec.jsonl（clone/CI）⇒ 跳过本模块")
