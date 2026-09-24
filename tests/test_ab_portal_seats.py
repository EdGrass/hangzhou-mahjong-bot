# -*- coding: utf-8 -*-
"""★ 2026-09-16 新增：`ab_portal_readout.scan_portal` 的**座位/去重**回归测试。

背景（实测）：一个自动房 = 10 个文件 = 10 场比赛，**每场座次重洗**。
旧实现把"我方座位"当整房一个值（取最后一个文件）⇒ 实测 **314 房里只有 3 房（1.0%）**
的逐房得分与 `auto_ranking.jsonl` 真值一致；修正后 **312/314 = 99.4%** 一致。
本测试把这个不变量钉死：**逐场座位 + 按 game_id 去重**。
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

spec = importlib.util.spec_from_file_location("ab_portal_rd", os.path.join(ROOT, "tools", "ab_portal_readout.py"))
rd = importlib.util.module_from_spec(spec)
sys.modules["ab_portal_rd"] = rd
spec.loader.exec_module(rd)

ME = rd.ME
OTHERS = ["u_a", "u_b", "u_c"]


def _game(gid, seat_of_me, rounds):
    """rounds = [(winner_seat, scores, multiplier, detail)]"""
    order = [None] * 4
    order[seat_of_me] = ME
    it = iter(OTHERS)
    for i in range(4):
        if order[i] is None:
            order[i] = next(it)
    blocks = [{"events": [{"type": "round_ended", "data": {"detail": det}}]} for (_, _, _, det) in rounds]
    return {
        "game_id": gid,
        "seats": [{"user_id": u} for u in order],
        "rounds": [{"round_no": i + 1, "dealer": 0, "winner": w, "scores": sc, "multiplier": m}
                   for i, (w, sc, m, _) in enumerate(rounds)],
        "blocks": blocks,
        "status": "finished",
    }


class TestScanPortalSeats(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="portal_test_")
        self.rep = os.path.join(self.tmp, "var", "replays", "d1")
        os.makedirs(self.rep)
        self.orig_root = rd.ROOT
        rd.ROOT = self.tmp
        self.addCleanup(self._restore)

    def _restore(self):
        rd.ROOT = self.orig_root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, obj):
        with open(os.path.join(self.rep, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)

    def test_seat_is_per_game_not_per_room(self):
        # 第 1 场：我在 0 号位，第 1 局我自摸 +24（其余各 −8）
        self._write("a_abcdef012345_r1_b0_t0.json", _game(
            "g0", 0, [(0, [24, -8, -8, -8], 2, ["爆头"]), (1, [-8, 10, -1, -1], 1, [])]))
        # 第 2 场：我在 2 号位，第 1 局我放铳（1 号位胡）
        self._write("a_abcdef012345_r1_b1_t0.json", _game(
            "g1", 2, [(1, [-8, 10, -1, -1], 1, []), (2, [-1, -8, -8, 18], 3, ["豪华七对"])]))
        p = rd.scan_portal()
        self.assertIn("a_abcdef012345", p)
        rounds = p["a_abcdef012345"]["rounds"]
        self.assertEqual(len(rounds), 4, "每场 2 局 × 2 场，不能被签名去重吃掉")
        mywin = [r[0] for r in rounds]
        self.assertEqual(mywin, [1, 0, 0, 1])
        self.assertEqual([r[3] for r in rounds], [24, -8, -1, -8])
        self.assertEqual([r[2] for r in rounds], [1, 0, 0, 0], "爆头标记只算我方那一胡（第 4 局我方是豪华七对）")

    def test_duplicate_game_is_dropped(self):
        g = _game("dup", 0, [(0, [24, -8, -8, -8], 1, [])])
        self._write("a_fedcba543210_r1_b0_t0.json", g)
        d2 = os.path.join(self.tmp, "var", "replays", "d2")
        os.makedirs(d2)
        with open(os.path.join(d2, "a_fedcba543210_r1_b0_t0.json"), "w", encoding="utf-8") as f:
            json.dump(g, f, ensure_ascii=False)
        p = rd.scan_portal()
        self.assertEqual(len(p["a_fedcba543210"]["rounds"]), 1, "同一 game_id 出现在两个目录 ⇒ 只算一次")
