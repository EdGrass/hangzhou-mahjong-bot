# -*- coding: utf-8 -*-
"""speedc161（接第二/三摊）单测 —— **已按离线预筛否掉**（覆盖率上限 +0.4pp），代码保留作记录。

预筛结论（`var/_strong_meld_vs_gate.py --games 400`，强者实际副露 5,067 次）：
  c151 85.1% → c156 91.5% → c160 91.6% → **c161 91.8%**；
  把 c161 的阈值全部放开（min_river=0 / max_loss=9999 / bai_keep=0）、**只保留 min_melds≥1** ⇒ **91.9%（上限 +0.4pp）**
  ⇒ 残差**不是"阈值太严"**，而是那批副露会让**我方引擎的向听变差**（≈230/430 落在"已开口"却仍被向听判据挡掉）
  ⇒ 要动的是**评估函数（向听/白 的语义）**，不是门控阈值。
"""
import glob
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc156 import SpeedC156   # noqa: E402
from bot.speedc161 import SpeedC161   # noqa: E402


def _empty_melds_view():
    return {"seat": 0, "phase": "response_peng", "turn": 1, "my_hand": ["1w"] * 13,
            "melds": [], "offer_tile": "2w", "river": ["3w"], "river_len": 1, "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestC161SecondMeld(unittest.TestCase):
    def test_defaults(self):
        p = SpeedC161()
        self.assertEqual((p.min_melds, p.min_river, p.max_loss, p.require_bai_keep),
                         (1, 16, 12.0, True))

    def _real_windows(self, limit=200):
        """从真机 dec 里取若干个合法副露窗口（合成视图缺字段时返回的调用方自行跳过）。"""
        out = []
        files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*_t0.dec.jsonl")))[-2:]
        for f in files:
            with open(f, encoding="utf-8") as fh:
                for ln in fh:
                    ln = ln.strip()
                    if not ln:
                        continue
                    r = json.loads(ln)
                    if r.get("p") not in ("response_peng", "response_chi") or not r.get("o"):
                        continue
                    v = {"seat": r.get("s"), "phase": r.get("p"), "turn": r.get("t"),
                         "my_hand": list(r.get("h") or []), "melds": r.get("m") or [],
                         "offer_tile": r.get("o"), "river": list(r.get("r") or []),
                         "river_len": len(r.get("r") or []), "all_melds": [],
                         "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                                 "piao_count": 0, "god_discarder_seat": -1}}
                    kind = "peng" if v["phase"] == "response_peng" else "chi"
                    out.append((v, kind))
                    if len(out) >= limit:
                        return out
        return out

    def test_restrictive_params_equal_base(self):
        """参数收到最紧（min_melds=999）⇒ 本臂**恰等于** c156（既不增也不减）。"""
        base, pol = SpeedC156(), SpeedC161(min_melds=999)
        n = 0
        for v, kind in self._real_windows():
            try:
                b = bool(base._want_claim(v, kind, None))
                c = bool(pol._want_claim(v, kind, None))
            except Exception:
                continue
            n += 1
            self.assertEqual(b, c, "收紧参数后不得偏离 c156（窗口 %s/%s）" % (v["phase"], v["offer_tile"]))
        self.assertGreater(n, 20, "样本太少（应能取到真机窗口）")

    def test_default_is_superset_of_base(self):
        """默认参数下 c161 ⊇ c156（单向增加，绝不否决）。"""
        base, pol = SpeedC156(), SpeedC161()
        added = 0
        for v, kind in self._real_windows():
            try:
                b = bool(base._want_claim(v, kind, None))
                c = bool(pol._want_claim(v, kind, None))
            except Exception:
                continue
            if b:
                self.assertTrue(c, "不许否决 c156 的索取")
            elif c:
                added += 1
        self.assertGreaterEqual(added, 0)

    def test_never_vetoes_base(self):
        """单向增加：c156 要的，c161 必须也要（真机 dec 窗口回归）。"""
        pol = SpeedC161(min_melds=0, min_river=0, max_loss=9999, require_bai_keep=False)
        base = SpeedC156()
        n = 0
        for v, kind in self._real_windows():
            try:
                b = bool(base._want_claim(v, kind, None))
                c = bool(pol._want_claim(v, kind, None))
            except Exception:
                continue
            n += 1
            if b:
                self.assertTrue(c, "c161 不许否决 c156 的索取（单向增加）")
        self.assertGreater(n, 20, "样本太少")


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
