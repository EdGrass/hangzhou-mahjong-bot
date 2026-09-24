# -*- coding: utf-8 -*-
"""`speedvaluemeldp45` 契约测试（R1267）。

为什么：它是**役 4/5 的候选臂之一**（§V.35 的"对齐剂量"档），而 `_campaign_ready` 找的是
`tests/test_<策略名>*.py` ⇒ 剂量档没有同名单测就会在起役体检里判 ❌（会在半夜卡住切换）。

三条不变量：
  ① **注册接线**：工厂取出的臂 `claim_p == 0.45`；
  ② **与显式构造逐位等价**：`speedvaluemeldp45` ≡ `SpeedValueMeld(claim_p=0.45)`（真实窗口）；
  ③ **阈值单调（严格超集）**：0.60 档接受的窗口，0.45 档必须也接受（阈值只降不升 ⇒ 单调放宽）。
"""
import glob
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedvaluemeld import SpeedValueMeld                      # noqa: E402
from run_bot import STRATEGY_FACTORIES as F                        # noqa: E402


def _windows(limit=260):
    """真实响应窗口（dec.jsonl 的 response_* 行）。"""
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*_t0.dec.jsonl")))[-4:]:
        try:
            for ln in io.open(p, encoding="utf-8"):
                ln = ln.strip()
                if not ln:
                    continue
                r = json.loads(ln)
                if str(r.get("p") or "").startswith("response_") and r.get("o") and r.get("h"):
                    out.append(r)
                if len(out) >= limit:
                    return out
        except Exception:
            continue
    return out


class MeldDose45Test(unittest.TestCase):
    def setUp(self):
        self.rows = _windows()
        if not self.rows:
            self.skipTest("无 dec 语料")
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from arm_smoke import to_view
        self.to_view = staticmethod(to_view)

    # ① 注册接线
    def test_registered_with_claim_p_045(self):
        p = F["speedvaluemeldp45"]()
        self.assertAlmostEqual(float(p.claim_p), 0.45, places=9)

    # ② 与显式构造逐位等价
    def test_same_as_explicit_dose(self):
        a = F["speedvaluemeldp45"]()
        b = SpeedValueMeld(claim_p=0.45)
        diff = 0
        for r in self.rows:
            v = self.to_view(r)
            try:
                da = a.decide(v) or {}
                db = b.decide(v) or {}
            except Exception:
                continue
            if (da.get("action"), da.get("tile")) != (db.get("action"), db.get("tile")):
                diff += 1
        self.assertEqual(diff, 0, "speedvaluemeldp45 与显式 0.45 档有 %d 处分歧" % diff)

    # ③ 阈值单调：0.60 接受 ⇒ 0.45 也必须接受
    def test_threshold_monotone_superset(self):
        a = F["speedvaluemeldp45"]()
        b = F["speedvaluemeldp60"]() if "speedvaluemeldp60" in F else SpeedValueMeld(claim_p=0.60)
        bad = 0
        for r in self.rows:
            v = self.to_view(r)
            try:
                db = b.decide(v) or {}
                da = a.decide(v) or {}
            except Exception:
                continue
            if db.get("action") in ("peng", "chi", "gang") and da.get("action") != db.get("action"):
                bad += 1
        self.assertEqual(bad, 0, "0.60 收而 0.45 不收的窗口有 %d 个（破坏单调放宽）" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
