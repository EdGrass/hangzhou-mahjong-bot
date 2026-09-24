# -*- coding: utf-8 -*-
"""speedc160（保白副露）单测 —— 它**已按预登记规则被否**（脚印 0.75% < 2%、覆盖率增量 +0.1pp），
代码与单测保留作记录（同 c159c 的先例），**不占真机臂位**。

夹具来自真机 dec 窗口（`var/_find_c160_fixture.py` 搜得）：
  hand=[2t,8b,4b,8b,5b,6w,白,4w,6t,5w,6t,4t,7b]、offer=5w（吃）、river 长 22、无副露
  ⇒ c156 说 pass；c160（min_river=20, max_loss=8）说 claim。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedc156 import SpeedC156   # noqa: E402
from bot.speedc160 import SpeedC160   # noqa: E402

HAND = ["2t", "8b", "4b", "8b", "5b", "6w", "白", "4w", "6t", "5w", "6t", "4t", "7b"]
OFFER = "5w"
RIVER = ["中", "中", "北", "发", "9t", "西", "北", "8t", "北", "2t", "1b", "9b", "2t",
         "4b", "1t", "4t", "1b", "6w", "8w", "南", "4w", "5w"]


def view(river=None, hand=None, offer=OFFER):
    return {"seat": 0, "phase": "response_chi", "turn": 1,
            "my_hand": list(hand if hand is not None else HAND),
            "melds": [], "offer_tile": offer, "river": list(river if river is not None else RIVER),
            "river_len": len(river if river is not None else RIVER), "all_melds": [],
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


class TestC160KeepJoker(unittest.TestCase):
    def test_fixture_base_pass_but_c160_claims(self):
        self.assertFalse(SpeedC156()._want_claim(view(), "chi", None),
                         "夹具必须仍被 c156 拒绝（否则测的不是增量）")
        self.assertTrue(SpeedC160()._want_claim(view(), "chi", None),
                        "c160 应在该窗口补要（白在手上且不吃白）")

    def test_early_river_rejected(self):
        v = view(river=RIVER[:10])            # 牌河过短（早盘）
        self.assertFalse(SpeedC160()._want_claim(v, "chi", None))

    def test_min_river_param_blocks(self):
        self.assertFalse(SpeedC160(min_river=99)._want_claim(view(), "chi", None))

    def test_max_loss_param_blocks(self):
        """进张损失有界：把 max_loss 压到 −1（要求进张必须净增）⇒ 该窗口必须被拒。

        实测：本夹具在 max_loss=0 时**仍会被接受**（说明 c160 补要的窗口并不都是"进张变差"的，
        与 `_strong_meld_vs_gate` 里"被拒组均值 −7.76"并不矛盾——那是对**强者全部被拒副露**的画像，
        而 c160 只覆盖其中一个子集）。所以这里只钉**参数单调性**，不假设该夹具的进张符号。
        """
        self.assertFalse(SpeedC160(max_loss=-1.0)._want_claim(view(), "chi", None))

    def test_never_vetoes_base(self):
        """单向增加：基线(c156)要的窗口，c160 必须也要（在参数极端收紧时也不许否决）。"""
        pol = SpeedC160(min_river=9999, max_loss=0.0)
        base = SpeedC156()
        for f in ("var/replays/auto_20260916_233329", "var/replays/auto_20260917_000150"):
            d = os.path.join(ROOT, f)
            if not os.path.isdir(d):
                continue
            import glob
            import json
            for p in sorted(glob.glob(os.path.join(d, "*_t0.dec.jsonl")))[:1]:
                with open(p, encoding="utf-8") as fh:
                    lines = list(fh)
                for ln in lines:
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
                    # ⚠ 合成视图可能缺字段（真机视图有）⇒ 抛异常的窗口跳过，不当作"被否决"
                    try:
                        base_yes = bool(base._want_claim(v, kind, None))
                    except Exception:
                        continue
                    if base_yes:
                        self.assertTrue(bool(pol._want_claim(v, kind, None)),
                                        "c160 不许否决 c156 的索取（单向增加）")


if __name__ == "__main__":
    unittest.main()
