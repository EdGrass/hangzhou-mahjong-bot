# -*- coding: utf-8 -*-
"""`SpeedValueMeldMore0Chi`（役 3 组合臂）护栏：正交性 + 身份。

要钉住：
  ① MRO：出牌轴来自 `SpeedValue`、副露轴来自 `ChiRealizedMixin`（不复制逻辑）；
  ② ★ 正交性（出牌）：在真实 draw 局面上，组合臂的动作 == `SpeedValue` 的动作；
  ③ ★ 正交性（副露）：在真实碰/吃局面上，组合臂的判定 == `SpeedMeldMore0Chi` 的判定；
  ④ 组合臂是 `SpeedValue` 与 `SpeedMeldMore0Chi` 的**共同子类**。

用法：python -X utf8 tests/test_speedvaluemeldmore0chi.py -v
"""
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from bot.speed import _chi_pairs                                     # noqa: E402
from bot.speedchirealized import ChiRealizedMixin, SpeedMeldMore0Chi  # noqa: E402
from bot.speedvalue import SpeedValue                                # noqa: E402
from bot.speedvaluemeldmore0chi import SpeedValueMeldMore0Chi        # noqa: E402
from test_speedmeldmore0chi import _windows                          # noqa: E402


def _draw_windows(limit=400, rooms=25):
    """Real draw-phase decisions (hand includes the drawn tile: 14-3e-g)."""
    import glob, json
    out = []
    dirs = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*")))[:rooms]
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
                if r.get("p") != "draw" or not r.get("d"):
                    continue
                melds = [{"type": x[0], "tile": x[1],
                          "tiles": [x[1]] * (4 if x[0] == "gang" else 3)}
                         for x in (r.get("m") or [])]
                h = list(r.get("h") or [])
                e, g = len(melds), sum(1 for m in melds if m["type"] == "gang")
                if len(h) != 14 - 3 * e - g:
                    continue
                god = r.get("god") or {}
                out.append({"seat": r.get("s"), "phase": "draw",
                            "turn": r.get("t"), "responding_seats": r.get("rs") or [],
                            "my_hand": h, "melds": melds,
                            "offer_tile": r.get("o"),
                            "river": r.get("r") or [],
                            "all_melds": [([{"type": "meld", "tile": ts[0], "tiles": list(ts)}]
                                           if ts else []) for ts in (r.get("am") or [])],
                            "god": {"baotou": bool(god.get("b")),
                                    "chain_count": int(god.get("cc") or 0),
                                    "piao_count": int(god.get("piao") or 0),
                                    "catch_play": bool(god.get("cp"))},
                            "drawn_tile": r.get("d"), "scores": None})
                if len(out) >= limit:
                    return out
    return out


class TestCombo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = _windows(600, 25)
        cls.draws = _draw_windows(300, 25)
        cls.combo = SpeedValueMeldMore0Chi()
        cls.sv = SpeedValue()
        cls.mm = SpeedMeldMore0Chi()

    def test_identity_and_mro(self):
        self.assertTrue(issubclass(SpeedValueMeldMore0Chi, SpeedValue))
        self.assertTrue(issubclass(SpeedValueMeldMore0Chi, SpeedMeldMore0Chi))
        self.assertIs(SpeedValueMeldMore0Chi._pick_discard, SpeedValue._pick_discard)
        self.assertIs(SpeedValueMeldMore0Chi._want_claim, ChiRealizedMixin._want_claim)

    def test_draw_axis_orthogonal(self):
        n = 0
        for v in self.draws:
            a = self.combo.decide(v)
            b = self.sv.decide(v)
            self.assertEqual(a, b, "组合臂的出牌必须与 SpeedValue 完全一致")
            n += 1
        self.assertGreater(n, 0, "需要 draw 局面样本")

    def test_claim_axis_orthogonal(self):
        n = 0
        for v in self.win:
            if v.get("phase") == "response_peng":
                self.assertEqual(self.combo._want_claim(v, "peng"),
                                 self.mm._want_claim(v, "peng"))
                n += 1
            elif v.get("phase") == "response_chi":
                opts = _chi_pairs(v["my_hand"], v["offer_tile"])
                if not opts:
                    continue
                for o in opts:
                    self.assertEqual(self.combo._want_claim(v, "chi", list(o)),
                                     self.mm._want_claim(v, "chi", list(o)))
                n += 1
        self.assertGreater(n, 0, "需要碰/吃局面样本")


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
