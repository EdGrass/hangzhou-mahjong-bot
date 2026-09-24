# -*- coding: utf-8 -*-
"""Guards for SpeedStack: composition must stay bounded and must fire."""
from __future__ import annotations

import glob
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from arm_smoke import to_view
from bot.speedgangfix import SpeedGangFixLate
from bot.speedstack import SpeedStack
from bot.speed import _chi_pairs
from bot.speedc136 import _after_best
from bot.ukeire import visible_counts
from mahjong.fan import calc as calc_fan
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as SH


def _rows(path, limit):
    out = []
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            out.append(row)
            if len(out) >= limit:
                break
    return out


def _geom(view, tile, gang_aware=False):
    hand = list(view.get("my_hand") or [])
    melds = view.get("melds") or []
    exposed = len(melds)
    gangs = sum(1 for m in melds
                if isinstance(m, dict) and m.get("type") == "gang")
    if tile not in hand:
        return (99, -1, -1)
    rem = list(hand)
    rem.remove(tile)
    try:
        if gang_aware and gangs:
            if len(rem) != 13 - 3 * exposed:
                return (99, -1, -1)
            s = SH(rem, qidui=(exposed == 0), exposed_melds=exposed, gangs=0)
        else:
            if len(rem) != 13 - 3 * exposed - gangs:
                return (99, -1, -1)
            s = SH(rem, qidui=(exposed == 0 and gangs == 0),
                   exposed_melds=exposed, gangs=gangs)
    except Exception:
        return (99, -1, -1)
    if s != 0:
        return (s, -1, -1)
    vis = visible_counts(hand, river=view.get("river"),
                         all_melds=view.get("all_melds"))
    try:
        if gang_aware and gangs:
            ws = waits(rem, exposed_melds=exposed, gangs=0)
        else:
            ws = waits(rem, exposed_melds=exposed, gangs=gangs)
    except Exception:
        return (99, -1, -1)
    live = sum(max(0, 4 - int(vis.get(t, 0))) for t in ws)
    god = view.get("god") or {}
    chain = {"count": int(god.get("chain_count") or 0),
             "piao": int(god.get("piao_count") or 0)}
    best_fan = None
    for wt in ws:
        try:
            result = calc_fan(list(rem), wt, chain, base=1,
                              exposed_melds=exposed,
                              gangs=(0 if (gang_aware and gangs) else gangs))
        except Exception:
            continue
        if result.get("hu"):
            fan = result.get("fan") or 0
            if best_fan is None or fan > best_fan:
                best_fan = fan
    return (0, live, best_fan if best_fan is not None else -1)


def _chi_first_pass(policy, view):
    hand = list(view.get("my_hand") or [])
    offer = view.get("offer_tile")
    if not offer:
        return None
    for pair in _chi_pairs(hand, offer):
        try:
            if policy._want_claim(view, "chi", pair):
                return tuple(pair)
        except Exception:
            return None
    return None


def _chi_key(view, pair):
    if pair is None:
        return None
    hand = list(view.get("my_hand") or [])
    melds = view.get("melds") or []
    exposed = len(melds)
    gangs = sum(1 for m in melds
                if isinstance(m, dict) and m.get("type") == "gang")
    normalized_gangs = 0
    vis = visible_counts(hand, river=view.get("river"),
                         all_melds=view.get("all_melds"))
    after = _after_best(hand, view.get("offer_tile"), "chi", pair,
                        exposed, normalized_gangs, vis, True)
    if after is None:
        return (99, 0.0)
    return (after[0], -(after[1] or 0.0))


