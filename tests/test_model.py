"""牌码工具与快照解析的单测（纯函数，无网络）。"""
import unittest

from bot.model import (GOD_TILE, VALID_TILES, hand_without, is_valid_tile,
                       snap_view, validate_hand, window_pending, my_turn,
                       sort_key, tile_kind)


class TestTiles(unittest.TestCase):
    def test_valid_codes(self):
        for t in ["1w", "9w", "1b", "9b", "1t", "9t", "东", "南", "西", "北",
                  "中", "发", "白"]:
            self.assertTrue(is_valid_tile(t), t)
        self.assertEqual(len(VALID_TILES), 34)  # 27 数牌 + 7 字牌

    def test_invalid_codes(self):
        for t in ["0w", "10w", "w1", "1", "w", "", "白板", "春", "梅"]:
            self.assertFalse(is_valid_tile(t), t)

    def test_god_tile(self):
        self.assertEqual(GOD_TILE, "白")

    def test_validate_hand(self):
        h = ["1w"] * 13
        self.assertEqual(validate_hand(h, 13), h)
        with self.assertRaises(ValueError):
            validate_hand(["1w"] * 12, 13)   # 张数不符
        with self.assertRaises(ValueError):
            validate_hand(["1w"] * 12 + ["X"], 13)  # 非法牌码
        with self.assertRaises(ValueError):
            validate_hand("1w")              # 非列表

    def test_hand_without(self):
        h = ["1w", "1w", "2w", "东"]
        self.assertEqual(hand_without(h, ["1w"]), ["1w", "2w", "东"])
        with self.assertRaises(ValueError):
            hand_without(h, ["白"])          # 手牌里没有

    def test_tile_kind_sort(self):
        self.assertEqual(tile_kind("3w"), ("w", 3))
        self.assertEqual(tile_kind("白"), ("honor", 6))
        self.assertEqual(tile_kind("东"), ("honor", 0))
        with self.assertRaises(ValueError):
            tile_kind("0w")
        # 排序：数牌在字牌前，同花色按点数
        seq = sorted(["中", "1b", "9w", "2w", "白", "东"], key=sort_key)
        self.assertEqual(seq, ["2w", "9w", "1b", "东", "中", "白"])


class TestSnapshotView(unittest.TestCase):
    def test_view_defaults(self):
        v = snap_view({})
        self.assertEqual(v["seat"], -1)
        self.assertEqual(v["phase"], "")
        self.assertEqual(v["responding_seats"], [])
        self.assertEqual(v["drawn_tile"], None)
        self.assertEqual(v["god"]["catch_play"], False)
        self.assertEqual(v["god"]["chain_count"], 0)

    def test_view_fields(self):
        snap = {
            "seat": 2, "phase": "draw", "turn": 2,
            "responding_seats": [0, 1], "drawn_tile": "5w",
            "my_hand": ["1w", "5w"],
            "god": {"baotou": True, "chain_count": 2, "catch_play": True},
        }
        v = snap_view(snap)
        self.assertTrue(v["god"]["baotou"])
        self.assertEqual(v["god"]["chain_count"], 2)
        self.assertEqual(v["my_hand"], ["1w", "5w"])
        # seat=2 不在 responding_seats 里 → 无窗口权
        self.assertFalse(window_pending(v))

    def test_window_pending(self):
        base = {"seat": 0, "responding_seats": [0, 2], "turn": 1, "drawn_tile": "3w",
                "my_hand": ["1w"], "god": {}}
        self.assertTrue(window_pending(snap_view(dict(base, phase="response_peng"))))
        self.assertTrue(window_pending(snap_view(dict(base, phase="response_chi"))))
        self.assertFalse(window_pending(snap_view(dict(base, phase="draw"))))
        self.assertFalse(window_pending(snap_view(dict(base, phase="response_peng",
                                                      responding_seats=[2]))))
        self.assertFalse(window_pending(snap_view(dict(base, phase="response_peng", seat=-1))))

    def test_my_turn(self):
        base = {"seat": 0, "responding_seats": [], "drawn_tile": None,
                "my_hand": ["1w"], "god": {}}
        self.assertTrue(my_turn(snap_view(dict(base, phase="draw", turn=0))))
        self.assertFalse(my_turn(snap_view(dict(base, phase="draw", turn=1))))
        self.assertFalse(my_turn(snap_view(dict(base, phase="deal", turn=0))))
        self.assertFalse(my_turn(snap_view(dict(base, phase="draw", seat=-1))))


if __name__ == "__main__":
    unittest.main()
