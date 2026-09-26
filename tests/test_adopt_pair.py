# -*- coding: utf-8 -*-
"""`var/_adopt_pair.py` 的单测（纯函数）。

为什么要钉：这是**唯一**能把役 3 推进到役 4 的自动化（`_bsegment` 只注册判词看护，
`HangzhouMajAdoptWatch` 只盯役 2 ⇒ 没人判就**静默停摆**）。它判错一次 = 起错役、白烧 1.7 天。
四格映射必须与役 3 读卡 §3 逐字一致；"无法判定"必须**原地不动**而不是猜。
R1480 起它还要把预登记 **B3（机制不达标 ⇒ 本役作废）**接上：
`_mech_watch` 写的 `var/.mech_warn` 以前**无人读** ⇒ 机制坏了也会被采用。
"""
from __future__ import annotations
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _adopt_pair as AP  # noqa: E402

ADOPT_BC = "ADOPT speedvaluebc（和牌率 z=+1.80、番 z=+1.60、护栏通过）"
ADOPT_V = "ADOPT speedvaluebaotouv5（和牌率 z=+1.55、番 z=+1.70、护栏通过）"


class TestLines(unittest.TestCase):
    def test_is_adopt_real_format(self):
        self.assertTrue(AP.is_adopt(ADOPT_BC))
        self.assertTrue(AP.is_adopt(ADOPT_V))
        for t in ("REFUSE / CONTINUE —— 第一率护栏未过", "REJECT speedvalue（和牌率 z=-2.1）",
                  "UNDECIDED（和牌率 z=+0.9）⇒ 继续攒房", ""):
            self.assertFalse(AP.is_adopt(t), t)

    def test_last_verdict_wins(self):
        t = "★ 判定：REFUSE 旧\n★ 判定：ADOPT speedvaluebc\n"
        self.assertTrue(AP.is_adopt(AP.last_verdict(t)))


class TestClassify(unittest.TestCase):
    def test_adopt_ok(self):
        self.assertEqual((True, "x"), (AP.classify_candidate(ADOPT_BC, 0)[0], "x"))

    def test_adopt_unknown_does_not_block(self):
        # §7.3/§8：样本不足 ⇒ 只记录、不据此翻转 ⇒ 仍算采用
        self.assertTrue(AP.classify_candidate(ADOPT_BC, 2)[0])

    def test_adopt_veto_blocks(self):
        # §7.2/§8：强手房/决赛相似层显著劣 ⇒ 不采用
        self.assertFalse(AP.classify_candidate(ADOPT_BC, 3)[0])

    def test_adopt_tool_error_is_undecidable(self):
        # 工具异常（rc=1 等）⇒ 必须"无法判定"，绝不当成采用或不采用
        self.assertIsNone(AP.classify_candidate(ADOPT_BC, 1)[0])
        self.assertIsNone(AP.classify_candidate(ADOPT_BC, None)[0])

    def test_non_adopt_never_needs_veto(self):
        for line in ("REFUSE / CONTINUE —— 第一率护栏未过",
                     "REJECT speedvalue（和牌率 z=-2.1）",
                     "UNDECIDED（和牌率 z=+1.27）"):
            self.assertFalse(AP.classify_candidate(line, None)[0], line)


class TestFourCell(unittest.TestCase):
    """四格必须与役 3 读卡 §3 一致：BC✓ ⇒ A 行（无论 V）；BC✗ 且 V✓ ⇒ B 行；都 ✗ ⇒ NONE 行。"""

    def test_rows(self):
        self.assertEqual("a", AP.pick_row(True, True))
        self.assertEqual("a", AP.pick_row(True, False))
        self.assertEqual("b", AP.pick_row(False, True))
        self.assertEqual("none", AP.pick_row(False, False))


