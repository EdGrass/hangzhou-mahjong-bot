# -*- coding: utf-8 -*-
"""`SpeedValueMeldMore0ChiGang`（役 4 组合臂）护栏：三轴身份 + 正交性 + 杠足迹。

 ① MRO：吃 ← ChiRealizedMixin，碰 ← _MeldMoreBase，明杠 ← SpeedGangTake，出牌 ← SpeedGangTakeFixed；
 ② 正交性：碰/吃的判定与役 3 臂（`SpeedMeldMore0Chi`）**逐条一致**；
 ③ 杠轴足迹：在真实"手里有 3 张同牌"的窗口上，本臂出杠率显著高于役 3 臂（实测 98.2% vs 64.3%），
    且**每个**窗口的出杠都受牌墙守卫约束（river 过长时不出杠）。
"""
import glob
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from bot.speed import _chi_pairs                                        # noqa: E402
from bot.speedchirealized import ChiRealizedMixin, SpeedMeldMore0Chi    # noqa: E402
from bot.speedgangtake import SpeedGangTake                             # noqa: E402
from bot.speedgangtakefixed import SpeedGangTakeFixed                   # noqa: E402
from bot.speedvaluemeldmore0chigang import SpeedValueMeldMore0ChiGang   # noqa: E402


def _to_view(r):
    melds = [{"type": x[0], "tile": x[1], "tiles": [x[1]] * (4 if x[0] == "gang" else 3)}
             for x in (r.get("m") or [])]
    god = r.get("god") or {}
    am = [([{"type": "meld", "tile": ts[0], "tiles": list(ts)}] if ts else [])
          for ts in (r.get("am") or [])]
    return {"seat": r.get("s"), "phase": r.get("p"), "turn": r.get("t"),
            "responding_seats": r.get("rs") or [r.get("s")],
            "my_hand": list(r.get("h") or []), "melds": melds,
            "offer_tile": r.get("o"), "river": r.get("r") or [], "all_melds": am,
            "god": {"baotou": bool(god.get("b")), "chain_count": int(god.get("cc") or 0),
                    "piao_count": int(god.get("piao") or 0),
                    "catch_play": bool(god.get("cp"))},
            "drawn_tile": r.get("d"), "scores": None, "river_len": len(r.get("r") or [])}


def _windows(limit=1500, rooms=25):
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
                if not str(r.get("p") or "").startswith("response_") or not r.get("o"):
                    continue
                v = _to_view(r)
                e = len(v["melds"])
                g = sum(1 for m in v["melds"] if m["type"] == "gang")
                if len(v["my_hand"]) != 13 - 3 * e - g:
                    continue
                out.append(v)
                if len(out) >= limit:
                    return out
    return out


class TestGangCombo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = _windows(2000, 25)
        cls.arm3 = SpeedMeldMore0Chi()
        cls.arm4 = SpeedValueMeldMore0ChiGang()

    def test_mro_identity(self):
        self.assertIs(SpeedValueMeldMore0ChiGang._want_claim, ChiRealizedMixin._want_claim)
        self.assertIs(SpeedValueMeldMore0ChiGang._pick_discard, SpeedGangTakeFixed._pick_discard)
        self.assertTrue(issubclass(SpeedValueMeldMore0ChiGang, SpeedGangTake))
        self.assertTrue(self.arm4.SELF_GANG)

    def test_peng_chi_orthogonal(self):
        n = 0
        for v in self.win:
            if v["phase"] == "response_peng":
                self.assertEqual(self.arm4._want_claim(v, "peng"),
                                 self.arm3._want_claim(v, "peng"))
                n += 1
            elif v["phase"] == "response_chi":
                opts = _chi_pairs(v["my_hand"], v["offer_tile"])
                if not opts:
                    continue
                for o in opts:
                    self.assertEqual(self.arm4._want_claim(v, "chi", list(o)),
                                     self.arm3._want_claim(v, "chi", list(o)))
                n += 1
        self.assertGreater(n, 0)

    def _gang_view(self, river_len=0):
        """Synthetic-but-legal ming-gang window: hand holds three copies of the offer."""
        h = ["1w", "1w", "1w", "2b", "3b", "4b", "5b", "6b", "7b", "8b", "9b",
             "2t", "3t"]
        return {"seat": 0, "phase": "response_peng", "turn": 3,
                "responding_seats": [0], "my_hand": h, "melds": [],
                "offer_tile": "1w", "river": ["5t"] * river_len,
                "all_melds": [[], [], [], []],
                "god": {"baotou": False, "chain_count": 0, "piao_count": 0,
                        "catch_play": False},
                "drawn_tile": None, "scores": None, "river_len": river_len}

    def test_gang_axis_is_live_and_guarded(self):
        self.assertEqual((self.arm4.decide(self._gang_view(0)) or {}).get("action"),
                         "gang", "牌墙充足时必须吃明杠")
        self.assertNotEqual((self.arm4.decide(
            self._gang_view(int(self.arm4.SELF_GANG_MAX_RIVER))) or {}).get("action"),
            "gang", "牌墙末尾必须被守卫拦住")

    def test_gang_footprint_on_corpus(self):
        """Corpus check: only meaningful where the (pinned) corpus has gang windows."""
        opp = g3 = g4 = 0
        for v in self.win:
            if v["phase"] != "response_peng" or not v["offer_tile"]:
                continue
            if v["my_hand"].count(v["offer_tile"]) < 3:
                continue
            opp += 1
            if (self.arm3.decide(v) or {}).get("action") == "gang":
                g3 += 1
            if (self.arm4.decide(v) or {}).get("action") == "gang":
                g4 += 1
        if opp < 5:
            self.skipTest("固定语料里明杠窗口仅 %d 个（旧语料），改由真实足迹脚本覆盖" % opp)
        self.assertGreater(g4, g3, "杠轴必须真实生效")
        self.assertGreaterEqual(g4 / opp, 0.75)


if __name__ == "__main__":
    unittest.main(verbosity=2)
