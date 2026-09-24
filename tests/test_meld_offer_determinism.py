# -*- coding: utf-8 -*-
"""★ 2026-09-16 新增：`value_of_take` 的**确定性**回归测试（修 flaky 用）。

现象：全量单测 5 次里翻 1 次 `test_peng_returns_value_when_pair_present`。
根因：14 张手牌规整到 13 张时要"扔掉一张"，旧实现 `for t in set(h)` 的**迭代顺序随 PYTHONHASHSEED 变**，
并列最优时偶尔把**要碰的那张**扔掉 ⇒ 判"碰不了"返回 None。
修法：① 碰的可行性在**原始手牌**上判；② 所有 `set(h)` 迭代改 `sorted(set(h))`；③ 规整若丢了本牌，改用"保留本牌"的规整。
"""
import importlib.util
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("moa_det", os.path.join(ROOT, "tools", "meld_offer_audit.py"))
moa = importlib.util.module_from_spec(spec)
sys.modules["moa_det"] = moa
spec.loader.exec_module(moa)

H14 = ["1w", "1w", "3w", "4w", "5w", "6w", "7w", "9w", "9t", "东", "南", "西", "白", "9b"]
H14_CHI = ["1w", "2w", "5w", "5w", "6w", "7w", "9w", "9t", "东", "南", "西", "白", "9b", "8b"]


class TestValueOfTakeDeterminism(unittest.TestCase):
    def test_peng_on_14_tile_hand_never_returns_none(self):
        rnd = random.Random(0)
        for _ in range(200):
            h = list(H14)
            rnd.shuffle(h)
            v, n = moa.value_of_take(h, "1w", "peng", 0, 0)
            self.assertIsNotNone(v, "14 张手牌里有两张 1w ⇒ 碰必须可行（顺序无关）")
            self.assertEqual(n, 2)

    def test_chi_on_14_tile_hand_never_returns_none(self):
        rnd = random.Random(1)
        for _ in range(200):
            h = list(H14_CHI)
            rnd.shuffle(h)
            v, n = moa.value_of_take(h, "3w", "chi", 0, 0)
            self.assertIsNotNone(v)
            self.assertEqual(n, 2)
