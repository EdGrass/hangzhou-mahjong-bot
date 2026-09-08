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
            with open(p, encoding="utf-8") as fh:
                lines = [json.loads(l) for l in fh]
            self.assertEqual([e["seq"] for e in lines], [1, 2])

    def test_same_seq_dedup_keeps_last(self):
        with tempfile.TemporaryDirectory() as td:
            rec = ReplayRecorder(td)
            # 同一 seq 事件重复投递（如缓冲复用/重掷），close 只应落最后一条
            rec.on_event("g9", {"type": "tile_discarded", "seat": 0,
                                "tile": "3b", "seq": 1})
            rec.on_event("g9", {"type": "tile_drawn", "seat": 1,
                                "seq": 2, "tile": None})
            rec.on_event("g9", {"type": "tile_discarded", "seat": 0,
                                "tile": "4b", "seq": 1})   # seq=1 重复（后到者应胜出）
            rec.close_game("g9")
            p = os.path.join(td, "g9.jsonl")
            with open(p, encoding="utf-8") as fh:
                lines = [json.loads(l) for l in fh]
            self.assertEqual([e["seq"] for e in lines], [1, 2])
            self.assertEqual(lines[0]["tile"], "4b")       # 保留同 seq 的最后一条

    def test_close_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            rec = ReplayRecorder(td)
            rec.on_event("g8", {"seq": 5, "type": "x"})
            rec.close_game("g8")
            rec.close_game("g8")   # 再次 close 无副作用、不追加
            p = os.path.join(td, "g8.jsonl")
            with open(p, encoding="utf-8") as fh:
                lines = [json.loads(l) for l in fh]
            self.assertEqual(len(lines), 1)

    def test_decisions_flush_to_separate_file(self):
        with tempfile.TemporaryDirectory() as td:
            rec = ReplayRecorder(td)
            rec.on_decision("g3", {"k": "d", "s": 0, "p": "draw", "a": "discard",
                                   "h": ["1w", "2w"], "sub": "ok"})
            rec.on_decision("g3", {"k": "d", "s": 0, "p": "response_peng",
                                   "a": "pass", "sub": "ok"})
            rec.close_game("g3")
            p = os.path.join(td, "g3.dec.jsonl")
            self.assertTrue(os.path.exists(p))
            with open(p, encoding="utf-8") as fh:
                lines = [json.loads(l) for l in fh]
            self.assertEqual([e["a"] for e in lines], ["discard", "pass"])
            # 无事件流 → 事件文件不生成（决策与事件双通道独立）
            self.assertFalse(os.path.exists(os.path.join(td, "g3.jsonl")))
            # 事件+决策并存时两文件都写
            rec2 = ReplayRecorder(td)
            rec2.on_event("g5", {"seq": 1, "type": "tile_discarded", "tile": "3b"})
            rec2.on_decision("g5", {"k": "d", "a": "pass", "sub": "ok"})
            rec2.close_game("g5")
            self.assertTrue(os.path.exists(os.path.join(td, "g5.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(td, "g5.dec.jsonl")))

    def test_decision_close_idempotent_no_dupes(self):
        with tempfile.TemporaryDirectory() as td:
            rec = ReplayRecorder(td)
            rec.on_decision("g4", {"k": "d", "a": "hu", "sub": "ok"})
            rec.close_game("g4")
            rec.close_game("g4")
            p = os.path.join(td, "g4.dec.jsonl")
            with open(p, encoding="utf-8") as fh:
                lines = [json.loads(l) for l in fh]
            self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
