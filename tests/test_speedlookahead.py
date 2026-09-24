# -*- coding: utf-8 -*-
"""Bounded-fire guards for SpeedLookahead."""
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
from bot.speedstack import SpeedStack
from bot.ukeire import visible_counts


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


class TestSpeedLookahead(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views = _draw_views(900)
        cls.stack = SpeedStack()
        cls.look = SpeedLookahead()

    @staticmethod
    def _pick(policy, view):
        hand, e, g = _meta(view)
        return policy._pick_discard(hand, view.get("drawn_tile"), e, g, view=view)

    def test_identity(self):
        self.assertTrue(issubclass(SpeedLookahead, SpeedStack))
        self.assertEqual(SpeedLookahead().name, "speedlookahead")
        self.assertGreater(SpeedLookahead.TOP_K, 0)
        self.assertGreater(SpeedLookahead.TOP_DRAWS, 0)

    def test_identity_s2(self):
        self.assertTrue(issubclass(SpeedLookahead2, SpeedLookahead))
        p = SpeedLookahead2()
        self.assertEqual(p.name, "speedlookahead2")
        self.assertEqual(p.TARGET_SHANTEN, 2)
        self.assertEqual(p.TOP_K, 8)
        self.assertGreaterEqual(p.SWITCH_MARGIN, 0.5)

    def test_identity_both(self):
        self.assertTrue(issubclass(SpeedLookaheadBoth, SpeedStack))
        p = SpeedLookaheadBoth()
        self.assertEqual(p.name, "speedlookaheadboth")
        self.assertEqual(p._p1.TARGET_SHANTEN, 1)
        self.assertEqual(p._p2.TARGET_SHANTEN, 2)

    def test_non_target_is_strict_noop(self):
        checked = 0
        for view in self.views:
            hand, e, g = _meta(view)
            if e or g or len(view.get("river") or []) >= SpeedLookahead.LOOK_RIVER_MIN:
                continue
            self.assertEqual(self._pick(self.stack, view), self._pick(self.look, view))
            checked += 1
        self.assertGreater(checked, 10, "no non-target rows in fixed corpus")

    def test_target_is_not_a_noop(self):
        changed = 0
        checked = 0
        for view in self.views:
            hand, e, g = _meta(view)
            if e or g or len(view.get("river") or []) < SpeedLookahead.LOOK_RIVER_MIN:
                continue
            a = self._pick(self.stack, view)
            b = self._pick(self.look, view)
            checked += 1
            if a != b:
                changed += 1
        self.assertGreater(checked, 10, "no target rows in fixed corpus")
        self.assertGreater(changed, 0, "lookahead never fires on fixed corpus")

    def test_switch_respects_margin(self):
        checked = 0
        for view in self.views:
            hand, e, g = _meta(view)
            if e or g or len(view.get("river") or []) < SpeedLookahead.LOOK_RIVER_MIN:
                continue
            base = self._pick(self.stack, view)
            chosen = self._pick(self.look, view)
            if chosen == base:
                continue
            public = visible_counts([], river=view.get("river"),
                                    all_melds=view.get("all_melds"))
            total_live = 136 - sum(int(x) for x in public.values()) - len(hand)
            eb = self.look._expected_lookahead(hand, public, total_live, base)[0]
            ec = self.look._expected_lookahead(hand, public, total_live, chosen)[0]
            if eb is None or ec is None:
                continue
            self.assertGreaterEqual(ec - eb, SpeedLookahead.SWITCH_MARGIN - 1e-9)
            checked += 1
            if checked >= 4:
                break
        self.assertGreater(checked, 0, "no switched target row available for margin guard")

    def test_deadline_falls_back_to_parent(self):
        looked = 0
        for view in self.views:
            hand, e, g = _meta(view)
            if e or g or len(view.get("river") or []) < SpeedLookahead.LOOK_RIVER_MIN:
                continue
            old = self.look.LOOK_DEADLINE_MS
            try:
                self.look.LOOK_DEADLINE_MS = 1e-9
                self.assertEqual(self._pick(self.look, view), self._pick(self.stack, view))
            finally:
                self.look.LOOK_DEADLINE_MS = old
            looked += 1
            if looked >= 3:
                break
        self.assertGreater(looked, 0, "no target row for deadline fallback guard")

    def test_end_to_end_decide(self):
        n = 0
        for view in self.views[:200]:
            action = self.look.decide(view)
            self.assertIsInstance(action, dict)
            self.assertIn("action", action)
            n += 1
        self.assertGreater(n, 0)

    def test_s2_end_to_end_decide(self):
        p = SpeedLookahead2()
        n = 0
        for view in self.views[:100]:
            action = p.decide(view)
            self.assertIsInstance(action, dict)
            self.assertIn("action", action)
            n += 1
        self.assertGreater(n, 0)

    def test_both_end_to_end_decide(self):
        p = SpeedLookaheadBoth()
        n = 0
        for view in self.views[:100]:
            action = p.decide(view)
            self.assertIsInstance(action, dict)
            self.assertIn("action", action)
            n += 1
        self.assertGreater(n, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
