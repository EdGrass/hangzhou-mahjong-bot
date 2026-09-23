# -*- coding: utf-8 -*-
"""ab_winrate / fetch_room_replays 单测：胜率口径必须与排行榜一致（只能自摸）。"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


wr = _load("wr", os.path.join("tools", "ab_winrate.py"))
fr = _load("fr", os.path.join("tools", "fetch_room_replays.py"))

ME = wr.ME
OTHER = ["u_o1", "u_o2", "u_o3"]


def _replay(rounds=(), seats=None, game_id="a_x_r1_b0_t0"):
    """构造一个最小可解析复盘：seats 固定为 [ME, o1, o2, o3]，rounds 是
    (winner_seat, draw, fan, score_delta_me, detail) 列表。"""
    seats = seats or ([{"user_id": ME}] + [{"user_id": x} for x in OTHER])
    blocks = []
    for (w, draw, fan, me_score, detail) in rounds:
        scores = [0, 0, 0, 0]
        scores[0] = me_score
        blocks.append({"events": [{"type": "round_ended", "seat": w,
                                   "data": {"draw": draw, "fan": fan, "detail": detail,
                                            "dealer": 0, "scores": scores}}]})
    return {"game_id": game_id, "seats": seats, "rounds": [{}] * len(rounds), "blocks": blocks}


def _recs(wins, total):
    return ([dict(win=True, fan=2, baotou=False, dealer=False, score=10)] * wins
            + [dict(win=False, fan=0, baotou=False, dealer=False, score=-5)] * (total - wins))


class TestScanRounds(unittest.TestCase):
    def test_self_draw_only_counts_as_win(self):
        me, recs, ok = wr.scan_rounds(_replay([
            (0, False, 2, 20, ["平胡", "爆头"]),   # 我方自摸 ⇒ 胜
            (1, False, 1, -10, ["平胡"]),          # 对手自摸 ⇒ 不算我方胜
            (0, True, 0, -1, []),                  # 流局 ⇒ 不算
        ]))
        self.assertEqual(me, 0)
        self.assertTrue(ok)
        self.assertEqual([r["win"] for r in recs], [True, False, False])

    def test_baotou_and_dealer_flags(self):
        _me, recs, _ok = wr.scan_rounds(_replay([(0, False, 4, 40, ["平胡", "爆头"])]))
        self.assertEqual(recs[0]["fan"], 4)
        self.assertTrue(recs[0]["baotou"])
        self.assertTrue(recs[0]["dealer"])
        self.assertEqual(recs[0]["score"], 40)

    def test_round_tabula_mismatch_is_flagged(self):
        d = _replay([(0, False, 1, 10, ["平胡"])])
        d["rounds"] = [{}, {}]           # 台账 2 局但事件流只有 1 局
        _me, _recs, ok = wr.scan_rounds(d)
        self.assertFalse(ok, "口径不一致必须能自检出来（宁可丢弃也不静默算错）")

    def test_room_without_me_is_skipped(self):
        seats = [{"user_id": x} for x in OTHER[:3]] + [{"user_id": "u_other"}]
        me, recs, _ok = wr.scan_rounds(_replay([], seats=seats))
        self.assertIsNone(me)
        self.assertEqual(recs, [])


class TestSummarize(unittest.TestCase):
    def test_win_rate_and_separation(self):
        data = {"A": {"rooms": {"r1": [dict(win=True, fan=2, baotou=True, dealer=False, score=20)] * 3
                                      + [dict(win=False, fan=0, baotou=False, dealer=False, score=-5)] * 5}},
                "B": {"rooms": {"r2": [dict(win=True, fan=1, baotou=False, dealer=True, score=10)] * 5
                                      + [dict(win=False, fan=0, baotou=False, dealer=False, score=-5)] * 3}}}
        st = wr.summarize(data)
        self.assertAlmostEqual(st["A"]["win"], 3 / 8.0)
        self.assertAlmostEqual(st["B"]["win"], 5 / 8.0)
        self.assertAlmostEqual(st["B"]["baotou_rate"], 0.0)
        self.assertAlmostEqual(st["A"]["fan_per_win"], 2.0)
        self.assertAlmostEqual(st["A"]["dealer_win"], 0.0)
        self.assertAlmostEqual(st["B"]["dealer_win"], 1.0)

    def test_cluster_se_covers_between_room_dispersion(self):
        """房级胜率真的散开时（像实测：SD≈6.5pp），聚类 SE 必须 > 二项 SE。

        ⚠ 注意：这不是恒等式。若每房局数少而**房内方差占主导**（例如每房 8/10 胡率），
        聚类 SE 反而可能小于二项 SE（有限簇设计效应 <1）；所以 ab_winrate 的做法是
        **两个都算、比较时取大者**（compare() 的 note 字段就是这个含义），而不是假定谁一定更大。
        """
        def room(k, n=10):
            return ([dict(win=True, fan=2, baotou=False, dealer=False, score=10)] * k
                    + [dict(win=False, fan=0, baotou=False, dealer=False, score=-5)] * (n - k))
        # 房级胜率 0.1~0.7（SD≈24pp）⇒ 设计效应 >1（实测 23,509 局的 SD=6.5pp 时是 1.35）
        rooms = {"r%d" % k: room(k) for k in (1, 2, 4, 6, 7)}
        st = wr.summarize({"A": {"rooms": rooms}})["A"]
        self.assertGreater(st["se_cluster"], st["se_binom"])
        self.assertEqual(st["rooms"], 5)
        self.assertEqual(st["rounds"], 50)

    def test_small_cluster_design_effect_can_be_below_one(self):
        """反例（写下来防止以后误以为"聚类 SE 一定更大"）：少量房 × 极端胡率时 cluster < binom。"""
        def room(k, n=10):
            return ([dict(win=True, fan=2, baotou=False, dealer=False, score=10)] * k
                    + [dict(win=False, fan=0, baotou=False, dealer=False, score=-5)] * (n - k))
        # 2 房 × 10 局、胡率 0.7/0.8：房内方差占主导 ⇒ 设计效应 ≈0.47 < 1
        rooms = {"r1": room(7), "r2": room(8)}
        st = wr.summarize({"A": {"rooms": rooms}})["A"]
        self.assertLess(st["se_cluster"], st["se_binom"])
        # 但 compare() 取大者 ⇒ 仍然保守
        c = wr.compare(st, dict(st, win=st["win"] + 0.02))
        self.assertGreaterEqual(c["se"], min(st["se_binom"], st["se_cluster"]))

    def test_empty_arm_is_all_zero(self):
        st = wr.summarize({"A": {"rooms": {}}})["A"]
        self.assertEqual((st["rooms"], st["rounds"], st["win"]), (0, 0, 0.0))
        self.assertEqual(st["se_binom"], 0.0)


class TestRoomDifferential(unittest.TestCase):
    """同房配对差分：我方胜率 − 同房三对手合并胜率。

    这是本项目**最敏感的场内度量**（对手吸收房间难度）。它的定义必须被钉死：
    分子只数我方自摸胡，分母是同一批轮次；对手侧按 3 席合并。
    """

    def test_zero_when_we_match_opponents(self):
        recs = _recs(4, 10)                     # 我方 4/10 = 40%
        self.assertAlmostEqual(wr.room_differential(recs, (12, 30)), 0.0)

    def test_positive_when_we_beat_opponents(self):
        recs = _recs(5, 10)                     # 50% vs 对手 12/30 = 40%
        self.assertAlmostEqual(wr.room_differential(recs, (12, 30)), 0.10)

    def test_missing_opponent_data_returns_none(self):
        self.assertIsNone(wr.room_differential(_recs(3, 10), (0, 0)))
        self.assertIsNone(wr.room_differential([], (3, 10)))

    def test_summarize_reports_diff_and_cluster_error(self):
        """两房：我方 50%/50%，对手 40%/60% ⇒ 差分 +0.10/−0.10，均值 0、SE>0。"""
        data = {"A": {"rooms": {"r1": _recs(5, 10), "r2": _recs(5, 10)},
                      "opp_by_room": {"r1": (12, 30), "r2": (18, 30)}}}
        st = wr.summarize(data)["A"]
        self.assertAlmostEqual(st["diff"], 0.0)
        self.assertGreater(st["se_diff"], 0.0)
        self.assertEqual(st["n_diff"], 2)

    def test_summarize_skips_rooms_without_opp_data(self):
        data = {"A": {"rooms": {"r1": _recs(5, 10)}, "opp_by_room": {}}}
        st = wr.summarize(data)["A"]
        self.assertEqual(st["n_diff"], 0)
        self.assertEqual(st["diff"], 0.0)


class TestCompare(unittest.TestCase):
    def test_uses_more_conservative_se(self):
        a = dict(win=0.25, rounds=10000, se_cluster=0.01)
        b = dict(win=0.27, rounds=10000, se_cluster=0.01)
        c = wr.compare(a, b)
        self.assertAlmostEqual(c["diff"], 0.02)
        self.assertEqual(c["note"], "cluster")
        self.assertGreater(c["se"], c["se_binom"])

    def test_identical_arms_give_zero(self):
        a = dict(win=0.25, rounds=1000, se_cluster=0.005)
        c = wr.compare(a, dict(a))
        self.assertEqual(c["diff"], 0.0)
        self.assertEqual(c["z"], 0.0)


class TestRoomsToFetch(unittest.TestCase):
    def test_tail_limit_and_since(self):
        rooms = [("r1", "s1", "2026-09-15 10:00:00"),
                 ("r2", "s2", "2026-09-16 10:00:00"),
                 ("r3", "s3", "2026-09-16 11:00:00")]
        todo = fr.rooms_to_fetch(rooms, ROOT, limit=1, since="2026-09-16 00:00:00")
        self.assertEqual([x[0] for x in todo], ["r3"])

    def test_limit_zero_means_all(self):
        rooms = [("r%d" % i, "s", "2026-09-16 10:00:00") for i in range(5)]
        self.assertEqual(len(fr.rooms_to_fetch(rooms, ROOT, limit=0)), 5)


if __name__ == "__main__":
    unittest.main()
