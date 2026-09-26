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

class TestPickDayCard(unittest.TestCase):
    """★ R1586：10/5（选臂提案日）的一屏版操作单。

    为什么：这是**人在 10/7 之前最后一个可以改变最终臂的时刻**，而此前只有 10/7 的卡与各役读卡。
    它必须与代码对得上：提案文件名、自动定臂任务名、以及“只能在已判正臂之间改选”这条纪律。"""

    def test_card_matches_code(self):
        p = os.path.join(ROOT, "docs", "iter", "reports", "pick-day-card-20261005.md")
        self.assertTrue(os.path.exists(p), p)
        c = read(p)
        self.assertIn("var/_final_pick_proposal.txt", c)
        self.assertIn("var/.final_arm.txt", c)
        self.assertIn(u"§V.161 A.1", c)
        self.assertIn("HangzhouMajFinalArmConfirm", c)
        vd = os.path.join(ROOT, "var")
        if os.path.isdir(vd):
            regs = u"".join(read(os.path.join(vd, f)) for f in os.listdir(vd)
                            if f.startswith("_register_") and f.endswith(".ps1"))
            self.assertIn("HangzhouMajFinalArmConfirm", regs,
                          u"卡上写的定臂任务名必须真在注册脚本里")

    def test_card_says_default_is_no_action(self):
        c = read(os.path.join(ROOT, "docs", "iter", "reports", "pick-day-card-20261005.md"))
        self.assertIn(u"什么都不用做", c)
        self.assertIn(u"不可区分", c)      # 用代码里的原词（_pick_arm 打的就是这四个字）
        self.assertIn(u"MDE", c)            # 不可区分 ≠ 没差别



class TestEventDayCard(unittest.TestCase):
    """★ R1587：10/10（正式赛当天）的一屏版操作单 —— 风险最高的一天。"""

    def test_card_matches_code(self):
        p = os.path.join(ROOT, "docs", "iter", "reports", "event-day-card-20261010.md")
        self.assertTrue(os.path.exists(p), p)
        c = read(p)
        self.assertIn("var/.token_final_20261010", c)
        self.assertIn(".EVENT_SWITCH_BLOCKED", c)
        self.assertIn("_switch_to_official.ps1", c)
        self.assertIn("AllowNotReady", c)
        for t in ("HangzhouMajFinalEventSwitch", "HangzhouMajFinalEventReady"):
            self.assertIn(t, c, t)
        self.assertIn("_exit_official.py", c)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "var", "_exit_official.py")))

    def test_escape_valve_is_gated(self):
        """逃生阀只能写成“有条件的人工决定”，不能写成默认动作。"""
        c = read(os.path.join(ROOT, "docs", "iter", "reports", "event-day-card-20261010.md"))
        self.assertIn(u"绝不自动使用", c)
        self.assertIn(u"人工确认", c)


class TestCardsDiscoverable(unittest.TestCase):
    """★ R1588：五张当天卡必须在**入口指引里列成一行** —— 敞在四处等于没有。"""

    CARDS = ("verdict-day-card-20260928.md", "pick-day-card-20261005.md",
             "final-switch-card-20261007.md", "submission-day-card.md",
             "event-day-card-20261010.md")

    def test_handoff_lists_all_cards(self):
        h = read(os.path.join(ROOT, "docs", "HANDOFF.md"))
        for c in self.CARDS:
            self.assertIn(c, h, u"HANDOFF 入口指引缺这张卡：" + c)

    def test_cards_exist(self):
        d = os.path.join(ROOT, "docs", "iter", "reports")
        for c in self.CARDS:
            self.assertTrue(os.path.exists(os.path.join(d, c)), c)

if __name__ == "__main__":
    unittest.main()
