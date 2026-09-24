# -*- coding: utf-8 -*-
"""10/7 换臂链的**接线门**（R1436）。

为什么要这门外加一层：本轮的第一次接线就插错了位置 —— 新增的两行被放进了**头部注释**
（`findIndex` 命中了注释里的 "HangzhouMajFinalCheck2"），而 `_ps_syntax_check.ps1` 照样
报 "syntax OK"：插错位置属于"语法合法、语义全错"。同一轮还踩了第二个坑：**新 .ps1 没写 BOM**
⇒ PS 5.1 按 ANSI 解码中文注释 ⇒ 把后面的 `param` 块吃掉 ⇒ `$Root` 为 null。

这门外加两条静态断言把两件事都钉死：
  ① 注册语句必须**真的调用注册函数**（在行首、且参数写对），不是只在注释里提到；
  ② 带中文的 .ps1 必须**带 BOM**，且 `param` 之前不许有执行语句。
"""
from __future__ import annotations
import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "var", "_register_final_day.ps1")
PS1 = os.path.join(ROOT, "var", "_prepare_submission.ps1")
RETRY = os.path.join(ROOT, "var", "_final_switch_retry.ps1")
CONFIRM = os.path.join(ROOT, "var", "_final_arm_confirm.py")


def read(p):
    with io.open(p, encoding="utf-8-sig") as f:
        return f.read()


