"""ml/features 与样本生成器的单测。"""
import json
import os
import tempfile
import unittest

from ml.features import ACTION_HU, encode, feature_row, label_of, legal_mask
from ml.gen_data import gen
from mahjong.sim import make_view

W = "白"


def _view(hand14, drawn, god=None, melds=None):
    return make_view(0, "draw", 0, hand14, drawn=drawn, melds=melds or [],
                     god=god or {})


class TestEncode(unittest.TestCase):
    def test_shape_and_roundtrip(self):
        hand = ["1w", "1w", "2b", "3t", "白"] + ["4w", "5w", "6w"] * 3
        hand = (hand * 2)[:14]
        v = _view(hand, "5w")
        f = encode(v)
        self.assertEqual(len(f["hand_counts"]), 34)
        self.assertEqual(len(f["melds"]), 3)
        self.assertEqual(len(f["god"]), 4)
        self.assertEqual(len(f["drawn"]), 34)
        # 计数一致性：手牌总和 == counts 和
        self.assertEqual(sum(f["hand_counts"]), len(hand))
        # drawn 位图有且仅有一位
        self.assertEqual(sum(f["drawn"]), 1)

    def test_label_and_mask(self):
        hand = ["1w", "1w", "2b", "3t", W] + ["4w", "5w", "6w"] * 3
        hand = (hand * 2)[:14]
        counts = encode(_view(hand, "5w"))["hand_counts"]
        m = legal_mask(counts)
        self.assertEqual(len(m), 35)
        # 手上有 1w → 1w 位可弃
        from mahjong.tiles import id_of
        self.assertEqual(m[id_of("1w")], 1)
        self.assertEqual(m[id_of("9w")], 0)   # 无 9w
        # 标签：弃 1w / hu
        self.assertEqual(label_of({"action": "discard", "tile": "1w"}, counts),
                         id_of("1w"))
        self.assertEqual(label_of({"action": "hu"}, counts), ACTION_HU)
        # 弃不在手中的牌 → None
        self.assertIsNone(label_of({"action": "discard", "tile": "9w"}, counts))
        self.assertIsNone(label_of({"action": "pass", "tile": ""}, counts))


class TestGenerator(unittest.TestCase):
    def test_gen_rows_valid(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "s.jsonl")
            n = gen(games=4, rounds=2, seed0=7, out_path=out)
            self.assertGreater(n, 10)
            with open(out, encoding="utf-8") as f:
                rows = [json.loads(l) for l in f if l.strip()]
            self.assertEqual(len(rows), n)
            from mahjong.tiles import id_of
            for r in rows:
                self.assertEqual(len(r["hand_counts"]), 34)
                self.assertIn(r["seat"], (0, 1, 2, 3))
                act = r["action"]
                if act == ACTION_HU:
                    self.assertEqual(r["hu_ok"], 1, "hu 标签必须 hu_ok")
                else:
                    self.assertGreater(r["hand_counts"][act], 0,
                                       "弃牌标签必须在手牌中")

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            o1 = os.path.join(td, "a.jsonl")
            o2 = os.path.join(td, "b.jsonl")
            gen(games=2, rounds=2, seed0=3, out_path=o1)
            gen(games=2, rounds=2, seed0=3, out_path=o2)
            with open(o1, encoding="utf-8") as f:
                a = f.read()
            with open(o2, encoding="utf-8") as f:
                b = f.read()
            self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
