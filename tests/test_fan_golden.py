"""mahjong/fan 黄金集回归：与服务器 fan-calc 缓存响应逐例比对（离线，零网络）。

黄金集：testdata/fan_calc_golden.json（tools/align_fan_calc.py 拉取缓存）。
KNOWN-DELTA 用例（服务器判定与本引擎差异已记录在案）跳过 fan 比对，仅防静默漂移。
"""
import json
import os
import unittest

from mahjong.fan import calc

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "..", "testdata", "fan_calc_golden.json")

# 与 tools/align_fan_calc.py 的 KNOWN_DELTA_CASES 保持一致
KNOWN_DELTA = {
    (("1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t", "4w", "白", "白", "白"), "东"),
    (("1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t", "中", "白", "白", "白"), "西"),
    (("1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t", "东", "白", "白", "白"), "南"),
    (("1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t", "4w", "白", "白", "白"), "5w"),
}


def _load_golden():
    if not os.path.exists(GOLDEN):
        raise unittest.SkipTest("黄金集缺失：先运行 python tools/align_fan_calc.py --refresh")
    with open(GOLDEN, encoding="utf-8") as f:
        return json.load(f)


class TestFanAgainstGolden(unittest.TestCase):
    def test_all_golden_records(self):
        mismatch = []
        n = 0
        for r in _load_golden():
            resp = r.get("resp") or {}
            if "error" in resp:
                continue
            hand, draw = r["hand"], r["draw"]
            if (tuple(hand), draw) in KNOWN_DELTA:
                continue
            if not resp.get("hu"):
                continue            # 非胡记录仅 hu 位参与对齐（tools 已比对）
            mine = calc(hand, draw, r.get("chain"))
            n += 1
            for key in ("hu", "baotou", "fan", "detail", "scores"):
                if mine.get(key) != resp.get(key):
                    mismatch.append((hand, draw, key, mine.get(key), resp.get(key)))
                    if len(mismatch) >= 5:
                        break
            if len(mismatch) >= 5:
                break
        self.assertEqual(mismatch, [],
                         "fan 黄金集不一致 %d 例（前5）：%r" % (len(mismatch), mismatch))
        self.assertGreaterEqual(n, 10, "可比的胡牌黄金记录过少: %d" % n)

    def test_known_delta_still_registered(self):
        """known-delta 用例仍可拉到服务器缓存（防止黄金集悄悄缩水）。"""
        recs = _load_golden()
        keys = {(tuple(r["hand"]), r["draw"]) for r in recs}
        for k in KNOWN_DELTA:
            self.assertIn(k, keys, "known-delta 用例丢失: %s" % (k,))


if __name__ == "__main__":
    unittest.main()
