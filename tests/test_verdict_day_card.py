# -*- coding: utf-8 -*-
"""★ R1585：`verdict-day-card-20260928.md`（**役3 判词当天的一屏版**）防飘门。

为什么：读卡有 17KB（含历史），赶时间时人只会看这张卡 ⇒ 它写错一个落点/窗口，
就是当天的直接代价。本文件把它与**读卡 §3 的四格表**、**真机 `.ab_mode.started`**、**阴影红线**对账。
"""
from __future__ import annotations
import io
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARD = os.path.join(ROOT, "docs", "iter", "reports", "verdict-day-card-20260928.md")
READ = os.path.join(ROOT, "docs", "iter", "reports", "yaku3-verdict-readcard.md")


def read(p):
    with io.open(p, encoding="utf-8-sig") as f:
        return f.read()


class TestVerdictDayCard(unittest.TestCase):
    def test_exists_and_has_three_rows(self):
        self.assertTrue(os.path.exists(CARD), CARD)
        c = read(CARD)
        for arm in ("speedvaluebcmeldp45", "speedvaluebaotouvmeld", "speedvaluemeldp45"):
            self.assertIn(arm, c, arm)
            self.assertIn(arm, read(READ), u"卡里的落点必须与读卡 §3 一致：" + arm)

    def test_redlines_present(self):
        c = read(CARD)
        self.assertIn(u"绝不手改", c)          # 不手改验证文件
        self.assertIn(u"没有", c)                    # “没有等人工破平的窗口”
        self.assertIn(u"B2", c)                             # 未判正只作旁证

    def test_window_matches_live_ab_mode(self):
        p = os.path.join(ROOT, "var", ".ab_mode")
        if not os.path.exists(p):
            self.skipTest(u"无 .ab_mode（役已收口或 var/ 不在）")
        cfg = json.loads(read(p))
        since = cfg.get("started") or ""
        if not since:
            self.skipTest(u".ab_mode 无 started")
        self.assertIn(since, read(CARD), u"卡上的 `--since` 必须等于当前役的 started")
