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
    def test_game_ids_prefers_my_games_and_ignores_batch(self):
        # \u2605 R1396\uff08\u56db\u6d4b\u771f\u6570\u636e\uff09\uff1a`my_games_by_batch` \u91cc\u542b**\u540c\u6279\u6b21\u522b\u4eba\u7684\u5bf9\u5c40**\uff0c
        #   \u62c9\u5b83\u4eec\u5168\u90e8 403 not-a-participant\uff08\u4e14\u62c9\u9ad8 429 \u98ce\u9669\uff09\u21d2 \u53ea\u8981 `my_games` \u80fd\u62ff\u5230 gid\uff0c
        #   **\u5c31\u4e0d\u770b batch**\u3002\uff08\u672c\u6d4b\u8bd5\u65e7\u7248\u672c\u671f\u671b\u5408\u5e76\u4e24\u8005\uff0c\u662f R1396 \u4e4b\u524d\u7684\u8bed\u4e49\uff09
        detail = {
            "my_games": [{"game_id": "g1"}, {"game_id": "g2"}, {"game_id": "g1"}],
            "my_games_by_batch": {"b1": [{"game_id": "g3"}], "b2": {"game_id": "g4"}},
        }
        self.assertEqual(ftr.game_ids_from_detail(detail), ["g1", "g2"])

    def test_game_ids_batch_fallback_when_my_games_empty(self):
        # \u540c\u4e0a\u7684\u5411\u540e\u517c\u5bb9\u5206\u652f\uff1a**\u4e00\u6761 gid \u90fd\u62ff\u4e0d\u5230**\u65f6\u624d\u56de\u9000 batch\uff0c
        #   \u4e14\u8981\u540c\u65f6\u5904\u7406 list \u503c\u4e0e dict \u503c\u4e24\u79cd\u5f62\u6001\u3002
        detail = {"my_games": [], "my_games_by_batch": {"b1": [{"game_id": "g3"}], "b2": {"game_id": "g4"}}}
        self.assertEqual(ftr.game_ids_from_detail(detail), ["g3", "g4"])

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
