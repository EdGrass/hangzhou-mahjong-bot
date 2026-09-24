# -*- coding: utf-8 -*-
"""`speedtenpai`（听牌时按**活等张**破并列）—— 可证占优 / 有界 / 非 no-op 护栏。

要钉住的四件事：
  ① **身份**：`SpeedTenpaiLive` 是 c151 的子类；
  ② ★ **可证占优**：每一次选择的 `(向听, 活等张数)` **弱优于** c151 的选择（向听不变、活等张只增不减）；
  ③ ★ **下行有界**：c151 的选择**不在听牌态（s!=0）**时，本臂**逐位相同**（不动非听牌决策）；
  ④ **非 no-op**：在**固定语料**上至少改变一次（R827/R828 量到约 0.94% 的听牌决策会变）。

⚠ 语料纪律（R896）：本测试用**固定语料** `var/smoke_corpus_v1.jsonl`，不用"最近 N 个房"。

用法：python -X utf8 tests/test_speedtenpai.py -v
"""
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from arm_smoke import to_view                                    # noqa: E402
from bot.speedc151 import SpeedC151                              # noqa: E402
from bot.speedtenpai import SpeedTenpaiLive, SpeedTenpaiLiveFan  # noqa: E402
from bot.ukeire import visible_counts                            # noqa: E402
from mahjong.shanten import waits                                # noqa: E402
from mahjong.shanten_exact import shanten as SH                  # noqa: E402


def _positions(limit=700):
    out = []
    with io.open(os.path.join(ROOT, "var", "smoke_corpus_v1.jsonl"), encoding="utf-8") as fh:
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


def _geom(pol, v, tile):
    """\u8fd4\u56de (s, live_waits)\uff1blive \u4ec5\u5728 s==0 \u65f6\u610f\u4e49\u6709\u6548\u3002"""
    h = list(v["my_hand"])
    melds = v.get("melds") or []
    e = len(melds)
    g = sum(1 for m in melds if m.get("type") == "gang")
    if tile not in h:
        return (99, -1, -1)
    rem = list(h)
    rem.remove(tile)
    try:
        s = SH(rem, qidui=(e == 0 and g == 0), exposed_melds=e, gangs=g, god_meld=True)
    except ValueError:
        return (99, -1)
    if s != 0:
        return (s, -1, -1)
    vis = visible_counts(h, river=v.get("river"), all_melds=v.get("all_melds"))
    try:
        ws = waits(rem, exposed_melds=e, gangs=g)
    except Exception:
        return (99, -1, -1)
    live = sum(max(0, 4 - int(vis.get(t, 0))) for t in ws)
    # 最高番（用与策略同一个算法）
    from mahjong.fan import calc as _cf
    god = v.get("god") or {}
    chain = {"count": int(god.get("chain_count") or 0),
             "piao": int(god.get("piao_count") or 0)}
    best = None
    for wt in (ws or []):
        try:
            r = _cf(list(rem), wt, chain, base=1, exposed_melds=e, gangs=g)
        except Exception:
            continue
        if r.get("hu"):
            f = r.get("fan") or 0
            if best is None or f > best:
                best = f
    return (0, live, (best if best is not None else -1))


class TestSpeedTenpai(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pos = _positions(700)
        cls.a = SpeedC151()
        cls.t = SpeedTenpaiLive()          # 频率档（可能降番）
        cls.g = SpeedTenpaiLiveFan()       # 占优档（不降番）

    def _pick(self, pol, v):
        h = list(v["my_hand"])
        melds = v.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if m.get("type") == "gang")
        return pol._pick_discard(h, v.get("drawn_tile"), e, g, view=v)

    def test_identity(self):
        self.assertTrue(issubclass(SpeedTenpaiLive, SpeedC151))
        self.assertEqual(self.t.name, "speedtenpailive")

    def test_freq_arm_live_not_worse_and_bounded(self):
        """频率档：(\u5411\u542c, \u6d3b\u7b49\u5f20) 不得变差；非听牌局面逐位不变。注：\u756a**可能降**（已在 docstring 声明）。"""
        self.assertTrue(self.pos, "\u53d6\u4e0d\u5230\u56fa\u5b9a\u8bed\u6599\u5c40\u9762")
        worse = 0
        non_tenpai_diff = 0
        for v in self.pos:
            x = self._pick(self.a, v)
            y = self._pick(self.t, v)
            gx = _geom(self.a, v, x)
            gy = _geom(self.t, v, y)
            if gy[0] > gx[0] or (gy[0] == gx[0] and gy[1] < gx[1]):
                worse += 1
            if gx[0] != 0 and x != y:
                non_tenpai_diff += 1
        self.assertEqual(worse, 0, "\u9891\u7387\u6863\u4e0d\u5f97\u5728(\u5411\u542c,\u6d3b\u7b49\u5f20)\u4e0a\u53d8\u5dee")
        self.assertEqual(non_tenpai_diff, 0, "\u975e\u542c\u724c\u5c40\u9762\u5fc5\u987b\u9010\u4f4d\u4e0d\u53d8")

    def test_guard_arm_is_dominant_on_three_axes(self):
        """占优档：(\u5411\u542c, \u6d3b\u7b49\u5f20, **\u6700\u9ad8\u756a**) 三\u4e2a\u7ef4\u5ea6都\u4e0d\u5f97\u53d8\u5dee。"""
        worse = 0
        for v in self.pos:
            x = self._pick(self.a, v)
            y = self._pick(self.g, v)
            gx = _geom(self.a, v, x)
            gy = _geom(self.g, v, y)
            if gy[0] > gx[0]:
                worse += 1
            elif gy[0] == gx[0] == 0:
                if gy[1] < gx[1] or (gx[2] >= 0 and gy[2] >= 0 and gy[2] < gx[2]):
                    worse += 1
        self.assertEqual(worse, 0, "\u5360\u4f18\u6863\u4e0d\u5f97\u5728\u5411\u542c/\u6d3b\u7b49\u5f20/\u6700\u9ad8\u756a\u4e0a\u53d8\u5dee")

    def test_both_arms_are_not_noop(self):
        for pol, nm in ((self.t, "SpeedTenpaiLive"), (self.g, "SpeedTenpaiLiveFan")):
            diff = sum(1 for v in self.pos if self._pick(self.a, v) != self._pick(pol, v))
            self.assertGreater(diff, 0, "%s \u56fa\u5b9a\u8bed\u6599\u4e0a\u5fc5\u987b\u81f3\u5c11\u6539\u53d8\u4e00\u6b21" % nm)


if __name__ == "__main__":
    unittest.main(verbosity=1)
