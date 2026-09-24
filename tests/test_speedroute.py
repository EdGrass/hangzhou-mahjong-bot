# -*- coding: utf-8 -*-
"""`bot/speedroute.py`（c151 的 ROUTE_BONUS / GATE_RIVER 阶梯）—— **方向护栏 + 保真** 回归。

要钉住的五件事：
  ① **保真**：`GATE_RIVER=0` + `ROUTE_BONUS=8.0` 的副本在真实弃牌局面上与 `SpeedC151` **逐位相同**
     （⇒ 阶梯里任何分歧都只来自旋钮，不是复制走样）；
  ② **绝不牺牲向听**（§2.2-bis 机制前提③）：所有阶梯臂选出的弃牌，其**向听 ≤ c151 的**（主键不被旋钮动到）；
  ③ **时机门的方向要说清**：`SpeedRouteLate` 在 `river_len >= GATE_RIVER` 的局面里与 c151 **逐位相同**
     （晚期行为不变），而**早期**（river<16）它等价于"**不加多对子惩罚**"⇒ 与 c151 **必然不同**。
     ⚠ 一开始我把这条写反了（以为"关掉惩罚"仍是 c151 行为）—— 测试当场抓住：`gate_river=0` 的
        `bonus=8` 才等于 c151；**把惩罚关掉等于换成"纯活张"键（c135 式）**。
  ④ **旋转是活的**：各臂在语料里至少改变过一次选择（否则是死臂）；
  ⑤ **身份**：类名/参数与设计一致。

用法：python -X utf8 tests/test_speedroute.py -v
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
from arm_smoke import to_view                                        # noqa: E402
from bot.speedc151 import SpeedC151                                  # noqa: E402
from bot.speedroute import (_RouteBase, SpeedRoute0, SpeedRoute2,   # noqa: E402
                            SpeedRoute16, SpeedRouteLate)
from mahjong.shanten_exact import shanten as SH                      # noqa: E402


def _positions(limit=800):
    """★ 用**固定语料** `var/smoke_corpus_v1.jsonl`（R880），而不是"最近 N 个房"。

    原因（R896）：旧写法**随语料漂移** —— 实测到过 `Route16` 在
    某一批 400 局面上**分歧恰好为 0**，于是 "knob 是活的" 这条护栏假失败。
    固定语料下分歧稳定（实测 800 局面：Route2 46、Route16 16、RouteLate 33）。
    """
    out = []
    path = os.path.join(ROOT, "var", "smoke_corpus_v1.jsonl")
    with io.open(path, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("p") != "draw" or len(r.get("h") or []) != 14:
                continue
            out.append(to_view(r))
            if len(out) >= limit:
                break
    return out


def _sh_after(v, tile):
    h = list(v["my_hand"])
    melds = v.get("melds") or []
    e = len(melds)
    g = sum(1 for m in melds if m.get("type") == "gang")
    if tile not in h:
        return 99
    h.remove(tile)
    try:
        return SH(h, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g, god_meld=True)
    except ValueError:
        return 99


class TestSpeedRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pos = _positions(800)
        cls.c151 = SpeedC151()
        cls.e8 = _RouteBase()          # bonus 8.0, gate 0
        cls.r0 = SpeedRoute0()
        cls.r2 = SpeedRoute2()
        cls.r16 = SpeedRoute16()
        cls.late = SpeedRouteLate()

    def _pick(self, pol, v):
        h = list(v["my_hand"])
        melds = v.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if m.get("type") == "gang")
        return pol._pick_discard(h, v.get("drawn_tile"), e, g, view=v)

    def test_identity(self):
        self.assertTrue(issubclass(_RouteBase, type(self.c151).__mro__[1]))
        self.assertEqual(self.e8.ROUTE_BONUS, 8.0)
        self.assertEqual(self.r0.ROUTE_BONUS, 0.0)
        self.assertEqual(self.r0.name, "speedroute0")
        self.assertEqual(self.r2.ROUTE_BONUS, 2.0)
        self.assertEqual(self.r16.ROUTE_BONUS, 16.0)
        self.assertEqual(self.late.GATE_RIVER, 16)
        self.assertEqual(self.late.ROUTE_BONUS, 8.0)

    def test_gate0_bonus8_is_bit_identical_to_c151(self):
        self.assertTrue(self.pos, "取不到真实弃牌局面")
        bad = [(v, self._pick(self.c151, v), self._pick(self.e8, v)) for v in self.pos]
        bad = [(a, b) for _v, a, b in bad if a != b]
        self.assertEqual(bad, [], "gate=0/bonus=8 的副本必须与 c151 逐位相同")

    def test_no_arm_ever_worsens_shanten(self):
        worse = 0
        for v in self.pos:
            base = self._pick(self.c151, v)
            sb = _sh_after(v, base)
            for pol in (self.r0, self.r2, self.r16, self.late):
                got = self._pick(pol, v)
                if _sh_after(v, got) > sb:
                    worse += 1
        self.assertEqual(worse, 0, "旋钮不得改变向听主键（绝不牺牲向听）")

    def test_late_gate_is_inert_after_threshold(self):
        """晚期（river>=16）必须与 c151 逐位相同；早期必须真的不同（否则这个旋钮是死的）。"""
        late = [v for v in self.pos if len(v.get("river") or []) >= 16]
        early = [v for v in self.pos if len(v.get("river") or []) < 16]
        self.assertTrue(late, "语料里应存在 river>=16 的局面")
        self.assertTrue(early, "语料里应存在 river<16 的局面")
        diff_late = [v for v in late if self._pick(self.c151, v) != self._pick(self.late, v)]
        self.assertEqual(diff_late, [], "river >= GATE_RIVER 时 SpeedRouteLate 必须与 c151 逐位相同")
        diff_early = sum(1 for v in early if self._pick(self.c151, v) != self._pick(self.late, v))
        self.assertGreater(diff_early, 0, "早期（river<16）必须真的改变选择（否则旋钮没生效）")

    def test_knobs_are_alive(self):
        for pol, nm in ((self.r0, "Route0"), (self.r2, "Route2"), (self.r16, "Route16"), (self.late, "RouteLate")):
            n = sum(1 for v in self.pos if self._pick(self.c151, v) != self._pick(pol, v))
            self.assertGreater(n, 0, "%s 在语料上必须至少改变一次选择" % nm)


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