class TestSpeedStack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = SpeedGangFixLate()
        cls.stack = SpeedStack()
        cls.draw_rows = [r for r in _rows(os.path.join(ROOT, "var", "smoke_corpus_v1.jsonl"), 6000)
                         if r.get("p") == "draw"]
        cls.gang_rows = [r for r in _rows(os.path.join(ROOT, "var", "smoke_corpus_gang_v1.jsonl"), 2500)
                         if r.get("p") == "draw"]

    def test_identity(self):
        self.assertTrue(issubclass(SpeedStack, SpeedGangFixLate))
        self.assertEqual(SpeedStack().name, "speedstack")

    def test_non_gang_only_changes_tenpai_choices(self):
        checked = 0
        changed = 0
        worse = 0
        for row in self.draw_rows[:1800]:
            view = to_view(row)
            hand = list(view.get("my_hand") or [])
            melds = view.get("melds") or []
            exposed = len(melds)
            gangs = sum(1 for m in melds
                        if isinstance(m, dict) and m.get("type") == "gang")
            if gangs or len(hand) != 14 - 3 * exposed:
                continue
            a = self.base._pick_discard(list(hand), view.get("drawn_tile"),
                                        exposed, gangs, view=view)
            b = self.stack._pick_discard(list(hand), view.get("drawn_tile"),
                                         exposed, gangs, view=view)
            if a not in hand or b not in hand:
                continue
            checked += 1
            ga = _geom(view, a)
            gb = _geom(view, b)
            if ga[0] != 0 and a != b:
                worse += 1
            if ga[0] == gb[0] == 0:
                if gb[1] < ga[1]:
                    worse += 1
                if ga[2] >= 0 and gb[2] >= 0 and gb[2] < ga[2]:
                    worse += 1
            if a != b:
                changed += 1
        self.assertGreater(checked, 100, "fixed draw corpus coverage too small")
        self.assertEqual(worse, 0, "stack must not worsen shanten/live-waits/fan")
        self.assertGreater(changed, 0, "tenpai-live component must fire on corpus")

    def test_gang_rows_do_not_throw_and_preserve_shanten(self):
        checked = 0
        broken = 0
        errors = 0
        for row in self.gang_rows[:600]:
            view = to_view(row)
            hand = list(view.get("my_hand") or [])
            melds = view.get("melds") or []
            exposed = len(melds)
            gangs = sum(1 for m in melds
                        if isinstance(m, dict) and m.get("type") == "gang")
            if not gangs or len(hand) != 14 - 3 * exposed:
                continue
            try:
                tile = self.stack._pick_discard(list(hand), view.get("drawn_tile"),
                                                exposed, gangs, view=view)
            except Exception:
                errors += 1
                continue
            if tile not in hand:
                broken += 1
                continue
            best = None
            for d in sorted(set(hand)):
                s = _geom(view, d, gang_aware=True)[0]
                if s < 99:
                    best = s if best is None else min(best, s)
            got = _geom(view, tile, gang_aware=True)[0]
            if best is not None and got != best:
                broken += 1
            checked += 1
        self.assertGreater(checked, 20, "gang corpus coverage too small")
        self.assertEqual(errors, 0)
        self.assertEqual(broken, 0, "gang-aware discard must preserve shanten")

    def test_chi_selection_never_worse_and_never_flips_decision(self):
        windows = []
        for row in _rows(os.path.join(ROOT, "var", "smoke_corpus_v1.jsonl"), 6000):
            if row.get("p") != "response_chi" or not row.get("o"):
                continue
            view = to_view(row)
            hand = list(view.get("my_hand") or [])
            if _chi_pairs(hand, view.get("offer_tile")):
                windows.append(view)
        self.assertGreater(len(windows), 20, "chi corpus coverage too small")
        changed = 0
        flips = 0
        worse = 0
        for view in windows[:600]:
            pa = _chi_first_pass(self.base, view)
            pb = _chi_first_pass(self.stack, view)
            if (pa is None) != (pb is None):
                flips += 1
            ka, kb = _chi_key(view, pa), _chi_key(view, pb)
            if ka is not None and kb is not None and kb > ka:
                worse += 1
            if pa != pb:
                changed += 1
        self.assertEqual(flips, 0)
        self.assertEqual(worse, 0)
        self.assertGreater(changed, 0, "chi selector must fire on real windows")

    def test_end_to_end_decide_has_no_exceptions(self):
        for path, limit in (("smoke_corpus_v1.jsonl", 250),
                            ("smoke_corpus_gang_v1.jsonl", 250)):
            n = 0
            for row in _rows(os.path.join(ROOT, "var", path), limit):
                view = to_view(row)
                try:
                    action = self.stack.decide(view)
                except Exception as exc:
                    self.fail("%s raised on row %d: %r" % (path, n, exc))
                self.assertIsInstance(action, dict)
                self.assertIn("action", action)
                n += 1
            self.assertGreater(n, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
