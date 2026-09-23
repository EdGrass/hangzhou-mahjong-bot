# -*- coding: utf-8 -*-
"""`tools/mech_mix.py` 单测：机制构成核对的口径（四家全信息 + detail 解析）。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import importlib.util
_spec = importlib.util.spec_from_file_location("mm", os.path.join(ROOT, "tools", "mech_mix.py"))
mm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mm)


def _room(me=0, events=None, seats=None):
    return {"game_id": "a_x_r1_b0_t0",
            "seats": seats or [{"user_id": mm.ME}, {"user_id": "u1"},
                               {"user_id": "u2"}, {"user_id": "u3"}],
            "blocks": [{"events": events or []}]}


class TestMechMix(unittest.TestCase):
    def test_ignores_rooms_without_me(self):
        d = _room(seats=[{"user_id": "a"}, {"user_id": "b"}, {"user_id": "c"}, {"user_id": "d"}])
        self.assertEqual(mm.scan_room(d), (None, None))

    def test_counts_gangs_and_detail_flags(self):
        ev = [
            {"type": "gang", "seat": 0, "tile": "5w", "data": {"kind": "ming"}},
            {"type": "gang", "seat": 0, "tile": "6w", "data": {"kind": "an"}},
            {"type": "gang", "seat": 2, "tile": "7w", "data": {"kind": "bu"}},   # 别人的不算
            {"type": "round_ended", "seat": 0, "data": {"draw": False, "fan": 4,
                                                        "detail": ["平胡", "杠开", "爆头"]}},
            {"type": "round_ended", "seat": 1, "data": {"draw": False, "fan": 2,
                                                        "detail": ["七对"]}},
            {"type": "round_ended", "seat": 0, "data": {"draw": False, "fan": 8,
                                                        "detail": ["平胡", "财飘", "爆头"]}},
            {"type": "round_ended", "seat": -1, "data": {"draw": True, "scores": [0, 0, 0, 0]}},
        ]
        me, c = mm.scan_room(_room(events=ev))
        self.assertEqual(me, 0)
        self.assertEqual(c["rounds"], 4)
        self.assertEqual(c["wins"], 2)
        self.assertEqual((c["gang_ming"], c["gang_an"], c["gang_bu"], c["gang_all"]), (1, 1, 0, 2))
        self.assertEqual(c["baotou"], 2)
        self.assertEqual(c["piao"], 1)
        self.assertEqual(c["ganghu"], 1)
        self.assertEqual(c["qidui"], 0)         # 七对是别人胡的，不计我方
        self.assertEqual(c["fan_sum"], 12)

    def test_white4_and_qidui(self):
        ev = [{"type": "round_ended", "seat": 0, "data": {"draw": False, "fan": 8,
                                                          "detail": ["豪华七对", "4个白板"]}}]
        _me, c = mm.scan_room(_room(events=ev))
        self.assertEqual(c["qidui"], 1)
        self.assertEqual(c["white4"], 1)


if __name__ == "__main__":
    unittest.main()
