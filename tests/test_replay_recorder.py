"""replay 记录器测试：按 gid 累积事件 → 落盘 JSON 行。"""
import json
import os
import tempfile
import unittest

from bot.replay_rec import ReplayRecorder


class TestReplayRecorder(unittest.TestCase):
    def test_accumulates_and_dumps(self):
        with tempfile.TemporaryDirectory() as td:
            rec = ReplayRecorder(td)
            rec.on_event("g1", {"type": "tile_discarded", "seat": 0,
                                "tile": "3b", "seq": 1})
            rec.on_event("g1", {"type": "tile_drawn", "seat": 1,
                                "seq": 2, "tile": None})
            rec.close_game("g1")
            p = os.path.join(td, "g1.jsonl")
            self.assertTrue(os.path.exists(p))
            lines = [json.loads(l) for l in open(p, encoding="utf-8")]
            self.assertEqual([e["seq"] for e in lines], [1, 2])


if __name__ == "__main__":
    unittest.main()
