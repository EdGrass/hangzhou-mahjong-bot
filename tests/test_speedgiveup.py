# -*- coding: utf-8 -*-
"""`speedgiveup`（弃胡换爆头的**期望余量**旋钮）—— 方向护栏 + 保真回归。

要钉住的四件事：
  ① **身份/继承**：两臂都是 c151 的子类，MARGIN = 1.0 / 2.0；
  ② **保真**：`MARGIN=1.0` 的副本在真实"可弃胡窗口"上与 c151 **逐位相同**（证明复制无偏差）；
  ③ **单向性**（方向护栏）：`MARGIN=2.0` 每一次弃胡，都对应 **c151 也弃胡**（越严格越少弃胡）；
  ④ **非 no-op**：存在真实窗口使 M2 不弃胡而 c151 弃胡（否则旋钮是死的）。

用法：python -X utf8 -m unittest tests.test_speedgiveup -v
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
from bot.speedc151 import SpeedC151                              # noqa: E402
from bot.speedgiveup import SpeedGiveupM1, SpeedGiveupM2         # noqa: E402
from mahjong.hu import is_baotou                                  # noqa: E402


def _giveup_positions(limit=40, rooms=25):
    """真实"可弃胡窗口"：(hand14, exposed, gangs)。"""
    out = []
    dirs = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*")))[-rooms:]
    for dd in dirs:
        for f in sorted(glob.glob(os.path.join(dd, "*_t0.dec.jsonl"))):
            try:
                lines = io.open(f, encoding="utf-8").read().splitlines()
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
                if r.get("p") != "draw" or len(r.get("h") or []) != 14:
                    continue
                hand = list(r["h"])
                m = r.get("m") or []
                e = len(m)
                g = sum(1 for x in m if x and x[0] == "gang")
                if len(hand) != 14 - 3 * e - g:
                    continue
                ok = False
                for d in sorted(set(hand)):
                    after = list(hand); after.remove(d)
                    try:
                        if is_baotou(after, allow_qidui=(e == 0 and g == 0),
                                     exposed_melds=e, gangs=g):
                            ok = True
                            break
                    except ValueError:
                        continue
                if ok:
                    out.append((hand, e, g))
                    if len(out) >= limit:
                        return out
    return out


FANS = (1, 2, 4, 8, 16)


class TestSpeedGiveup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pos = _giveup_positions(40, 25)
        cls.a = SpeedC151()
        cls.m1 = SpeedGiveupM1()
        cls.m2 = SpeedGiveupM2()

    def test_identity(self):
        self.assertTrue(issubclass(SpeedGiveupM1, SpeedC151))
        self.assertTrue(issubclass(SpeedGiveupM2, SpeedC151))
        self.assertEqual(self.m1.MARGIN, 1.0)
        self.assertEqual(self.m2.MARGIN, 2.0)
        self.assertEqual(self.m1.name, "speedgiveupm1")
        self.assertEqual(self.m2.name, "speedgiveupm2")

    def test_margin1_is_bit_identical_to_c151(self):
        self.assertTrue(self.pos, "取不到真实可弃胡窗口")
        diff = 0
        for hand, e, g in self.pos:
            for fan_now in FANS:
                chain = {"count": 0, "piao": 0}
                x = self.a._best_giveup(list(hand), e, g, fan_now, dict(chain))
                y = self.m1._best_giveup(list(hand), e, g, fan_now, dict(chain))
                if x != y:
                    diff += 1
        self.assertEqual(diff, 0, "MARGIN=1.0 的副本必须与 c151 逐位相同")

    def test_monotone_less_giveup(self):
        """方向护栏：M2 弃胡 ⇒ c151 也弃胡（且同一张牌）。"""
        vio = 0
        m2_yes = 0
        for hand, e, g in self.pos:
            for fan_now in FANS:
                chain = {"count": 0, "piao": 0}
                x = self.a._best_giveup(list(hand), e, g, fan_now, dict(chain))
                y = self.m2._best_giveup(list(hand), e, g, fan_now, dict(chain))
                if y is not None:
                    m2_yes += 1
                    if x != y:
                        vio += 1
        self.assertEqual(vio, 0, "M2 不得出现'c151 不弃胡、M2 弃胡'")
        self.assertGreater(m2_yes, 0, "语料里 M2 至少要弃胡一次（否则护栏没测到东西）")

    def test_is_not_a_noop(self):
        diff = 0
        for hand, e, g in self.pos:
            for fan_now in FANS:
                chain = {"count": 0, "piao": 0}
                x = self.a._best_giveup(list(hand), e, g, fan_now, dict(chain))
                y = self.m2._best_giveup(list(hand), e, g, fan_now, dict(chain))
                if x is not None and y is None:
                    diff += 1
        self.assertGreater(diff, 0, "M2 必须真的比 c151 少弃胡（至少一次）")


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
