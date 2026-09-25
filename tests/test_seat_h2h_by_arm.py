# -*- coding: utf-8 -*-
"""★ R1501：`_seat_h2h.py` 的**按臂「另三家」行必须是真数字**（回归门）。

为什么钉：`_pick_arm.py`（10/5 定臂 + §V.66 ② 两半 Pareto 破平）**强制**用 `--top 32` 调用本工具；
旧实现只在 `--top` 时往 `top` / `other` 两个键写数据、**从不写 `oth`**，而每臂那行读的正是 `oth`
⇒ 每臂「另三家」恒为 `0 局 / 0.00% / +0.00`（**看着像“对手不赢分、不胡牌”**）。
这是**决策链上会被读错的一列**，而且第一次跑出来是“看着正常”的绿 —— 所以用测试钉住。

本测试自造最小台账 + 最小复盘（不依赖 `var/` 真数据），钉两件事：
  ① 每臂「另三家」局数 > 0（不再恒 0）；
  ② `--top` 时**每臂**也有 `vs TOPn` / `vs 非TOP` 分层行（旧实现只有全局 `★` 行有分层）。
"""
from __future__ import annotations
import io, json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"
TOP = "u_top00000001"
OTH1 = "u_oth00000001"
OTH2 = "u_oth00000002"
ROOM = "a_testrm0001"
SINCE = "2026-09-20 00:00:00"
TS = "2026-09-25 12:00:00"


def _replay():
    ended = {"type": "round_ended", "seat": 0,
             "data": {"scores": [30, -10, -10, -10], "fan": 3, "detail": ["爆头"]}}
    meld = {"type": "peng", "seat": 1}
    return {"game_id": ROOM + "_r1_b0_t0",
            "seats": [{"user_id": ME}, {"user_id": TOP}, {"user_id": OTH1}, {"user_id": OTH2}],
            "blocks": [{"events": [ended, meld]}]}


class TestSeatH2HByArm(unittest.TestCase):
    def _run(self, extra):
        with tempfile.TemporaryDirectory() as td:
            ledger = os.path.join(td, "ledger.jsonl")
            with io.open(ledger, "w", encoding="utf-8") as f:
                f.write(json.dumps({"room": ROOM, "strategy": "arm_A", "ts": TS,
                                    "status": "finished"}) + "\n")
            rep = os.path.join(td, "rep.json")
            with io.open(rep, "w", encoding="utf-8") as f:
                f.write(json.dumps(_replay(), ensure_ascii=False))
            cmd = [sys.executable, "-X", "utf8", os.path.join("var", "_seat_h2h.py"),
                   "--since", SINCE, "--by-arm", "--ledger", ledger, "--replays", rep] + list(extra)
            return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)

    def test_by_arm_others_is_not_silently_zero(self):
        r = self._run(["--top", "32", "--top-uids", TOP])
        self.assertEqual(0, r.returncode, r.stderr)
        lines = [l for l in r.stdout.splitlines() if l.startswith("arm_A 另三家")]
        self.assertEqual(1, len(lines), r.stdout)
        rounds = int(lines[0].split("局")[1].split("|")[0].strip())
        self.assertGreater(rounds, 0, "每臂「另三家」被静默写成 0（这就是 R1501 的回归）")
        self.assertTrue(any(l.startswith("arm_A vs TOP32") for l in r.stdout.splitlines()), r.stdout)
        self.assertTrue(any(l.startswith("arm_A vs 非TOP") for l in r.stdout.splitlines()), r.stdout)

    def test_without_top_still_works(self):
        r = self._run([])
        self.assertEqual(0, r.returncode, r.stderr)
        lines = [l for l in r.stdout.splitlines() if l.startswith("arm_A 另三家")]
        self.assertEqual(1, len(lines), r.stdout)
        self.assertGreater(int(lines[0].split("局")[1].split("|")[0].strip()), 0)


if __name__ == "__main__":
    unittest.main()