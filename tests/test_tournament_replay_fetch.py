# -*- coding: utf-8 -*-
"""锦标赛复盘补拉工具的纯函数单测（2026-09-17）。

背景（STATUS §9.40/§9.41）：赛后审计 `real_game_audit --dirs official_*` 读不了本地录制格式
⇒ 需要从门户按**锦标赛 id** 补拉门户格式复盘。本测试只覆盖**从锦标赛详情里抽 gid/room** 的纯逻辑
（网络部分不测，实测记录见 §9.41）。
"""
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import importlib.util

spec = importlib.util.spec_from_file_location(
    "ftr", os.path.join(ROOT, "tools", "fetch_tournament_replays.py"))
ftr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ftr)


class TestExtractIds(unittest.TestCase):
    def test_game_ids_flat_and_batched(self):
        detail = {
            "my_games": [{"game_id": "g1"}, {"game_id": "g2"}, {"game_id": "g1"}],
            "my_games_by_batch": {"b1": [{"game_id": "g3"}], "b2": {"game_id": "g4"}},
        }
        self.assertEqual(ftr.game_ids_from_detail(detail), ["g1", "g2", "g3", "g4"])

    def test_game_ids_tolerant_aliases(self):
        detail = {"my_games": [{"gid": "x1"}, {"id": "x2"}, {"game_id": ""}]}
        self.assertEqual(ftr.game_ids_from_detail(detail), ["x1", "x2"])

    def test_room_ids_for_fallback(self):
        detail = {"my_games": [{"room_id": "a_1"}, {"room": "a_2"}, {"room_id": "a_1"}]}
        self.assertEqual(ftr.room_ids_from_detail(detail), ["a_1", "a_2"])

    def test_empty_detail_is_safe(self):
        self.assertEqual(ftr.game_ids_from_detail({}), [])
        self.assertEqual(ftr.room_ids_from_detail({}), [])
        self.assertEqual(ftr.game_ids_from_detail({"my_games": None}), [])


if __name__ == "__main__":
    unittest.main()
