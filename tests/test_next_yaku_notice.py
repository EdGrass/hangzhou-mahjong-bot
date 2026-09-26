# -*- coding: utf-8 -*-
"""`var/_next_yaku_notice.py` 的单测（R1476）。

为什么要钉：链上只有 `AdoptWatch`（役 2）与 `AdoptPairWatch`（役 3→役 4）两个自动推进器，
**役 4 判词落地后没有任何计划任务去消费它** ⇒ 默认会“继续跑役 4 超过役盒 + 役 5 永远不起”。
本脚本不自动起役（因为 §V.186 对候选臂剂量口径留了一个未定选择），只把“该决定了 + 可照拄命令”摆出来。
下面钉死：① 四格判据与 §V.186 逐字一致；② 命令里必须带对基线/候选/机制；
③ 缺任一输入（例如役 4 还没起）⇒ **一字不写**；④ 幂等（已提醒过不重复写）。
"""
from __future__ import annotations
import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _next_yaku_notice as N  # noqa: E402


def _write(d, name, text):
    with io.open(os.path.join(d, name), "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _fixture(d, meld_line, bc_line="★ 室判：ADOPT speedvaluebc", v_line="★ 室判：ADOPT speedvaluebaotouv5"):
    _write(d, ".adopted_pair_役3",
           "2026-09-29 03:00:00 row=a base=speedvaluebc cands=speedvaluebcmeldp45\n")
    _write(d, ".verdict_done_役4speedvaluebcmeldp45", "x")
    _write(d, "_verdict_役4speedvaluebcmeldp45.txt", meld_line + "\n")
    _write(d, ".verdict_done_役3bc", "x")
    _write(d, "_verdict_役3bc.txt", bc_line + "\n")
    _write(d, ".verdict_done_役3v", "x")
    _write(d, "_verdict_役3v.txt", v_line + "\n")


ADOPT4 = "★ 判定：ADOPT speedvaluebcmeldp45（和牌率 z=+2.1、机制通过）"
ADOPT_BC = "★ 判定：ADOPT speedvaluebc"
ADOPT_V = "★ 判定：ADOPT speedvaluebaotouv5"
REJ_4 = "★ 判定：UNDECIDED（和牌率 z=+1.1）⇒ 继续攒房"


class TestPure(unittest.TestCase):
    def test_last_verdict_line_takes_last(self):
        t = "★ 判定：ADOPT a\n★ 判定：REJECT b\n"
        self.assertEqual("REJECT b", N.last_verdict_line(t))

    def test_is_adopt(self):
        self.assertTrue(N.is_adopt("ADOPT x"))
        self.assertTrue(N.is_adopt("adopt x"))
        self.assertFalse(N.is_adopt("UNDECIDED"))
        self.assertFalse(N.is_adopt(""))

    def test_verdict_label_matches_registrar(self):
        self.assertEqual("役4speedvaluebcmeldp45", N.verdict_label("役4", "speedvaluebcmeldp45"))
        self.assertEqual("役3bc", N.verdict_label("役3", "bc"))

    def test_parse_pair_marker(self):
        row, base, cands = N.parse_pair_marker("2026-09-29 03:00:00 row=a base=speedvaluebc cands=x,y\n")
        self.assertEqual("a", row)
        self.assertEqual("speedvaluebc", base)
        self.assertEqual("x,y", cands)
        self.assertEqual(("", "", ""), N.parse_pair_marker(""))

    def test_decide_section_v186(self):
        k, why, cmds = N.decide(True, True, True, "speedvaluebc", "speedvaluebcmeldp45")
        self.assertEqual("start", k)
        self.assertEqual(2, len(cmds))
        self.assertEqual("speedvaluebcmeldp45", cmds[0][0])
        self.assertEqual("speedvaluebcvmeld", cmds[0][1])
        self.assertEqual("speedvaluebcvmeldp40", cmds[1][1])
        # 单层 ⇒ 不起役 5
        self.assertEqual("no_yaku5", N.decide(True, True, False, "b", "c")[0])
        self.assertEqual("no_yaku5", N.decide(True, False, True, "b", "c")[0])
        # 副露判负 + 两层都判正 ⇒ 列 BC+V 组合臂选项（不当默认）
        k, why, cmds = N.decide(False, True, True, "b", "c")
        self.assertEqual("combo_option", k)
        self.assertEqual([("speedvalue", "speedvaluebcv")], cmds)
        self.assertEqual("no_yaku5", N.decide(False, True, False, "b", "c")[0])


class TestEndToEnd(unittest.TestCase):
    def test_no_pair_marker_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(0, N.main(["--label", "役4", "--var-dir", d]))
            self.assertFalse(os.path.exists(os.path.join(d, ".YAKU_NEXT_PENDING")))

    def test_start_branch_writes_copyable_command(self):
        with tempfile.TemporaryDirectory() as d:
            _fixture(d, ADOPT4, ADOPT_BC, ADOPT_V)
            self.assertEqual(0, N.main(["--label", "役4", "--var-dir", d]))
            body = io.open(os.path.join(d, ".YAKU_NEXT_PENDING"), encoding="utf-8").read()
            self.assertIn("--label 役5", body)
            self.assertIn("--baseline speedvaluebcmeldp45", body)
            self.assertIn("--candidates speedvaluebcvmeld ", body + " ")
            self.assertIn("--candidates speedvaluebcvmeldp40", body)
            self.assertIn("--watch-mechanism none", body)

    def test_boxed_verdict_says_not_a_reject(self):
        """★ R1556：役 4 判词是 **BOXED（到盛未决定）** 时，提醒必须说清“**不是判负**”

        并指向读卡 §0 的**人工定性**路径（预登记下 A/B 行副端点只需‘同号’）。
        否则人会把“到盛仍不决定”误读成“这一层没用”，直接放弃组合臂。
        """
        boxed = u"★ 判定：BOXED（达役盒未决定性，按§V.66破平收口）"
        with tempfile.TemporaryDirectory() as d:
            _fixture(d, boxed, ADOPT_BC, ADOPT_V)
            self.assertEqual(0, N.main(["--label", "役4", "--var-dir", d]))
            body = io.open(os.path.join(d, ".YAKU_NEXT_PENDING"), encoding="utf-8").read()
            self.assertIn(u"不是判负", body)
            self.assertIn(u"yaku4-verdict-readcard.md §0", body)
            self.assertIn(u"人工定性", body)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            _fixture(d, ADOPT4, ADOPT_BC, ADOPT_V)
            N.main(["--label", "役4", "--var-dir", d])
            first = io.open(os.path.join(d, ".YAKU_NEXT_PENDING"), encoding="utf-8").read()
            N.main(["--label", "役4", "--var-dir", d])
            second = io.open(os.path.join(d, ".YAKU_NEXT_PENDING"), encoding="utf-8").read()
            self.assertEqual(first, second)
            self.assertTrue(os.path.exists(os.path.join(d, ".next_yaku_notice_役4")))

    def test_meld_rejected_says_no_new_yaku(self):
        # \u53ea\u6709\u5355\u5c42\u5224\u6b63\uff08BC \u2713 / V \u2717\uff09+ \u526f\u9732\u672a\u5224\u6b63 \u21d2 \u771f\u7684\u6ca1\u6709\u53ef\u9009\u7ec4\u5408\u81c2\n
        with tempfile.TemporaryDirectory() as d:
            _fixture(d, REJ_4, ADOPT_BC, "\\u2605 \\u5224\\u5b9a\\uff1aUNDECIDED\uff08z=+0.9\uff09")
            N.main(["--label", "役4", "--var-dir", d])
            body = io.open(os.path.join(d, ".YAKU_NEXT_PENDING"), encoding="utf-8").read()
            self.assertIn("FinalPickProposal", body)
            self.assertNotIn("--label 役5", body)

    def test_meld_not_decisive_waits(self):
        with tempfile.TemporaryDirectory() as d:
            _fixture(d, ADOPT4, ADOPT_BC, ADOPT_V)
            os.remove(os.path.join(d, ".verdict_done_役4speedvaluebcmeldp45"))
            N.main(["--label", "役4", "--var-dir", d])
            self.assertFalse(os.path.exists(os.path.join(d, ".YAKU_NEXT_PENDING")))

    def test_includes_mech_warn_content(self):
        # \u2605 R1483\uff1a\u673a\u5236\u544a\u8b66\u4f1a\u6539\u5199\u56db\u683c\uff08B3\uff09\u21d2 \u51b3\u7b56\u5305\u5fc5\u987b\u5e26\u4e0a\u5b83\n
        with tempfile.TemporaryDirectory() as d:
            _fixture(d, ADOPT4, ADOPT_BC, ADOPT_V)
            _write(d, ".mech_warn", u"2026-09-25 22:00:00 speedvaluebc draw \u8db3\u8ff9 6.2%/action 0.0% \u8131\u79bb\u9884\u671f\n")
            N.main(["--label", u"\u5f794", "--var-dir", d])
            body = io.open(os.path.join(d, ".YAKU_NEXT_PENDING"), encoding="utf-8").read()
            self.assertIn(".mech_warn", body)
            self.assertIn("speedvaluebc", body)

    def test_includes_v_mech_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            _fixture(d, ADOPT4, ADOPT_BC, ADOPT_V)
            _write(d, ".v_mech_unknown", u"2026-09-25 22:00:00 speedvaluebaotouv5 \u6837\u672c\u4e0d\u8db3\n")
            N.main(["--label", u"\u5f794", "--var-dir", d])
            body = io.open(os.path.join(d, ".YAKU_NEXT_PENDING"), encoding="utf-8").read()
            self.assertIn(".v_mech_unknown", body)

    def test_combo_option_when_meld_fails_but_both_layers_adopt(self):
        with tempfile.TemporaryDirectory() as d:
            _fixture(d, REJ_4, ADOPT_BC, ADOPT_V)
            N.main(["--label", "役4", "--var-dir", d])
            body = io.open(os.path.join(d, ".YAKU_NEXT_PENDING"), encoding="utf-8").read()
            self.assertIn("speedvaluebcv", body)
            self.assertIn("--watch-mechanism none", body)


class TestYaku5WatchMechanismR1531(unittest.TestCase):
    """★ R1531：役5 的起役命令**必须** `--watch-mechanism none`。

    为什么：役5 的基线（役4 赢家）**已含副露层** ⇒ 若写 `melds`，
    `_gate2` 的**硬机制闸**会要求“已存在的层”继续上升 ⇒ 可能把最终组合臂误判 REFUSE。
    预登记 `prereg-campaign8-combo-20260925.md` §5 写的就是 `none`。
    """

    def test_yaku5_command_uses_none(self):
        src = io.open(os.path.join(ROOT, "var", "_next_yaku_notice.py"), encoding="utf-8").read()
        cmds = [ln for ln in src.splitlines() if "--label 役5" in ln and "watch-mechanism" in ln]
        self.assertTrue(cmds, "没找到役5 起役命令（测试已失效）")
        for ln in cmds:
            self.assertIn("--watch-mechanism none", ln, ln)
            self.assertNotIn("melds", ln, ln)

    def test_advisory_points_to_readcards(self):
        src = io.open(os.path.join(ROOT, "var", "_next_yaku_notice.py"), encoding="utf-8").read()
        self.assertIn("yaku4-verdict-readcard.md", src)
        self.assertIn("yaku5-verdict-readcard.md", src)


if __name__ == "__main__":
    unittest.main()