def read_raw(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


@unittest.skipUnless(os.path.exists(REG), "var/ 不在仓库里（gitignore）")
class TestFinalDayWiring(unittest.TestCase):
    def test_confirm_task_really_registered(self):
        s = read(REG)
        self.assertRegex(
            s,
            r'(?m)^Reg-One\s+"HangzhouMajFinalArmConfirm"\s+"2026-10-07 08:30:00"\s+"_final_arm_confirm\.py"',
            "HangzhouMajFinalArmConfirm 必须真的被 Reg-One 注册（行首调用，不能只在注释里）")

    def test_retry_task_really_registered(self):
        s = read(REG)
        self.assertIn('$retryName = "HangzhouMajFinalSwitchRetry"', s)
        self.assertRegex(s, r'Register-ScheduledTask -TaskName \$retryName',
                        "换臂重试必须真的 Register-ScheduledTask")
        self.assertIn('"2026-10-07 12:00:00"', s)
        self.assertIn("-WindowStyle Hidden", s, "后台任务不得弹窗")

    def test_param_is_first_statement(self):
        """param 之前只允许注释/空行 —— 否则 PS 会忽略默认值（本轮真实踩过）。"""
        lines = read(REG).splitlines()
        pi = next(i for i, l in enumerate(lines) if l.strip().startswith("param("))
        for l in lines[:pi]:
            t = l.strip()
            self.assertTrue(t == "" or t.startswith("#"),
                            "param 之前出现了语句：%r" % l)

    def test_new_files_in_closure_list(self):
        s = read(PS1)
        self.assertIn('"var/_final_arm_confirm.py"', s)
        self.assertIn('"var/_final_switch_retry.ps1"', s)

    def test_ps1_files_have_bom(self):
        """中文注释的 .ps1 必须带 BOM（PS 5.1 否则按 ANSI 解码，会吃掉 param 块）。"""
        for p in (REG, RETRY):
            self.assertTrue(read_raw(p).startswith("\ufeff"),
                            "%s 缺 BOM" % os.path.basename(p))

    def test_wrapper_is_rehearsable(self):
        """包装脚本必须能随时排练（-DryRun 全链路 --dry-run），否则只能等 10/7 才能验。"""
        s = read(RETRY)
        self.assertIn("[switch]$DryRun", s)
        self.assertIn("--dry-run", s)
        self.assertIn("--go", s)
        self.assertIn("_final_arm_confirm.py", s)
        self.assertIn("_switch_final.py", s)


@unittest.skipUnless(os.path.exists(CONFIRM), "var/ 不在仓库里（gitignore）")
class TestConfirmScriptInvariants(unittest.TestCase):
    def test_never_writes_arm_without_instantiation_check(self):
        """落盘前必须有 arm_ok 校验，且失败路径 return 2（顺序：校验在写之前）。"""
        s = read(CONFIRM)
        i_ok = s.index("ok, why = arm_ok(arm)")
        i_w = s.index('with io.open(a.out, "w"')
        self.assertLess(i_ok, i_w, "实例化校验必须在写入之前")
        self.assertIn("if not ok:", s[:i_w + 200])

    def test_refresh_cannot_downgrade(self):
        s = read(CONFIRM)
        self.assertIn("不降级", s)
        self.assertIn("--refresh", s)

    def test_fallback_when_no_ab_mode(self):
        # R1450：役收口会删 .ab_mode ⇒ 提案不能因此什么都不出（必须有回退窗口口径）
        src = read(os.path.join(ROOT, "var", "_final_pick_proposal.py"))
        self.assertIn("--fallback-days", src)
        self.assertIn("fallback = True", src)
        self.assertIn("回退口径", src)



@unittest.skipUnless(os.path.exists(os.path.join(ROOT, "var", "_final_pick_proposal.py")),
                     "var/ 不在仓库里（gitignore）")
class TestPickProposalStrata(unittest.TestCase):
    """10/5 选臂提案必须带**分层读数**（R1445）。

    为什么要钉：top32 只出现在"房里有 top32"的房里 ⇒ 单独的 top32 行本就是强手房口径；
    而"强手房 ≥1"与"强手房 ≥2（决赛相似层）"的优劣**可能方向相反**（役 2 本机实测过），
    正式赛是 16 人强场 ⇒ 提案若只给 §V.66 主序列（≥1 层），选臂时就会漏掉难点层的翻转。
    """

    def test_proposal_includes_verdict_by_elite(self):
        src = read(os.path.join(ROOT, "var", "_final_pick_proposal.py"))
        self.assertIn("_verdict_by_elite.py", src, "提案必须并读分层工具")
        self.assertIn("分层读数", src, "必须有一段明确标注的分层读数")
        self.assertIn("不改 §V.66 判据", src, "必须声明只加读数、不改判据")

    def test_verdict_by_elite_has_two_layer(self):
        src = read(os.path.join(ROOT, "var", "_verdict_by_elite.py"))
        self.assertIn("强手房>=2", src, "分层工具必须产出 >=2 名 top32 那一层（预登记 §8 必报）")


@unittest.skipUnless(os.path.exists(os.path.join(ROOT, "var", "_final_event_ready.py")),
                     "var/ 不在仓库里（gitignore）")
class TestEventReadyInsurance(unittest.TestCase):
    """R1452：10/10 19:25 的 T-5 保险必须是"开关感知"的，且**绝不自动使用逃生阀**。"""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "var"))
        import _final_event_ready as F
        self.F = F

    def test_plan(self):
        self.assertEqual("ready_only", self.F.plan(True))          # 已在官方模式 ⇒ 与旧行为一致
        self.assertEqual("switch_then_ready", self.F.plan(False))  # 不在 ⇒ 先重试上线

    def test_registrar_points_to_insurance(self):
        src = read(os.path.join(ROOT, "var", "_register_final_event.ps1"))
        self.assertIn("_final_event_ready.py", src, "19:25 任务必须调用保险脚本")

    def test_never_auto_passes_allow_not_ready(self):
        src = read(os.path.join(ROOT, "var", "_final_event_ready.py"))
        self.assertIn("AllowNotReady", src, "逃生阀应写进人工提示")
        self.assertNotIn(chr(34) + "-AllowNotReady" + chr(34), src,
                         "绝不把 -AllowNotReady 作为参数自动传给切换脚本（人做决定）")


@unittest.skipUnless(os.path.exists(os.path.join(ROOT, "var", "_gate2.py")),
                     "var/ 不在仓库里（gitignore）")
