# -*- coding: utf-8 -*-
"""Bounded-fire guards for the pair-KEEPING route arms (SpeedRouteKeep*)."""
from __future__ import annotations

import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from arm_smoke import to_view
from bot.speedc150 import SpeedC150
from bot.speedc151 import SpeedC151
from bot.speedroute import _pick_discard_route_bonus
from bot.speedroutekeep import SpeedRouteKeep4, SpeedRouteKeep8, SpeedRouteKeep8Late


def _draw_views(limit=900):
    out = []
    with io.open(os.path.join(ROOT, "var", "smoke_corpus_v1.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("p") != "draw":
                continue
            out.append(to_view(row))
            if len(out) >= limit:
                break
    return out


def _meta(view):
    hand = list(view.get("my_hand") or [])
    melds = view.get("melds") or []
    e = len(melds)
    g = sum(1 for m in melds
            if isinstance(m, dict) and m.get("type") == "gang")
    return hand, e, g


class _Control(SpeedC150):
    """Identical scoring path with the ORIGINAL bonus -- must equal c151."""

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _pick_discard_route_bonus(
            hand, drawn, exposed, gangs, god_meld=self.GOD_MELD, view=view,
            route_bonus=8.0, gate_river=0)


class _Control0(SpeedC150):
    """Identical path with the bonus switched OFF -- what *Late is before the gate."""

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        return _pick_discard_route_bonus(
            hand, drawn, exposed, gangs, god_meld=self.GOD_MELD, view=view,
            route_bonus=0.0, gate_river=0)


class TestRouteKeep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views = _draw_views(900)
        cls.c151 = SpeedC151()

    @staticmethod
    def _pick(policy, view):
        hand, e, g = _meta(view)
        return policy._pick_discard(hand, view.get("drawn_tile"), e, g, view=view)

    def test_identity(self):
        for cls, bonus in ((SpeedRouteKeep4, -4.0), (SpeedRouteKeep8, -8.0),
                           (SpeedRouteKeep8Late, -8.0)):
            self.assertTrue(issubclass(cls, SpeedC150))
            self.assertEqual(cls.ROUTE_BONUS, bonus)
        self.assertEqual(SpeedRouteKeep8Late.GATE_RIVER, 12)
        self.assertEqual(SpeedRouteKeep8.GATE_RIVER, 0)

    def test_control_path_reproduces_c151(self):
        """The copied scoring path with bonus=+8 must be byte-identical to c151."""
        ctl = _Control()
        n = 0
        for view in self.views[:200]:
            self.assertEqual(self._pick(self.c151, view), self._pick(ctl, view))
            n += 1
        self.assertGreater(n, 0)

    def test_mechanism_fires(self):
        keep = SpeedRouteKeep8()
        changed = 0
        for view in self.views:
            if self._pick(self.c151, view) != self._pick(keep, view):
                changed += 1
        self.assertGreater(changed, 0, "pair-keeping never changes a decision")

    def test_late_gate_switches_the_bonus_off_before_the_river(self):
        """Before the river gate the bonus is OFF, i.e. it equals bonus=0 -- not c151."""
        late = SpeedRouteKeep8Late()
        off = _Control0()
        checked = 0
        for view in self.views:
            if len(view.get("river") or []) >= SpeedRouteKeep8Late.GATE_RIVER:
                continue
            self.assertEqual(self._pick(off, view), self._pick(late, view))
            checked += 1
        self.assertGreater(checked, 10, "no pre-gate rows in fixed corpus")

    def test_end_to_end_decide(self):
        for policy in (SpeedRouteKeep4(), SpeedRouteKeep8(), SpeedRouteKeep8Late()):
            n = 0
            for view in self.views[:150]:
                act = policy.decide(view)
                self.assertIsInstance(act, dict)
                self.assertIn("action", act)
                n += 1
            self.assertGreater(n, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)


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