class TestVRuleConflict(unittest.TestCase):
    """R1487\uff1aV \u8f74\u526f\u7aef\u70b9\u7684**\u53e3\u5f84\u51b2\u7a81**\uff08campaign7 \u00a72 \u53ea\u8981\u65b9\u5411 vs _gate2 \u901a\u7528 z\u22651.50\uff09\u3002

    \u8fd9\u4e00\u683c\u4e0d\u80fd\u8ba9\u673a\u5668\u60c4\u60c4\u5f53\u201c\u4e0d\u91c7\u7528\u201d\uff1a\u9884\u767b\u8bb0\u7684 B1 \u5176\u5b9e\u5df2\u7ecf\u6ee1\u8db3 \u21d2 \u5e94\u201c\u539f\u5730\u4e0d\u52a8 + \u843d\u6807\u8bb0\u7b49\u4eba\u5224\u201d\u3002"""

    def test_parse_gate2_zs(self):
        self.assertEqual((1.83, 1.77), AP.parse_gate2_zs(
            u"ADOPT speedvalue\uff08\u548c\u724c\u7387 z=+1.83\u3001\u756a z=+1.77\u3001\u62a4\u680f\u901a\u8fc7\uff09"))
        self.assertEqual((1.24, 1.41), AP.parse_gate2_zs(
            u"UNDECIDED\uff08\u548c\u724c\u7387 z=+1.24\u3001\u756a z=+1.41\uff09\u21d2 \u7ee7\u7eed\u6512\u623f"))
        self.assertEqual((None, None), AP.parse_gate2_zs(u"REFUSE / CONTINUE \u2014\u2014 \u590d\u76d8\u8986\u76d6 < 70%"))
        self.assertEqual((None, None), AP.parse_gate2_zs(""))
        self.assertEqual((-2.0, 0.5), AP.parse_gate2_zs(u"REJECT speedvalue\uff08\u548c\u724c\u7387 z=-2.0\u3001\u756a z=+0.5\uff09"))

    def test_conflict_only_in_the_gap_cell(self):
        arm = "speedvaluebaotouv5"
        self.assertTrue(AP.v_rule_conflict(False, arm, 1.7, 0.9))    # \u4e3b\u8fc7\u3001\u526f\u65b9\u5411\u6b63\u4f46 z<1.5 \u21d2 \u51b2\u7a81
        self.assertFalse(AP.v_rule_conflict(False, arm, 1.7, 1.6))   # \u526f\u4e5f\u8fc7 \u21d2 \u672c\u6765\u5c31\u4f1a\u88ab\u5224 ADOPT
        self.assertFalse(AP.v_rule_conflict(False, arm, 1.2, 0.9))   # \u4e3b\u4e0d\u8fc7 \u21d2 \u6b63\u5e38\u672a\u51b3
        self.assertFalse(AP.v_rule_conflict(False, arm, 1.7, -0.3))  # \u526f\u65b9\u5411\u4e3a\u8d1f \u21d2 \u9884\u767b\u8bb0\u4e5f\u4e0d\u6ee1\u8db3
        self.assertFalse(AP.v_rule_conflict(True, arm, 1.7, 0.9))    # \u5df2 ADOPT
        self.assertFalse(AP.v_rule_conflict(False, "speedvaluebc", 1.7, 0.9))  # BC \u7528\u901a\u7528\u53e3\u5f84
        self.assertFalse(AP.v_rule_conflict(False, arm, None, None))  # \u8bfb\u4e0d\u51fa \u21d2 \u4e0d\u731c

    def test_conflict_marker_in_var(self):
        self.assertTrue(AP.CONFLICT_OUT.replace("\\", "/").endswith("var/.VERDICT_RULE_CONFLICT"))


