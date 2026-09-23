# -*- coding: utf-8 -*-
"""Unit tests for the hybrid /state sufficiency predicate."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from bot.faststate import snapshot_covers      # noqa: E402


def snap(**kw):
    base = {"phase": "draw", "seat": 0, "turn": 0, "my_hand": ["1w"], "melds": []}
    base.update(kw)
    return base


class TestFastStateCovers(unittest.TestCase):
    def test_none(self):
        self.assertFalse(snapshot_covers(None)[0])

    def test_draw_needs_drawn_tile_when_our_turn(self):
        ok, why = snapshot_covers(snap(drawn_tile=None))
        self.assertFalse(ok)
        self.assertEqual(why, "draw_needs_drawn_tile")
        self.assertTrue(snapshot_covers(snap(drawn_tile="5w"))[0])
        # not our turn -> no drawn_tile needed
        self.assertTrue(snapshot_covers(snap(turn=2, drawn_tile=None))[0])

    def test_draw_needs_hand_and_melds(self):
        self.assertEqual(snapshot_covers(snap(my_hand=None))[1], "missing_my_hand")
        self.assertEqual(snapshot_covers(snap(melds=None))[1], "missing_melds")

    def test_response_requirements(self):
        base = snap(phase="response_peng", offer_tile="3b", responding_seats=[0, 1])
        self.assertTrue(snapshot_covers(base)[0])
        self.assertEqual(snapshot_covers(dict(base, offer_tile=None))[1],
                         "response_needs_offer_tile")
        self.assertEqual(snapshot_covers(dict(base, responding_seats=None))[1],
                         "response_needs_responding_seats")
        self.assertEqual(snapshot_covers(dict(base, responding_seats=[1, 2]))[1],
                         "response_seat_not_listed")
        self.assertTrue(snapshot_covers(dict(base, phase="response_chi"))[0])

    def test_terminal_phases(self):
        for ph in ("finished", "settled", "closed", "void"):
            ok, why = snapshot_covers({"phase": ph})
            self.assertTrue(ok, ph)
            self.assertEqual(why, "terminal")


    def test_response_accepts_last_discard(self):
        """快照不带 offer_tile，窗口牌面在 last_discard —— hybrid 必须认它。"""
        ok, why = snapshot_covers({
            "phase": "response_peng", "my_hand": ["1w"] * 13, "melds": [[], [], [], []],
            "seat": 2, "turn": 1, "responding_seats": [2], "last_discard": "5w",
        })
        self.assertTrue(ok, why)

    def test_response_still_needs_responding_seat(self):
        ok, why = snapshot_covers({
            "phase": "response_peng", "my_hand": ["1w"] * 13, "melds": [[], [], [], []],
            "seat": 2, "turn": 1, "responding_seats": [0], "last_discard": "5w",
        })
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
