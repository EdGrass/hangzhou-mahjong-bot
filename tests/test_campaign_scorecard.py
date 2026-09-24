# -*- coding: utf-8 -*-
"""campaign_scorecard \u7684\u6570\u5b66\u5355\u6d4b\uff08\u81ea\u5305\u542b\uff1a\u81ea\u5df1\u9020\u4e00\u4efd\u5408\u6210\u95e8\u6237\u590d\u76d8\uff0c\u4e0d\u4f9d\u8d56\u4efb\u4f55\u8bed\u6599\uff09\u3002

\u4e3a\u4ec0\u4e48\u8981\u5355\u6d4b\uff1a4 \u56db\u6d4b\u671f\u95f4\u6211\u7528\u4e34\u65f6\u811a\u672c\u7b97\u51fa\u201c\u7206\u5934\u5f97\u624b 10 / \u88ab\u7206 25\u3001\u7ffb\u500d\u5c40 11 \u80dc 31 \u8d1f\u201d
\u8fd9\u7c7b\u7ed3\u8bba\uff0c\u800c\u4e34\u65f6\u811a\u672c\u8bf4\u6ca1\u5c31\u6ca1\u4e86\u3002\u628a\u53e3\u5f84\u9489\u6b7b\u5728\u6d4b\u8bd5\u91cc\uff0c10/10 \u5f53\u665a\u518d\u8dd1\u624d\u4e0d\u4f1a\u201c\u6362\u4e2a\u7b97\u6cd5\u5f97\u51fa\u53e6\u4e00\u4e2a\u6570\u201d\u3002
"""
from __future__ import annotations
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import campaign_scorecard as cs  # noqa: E402


def _doc():
    """2 \u8f6e\u5408\u6210\u5c40\uff1ar1 \u6211\u65b9\u7206\u5934\uff08mult=2\uff09\uff1br2 \u5bf9\u5bb6\u5e73\u80e1\uff08mult=1\uff09\u3002"""
    seats = [{"user_id": cs.ME, "name": "me"}, {"user_id": "u_x1", "name": "a"},
             {"user_id": "u_x2", "name": "b"}, {"user_id": "u_x3", "name": "c"}]
    rounds = [
        {"round_no": 1, "winner": 0, "is_draw": False, "multiplier": 2, "scores": [20, -8, -8, -4]},
        {"round_no": 2, "winner": 1, "is_draw": False, "multiplier": 1, "scores": [-4, 12, -4, -4]},
    ]
    events = [
        {"seq": 1, "type": "round_ended", "seat": 0,
         "data": {"round_no": 1, "detail": ["\u5e73\u80e1", "\u7206\u5934"], "fan": 2, "scores": [20, -8, -8, -4]}},
        {"seq": 2, "type": "round_ended", "seat": 1,
         "data": {"round_no": 2, "detail": ["\u5e73\u80e1"], "fan": 1, "scores": [-4, 12, -4, -4]}},
    ]
    return {"game_id": "t_synth_b1_t0", "status": "finished", "seats": seats,
            "rounds": rounds, "blocks": [{"round_no": 1, "events": events}]}


class TestCampaignScorecard(unittest.TestCase):
    def test_load_file_math(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "t_synth_b1_t0.json")
            with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(_doc(), ensure_ascii=False))
            d = cs.load_file(p)
        self.assertEqual(["u_x3"], ["u_x3"])
        self.assertEqual(4, len(d["seats"]))
        me = d["per_seat"][0]
        self.assertEqual(2, me["rounds"])          # \u4e24\u8f6e\u90fd\u7b97\u5230\u6211
        self.assertEqual(16, me["score"])          # +20 -4
        self.assertEqual(1, me["wins"])
        self.assertEqual(1, me["baotou_wins"])     # r1 \u7206\u5934
        self.assertEqual(1, me["mult_wins"])       # r1 mult=2
        self.assertEqual(0, me["mult_losses"])     # r2 mult=1 \u21d2 \u4e0d\u8ba1\u5165\u7ffb\u500d\u5c40
        opp = d["per_seat"][1]
        self.assertEqual(4, opp["score"])          # -8 +12
        self.assertEqual(1, opp["wins"])
        self.assertEqual(0, opp["baotou_wins"])

    def test_round_details_map(self):
        det = cs.round_details(_doc())
        self.assertEqual(["\u5e73\u80e1", "\u7206\u5934"], det[1]["detail"])
        self.assertEqual(2, det[1]["fan"])
        self.assertEqual(1, det[2]["winner"])


if __name__ == "__main__":
    unittest.main()