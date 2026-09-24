# -*- coding: utf-8 -*-
"""`speedmeldmore0chi`（pair-exact 副露放宽）护栏：
  ① 身份/MRO：碰来自 SpeedMeldMore0，吃来自 ChiRealizedMixin；
  ② ★ **pair-exact 有界性**：判为接受的每一个吃窗口，**平台实际会用的那一对**
     （最后一个合法选项，实测 1168 例 100%）必须满足
     向听不变且 live 进张不掉（before>0）或 s_after==0 且 waits 变多（已听）；
  ③ 判据与传入 pair 无关（它只看"平台会用的那一对"）；
  ④ 超集性（碰）：c151 接受的碰，本臂一定接受；
  ⑤ 非 no-op：真实窗口上确实新增接受。

用法：python -X utf8 tests/test_speedmeldmore0chi.py -v
"""
import glob
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from bot.speed import _chi_pairs                                    # noqa: E402
from bot.speedc136 import _state                                    # noqa: E402
from bot.speedc151 import SpeedC151                                 # noqa: E402
from bot.speedchirealized import (SpeedMeldMore0Chi,                # noqa: E402
                                  _after_pair, platform_chi_pair)
from bot.speedmeldmore import SpeedMeldMore0                        # noqa: E402
from bot.ukeire import visible_counts                               # noqa: E402



def _am(tiles):
    tiles = list(tiles or [])
    if not tiles:
        return []
    return [{"type": "meld", "tile": tiles[0], "tiles": tiles}]


def _windows(limit=4000, rooms=25):
    out = []
    dirs = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*")))[-rooms:]
    for dd in dirs:
        for f in sorted(glob.glob(os.path.join(dd, "*_t0.dec.jsonl"))):
            try:
                with io.open(f, encoding="utf-8") as fh:
                    lines = fh.read().splitlines()
            except OSError:
                continue
            for ln in lines:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                if not str(r.get("p") or "").startswith("response_") or not r.get("o"):
                    continue
                melds = [{"type": x[0], "tile": x[1],
                          "tiles": [x[1]] * (4 if x[0] == "gang" else 3)}
                         for x in (r.get("m") or [])]
                god = r.get("god") or {}
                h = list(r.get("h") or [])
                v = {"seat": r.get("s"), "phase": r.get("p"), "turn": r.get("t"),
                     "responding_seats": r.get("rs") or [r.get("s")],
                     "my_hand": h, "melds": melds, "offer_tile": r.get("o"),
                     "river": r.get("r") or [],
                     "all_melds": [_am(ts) for ts in (r.get("am") or [])],
                     "god": {"baotou": bool(god.get("b")),
                             "chain_count": int(god.get("cc") or 0),
                             "piao_count": int(god.get("piao") or 0),
                             "catch_play": bool(god.get("cp"))},
                     "drawn_tile": r.get("d"), "scores": None}
                e = len(melds)
                g = sum(1 for m in melds if m["type"] == "gang")
                if len(h) != 13 - 3 * e - g:
                    continue
                if v["phase"] == "response_chi" and not _chi_pairs(h, v["offer_tile"]):
                    continue
                if v["phase"] == "response_peng" and h.count(v["offer_tile"]) < 2:
                    continue
                out.append(v)
                if len(out) >= limit:
                    return out
    return out


