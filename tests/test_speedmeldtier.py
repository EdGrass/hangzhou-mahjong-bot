# -*- coding: utf-8 -*-
"""SpeedMeldTier（副露门控档位阶梯）—— **结构护栏**回归。

要钉住的三件事：
  ① **零档 == 生产基线**：`mild_upto=0` 与 `want_claim_strict_meld` 在真实副露窗口上**逐例等价**
     （这是"阶梯零档就是基线"的硬证据 ⇒ 标定仪表无系统偏差）；
  ② **单调性**：`mild_upto` 增大时，接受集合**只增不减**（若 K 接受则 K+1 必接受）；
  ③ **不是 no-op**：存在某一档与基线不同（否则这个旋钮是死的）。

用法：python -X utf8 -m unittest tests.test_speedmeldtier -v
"""
import glob
import io
import json
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "var"))
from bot.speedmeldtier import SpeedMeldTier                     # noqa: E402
from bot.speedtugc import SpeedTUGC, want_claim_strict_meld      # noqa: E402
from bot.speedmeldtier import want_claim_tiered                  # noqa: E402
from bot.speed import _chi_pairs                                 # noqa: E402


def _windows(limit=400):
    """真实副露窗口：(view, kind, pair)。"""
    out = []
    files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "*", "*.json")))
    random.Random(20260921).shuffle(files)
    for f in files:
        try:
            p = json.load(io.open(f, encoding="utf-8"))
        except Exception:
            continue
        for blk in (p.get("blocks") or []):
            sh = blk.get("start_hands")
            if not sh or all(x is None for x in sh):
                continue
            h = list(sh[0] or [])
            if len(h) != 13:
                continue
            base = {"my_hand": list(h), "melds": [], "river": [],
                    "all_melds": [[], [], [], []], "god": None}
            for offer in sorted(set(h)):
                if h.count(offer) >= 2:
                    v = dict(base); v["offer_tile"] = offer; v["phase"] = "response_peng"
                    out.append((v, "peng", None))
                for pr in _chi_pairs(h, offer):
                    v = dict(base); v["offer_tile"] = offer; v["phase"] = "response_chi"
                    out.append((v, "chi", pr))
            if len(out) >= limit:
                return out[:limit]
    return out


class TestMeldTier(unittest.TestCase):
    def setUp(self):
        self.w = _windows(400)
        self.assertTrue(self.w, "取不到真实副露窗口")

    def test_subclass_and_identity(self):
        self.assertTrue(issubclass(SpeedMeldTier, SpeedTUGC))
        self.assertEqual(SpeedMeldTier().name, "meldk0")
        self.assertEqual(SpeedMeldTier(mild_upto=3).name, "meldk3")
        self.assertEqual(SpeedMeldTier(mild_upto=3).MILD_UPTO, 3)

    def test_tier0_equals_strict_baseline(self):
        bad = 0
        for v, kind, pr in self.w:
            a = want_claim_strict_meld(v, kind, pr)
            b = want_claim_tiered(v, kind, pr, mild_upto=0)
            if a != b:
                bad += 1
        self.assertEqual(bad, 0, "零档必须与生产基线逐例等价")

    def test_monotone_in_mild_upto(self):
        bad = 0
        for v, kind, pr in self.w:
            prev = want_claim_tiered(v, kind, pr, mild_upto=0)
            for k in range(1, 8):
                cur = want_claim_tiered(v, kind, pr, mild_upto=k)
                if cur and not prev:
                    ok = True
                elif prev and not cur:
                    bad += 1        # 接受集合缩水 = 违反单调性
                prev = cur
        self.assertEqual(bad, 0, "mild_upto 增大时接受集合只增不减")

    def test_not_a_noop(self):
        diff = sum(1 for v, kind, pr in self.w
                   if want_claim_tiered(v, kind, pr, mild_upto=2)
                   != want_claim_strict_meld(v, kind, pr))
        self.assertGreater(diff, 0, "高档位必须与基线有差异（旋钮不是死的）")


if __name__ == "__main__":
    unittest.main()


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
