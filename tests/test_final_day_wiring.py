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

    def test_switch_card_matches_ready_check_items(self):
        """★ R1573：`final-switch-card` 是 10/7 那天**照读**的东西 ⇒ 它写的“就绪校验（N 项）”
        必须等于 `_final_ready_check.py` 里的 chk 项数，且四个新事实（令牌/申报页/11:00、10/9）必须在卡上。"""
        import re
        card = read(os.path.join(ROOT, "docs", "iter", "reports", "final-switch-card-20261007.md"))
        src = read(os.path.join(ROOT, "var", "_final_ready_check.py"))
        # ★ 注意：同一个项号会因分支（PASS/FAIL）出现多次 chk 调用 ⇒ 必须数**不同项号**，不是调用次数。
        n = len(set(re.findall(r'chk\("(\d+) ', src)))
        m = re.search(u"就绪校验（\\*\\*(\\d+) 项\\*\\*）", card)
        self.assertIsNotNone(m, u"操作卡里没有‘就绪校验（N 项）’")
        self.assertEqual(n, int(m.group(1)),
                         u"操作卡写 %s 项，脚本实际 %d 项 ⇒ 卡已过期" % (m.group(1), n))
        for k in (".token_final_20261010", ".SUBMITTED_FORM", "11:00", "10/9"):
            self.assertIn(k, card, k)

    def test_check3_really_registered(self):
        """★ R1563：T-1 天的第三次就绪校验必须**真的被注册**（行首调用，不能只在注释里）。"""
        s = read(REG)
        self.assertRegex(
            s,
            r'(?m)^Reg-One\s+"HangzhouMajFinalCheck3"\s+"2026-10-09 09:00:00"\s+"_final_ready_check\.py"',
            "HangzhouMajFinalCheck3（T-1 天）必须真的被 Reg-One 注册")

    def test_ready_check_includes_event_token(self):
        """★ R1563：就绪校验必须把**唯一人工输入**（10/10 令牌）列为一项。
        注意：该文件用的是**字面 \\uXXXX 转义** ⇒ 断言只能用 ASCII 子串。"""
        src = read(os.path.join(ROOT, "var", "_final_ready_check.py"))
        self.assertIn(".token_final_20261010", src)
        self.assertIn("8 10/10", src)
        self.assertIn("fail-closed", src)
        # ★ R1565：第九项 = 人工申报页提交收据（机器只能推仓，不能替人交表）。
        self.assertIn(".SUBMITTED_FORM", src)
        self.assertIn("12:00", src)

    def test_submit_retry_really_registered(self):
        """★ R1569：10/8 提交失败不能静默 —— 11:00 必须真的有一次自动重试。"""
        s = read(REG)
        self.assertRegex(
            s,
            r'(?m)^Reg-One\s+"HangzhouMajFinalSubmitRetry"\s+"2026-10-08 11:00:00"\s+"_submit_final\.py"',
            "HangzhouMajFinalSubmitRetry（10/8 11:00）必须真的被 Reg-One 注册")

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
        # ★ R1564：不只要“注释里有”——该标签必须打在**提案正文**里（人读的是正文）。
        # 该文件正文用的是**字面 \\uXXXX 转义** ⇒ 断言必须用 raw 字面量。
        self.assertIn(r"\u8de8\u591a\u4e2a\u5f79\u6b21", src)
        self.assertIn(r"\u4e0d\u53ef\u5f53\u67d0\u4e00\u5f79\u7684\u5224\u8bcd", src)



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


    def test_campaign_ready_runs_prereg_format_gate(self):
        """★ R1506：起役前体检必须跑**预登记格式门**（只查“存在/未作废”会放行缺项的判据）。"""
        import tempfile
        sys.path.insert(0, os.path.join(ROOT, "var"))
        import _campaign_ready as C
        real = os.path.join(ROOT, "docs", "iter", "reports",
                            "prereg-campaign8-combo-20260925.md")
        self.assertTrue(os.path.exists(real), real)
        ok, msg = C.check_prereg_format(real)
        self.assertTrue(ok, "campaign8（决定最终臂的那份）必须格式合格：%s" % msg)
        fd, bad = tempfile.mkstemp(prefix="prereg-selftest-", suffix=".md")
        os.close(fd)
        with io.open(bad, "w", encoding="utf-8") as f:
            f.write("# 只有标题，没有任何必需项\n")
        ok2, _ = C.check_prereg_format(bad)
        self.assertFalse(ok2, "缺项预登记必须判不合格（否则格式门是空跑）")

    def test_m_high_marker_written_and_cleared(self):
        """★ R1504：M>10 必须落**可见标记** .EVENT_M_HIGH（不能只埋日志）；M≤10 自动清除。"""
        import tempfile
        sys.path.insert(0, os.path.join(ROOT, "var"))
        import _final_event_switch as S
        tok = os.path.join(ROOT, "var", ".token_4test_20260924")
        if not os.path.exists(tok):
            self.skipTest("缺 var/.token_4test_20260924（clone）")
        self.assertIsNone(S.m_high_note(10))
        self.assertIsNone(S.m_high_note(None))
        self.assertIn("M=16", S.m_high_note(16))
        fd, armfile = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        with io.open(armfile, "w", encoding="utf-8") as f:
            f.write("speedvaluebc")
        fd2, mfile = tempfile.mkstemp(suffix=".mk")
        os.close(fd2)
        os.remove(mfile)
        olds = (S.log, S.rules_guard_rc, S.registered_arms, S.M_HIGH, sys.argv)
        try:
            S.log = lambda m: None
            S.M_HIGH = mfile
            S.registered_arms = lambda: set()
            sys.argv = ["x", "--dry-run", "--final-file", armfile,
                        "--token-file", tok, "--tid", "t_x"]
            import contextlib
            S.rules_guard_rc = lambda a, t, server=None: (
                0, '锦标赛 config：{"M": 16, "Rounds": 16, "YouCaiBiKao": false}')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, S.main())
            self.assertTrue(os.path.exists(mfile), "M=16 必须落 .EVENT_M_HIGH")
            self.assertIn("M=16", io.open(mfile, encoding="utf-8").read())
            S.rules_guard_rc = lambda a, t, server=None: (
                0, '锦标赛 config：{"M": 10, "Rounds": 16, "YouCaiBiKao": false}')
            with contextlib.redirect_stdout(io.StringIO()):
                S.main()
            self.assertFalse(os.path.exists(mfile), "M=10 必须自动清除")
        finally:
            S.log, S.rules_guard_rc, S.registered_arms, S.M_HIGH, sys.argv = olds

    def test_config_summary_parses_event_M(self):
        """★ R1504：18:50 要在日志里记下赛事的 M（正式赛 M 未知；M 直接决定延迟风险）。"""
        sys.path.insert(0, os.path.join(ROOT, "var"))
        import _final_event_switch as S
        line = '锦标赛 config：{"M": 10, "Rounds": 16, "BaseScore": 1, "YouCaiBiKao": true}'
        self.assertEqual((10, 16, True), S.config_summary(line))
        self.assertEqual((None, None, None), S.config_summary("noise only"))
        self.assertEqual((None, None, None), S.config_summary(None))

    def test_event_switch_wiring_actually_switches_arm(self):
        """★ R1503 接线级：不只是纯函数对，**`main()` 真跑时也会把上线臂换成孪生**（dry-run，不执行、不落标记）。"""
        import tempfile
        sys.path.insert(0, os.path.join(ROOT, "var"))
        import _final_event_switch as S
        tok = os.path.join(ROOT, "var", ".token_4test_20260924")
        if not os.path.exists(tok):
            self.skipTest("缺 var/.token_4test_20260924（clone）")
        lines = []
        old_log, old_rc, old_reg = S.log, S.rules_guard_rc, S.registered_arms
        fd, armfile = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        with io.open(armfile, "w", encoding="utf-8") as f:
            f.write("speedvaluebc")
        old_argv = sys.argv
        try:
            S.log = lambda m: lines.append(str(m))
            S.rules_guard_rc = lambda arm, tf, server=None: (2, "自测：需闸门臂")
            S.registered_arms = lambda: {"speedvaluebcycbk"}
            sys.argv = ["_final_event_switch.py", "--dry-run", "--final-file", armfile,
                        "--token-file", tok, "--tid", "t_selftest"]
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):   # 被测脚本会 print（保持测试输出干净）
                rc = S.main()
        finally:
            S.log, S.rules_guard_rc, S.registered_arms = old_log, old_rc, old_reg
            sys.argv = old_argv
        self.assertEqual(0, rc, lines)
        joined = "\n".join(lines)
        self.assertIn("speedvaluebcycbk", joined, "main() 没把上线臂换成孪生：%s" % joined)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "var", ".EVENT_SWITCH_BLOCKED")),
                         "dry-run 不得落真标记")

    def test_event_switch_auto_maps_to_registered_twin(self):
        """★ R1503：18:50 自动上线时，若赛事要求 YCBK 闸门，必须**自动**换成已注册的同剂量孪生（不能等人）。"""
        sys.path.insert(0, os.path.join(ROOT, "var"))
        import _final_event_switch as S
        from run_bot import STRATEGY_FACTORIES as F
        reg = set(F)
        self.assertIn("speedvaluebcycbk", reg, "链上孪生必须已注册，否则自动映射无从谈起")
        self.assertEqual("speedvaluebcycbk", S.resolve_event_arm("speedvaluebc", 2, reg)[0])
        # rc=2 但孪生未注册 ⇒ **不猜**，保持原臂（交给权威 rules_guard 挡下并落标记）
        self.assertEqual("speedvaluebc", S.resolve_event_arm("speedvaluebc", 2, set())[0])
        # rc=0（不需闸门）/ rc=None（判不了）⇒ 原臂
        self.assertEqual("speedvaluebc", S.resolve_event_arm("speedvaluebc", 0, reg)[0])
        self.assertEqual("speedvaluebc", S.resolve_event_arm("speedvaluebc", None, reg)[0])
        # 覆盖面空洞：役 3→役 5 每一根都必须能被映射到（否则 10/10 会变成“上不了线”）
        for base in ("speedc151", "speedvaluebc", "speedvaluebcv", "speedvaluebcmeld",
                     "speedvaluebcmeldp45", "speedvaluebcvmeld", "speedvaluebcvmeldp40",
                     "speedvaluebcvmeldp35", "speedvaluemeld", "speedvaluemeldp45",
                     "speedvaluemeldp40", "speedvaluebaotouv5", "speedvaluebaotouvmeld"):
            self.assertEqual(base + "ycbk", S.resolve_event_arm(base, 2, reg)[0],
                             "%s 在 YCBK=true 下无孪生可换" % base)


if __name__ == "__main__":
    unittest.main()