class TestB2AndVMech(unittest.TestCase):
    """R1486\uff1a\u9884\u767b\u8bb0\u7684 **B2**\uff08\u673a\u5236\u6210\u7acb\u3001\u4e3b\u7aef\u70b9\u672a\u8bc1\u5b9e\uff09\u5fc5\u987b\u843d\u76d8\u3002

    \u4e3a\u4ec0\u4e48\uff1acampaign7 \u00a74 \u660e\u5199 B2 \u8981\u201c\u4fdd\u7559\u4e3a\u6b63\u5f0f\u8d5b\u5907\u9009\u81c2\u201d\uff0c\u800c\u672c\u811a\u672c\u4ee5\u524d**\u6ca1\u6709\u4efb\u4f55\u843d\u76d8**\n
    \u21d2 10/5 \u9009\u81c2\u65f6\u770b\u4e0d\u5230\u5b83\u3002\u53e6\u9489\u4f4f\uff1a\u201c\u8bfb\u4e0d\u51fa/None\u201d\u4e0d\u7b97 B2\uff08\u4e0d\u731c\uff09\u3002"""

    def test_is_b2_truth_table(self):
        self.assertTrue(AP.is_b2(False, "ok", True))
        self.assertFalse(AP.is_b2(False, "ok", None))      # \u8bfb\u4e0d\u51fa \u21d2 \u4e0d\u731c
        self.assertFalse(AP.is_b2(False, "ok", False))     # \u673a\u5236\u4e0d\u8fbe\u6807 \u21d2 \u4e0d\u662f B2
        self.assertFalse(AP.is_b2(False, "fail", True))
        self.assertFalse(AP.is_b2(False, "unknown", True))
        self.assertFalse(AP.is_b2(True, "ok", True))       # \u5df2\u91c7\u7528 \u21d2 \u4e0d\u662f B2
        self.assertFalse(AP.is_b2(None, "ok", True))       # \u672a\u51b3 \u21d2 \u4e0d\u52a8

    def test_v_mech_last_takes_latest(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "v.jsonl")
            with io.open(f, "w", encoding="utf-8") as fh:
                fh.write(u'{"arm": "speedvaluebaotouv5", "ok": null, "why": "\u6837\u672c\u4e0d\u8db3"}\n')
                fh.write(u'{"arm": "speedvaluebc", "ok": true, "why": "x"}\n')
                fh.write(u'{"arm": "speedvaluebaotouv5", "ok": true, "why": "\u4e24\u9879\u90fd\u5347"}\n')
                fh.write(u'not-json\n')
            ok, why = AP.v_mech_last("speedvaluebaotouv5", path=f)
            self.assertTrue(ok)
            self.assertIn(u"\u4e24\u9879", why)

    def test_v_mech_last_missing_and_unreadable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "v.jsonl")
            with io.open(f, "w", encoding="utf-8") as fh:
                fh.write(u'{"arm": "speedvaluebc", "ok": true}\n')
            self.assertEqual((None, u"\u65e0\u8bb0\u5f55"), AP.v_mech_last("speedvaluebaotouv5", path=f))
            self.assertEqual(None, AP.v_mech_last("x", path=os.path.join(d, "nope.jsonl"))[0])

    def test_b2_marker_path_in_var(self):
        self.assertTrue(AP.B2_OUT.replace("\\", "/").endswith("var/.B2_CANDIDATES"), AP.B2_OUT)


class TestMechState(unittest.TestCase):
    """R1480：预登记 B3 在采用路径上的读数（用临时文件，不碰真实 `var/.mech_warn`）。"""

    def setUp(self):
        import tempfile
        self.d = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.d.name, ".mech_warn")
        self.since = "2026-09-25 20:52:39"

    def tearDown(self):
        self.d.cleanup()

    def _write(self, text, mtime=None):
        with io.open(self.p, "w", encoding="utf-8") as f:
            f.write(text)
        if mtime is not None:
            os.utime(self.p, (mtime, mtime))

    def test_no_warn_is_ok(self):
        self.assertEqual("ok", AP.mech_state("speedvaluebc", self.since, path=self.p)[0])

    def test_warn_naming_arm_is_fail(self):
        self._write(u"2026-09-25 21:00:00 speedvaluebc draw 足迹 6.2%/action 0.0% 脱离预期\n")
        st, why = AP.mech_state("speedvaluebc", self.since, path=self.p)
        self.assertEqual("fail", st)
        self.assertIn("speedvaluebc", why)

    def test_warn_naming_other_arm_is_ok(self):
        self._write(u"2026-09-25 21:00:00 speedvaluebaotouv5 draw 足迹 22.0%/action 0.0% 脱离预期\n")
        self.assertEqual("ok", AP.mech_state("speedvaluebc", self.since, path=self.p)[0])

    def test_stale_warn_before_window_is_ok(self):
        # 告警时间早于本役起点 ⇒ 陈旧，不得误伤
        import datetime as dt
        old = dt.datetime(2026, 9, 20, 10, 0, 0).timestamp()
        self._write(u"2026-09-20 10:00:00 speedvaluebc …\n", mtime=old)
        self.assertEqual("ok", AP.mech_state("speedvaluebc", self.since, path=self.p)[0])

    def test_unreadable_is_unknown(self):
        # 路径是目录 ⇒ 读不出 ⇒ unknown（调用方必须原地不动）
        self.assertEqual("unknown", AP.mech_state("speedvaluebc", self.since, path=self.d.name)[0])


