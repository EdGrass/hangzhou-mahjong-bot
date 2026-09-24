# -*- coding: utf-8 -*-
"""C135D（有界延迟版 c135）—— **方向/语义护栏**回归。

要钉住的四件事（其余全靠战役）：
  ① **单变量**：`SpeedC135D` 继承 `SpeedTUGC`，唯一差别是"给 real_ukeire 加预算 + 超预算回退基线"；
  ② **预算足够大时与 c135 逐字相同**（有界化不改变行为）；
  ③ **预算为 0 时与基线 `_best_discard_t` 逐字相同**（干净回退；**绝不把 None 当 0 做有偏比较**）；
  ④ **绝不牺牲向听**：选出来的牌留下的向听 = 最小向听（与 c135 的契约一致）。

单测用**真实复盘局面**（本地 dec 流的 `h/d/m`），不手搓牌型。
用法：python -X utf8 -m unittest tests.test_speedc135d -v
"""
import glob, io, json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools")); sys.path.insert(0, os.path.join(ROOT, "var"))
from bot.speedc135d import SpeedC135D, _best_discard_realukeire_bounded  # noqa: E402
from bot.speedc135 import _best_discard_realukeire as c135_choice          # noqa: E402
from bot.speedtugc import SpeedTUGC                                        # noqa: E402
from bot.speedt import _best_discard_t as base_choice                      # noqa: E402
from mahjong.shanten_exact import shanten as SH                            # noqa: E402


def _positions(limit=40):
    """真实弃牌局面：(hand(14-3e-g 张), drawn, exposed, gangs)。"""
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "a_*_t0.dec.jsonl")))[-40:]:
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
            if r.get("p") != "draw":
                continue
            if (r.get("a") or {}).get("action") != "discard":
                continue
            h = r.get("h"); m = r.get("m") or []
            e = len(m); g = sum(1 for x in m if len(x) == 4)
            if not h or len(h) != 14 - 3 * e - g:
                continue
            out.append((list(h), r.get("d"), e, g))
            if len(out) >= limit:
                return out
    return out


def _min_shanten(hand, drawn, e, g):
    best = None
    for d in set(hand):
        hh = list(hand); hh.remove(d)
        try:
            v = SH(hh, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g)
        except Exception:
            continue
        if best is None or v < best:
            best = v
    return best


class TestC135D(unittest.TestCase):
    def setUp(self):
        self.pos = _positions(40)
        self.assertTrue(self.pos, "取不到真实局面（dec 流）")

    def test_is_single_variable(self):
        self.assertTrue(issubclass(SpeedC135D, SpeedTUGC))
        src = io.open(os.path.join(ROOT, "bot", "speedc135d.py"), encoding="utf-8").read()
        self.assertIn("_best_discard_realukeire_bounded", src)
        self.assertIn("_best_discard_t", src)          # 干净回退必须存在

    def test_huge_budget_matches_c135(self):
        bad = 0
        for h, d, e, g in self.pos:
            a = _best_discard_realukeire_bounded(h, d, e, g, god_meld=True, view=None, budget_ms=1e6)
            b = c135_choice(h, d, e, g, god_meld=True, view=None)
            if a != b:
                bad += 1
        self.assertEqual(bad, 0, "预算足够大时必须与 c135 逐字相同（有界化不得改变行为）")

    def test_zero_budget_falls_back_to_baseline(self):
        bad = 0
        for h, d, e, g in self.pos:
            a = _best_discard_realukeire_bounded(h, d, e, g, god_meld=True, view=None, budget_ms=0.0)
            b = base_choice(h, d, e, g, god_meld=True)
            if a != b:
                bad += 1
        self.assertEqual(bad, 0, "预算为 0 时必须干净回退到基线（不得把 None 当 0 做有偏比较）")

    def test_never_sacrifices_shanten(self):
        bad = 0
        for h, d, e, g in self.pos[:20]:
            pick = _best_discard_realukeire_bounded(h, d, e, g, god_meld=True, view=None, budget_ms=40.0)
            hh = list(h)
            if pick not in hh:
                bad += 1; continue
            hh.remove(pick)
            try:
                s = SH(hh, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g)
            except Exception:
                continue
            smin = _min_shanten(h, d, e, g)
            if smin is not None and s > smin:
                bad += 1
        self.assertEqual(bad, 0, "绝不允许为了预算/回退而牺牲向听")


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
