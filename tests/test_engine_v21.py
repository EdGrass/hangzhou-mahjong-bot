"""引擎 v21 口径回归（2026-09-07 服务器规则修订，2026-09-08 fan-calc 实测锚定）。

覆盖两条 v21 修订 + 关联链/飘叠加：
① 正好 4 张白板听任意 = 爆头（撤销旧"4 白不视为爆头"裁；hu.is_baotou）；
② 七对豪华组：白×4 仅当其余实体牌无落单（白板两两自配）时计 1 组四张，
   白板消耗于补配单张时不再计豪华（fan._qidui_groups）。
全部期望值来自 2026-09-08 服务器 fan-calc 实测（tools/align_fan_calc.py 的
V21_EDGE_CASES 注释），黄金集 testdata/fan_calc_golden.json 同步锚定。
"""
import unittest

from mahjong.fan import calc
from mahjong.hu import is_baotou, is_win

W = "白"


def detail_of(hand_pre, draw, chain=None):
    r = calc(hand_pre, draw, chain)
    return (r["hu"], r["baotou"], r["fan"], tuple(r["detail"]))


class TestBaotouFourWhites(unittest.TestCase):
    """v21 修订①：4 白板听任意形 = 爆头（叠加 4白板 ×2）。"""

    # A: 3 刻 + 4 白
    A = ["1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t", W, W, W, W]
    # B: 3 对 + 3 单 + 4 白
    B = ["1w", "1w", "5b", "5b", "9t", "9t", "东", "南", "中", W, W, W, W]
    # D: 双实四张 + 3t 单 + 4 白
    D = ["1w", "1w", "1w", "1w", "2b", "2b", "2b", "2b", "3t", W, W, W, W]

    def test_baotou_true_all_shapes(self):
        self.assertTrue(is_baotou(self.A))
        self.assertTrue(is_baotou(self.B))
        self.assertTrue(is_baotou(self.D))

    def test_any_draw_wins(self):
        for pre in (self.A, self.B, self.D):
            for d in ("1w", "2w", "9t", "东", "中"):
                self.assertTrue(is_win(pre + [d]), (pre, d))

    def test_regression_baotou_still_works_without_four_whites(self):
        # 4 面子 + 单钓白（旧语义不变）
        pre = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
               "1b", "1b", "1b", W]
        self.assertTrue(is_baotou(pre))
        # 4 面子 + 单钓 东：仅摸东胡 → 非爆头
        pre2 = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
                "1b", "1b", "1b", "东"]
        self.assertFalse(is_baotou(pre2))


class TestLuxuryQiduiV21(unittest.TestCase):
    """v21 修订②：白×4 仅无落单时计豪华组（fan 分解 + 总番）。"""

    def test_case_a_white_consumed_no_luxury(self):
        # 3 刻+4 白 摸 1w：实体 1w×4 一组；白补 2b/3t 单各一张 → 白不组豪华
        pre = ["1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t",
               W, W, W, W]
        self.assertEqual(detail_of(pre, "1w"),
                         (True, True, 16, ("豪华七对×1", "4个白板", "爆头")))

    def test_case_a_other_draws_plain_qidui(self):
        pre = ["1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t",
               W, W, W, W]
        self.assertEqual(detail_of(pre, "1b"),
                         (True, True, 8, ("七对", "4个白板", "爆头")))

    def test_case_b_whites_fill_all_singles_no_luxury(self):
        # 3 对+3 单+4 白 摸北：4 白全部补 东南中北 → 纯七对
        pre = ["1w", "1w", "5b", "5b", "9t", "9t", "东", "南", "中",
               W, W, W, W]
        self.assertEqual(detail_of(pre, "北"),
                         (True, True, 8, ("七对", "4个白板", "爆头")))

    def test_case_d_no_singles_white_group_counts(self):
        # 双实四张+3t 单+4 白 摸 3t：无落单 → 白×4 计 1 组 = 三豪华 ×16
        pre = ["1w", "1w", "1w", "1w", "2b", "2b", "2b", "2b", "3t",
               W, W, W, W]
        self.assertEqual(detail_of(pre, "3t"),
                         (True, True, 64, ("豪华七对×3", "4个白板", "爆头")))

    def test_case_d_singles_present_no_white_group(self):
        # 同上但摸东（东成单）→ 2 白补单 → 白不组豪华 = 双豪华 ×8
        pre = ["1w", "1w", "1w", "1w", "2b", "2b", "2b", "2b", "3t",
               W, W, W, W]
        self.assertEqual(detail_of(pre, "东"),
                         (True, True, 32, ("豪华七对×2", "4个白板", "爆头")))


class TestChainPiaoWithThreeWhites(unittest.TestCase):
    """链/飘与 4白板 判定叠加（手留白 + piao == 4 → ×2）。"""

    def test_case_c_chain_piao_stacking(self):
        pre = ["1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t",
               W, W, W, "东"]
        self.assertEqual(detail_of(pre, "1w"),
                         (True, True, 8, ("豪华七对×1", "爆头")))
        self.assertEqual(detail_of(pre, "1w", {"count": 1, "piao": 1}),
                         (True, True, 32, ("豪华七对×1", "财飘", "4个白板", "爆头")))
        self.assertEqual(detail_of(pre, "东", {"count": 1, "piao": 1}),
                         (True, True, 16, ("七对", "财飘", "4个白板", "爆头")))


if __name__ == "__main__":
    unittest.main()
