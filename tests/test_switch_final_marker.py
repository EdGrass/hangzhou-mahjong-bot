# -*- coding: utf-8 -*-
"""`var/_switch_final.marker_text` \u7684\u5355\u6d4b\uff1a10/7 \u5b89\u88c5\u51ed\u8bc1\u91cc\u5fc5\u987b\u5e26\u7740 **10/10 \u53ef\u76f4\u63a5\u6267\u884c\u7684\u6b63\u5f0f\u8d5b\u547d\u4ee4**\u3002

\u4e3a\u4ec0\u4e48\u8981\u9489\uff1a\u6b63\u5f0f\u8d5b\u5f53\u5929\u8981\u628a\u540c\u4e00\u4e2a\u81c2\u4f20\u7ed9 `_switch_to_official.ps1`\uff1b\u82e5\u51ed\u8bc1\u91cc\u53ea\u6709\u201c\u88c5\u4e86\u54ea\u4e2a\u81c2\u201d
\u800c\u6ca1\u6709\u547d\u4ee4\uff0c\u4e34\u573a\u53c8\u8981\u62fc\u53c2\u6570\uff08\u800c\u4e14\u5fc5\u987b\u786e\u4fdd\u7528\u7684\u5c31\u662f\u88c5\u597d\u7684\u90a3\u4e2a\u81c2\uff09\u3002
"""
from __future__ import annotations
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _switch_final as SF  # noqa: E402


class TestMarkerText(unittest.TestCase):
    def test_contains_arm_and_commands(self):
        t = SF.marker_text("speedvaluebcvmeldp40", [1234])
        self.assertIn("arm=speedvaluebcvmeldp40", t)
        self.assertIn("keeper=[1234]", t)
        self.assertIn("_ready_1024.py --tid <TID> --token-file <TOK>", t)
        self.assertIn("-Strategy speedvaluebcvmeldp40", t)
        self.assertIn("_switch_to_official.ps1", t)

    def test_allow_not_ready_only_as_note(self):
        t = SF.marker_text("speedvalue", [1])
        cmd = [l for l in t.splitlines() if "_switch_to_official.ps1" in l][0]
        self.assertNotIn("-AllowNotReady", cmd)
        self.assertIn("-AllowNotReady", t)


class TestR1444DeadlockAndGuard(unittest.TestCase):
    """★ R1444：10/7 换臂链的两个真雷（本机 watchdog 日志/rate_guard 源码实证）。

    ① **死等 keeper**：原等待条件是 run_bot + match_super + **_keeper** 三者全无，
       但 watchdog 每 90 秒必把 keeper 拉回来（日志 09-23 03:07:50 / 03:09:20 恰好 90s）
       ⇒ 25 分钟必然超时 ⇒ 换臂失败。
    ② **熔断静默回退**：A/B 一停、.official_mode 未写时 rate_guard 生效，
       40 房净胜 < −40 ⇒ 把 _keeper_strategy.txt 改回 speedtugc ⇒ 刚装上的最终臂被改掉。
    """

    def test_wait_patterns_excludes_keeper(self):
        pats = SF.wait_patterns()
        self.assertIn("run_bot.py", pats)
        self.assertIn("match_super.py", pats)
        self.assertNotIn("_keeper.py", pats)      # ← 死等的根因，必须不在等待集合里

    def test_guard_off_path(self):
        self.assertTrue(SF.GUARD_OFF.endswith(".rate_guard_off"))

    def test_main_flow_order_and_guard_off(self):
        """接线条：主流程必须 先写策略 → 杀 keeper → 用 wait_patterns 等对局 → 成功后关熔断。"""
        import io as _io
        src = _io.open(os.path.join(ROOT, "var", "_switch_final.py"),
                       encoding="utf-8-sig").read()
        i_write = src.index("已写 _keeper_strategy.txt")
        i_kill = src.index("kk = kill_keepers()")
        i_wait = src.index("alive = [x for pat in wait_patterns()")
        i_guard = src.index("io.open(GUARD_OFF")
        self.assertLess(i_write, i_kill, "必须先写策略文件再杀 keeper（否则 watchdog 会按旧策略重启）")
        self.assertLess(i_kill, i_wait, "必须先杀 keeper 再等对局结束（否则会不停起新房，等不到空档）")
        self.assertLess(i_wait, i_guard, "关熔断应在换臂流程之后")
        # 绝不再把 keeper 并进等待集合
        wait_src = src.split("alive = [x for pat in")[1].split("if not alive")[0]
        self.assertNotIn("_keeper.py", wait_src)



if __name__ == "__main__":
    unittest.main()