class TestMeldMore0Chi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = _windows(4000, 25)
        cls.base = SpeedC151()
        cls.arm = SpeedMeldMore0Chi()

    def test_identity(self):
        self.assertTrue(issubclass(SpeedMeldMore0Chi, SpeedC151))
        self.assertTrue(issubclass(SpeedMeldMore0Chi, SpeedMeldMore0))
        self.assertEqual(self.arm.TOL, 0.0)
        self.assertEqual(self.arm.name, "speedmeldmore0chi")

    def test_platform_pair_is_last_option(self):
        for v in self.win:
            if v["phase"] != "response_chi":
                continue
            opts = _chi_pairs(v["my_hand"], v["offer_tile"])
            if opts:
                self.assertEqual(platform_chi_pair(v["my_hand"], v["offer_tile"]),
                                 opts[-1])
                return
        self.fail("no chi window in corpus")

    def test_pair_exact_bounded(self):
        checked = 0
        for v in self.win:
            if v["phase"] != "response_chi":
                continue
            opts = _chi_pairs(v["my_hand"], v["offer_tile"])
            if not opts:
                continue
            p = platform_chi_pair(v["my_hand"], v["offer_tile"])
            verdicts = {bool(self.arm._want_claim(v, "chi", list(o))) for o in opts}
            self.assertEqual(len(verdicts), 1, "吃判据必须只看平台会用的那一对")
            if not verdicts.pop():
                continue
            checked += 1
            melds = v["melds"]
            e = len(melds)
            g = sum(1 for m in melds if m["type"] == "gang")
            vis = visible_counts(v["my_hand"], river=v.get("river"),
                                 all_melds=v.get("all_melds"))
            before = _state(v["my_hand"], e, g, vis, self.arm.GOD_MELD)
            after = _after_pair(v["my_hand"], v["offer_tile"], p, e, g, vis,
                                self.arm.GOD_MELD)
            self.assertIsNotNone(before)
            self.assertIsNotNone(after)
            if before[0] == 0:
                self.assertEqual(after[0], 0, "已听档：吃后必须仍听")
            else:
                self.assertLessEqual(after[0], before[0], "绝不接受抬高向听的吃")
                if after[0] == before[0]:
                    self.assertGreaterEqual(after[1], before[1] - self.arm.TOL,
                                            "等向听档：活进张不得下降")
        self.assertGreater(checked, 0, "语料里应有被接受的吃窗口")

    def test_peng_superset(self):
        viol = 0
        for v in self.win:
            if v["phase"] != "response_peng":
                continue
            if self.base._want_claim(v, "peng") and not self.arm._want_claim(v, "peng"):
                viol += 1
        self.assertEqual(viol, 0, "碰必须是 c151 接受集合的超集")

    def test_not_a_noop(self):
        new = 0
        for v in self.win:
            for kind in ("peng", "chi"):
                if v["phase"] != "response_" + kind:
                    continue
                if kind == "chi":
                    opts = _chi_pairs(v["my_hand"], v["offer_tile"])
                    if not opts:
                        continue
                    b = self.base._want_claim(v, "chi", list(opts[-1]))
                else:
                    b = self.base._want_claim(v, "peng")
                a = self.arm._want_claim(v, kind,
                                         list(opts[-1]) if kind == "chi" else None)
                if a and not b:
                    new += 1
        self.assertGreater(new, 0, "真实窗口上必须存在新增接受")



class TestPairAgnosticDefect(unittest.TestCase):
    """Deterministic regression for the defect that `tests/test_speedmeldmore.py`
    finds only when its (changing) corpus happens to contain such a window.

    View (from a real campaign game): hand 5b,白,9t,7b,8t,7w,6t,9b,7t,9w,9t,6w,7b
    with 8t discarded.  Two chi options: (6t,7t) which is bounded, and (7t,9t)
    which RAISES the shanten 1 -> 2.  The platform always uses the LAST option,
    so (7t,9t) is what actually happens.
    """

    HAND = ["5b", "白", "9t", "7b", "8t", "7w", "6t", "9b", "7t", "9w", "9t",
            "6w", "7b"]
    OFFER = "8t"

    def _view(self):
        return {"seat": 0, "phase": "response_chi", "turn": 3,
                "responding_seats": [0], "my_hand": list(self.HAND), "melds": [],
                "offer_tile": self.OFFER, "river": [], "all_melds": [[], [], [], []],
                "god": {"baotou": False, "chain_count": 0, "piao_count": 0,
                        "catch_play": False},
                "drawn_tile": None, "scores": None}

    def test_options_and_platform_choice(self):
        opts = _chi_pairs(self.HAND, self.OFFER)
        self.assertEqual([tuple(o) for o in opts], [("6t", "7t"), ("7t", "9t")])
        self.assertEqual(platform_chi_pair(self.HAND, self.OFFER), ["7t", "9t"])

    def test_old_arm_reports_the_bad_pair_as_accepted(self):
        v = self._view()
        self.assertTrue(SpeedMeldMore0()._want_claim(v, "chi", ["7t", "9t"]),
                        "旧臂的缺陷：不按传入 pair 判定")
        before = _state(v["my_hand"], 0, 0,
                        visible_counts(v["my_hand"], river=[], all_melds=[[], [], [], []]),
                        True)
        after = _after_pair(v["my_hand"], v["OFFER"] if False else self.OFFER,
                            ["7t", "9t"], 0, 0,
                            visible_counts(v["my_hand"], river=[], all_melds=[[], [], [], []]),
                            True)
        self.assertEqual(before[0], 1)
        self.assertEqual(after[0], 2, "这一对会让向听由 1 变 2（即无界）")

    def test_new_arm_rejects_it(self):
        v = self._view()
        self.assertFalse(SpeedMeldMore0Chi()._want_claim(v, "chi", ["7t", "9t"]))
        self.assertFalse(SpeedMeldMore0Chi()._want_claim(v, "chi", ["6t", "7t"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)


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