class TestMechConflictGuard(unittest.TestCase):
    """★ R1515：不得拿“已存在的层”当硬闸。

    `_gate2 --mechanism X` 的机制核对是硬闸（z>0 且和牌率不降）；
    若基线已含该层，指标本就持平 ⇒ 会把更好的组合臂误判 REFUSE。
    """
    def _A(self):
        sys.path.insert(0, os.path.join(ROOT, "var"))
        import _adopt_pair as A
        return A

    def test_fresh_layer_is_fine(self):
        A = self._A()
        self.assertIsNone(A.mech_conflict("speedvaluebc", "speedvaluebcmeldp45", "melds"))

    def test_already_present_layer_conflicts(self):
        A = self._A()
        self.assertIsNotNone(A.mech_conflict("speedvaluebcmeldp45", "speedvaluebcvmeld", "melds"))
        self.assertIsNotNone(A.mech_conflict("speedvaluebaotouvmeld",
                                             "speedvaluebcvmeld,speedvaluebcvmeldp40", "melds"))

    def test_none_and_other_mech_unaffected(self):
        A = self._A()
        self.assertIsNone(A.mech_conflict("speedvaluebcmeldp45", "speedvaluebcvmeld", "none"))
        self.assertIsNone(A.mech_conflict("speedvalue", "speedvaluebc", "pairs"))




