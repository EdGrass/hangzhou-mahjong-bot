# -*- coding: utf-8 -*-
"""R1092: 只有"可能该我行动"的事件批才需要全量快照。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from bot.game import _needs_snapshot


class TestNeedsSnapshot(unittest.TestCase):
    def test_pass_and_timeout_do_not_need_snapshot(self):
        self.assertFalse(_needs_snapshot([{"type": "pass"}, {"type": "timeout"}]))
        self.assertFalse(_needs_snapshot([]))

    def test_other_draw_does_not_need_snapshot(self):
        self.assertFalse(_needs_snapshot([{"type": "tile_drawn", "seat": 1, "tile": ""}]))

    def test_my_draw_needs_snapshot(self):
        self.assertTrue(_needs_snapshot([{"type": "tile_drawn", "seat": 2, "tile": "5w"}]))

    def test_discard_needs_snapshot(self):
        self.assertTrue(_needs_snapshot([{"type": "tile_discarded", "tile": "3b"}]))

    def test_claims_and_round_end_need_snapshot(self):
        for t in ("peng", "chi", "gang", "round_ended", "finished"):
            self.assertTrue(_needs_snapshot([{"type": t}]))

    def test_mixed_batch(self):
        self.assertTrue(_needs_snapshot([{"type": "pass"}, {"type": "tile_discarded", "tile": "9t"}]))

    # ---- R1098: 本地窗口预判（用缓存手牌决定是否真的需要快照）----
    def test_any_discard_needs_snapshot(self):
        """R1113：**任何**弃牌都要快照——服务端可能稍后才登记响应者名单，
        靠后续批次"再看一眼"才能捕获延迟登记的吃/碰窗口（跳过快照实测吃实现 -50%）。"""
        hand = ["1w"] * 13
        self.assertTrue(_needs_snapshot(
            [{"type": "tile_discarded", "seat": 1, "tile": "9t"}], hand, 0))

    def test_discard_with_peng_素材_needs_snapshot(self):
        hand = ["9t", "9t"] + ["1w"] * 11
        self.assertTrue(_needs_snapshot(
            [{"type": "tile_discarded", "seat": 1, "tile": "9t"}], hand, 0))

    def test_discard_with_chi_素材_needs_snapshot_from_upstream(self):
        # seat 0 的上家是 seat 3：(0-3)%4 == 1
        hand = ["3w", "4w"] + ["1t"] * 11
        self.assertTrue(_needs_snapshot(
            [{"type": "tile_discarded", "seat": 3, "tile": "2w"}], hand, 0))

    def test_discard_from_non_upstream_still_needs_snapshot(self):
        hand = ["3w", "4w"] + ["1t"] * 11
        self.assertTrue(_needs_snapshot(
            [{"type": "tile_discarded", "seat": 1, "tile": "2w"}], hand, 0))

    def test_no_cached_hand_stays_conservative(self):
        self.assertTrue(_needs_snapshot(
            [{"type": "tile_discarded", "seat": 1, "tile": "9t"}], None, 0))

    def test_god_tile_in_hand_stays_conservative(self):
        """手上有白（财神可能作万能）⇒ 不本地跳过。"""
        hand = ["白"] + ["1w"] * 12
        self.assertTrue(_needs_snapshot(
            [{"type": "tile_discarded", "seat": 1, "tile": "9t"}], hand, 0))

    def test_offered_god_tile_stays_conservative(self):
        hand = ["1w"] * 13
        self.assertTrue(_needs_snapshot(
            [{"type": "tile_discarded", "seat": 1, "tile": "白"}], hand, 0))


if __name__ == "__main__":
    unittest.main()
