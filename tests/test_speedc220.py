# -*- coding: utf-8 -*-
"""C220：等张"期望分值"取舍 —— **方向护栏**回归。

要钉住的只有两件事（其余全靠 A/B）：
  ① 它是**并列项**：只在"基线弃牌后仍听牌"的场合动手，**绝不能把听牌换掉**；
  ② 规则本身：`wait_set_value` 用**集合加权平均**（不是集合里最好的那一张 —— R688 的 300 倍度量坑）。
单测用**真实复盘局面**（重建我方 14 张手牌）跑属性断言，而不是手搓牌型。
"""
import glob, importlib.util, json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "var"))
from bot.speedc220 import SpeedC220, wait_set_value          # noqa: E402
from bot.speedtugc import SpeedTUGC                          # noqa: E402
from mahjong.shanten import waits as WAITS                   # noqa: E402
from _track_hands import track                               # noqa: E402

ME = "u_7a3fba48d70b"


def _my_positions(limit=200):
    """从真实复盘里取我方 14 张的弃牌局面：(hand, drawn, exposed, gangs)。"""
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "var", "replays", "recent", "*.json")))[:12]:
        try:
            p = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        uids = [s.get("user_id") or "" for s in (p.get("seats") or [])]
        if len(uids) != 4 or ME not in uids:
            continue
        me = uids.index(ME)
        cur = None; start = None
        for b in p.get("blocks") or []:
            sh = b.get("start_hands")
            if sh and len(sh) == 4 and any(isinstance(x, (list, tuple)) for x in sh):
                start = sh
            if start is None:
                continue
            for e in (b.get("events") or []):
                if e.get("type") == "round_ended":
                    start = None; continue
            evs = b.get("events") or []
            try:
                st = track(evs, start)
            except Exception:
                continue
            for i, e in enumerate(evs):
                if e.get("type") != "tile_discarded" or e.get("seat") != me or i >= len(st):
                    continue
                hand, ec, gc, _m = st[i][me]
                # ★ `_pick_discard` 接受的是**含刚摸牌的弃牌前状态**，其合法长度由副露决定：
                #    `len(hand) == 14 - 3*ec - gc`（track 自述的同一不变量 13-3e-g 再加摸到的那张）。
                #    R1173：旧夹具只判 `len(hand)==14`，于是把 `ec=1` 的 11 张局面当成 14 张喂进去，
                #    在 shanten_exact 收紧入参校验后直接 ValueError（全套唯一红灯）。
                if len(hand) == 14 - 3 * ec - gc:
                    out.append((list(hand), e.get("tile"), ec, gc))
                if len(out) >= limit:
                    return out
    return out


class TestC220(unittest.TestCase):
    def test_registered_and_subclass_of_baseline(self):
        from run_bot import STRATEGY_FACTORIES as F
        self.assertIn("speedc220", F)
        p = F["speedc220"]()
        self.assertIsInstance(p, SpeedC220)
        self.assertTrue(issubclass(SpeedC220, SpeedTUGC))     # ★ 单变量：基座就是现役基线

    def test_wait_set_value_is_mean_not_max(self):
        # 集合加权平均：{高值牌, 低值牌} 必须**低于**只取高值牌
        hi = wait_set_value(["3b"])
        lo = wait_set_value(["1t"])
        both = wait_set_value(["3b", "1t"])
        self.assertLess(both, hi)
        self.assertGreater(both, lo)
        self.assertAlmostEqual(both, (hi + lo) / 2, places=6)
        self.assertEqual(wait_set_value([]), 0.0)

    def test_never_breaks_tenpai_on_real_positions(self):
        """★ 方向护栏：基线弃牌仍听牌时，c220 的选择**也必须保持听牌**。"""
        pos = _my_positions(200)
        self.assertGreater(len(pos), 5, "样本太少，无法验证")
        base_pol = SpeedTUGC()
        pol = SpeedC220()
        checked = 0
        for hand, drawn, ec, gc in pos:
            b = base_pol._pick_discard(list(hand), drawn, ec, gc, {"river": [], "all_melds": []})
            if not b or b not in hand:
                continue
            hb = list(hand); hb.remove(b)
            try:
                if not WAITS(hb, exposed_melds=ec, gangs=gc):
                    continue                    # 基线本就不听 ⇒ 不在并列项范围内
            except Exception:
                continue
            a = pol._pick_discard(list(hand), drawn, ec, gc, {"river": [], "all_melds": []})
            self.assertIn(a, hand)
            ha = list(hand); ha.remove(a)
            self.assertTrue(WAITS(ha, exposed_melds=ec, gangs=gc),
                            "c220 把听牌换掉了（违反并列项护栏）")
            checked += 1
        self.assertGreater(checked, 3, "没有覆盖到'基线仍听牌'的局面")

    def test_margin_zero_still_safe_and_counts(self):
        pol = SpeedC220(margin=0.0)
        pos = _my_positions(20)
        for hand, drawn, ec, gc in pos:
            a = pol._pick_discard(list(hand), drawn, ec, gc, {"river": [], "all_melds": []})
            self.assertIn(a, hand)
        self.assertGreater(pol.stats["dec"], 0)
        self.assertLessEqual(pol.stats["switch"], pol.stats["tp"])


if __name__ == "__main__":
    unittest.main()



def setUpModule():
    """★ R1346：**无真实语料就整模块跳过**（clone / CI）。

    为什么：本模块的护栏要在**真实对局记录**（`var/replays/**/*.dec.jsonl`）上取窗口；
    语料不在时它们报“取不到真实吃牌窗口”这类**假失败**，把真问题淹没。
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
