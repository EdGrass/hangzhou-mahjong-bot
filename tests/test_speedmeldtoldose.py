# -*- coding: utf-8 -*-
"""Boundedness/superset tests for the TOL dose variants (candidate for 役 4).

Why they matter: `SpeedMeldTol2Chi` measured BETTER than `SpeedMeldMore0Chi` on both axes --
more 碰 (+30 vs +18 per 20 rooms), the same 吃, and 0 draw-window overruns under M=10 --
so it is the preferred 役 4 candidate IF its contract holds:
  * superset of c151's accepts,
  * never a worse shanten,
  * equal-shanten accepts may lose at most TOL live tiles,
  * 吃 verdict depends only on the pair the platform actually uses (pair-exact).

usage: python -X utf8 tests/test_speedmeldtoldose.py -v
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from bot.speed import _chi_pairs                                       # noqa: E402
from bot.speedc136 import _after_best, _state                          # noqa: E402
from bot.speedc151 import SpeedC151                                    # noqa: E402
from bot.speedchirealized import platform_chi_pair                     # noqa: E402
from bot.speedmeldtoldose import SpeedMeldTol2Chi, SpeedMeldTol4Chi    # noqa: E402
from bot.ukeire import visible_counts                                  # noqa: E402
from test_speedmeldmore0chi import _windows                            # noqa: E402


class TestTolDose(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = _windows(1500, 25)
        cls.base = SpeedC151()
        cls.arms = [(SpeedMeldTol2Chi(), 2.0), (SpeedMeldTol4Chi(), 4.0)]
        from bot.speedchirealized import SpeedMeldMore0Chi
        cls.pair_exact0 = SpeedMeldMore0Chi()

    def test_identity(self):
        for pol, tol in self.arms:
            self.assertEqual(pol.TOL, tol)
            self.assertTrue(issubclass(type(pol), SpeedC151))

    def test_superset_of_c151_and_bounded(self):
        viol_super = viol_bound = new_accept = checked = 0
        for v in self.win:
            for pol, tol in self.arms:
                if v["phase"] == "response_peng":
                    base_ok = self.base._want_claim(v, "peng")
                    got_ok = pol._want_claim(v, "peng")
                    if base_ok and not got_ok:
                        viol_super += 1
                    if got_ok and not base_ok:
                        new_accept += 1
                        checked += 1
                        self._assert_bounded(v, "peng", None, tok=tol)
                elif v["phase"] == "response_chi":
                    opts = _chi_pairs(v["my_hand"], v["offer_tile"])
                    if not opts:
                        continue
                    real = platform_chi_pair(v["my_hand"], v["offer_tile"])
                    # pair-exactness: the verdict must not depend on the passed pair
                    verdicts = {bool(pol._want_claim(v, "chi", list(o))) for o in opts}
                    self.assertEqual(len(verdicts), 1, "吃判据必须只看平台会用的那一对")
                    # NOTE: c151's 吃 gate is pair-AGNOSTIC (accepts if ANY pair would
                    # work), so it is NOT the right superset baseline for a pair-exact
                    # arm.  The correct baseline is the pair-exact TOL=0 arm.
                    base_ok = self.pair_exact0._want_claim(v, "chi", list(real))
                    got_ok = pol._want_claim(v, "chi", list(real))
                    if base_ok and not got_ok:
                        viol_super += 1
                    if got_ok and not base_ok:
                        new_accept += 1
                        checked += 1
                        self._assert_bounded(v, "chi", list(real), tok=tol)
        self.assertEqual(viol_super, 0,
                         "碰必须是 c151 超集；吃必须是 pair-exact TOL=0 臂的超集")
        self.assertGreater(new_accept, 0, "语料里应存在新增接受")

    def _assert_bounded(self, v, kind, pair, tok):
        melds = v.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if m.get("type") == "gang")
        vis = visible_counts(v["my_hand"], river=v.get("river"),
                             all_melds=v.get("all_melds"))
        before = _state(v["my_hand"], e, g, vis, True)
        after = _after_best(v["my_hand"], v["offer_tile"], kind, pair, e, g, vis, True)
        self.assertIsNotNone(before)
        self.assertIsNotNone(after)
        if before[0] > 0:
            self.assertLessEqual(after[0], before[0], "绝不接受抬高向听的副露")
            if after[0] == before[0]:
                self.assertGreaterEqual(after[1], before[1] - tok,
                                        "等向听档的活张损失不得超过 TOL")


if __name__ == "__main__":
    unittest.main(verbosity=2)


def setUpModule():
    """★ R1346：**无真实语料就整模块跳过**（clone / CI）。

    为什么：本模块的护栏都要在**真实对局记录**（`var/replays/**/*.dec.jsonl`）上取窗口；
    语料不在时它们会报“取不到真实吃牌窗口”这类**假失败**，把真问题淹没。
    `var/` 不在仓库里（.gitignore）⇒ 刚 clone 下来必定无语料，这里明确“跳过”而不是“失败”。
    本地（有语料）行为不变。
    """
    import os as _os
    import unittest as _ut
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    _rep = _os.path.join(_root, "var", "replays")
    _has = False
    if _os.path.isdir(_rep):
        for _dp, _dn, _fn in _os.walk(_rep):
            if any(_x.endswith(".dec.jsonl") for _x in _fn):
                _has = True
                break
    if not _has:
        raise _ut.SkipTest("无真实语料 var/replays/**/*.dec.jsonl（clone/CI）⇒ 跳过本模块")
