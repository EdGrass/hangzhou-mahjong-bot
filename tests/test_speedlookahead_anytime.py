# -*- coding: utf-8 -*-
"""Bounded-fire guards for the anytime lookahead arms."""
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
from bot.speedlookahead import SpeedLookahead, SpeedLookahead2, SpeedLookaheadBoth
from bot.speedlookahead_anytime import (SpeedLookaheadAnytime, SpeedLookaheadAnytime2,
                                        SpeedLookaheadAnytimeBoth, SpeedLookaheadAnytimeTUGC,
                                        SpeedLookaheadLong, SpeedLookaheadLong2,
                                        SpeedLookaheadLongBoth, SpeedLookaheadNoDeadlineBoth)
from bot.speedlookahead_tugc import SpeedLookaheadTUGC
from bot.speedstack import SpeedStack


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
    g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
    return hand, e, g


class TestAnytimeLookahead(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views = _draw_views(900)
        cls.stack = SpeedStack()
        cls.any1 = SpeedLookaheadAnytime()

    @staticmethod
    def _pick(policy, view):
        hand, e, g = _meta(view)
        return policy._pick_discard(hand, view.get("drawn_tile"), e, g, view=view)

    def test_identity(self):
        self.assertTrue(issubclass(SpeedLookaheadAnytime, SpeedLookahead))
        self.assertTrue(issubclass(SpeedLookaheadAnytime2, SpeedLookaheadAnytime))
        self.assertTrue(issubclass(SpeedLookaheadAnytimeBoth, SpeedStack))
        self.assertTrue(issubclass(SpeedLookaheadAnytimeTUGC, SpeedLookaheadTUGC))
        self.assertEqual(SpeedLookaheadAnytime().name, "speedlookaheadanytime")
        self.assertEqual(SpeedLookaheadAnytime2().TARGET_SHANTEN, 2)
        self.assertEqual(SpeedLookaheadAnytime2().TOP_K, 8)

    def test_budget_variants(self):
        self.assertEqual(SpeedLookaheadLong.LOOK_DEADLINE_MS, 900.0)
        self.assertEqual(SpeedLookaheadLong2.LOOK_DEADLINE_MS, 900.0)
        self.assertEqual(SpeedLookaheadNoDeadlineBoth.LOOK_DEADLINE_MS, 0.0)
        p = SpeedLookaheadLongBoth()
        self.assertEqual(p._p1.LOOK_DEADLINE_MS, 900.0)
        self.assertEqual(p._p2.LOOK_DEADLINE_MS, 900.0)

    def test_non_target_is_strict_noop(self):
        checked = 0
        for view in self.views:
            hand, e, g = _meta(view)
            if e or g or len(view.get("river") or []) >= SpeedLookahead.LOOK_RIVER_MIN:
                continue
            self.assertEqual(self._pick(self.stack, view), self._pick(self.any1, view))
            checked += 1
        self.assertGreater(checked, 10, "no non-target rows in fixed corpus")

    def test_mechanism_fires(self):
        changed = checked = 0
        for view in self.views:
            hand, e, g = _meta(view)
            if e or g or len(view.get("river") or []) < SpeedLookahead.LOOK_RIVER_MIN:
                continue
            checked += 1
            if self._pick(self.stack, view) != self._pick(self.any1, view):
                changed += 1
        self.assertGreater(checked, 10, "no target rows in fixed corpus")
        self.assertGreater(changed, 0, "anytime lookahead never fires")

    def test_zero_budget_falls_back_to_parent(self):
        looked = 0
        for view in self.views:
            hand, e, g = _meta(view)
            if e or g or len(view.get("river") or []) < SpeedLookahead.LOOK_RIVER_MIN:
                continue
            old = self.any1.LOOK_DEADLINE_MS
            try:
                self.any1.LOOK_DEADLINE_MS = 1e-9
                self.assertEqual(self._pick(self.any1, view), self._pick(self.stack, view))
            finally:
                self.any1.LOOK_DEADLINE_MS = old
            looked += 1
            if looked >= 3:
                break
        self.assertGreater(looked, 0, "no target row for budget-exhausted guard")

    def test_partial_scan_is_never_fabricated(self):
        """Every retained score must equal a full (deadline-free) computation."""
        checked = 0
        for view in self.views:
            hand, e, g = _meta(view)
            if e or g or len(view.get("river") or []) < SpeedLookahead.LOOK_RIVER_MIN:
                continue
            from bot.ukeire import visible_counts
            base = self._pick(self.stack, view)
            public = visible_counts([], river=view.get("river"),
                                    all_melds=view.get("all_melds"))
            total_live = 136 - sum(int(x) for x in public.values()) - len(hand)
            if total_live <= 0:
                continue
            full = SpeedLookahead()._score_candidates(hand, public, total_live)
            full_by = {d: v for d, v, _c in full}
            partial = self.any1._score_candidates(
                hand, public, total_live,
                deadline=__import__("time").monotonic() + 0.250, base=base)
            for d, v, _c in partial:
                if d in full_by:
                    self.assertAlmostEqual(v, full_by[d], places=9)
                    checked += 1
            if checked >= 5:
                break
        self.assertGreater(checked, 0, "no partial row available for exactness guard")

    def test_end_to_end_decide(self):
        for policy in (SpeedLookaheadAnytime(), SpeedLookaheadAnytime2(),
                       SpeedLookaheadAnytimeBoth(), SpeedLookaheadLongBoth()):
            n = 0
            for view in self.views[:120]:
                action = policy.decide(view)
                self.assertIsInstance(action, dict)
                self.assertIn("action", action)
                n += 1
            self.assertGreater(n, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
