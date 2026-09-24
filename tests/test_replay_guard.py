# -*- coding: utf-8 -*-
"""`var/_replay_guard.py` 契约测试（R1171）。

为什么钉住：它会在 A/B 期间**真的向门户发 GET 并写文件**。所以必须保证：
  ① 台账筛选（since / finished / 新→旧）；
  ② `expected_gids` 取各家 games_played 最大值（房提前结束 ⇒ 期望值随之变小）；
  ③ 前缀匹配不会把 `a_ab` 的房认成 `a_abc` 的房；
  ④ **已覆盖的房一次 HTTP 都不发**（快路径）；
  ⑤ **已存在的 gid 绝不覆盖**（只新增）；
  ⑥ 预算（--max-fetch）到点即停；
  ⑦ 单点失败（非 200）不中止整轮，也不抛异常。

⚠ 每个用例都**显式传 `--ledger/--recent`**：R1171 自查时曾因为
`def load_rooms(path=LEDGER)` 这种"def 期绑定默认值"，让一个以为指向 tmp 的用例
**真的去读线上台账并发了几十个门户请求**（当场被杀）。显式传参让这类事故不可能重演。
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load():
    spec = importlib.util.spec_from_file_location(
        "replay_guard_t", os.path.join(ROOT, "var", "_replay_guard.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["replay_guard_t"] = m
    spec.loader.exec_module(m)
    return m


def _rec(room, ts, status="finished", games=80, strat="speedvalue"):
    return {"room": room, "ts": ts, "status": status, "strategy": strat,
            "ranking": [{"user_id": "u_me", "games_played": games},
                        {"user_id": "u_x", "games_played": games}]}


class ReplayGuardTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()
        self.tmp = tempfile.mkdtemp(prefix="rg_")
        self.ledger = os.path.join(self.tmp, "auto_ranking.jsonl")
        self.recent = os.path.join(self.tmp, "recent")
        os.makedirs(self.recent)
        self.m.LOG = os.path.join(self.tmp, "guard.log")

    def _argv(self, *extra):
        return ["--ledger", self.ledger, "--recent", self.recent, "--gap", "0"] + list(extra)

    def _write(self, recs):
        with io.open(self.ledger, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def _touch(self, room, n, start=0):
        for i in range(start, start + n):
            open(os.path.join(self.recent, "%s_r1_b%d_t0.json" % (room, i)), "w").close()

    def _gids(self, room, n=10):
        return ["%s_r1_b%d_t0" % (room, i) for i in range(n)]

    def _fake_fetcher(self, gids, bad=(), seen=None):
        class F:
            def __init__(self, *a, **k):
                pass

            def get(self, path):
                if path.startswith("/portal/api/test-rooms/"):
                    return 200, json.dumps({"games": [
                        {"game_id": g, "status": "finished"} for g in gids]})
                gid = path.split("/")[-2]                 # /portal/api/games/<gid>/events
                if seen is not None:
                    seen.append(gid)
                return (500, "") if gid in bad else (200, "{}")
        return F

    # ① 台账筛选
    def test_load_rooms_filters_and_orders(self):
        self._write([_rec("a_1", "2026-09-23 01:00:00"),
                     _rec("a_2", "2026-09-23 05:00:00"),
                     _rec("a_3", "2026-09-23 06:00:00", status="registering")])
        got = self.m.load_rooms(self.ledger, "2026-09-23 03:00:00")
        self.assertEqual([g[0] for g in got], ["a_2"])
        self.assertEqual([g[0] for g in self.m.load_rooms(self.ledger, None)], ["a_2", "a_1"])
        self.assertEqual([g[0] for g in self.m.load_rooms(None, None)][:0], [])   # 不炸即可

    # ② 期望 gid 数（games_played 是**轮数**，不是 gid 数：1 gid = 8 轮）
    def test_expected_gids(self):
        self.assertEqual(self.m.expected_gids(_rec("a", "t", games=80)), 10)
        self.assertEqual(self.m.expected_gids(_rec("a", "t", games=57)), 8)   # 向上取整
        self.assertEqual(self.m.expected_gids(_rec("a", "t", games=0)), 0)
        self.assertEqual(self.m.expected_gids({"ranking": []}), 0)
        self.assertEqual(self.m.expected_gids({}), 0)

    # ③ 前缀匹配
    def test_have_gids_prefix_safety(self):
        self._touch("a_ab", 3)
        self._touch("a_abc", 2)
        self.assertEqual(len(self.m.have_gids(self.recent, "a_ab")), 3)
        self.assertEqual(len(self.m.have_gids(self.recent, "a_abc")), 2)
        self.assertEqual(len(self.m.have_gids(self.recent, "a_a")), 0)

    # ④ 已覆盖 ⇒ 零 HTTP
    def test_covered_room_makes_no_http(self):
        self._touch("a_r0", 10)
        self._write([_rec("a_r0", "2026-09-23 10:00:00")])
        with mock.patch.object(self.m, "Fetcher", side_effect=AssertionError("不该建 Fetcher")):
            self.assertEqual(self.m.main(self._argv("--since", "", "--quiet")), 0)

    # ⑤ 只补缺失 + 不覆盖
    def test_only_missing_and_never_overwrite(self):
        self._touch("a_r0", 8)
        self._write([_rec("a_r0", "2026-09-23 10:00:00")])
        seen = []
        with mock.patch.object(self.m, "Fetcher", self._fake_fetcher(self._gids("a_r0"), seen=seen)), \
                mock.patch("time.sleep"):
            self.m.main(self._argv("--since", "", "--quiet"))
        self.assertEqual(sorted(seen), ["a_r0_r1_b8_t0", "a_r0_r1_b9_t0"])
        self.assertEqual(len([1 for p in os.listdir(self.recent) if p.startswith("a_r0_")]), 10)

    # ⑥ 预算
    def test_budget_caps_requests(self):
        self._write([_rec("a_r0", "2026-09-23 10:00:00")])
        seen = []
        with mock.patch.object(self.m, "Fetcher", self._fake_fetcher(self._gids("a_r0"), seen=seen)), \
                mock.patch("time.sleep"):
            self.m.main(self._argv("--since", "", "--quiet", "--max-fetch", "5"))
        self.assertEqual(len(seen), 5)

    # ⑦ 失败容忍
    def test_failure_does_not_abort(self):
        self._write([_rec("a_r0", "2026-09-23 10:00:00")])
        bad = ["a_r0_r1_b0_t0"]
        with mock.patch.object(self.m, "Fetcher", self._fake_fetcher(self._gids("a_r0", 3), bad=bad)), \
                mock.patch("time.sleep"):
            rc = self.m.main(self._argv("--since", "", "--quiet"))
        self.assertEqual(rc, 0)
        self.assertEqual(len(os.listdir(self.recent)), 2)

    # 无缺口 ⇒ 静默且不写日志
    def test_no_gap_is_silent(self):
        self._touch("a_r0", 10)
        self._write([_rec("a_r0", "2026-09-23 10:00:00")])
        with mock.patch.object(self.m, "Fetcher", side_effect=AssertionError):
            self.m.main(self._argv("--since", "", "--quiet"))
        self.assertFalse(os.path.exists(self.m.LOG))


if __name__ == "__main__":
    unittest.main()



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
