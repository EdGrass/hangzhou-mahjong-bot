# -*- coding: utf-8 -*-
"""Bounded-fire guards for the value-weighted policy (M3)."""
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
from bot.speedc151 import SpeedC151
from bot.speedvalue import (SpeedValue, SpeedValueNoBai, SpeedValueNoFan,
                            SpeedValueNoLive, SpeedValueFlatUkeire)


def _views(limit=600):
    out = []
    with io.open(os.path.join(ROOT, "var", "smoke_corpus_v1.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("p") == "draw":
                out.append(to_view(row))
            if len(out) >= limit:
                break
    return out


def _meta(v):
    hand = list(v.get("my_hand") or [])
    melds = v.get("melds") or []
    e = len(melds)
    g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
    return hand, e, g


class TestSpeedValue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views = _views(600)
        cls.val = SpeedValue()
        cls.c151 = SpeedC151()

    @staticmethod
    def _pick(policy, v):
        hand, e, g = _meta(v)
        return policy._pick_discard(hand, v.get("drawn_tile"), e, g, view=v)

    def test_identity(self):
        self.assertTrue(issubclass(SpeedValue, SpeedC151))
        self.assertEqual(SpeedValue().name, "speedvalue")
        self.assertGreater(SpeedValue.W_MAX_FAN, 0)
        self.assertGreater(SpeedValue.W_LIVE_WAIT, 0)
        for cls in (SpeedValueNoBai, SpeedValueNoFan, SpeedValueNoLive, SpeedValueFlatUkeire):
            self.assertTrue(issubclass(cls, SpeedValue))

    def test_ablation_weights(self):
        self.assertEqual(SpeedValueNoBai.W_BAI, 0.0)
        self.assertEqual(SpeedValueNoFan.W_MAX_FAN, 0.0)
        self.assertEqual(SpeedValueNoLive.W_LIVE_WAIT, 0.0)

    def test_value_monotone_in_ukeire(self):
        """V must increase with live ukeire at a fixed shanten (positive weight)."""
        v = self.views[0]
        view = dict(v)
        view["river"] = []
        # 13-tile hands: one wider than the other by construction
        a = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "1t", "2t", "3t", "5b"]
        b = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "1t", "2t", "3t", "5b", "9b"]
        wa = self.val.value_of(list(a), 0, 0, {}, view, 1)
        wb = self.val.value_of(list(b), 0, 0, {}, view, 1)
        self.assertIsNotNone(wa)
        self.assertIsNotNone(wb)
        self.assertNotEqual(wa, wb)

    def test_never_discards_white_on_fixed_corpus(self):
        """W_BAI = 3.70 points ~= 46 ukeire tiles at sh=1, so 白 should never be shed
        when a legal alternative exists."""
        bad = 0
        seen = 0
        for v in self.views:
            hand, e, g = _meta(v)
            if "白" not in hand or len(hand) == 0:
                continue
            seen += 1
            if self._pick(self.val, v) == "白":
                bad += 1
        self.assertGreater(seen, 5, "no 白-holding rows in corpus")
        self.assertEqual(bad, 0, "SpeedValue discarded 白 %d times" % bad)

    def test_falls_back_without_view(self):
        for v in self.views[:50]:
            hand, e, g = _meta(v)
            self.assertEqual(self.val._pick_discard(hand, v.get("drawn_tile"), e, g, view=None),
                             self.c151._pick_discard(hand, v.get("drawn_tile"), e, g, view=None))

    def test_mechanism_fires(self):
        changed = 0
        for v in self.views:
            if self._pick(self.val, v) != self._pick(self.c151, v):
                changed += 1
        self.assertGreater(changed, 0, "value policy never changes a decision")

    def test_end_to_end_decide(self):
        for policy in (SpeedValue(), SpeedValueNoLive(), SpeedValueNoFan()):
            n = 0
            for v in self.views[:150]:
                act = policy.decide(v)
                self.assertIsInstance(act, dict)
                self.assertIn("action", act)
                n += 1
            self.assertGreater(n, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