class TestGate2LowersPriority(unittest.TestCase):
    """R1458：判词工具由看护**每 10 分钟自动跑**（读 150–250 份复盘）。

    R1182 实测：A/B 期间跑重活会抬高提交延迟、丢动作 ⇒ 不降级会**既扰动正在判的数据、又实打实丢分**。
    """

    def test_gate2_lowers_self(self):
        src = read(os.path.join(ROOT, "var", "_gate2.py"))
        self.assertIn("lower_self", src, "必须自我降优先级")
        self.assertIn("[gate2]", src, "必须打印降级结果（便于日志核对）")


@unittest.skipUnless(os.path.exists(os.path.join(ROOT, "var", "_strong_veto.py")),
                     "var/ 不在仓库里（gitignore）")
class TestReplayHeavyToolsLowerPriority(unittest.TestCase):
    """R1459：会读上百份复盘的自动化工具必须自我降优先级。

    尤其是 `_strong_veto`：它在**判词那一刻**由 `_adopt_pair` 自动调用，若与正在打的对局抢 CPU，
    会抬高提交延迟、丢动作（R1182 实测）⇒ 既扰动正在判的数据、又实打实丢分。
    """

    def test_strong_veto_lowers_self(self):
        src = read(os.path.join(ROOT, "var", "_strong_veto.py"))
        self.assertIn("lower_self", src)
        self.assertIn("[strong_veto]", src)

    def test_strong_slice_lowers_self(self):
        src = read(os.path.join(ROOT, "var", "_strong_slice.py"))
        self.assertIn("lower_self", src)
        self.assertIn("[strong_slice]", src)


@unittest.skipUnless(os.path.exists(os.path.join(ROOT, "var", "_verdict_watch.py")),
                     "var/ 不在仓库里（gitignore）")
class TestBoxedSentinel(unittest.TestCase):
    """R1460（真缺口）：到役盒仍未决定性时，看护**也必须落 sentinel**。

    原实现只给决定性判词写 `.verdict_done_<label>`；而 §V.66 功率预算说"到 120 房/臂仍不可判定"是
    **预期落点** ⇒ 采用看护 `_adopt_when_ready` 永远等不到 sentinel ⇒ **役 2→役 3 在役盒处静默停摆**。
    读卡与 `_adopt_when_ready.classify()` 都写明"到盒应进下一役"，缺的只是这一步接线。
    """

    def test_boxed_writes_sentinel(self):
        src = read(os.path.join(ROOT, "var", "_verdict_watch.py"))
        idx_boxed = src.find("if boxed:")
        idx_else = src.find("    else:", idx_boxed)
        self.assertGreater(idx_boxed, 0, "必须有 boxed 分支")
        seg = src[idx_boxed:idx_else]
        self.assertIn("io.open(sent", seg, "boxed 分支必须写 sentinel")
        self.assertIn("BOXED", seg, "写入内容应标明是到盒收口（可审计）")

    def test_classify_accepts_boxed(self):
        sys.path.insert(0, os.path.join(ROOT, "var"))
        import _adopt_when_ready as A
        txt = "已达役盒（>= 120 房/臂仍未决定性）\n" + "\u2605 \u5224\u5b9a\uff1aUNDECIDED（和牌率 z=+1.27）"
        self.assertEqual("proceed", A.classify(txt)[0])



    def test_blocked_marker_has_rules_guard_fallback(self):
        """R1463：rules_guard 不匹配时 `-AllowNotReady` **绕不过**（它只管 preflight）。

        四测实测 YouCaiBiKao=false，但若正式赛改成 true，链上臂几乎都没有 ycbk 孪生 ⇒
        T-5 的 BLOCKED 提示里必须给出唯一已注册合规孪生（speedvalueycbk）的可照抄命令。
        """
        src = read(os.path.join(ROOT, "var", "_final_event_ready.py"))
        self.assertIn("rules_guard", src, "提示里必须点名 rules_guard")
        self.assertIn("speedvalueycbk", src, "必须给出合规孪生作为兜底")
        self.assertIn("-TokenFile %s -TournamentId <TID>", src)


if __name__ == "__main__":
    unittest.main()
