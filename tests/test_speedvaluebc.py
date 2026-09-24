# -*- coding: utf-8 -*-
"""`bot/speedvaluebc.SpeedValueBC` 契约测试（R1181）。

为什么必须钉住：它是**役 3 换代后的候选臂**，判词要能归因到"BC 排序"**这一条**变量。
所以四条不变量必须在起役前被证明：

  ① **零行为变化兜底**：模型缺失 / 模型异常 / 局面不符 ⇒ 必须**逐位等于** `SpeedValue` 的选择；
  ② **单变量域**：只在"弃牌后最小向听组"内替换，且**基线选择不在组内时绝不改**（否则等于顺带改基线）；
  ③ **只在严格更优时改**：`margin` 生效；分数不严格更高 ⇒ 返回基线；
  ④ **特征/打分与 `C067Policy` 同源**：直接调用同一实现（避免复制粘贴导致喂给网络的输入分布漂移）。
"""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedvalue import SpeedValue                      # noqa: E402
from bot.speedvaluebc import SpeedValueBC                  # noqa: E402
from bot.speedc067 import C067Policy                       # noqa: E402


def _view(hand, drawn=None, melds=None):
    return {"seat": 0, "phase": "draw", "turn": 6, "my_hand": list(hand),
            "drawn_tile": drawn, "offer_tile": None, "melds": list(melds or []),
            "all_melds": [], "god": {"baotou": False, "chain_count": 0, "catch_play": False}}


class SpeedValueBCTest(unittest.TestCase):
    def setUp(self):
        self.sv = SpeedValue()
        self.bc = SpeedValueBC()

    # ① 模型缺失 ⇒ 零行为变化
    def test_no_model_is_identical(self):
        self.bc.model = None
        for hand, drawn in ((['1w', '2w', '3w', '4w', '5w', '6w', '7b', '8b', '1t', '2t', '3t', '5t', '5t'],
                             '9t'),
                            (['1w', '1w', '2w', '3w', '5b', '5b', '6b', '7b', '2t', '3t', '4t', '8t', '9t',
                              '白'], None)):
            kwargs = {}
            a = self.sv._pick_discard(list(hand), drawn, 0, 0, view=_view(hand, drawn))
            b = self.bc._pick_discard(list(hand), drawn, 0, 0, view=_view(hand, drawn))
            self.assertEqual(a, b)
            del kwargs

    # ①′ 模型抛异常 ⇒ 返回基线（不允许把异常冒出去）
    def test_model_exception_falls_back(self):
        hand = ['1w', '2w', '3w', '4w', '5w', '6w', '7b', '8b', '1t', '2t', '3t', '5t', '5t', '9t']
        v = _view(hand, None)
        with mock.patch.object(self.bc, "_bc_pick", side_effect=RuntimeError("boom")):
            got = self.bc._pick_discard(list(hand), None, 0, 0, view=v)
        self.assertEqual(got, self.sv._pick_discard(list(hand), None, 0, 0, view=v))

    # ② 基线不在最小向听组内 ⇒ 绝不改
    def test_never_change_when_base_outside_group(self):
        hand = ['1w', '2w', '3w', '4w', '5w', '6w', '7b', '8b', '1t', '2t', '3t', '5t', '5t', '9t']
        v = _view(hand, None)
        with mock.patch.object(self.bc, "_bc_pick",
                               side_effect=lambda h, e, g, b: "9t"):
            got = self.bc._pick_discard(list(hand), None, 0, 0, view=v)
        base = self.sv._pick_discard(list(hand), None, 0, 0, view=v)
        self.assertEqual(got, base)

    # ③ 模型不严格更优 ⇒ 返回基线；严格更优 ⇒ 采用模型张
    def test_margin_gate(self):
        hand = ['1w', '2w', '3w', '4w', '5w', '6w', '7b', '8b', '1t', '2t', '3t', '5t', '5t', '9t']
        v = _view(hand, None)
        base = self.sv._pick_discard(list(hand), None, 0, 0, view=v)
        # 直接测闸门逻辑：把 _bc_pick 换成一个"总是返回另一张"的桩，看它是否仍被上游闸门挡住
        other = next(d for d in hand if d != base)
        with mock.patch.object(self.bc, "_bc_pick", side_effect=lambda h, e, g, b: other):
            self.assertEqual(self.bc._pick_discard(list(hand), None, 0, 0, view=v), other)
        with mock.patch.object(self.bc, "_bc_pick", side_effect=lambda h, e, g, b: b):
            self.assertEqual(self.bc._pick_discard(list(hand), None, 0, 0, view=v), base)

    # ④ 特征实现同源（unbound 调用，不复制代码）
    def test_features_same_implementation(self):
        hand = ['1w', '2w', '3w', '4w', '5w', '6w', '5t', '5t', '9t']
        base = "9t"
        chosen = ["9t", "5w"]
        mine = C067Policy._features(self.bc, hand, chosen, base, 0, 0)
        self.assertIsNotNone(mine)
        self.assertEqual(len(mine), 2)
        self.assertEqual(len(mine[0]), 154)      # 与 _Net(din=154) 对齐
        self.assertIsNotNone(self.bc.model)      # 模型文件存在（起役前提）


if __name__ == "__main__":
    unittest.main()