class TestAbConfig(unittest.TestCase):
    """★ R1543：`.adopted_pair_役3` 里必须记**实际切成的配置**（以 `.ab_mode` 为准）。

    为什么：`_next_yaku_notice` 靠这个标记的 `cands` 去找役 4 的判词文件（label = 役4 + 候选）；
    重试路径会重算四格，若结果翻转而标记照旧写，就会指向一个**没在跑的臂** ⇒ 静默停摆。
    """

    def _ab(self, d, obj):
        f = os.path.join(d, ".ab_mode")
        with io.open(f, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return f

    def test_reads_baseline_and_candidates(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = self._ab(d, {"started": "x", "arms": ["speedvaluebc", "speedvaluebcmeldp45"],
                             "bundles": ["speedvaluebc"]})
            self.assertEqual(("speedvaluebc", "speedvaluebcmeldp45"), AP.ab_config(f))

    def test_missing_file(self):
        self.assertEqual(("", ""), AP.ab_config("no_such_ab_mode_xyz"))

    def test_single_arm_is_not_enough(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = self._ab(d, {"arms": ["speedvalue"], "bundles": ["speedvalue"]})
            self.assertEqual(("", ""), AP.ab_config(f))

    def test_marker_write_uses_ab_config(self):
        src = io.open(os.path.join(ROOT, "var", "_adopt_pair.py"), encoding="utf-8").read()
        i = src.index("ab_config()")
        j = src.index("with io.open(marker,")
        self.assertLess(i, j, "必须先读实际配置再写标记")


class TestVMechVerdict(unittest.TestCase):
    """★ R1534：V 机制读数的**采用口径** —— 取“最新一条 ok 非 None”，不是“最后一条”。

    为什么：`_mech_watch` 会把“读数缺失/样本不足”也写成一条 `ok=null` 的记录
    （2026-09-26 00:37 实测过一次解析为空的瞬时失败）⇒ 按“最后一条”读，一次抖动
    就会把**已判成立**的臂打成“读不出”。
    """

    def _rec(self, d, rows):
        return AP.v_mech_verdict("speedvaluebaotouv5", path=self._file(d, rows))

    def _file(self, d, rows):
        f = os.path.join(d, "v.jsonl")
        with io.open(f, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(r + u"\n")
        return f

    def test_non_v_arm_is_not_applicable(self):
        self.assertEqual("n/a", AP.v_mech_verdict("speedvaluebc")[0])
        self.assertEqual("n/a", AP.v_mech_verdict("speedvaluebcmeldp45")[0])

    def test_pass_when_latest_non_none_is_true(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            st, why = self._rec(d, [u'{"arm": "speedvaluebaotouv5", "ok": null, "why": "\u6837\u672c\u4e0d\u8db3"}',
                                   u'{"arm": "speedvaluebaotouv5", "ok": true, "why": "\u4e24\u9879\u90fd\u5347"}'])
            self.assertEqual("pass", st)
            self.assertIn(u"\u4e24\u9879", why)

    def test_transient_none_after_pass_does_not_flip_it(self):
        """★ 核心用例：最后一条是 None（抖动），但上一条是 True ⇒ 仍判 pass。"""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            st, _ = self._rec(d, [u'{"arm": "speedvaluebaotouv5", "ok": true, "why": "x"}',
                                  u'{"arm": "speedvaluebaotouv5", "ok": null, "why": "\u8bfb\u6570\u7f3a\u5931"}'])
            self.assertEqual("pass", st)

    def test_fail_when_latest_non_none_is_false(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            st, why = self._rec(d, [u'{"arm": "speedvaluebaotouv5", "ok": true, "why": "old"}',
                                    u'{"arm": "speedvaluebaotouv5", "ok": false, "why": "\u7206\u5934\u4e0b\u964d"}'])
            self.assertEqual("fail", st)
            self.assertIn(u"\u7206\u5934", why)

    def test_unknown_when_only_none_records(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            st, why = self._rec(d, [u'{"arm": "speedvaluebaotouv5", "ok": null, "why": "no"}'])
            self.assertEqual("unknown", st)
            self.assertIn(u"\u53ea\u6709", why)

    def test_unknown_when_no_record_for_arm(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            st, why = self._rec(d, [u'{"arm": "speedvaluebc", "ok": true}'])
            self.assertEqual("unknown", st)
            self.assertIn(u"\u65e0\u8bb0\u5f55", why)

    def test_unknown_when_unreadable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            st, _ = AP.v_mech_verdict("speedvaluebaotouv5", path=d)
            self.assertEqual("unknown", st)

    def test_marker_path_in_var(self):
        self.assertTrue(AP.UNK_OUT.replace("\\", "/").endswith("var/.v_mech_unknown"), AP.UNK_OUT)


class TestApplyVGate(unittest.TestCase):
    """★ R1534：V 的采用必须以**明确的机制读数**为前提（fail-closed）。

    旧路径把“判不出”（`.v_mech_unknown`）当成“无 `.mech_warn` ＝ 机制正常”
    ⇒ V 可以在**机制从未验证**的情况下被采用、并据此起役 4 的 B 行。
    """

    def test_pass_keeps_adopted(self):
        self.assertEqual((True, None), AP.apply_v_gate(True, "pass", ""))

    def test_fail_downgrades_to_not_adopted(self):
        # B3：机制不达标 ⇒ 本役作废 ⇒ V 记 ✗（四格会重算，不再走 B 行）
        self.assertEqual((False, None), AP.apply_v_gate(True, "fail", "x"))

    def test_unknown_stalls_loudly(self):
        out, why = AP.apply_v_gate(True, "unknown", u"\u65e0\u8bb0\u5f55")
        self.assertIsNone(out)
        self.assertTrue(why and u"\u539f\u5730\u4e0d\u52a8" in why)

    def test_not_adopted_never_blocked(self):
        # V 本来就没被判正（A/NONE 行）⇒ 不得因为 V 读不出而拦
        for state in ("pass", "fail", "unknown", "n/a"):
            self.assertEqual((False, None), AP.apply_v_gate(False, state, "x"))
        self.assertEqual((None, None), AP.apply_v_gate(None, "unknown", "x"))


if __name__ == "__main__":
    unittest.main()
