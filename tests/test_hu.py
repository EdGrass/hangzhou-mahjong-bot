"""mahjong/hu 胡牌判定的单测（TDD：先写期望行为）。

口径说明（接入指南 §1.2，细节以 fan-calc 对齐为准）：
- 白板 = 财神（百搭），可替代任意牌补面子/补对（本阶段先实现通配语义，
  与服务器在特殊边界（纯财神面子等）的口径差异留待 fan-calc 对齐用例收敛）；
- 普通胡 = 4 组面子 + 1 对将；七对 = 7 个对子（财神可补对）；
- v1 仅判定 3n+2 张纯手牌（无副露参数，副露场景后续版本）。
"""
import unittest

from mahjong.hu import is_win

W = "白"  # 财神


class TestStandardWin(unittest.TestCase):
    def test_basic_win(self):
        # 123w 456w 789w + 11b 对 + 东东东 刻
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "1b", "1b", "东", "东", "东"]
        self.assertTrue(is_win(hand))

    def test_not_win_single_honors(self):
        # 三顺 + 两单张字 → 无将/面子不齐
        hand = ["1w", "2w", "3w", "4b", "5b", "6b", "7t", "8t", "9t",
                "东", "南", "北", "中", "发"]
        self.assertFalse(is_win(hand))

    def test_win_all_kongs_shape(self):
        # 4 刻 + 将（杠未实际杠出，仅手牌结构）
        hand = ["1w"] * 3 + ["2b"] * 3 + ["3t"] * 3 + ["4w"] * 3 + ["5t"] * 2
        self.assertTrue(is_win(hand))

    def test_all_sequences_win(self):
        # 4 顺 + 将对
        hand = ["1w", "2w", "3w", "2w", "3w", "4w", "1b", "2b", "3b",
                "1t", "2t", "3t", "5w", "5w"]
        self.assertTrue(is_win(hand))

    def test_14_tiles_with_leftover_singles_not_win(self):
        # 3 面子 + 1 对 + 3 张散牌 → 张数够但不成形
        hand = ["1w", "2w", "3w", "4b", "5b", "6b", "1t", "2t", "3t",
                "东", "东", "南", "北", "中"]
        self.assertFalse(is_win(hand))


class TestJokerSubstitution(unittest.TestCase):
    def test_joker_completes_run(self):
        # 白 代替 6w 组成 456w；其余 3 面子 + 将对
        hand = ["4w", "5w", W,
                "1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t",
                "东", "东"]
        self.assertTrue(is_win(hand))

    def test_joker_completes_triplet(self):
        # 白 代替第三张 2b
        hand = ["2b", "2b", W, "1w", "2w", "3w", "4w", "5w", "6w",
                "7w", "8w", "9w", "东", "东"]
        self.assertTrue(is_win(hand))

    def test_joker_completes_pair(self):
        # 三组顺 + 白补 东 成将（财神可补对）
        hand = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "1b", "2b", "3b", "东", W]
        self.assertTrue(is_win(hand))


class TestQidui(unittest.TestCase):
    def test_pure_qidui_win(self):
        # 6 真对 + 1 单张 + 财神补对 → 七对
        hand = ["1w", "1w", "2w", "2w", "3b", "3b", "4t", "4t",
                "5t", "5t", "东", "东", "南", W]
        self.assertTrue(is_win(hand))

    def test_six_pairs_two_singles_no_joker_not_win(self):
        # 6 对 + 2 单张（无财神）→ 既非七对也非标准形
        hand = ["1w", "1w", "2w", "2w", "3b", "3b", "4t", "4t",
                "5t", "5t", "东", "东", "南", "北"]
        self.assertFalse(is_win(hand))

    def test_qidui_with_four_of_kind(self):
        # 4 张 1w（豪华七对基础）+ 4 真对 + 单张 + 财神补对
        hand = ["1w"] * 4 + ["2w", "2w", "3b", "3b", "4t", "4t",
                "5t", "5t", "东", W]
        self.assertTrue(is_win(hand))

    def test_standard_shape_win_ok(self):
        # 4 刻 + 将：标准形成立即胡（不作为七对判定的反例用途）
        hand = ["1w"] * 3 + ["2w"] * 3 + ["3b"] * 3 + ["4t"] * 3 + ["东"] * 2
        self.assertTrue(is_win(hand))


class TestInputValidation(unittest.TestCase):
    def test_bad_length_raises(self):
        with self.assertRaises(ValueError):
            is_win(["1w"] * 13)            # 摸牌前 13 张不可直接判胡
        with self.assertRaises(ValueError):
            is_win(["1w"] * 15)
        with self.assertRaises(ValueError):
            is_win([])                     # 0 张不符合 3n+2

    def test_bad_tile_raises(self):
        with self.assertRaises(ValueError):
            is_win(["1w"] * 13 + ["X"])


if __name__ == "__main__":
    unittest.main()
