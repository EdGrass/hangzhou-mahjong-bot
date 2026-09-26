# -*- coding: utf-8 -*-
"""`var/_final_arm_confirm.py` 的单测（纯函数 + main 的 dry-run / 写入 / 拒绝路径）。

为什么要钉：这是 10/7 换臂前**唯一**的自动化写入点。它判错 ⇒ 正式赛上装的是"没判正过的臂"
（§V.165 红线）；它在"人工已裁决"时还去写 ⇒ 等于抢了人的裁决。
"""
from __future__ import annotations
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _final_arm_confirm as C  # noqa: E402

M = "\u2605 \u5224\u5b9a\uff1a"


def hdr(cand, base="speedvalue"):
    """真实判词文件里 `_gate2` 的头行（★ R1567起：认它才算“这份判词属于这个臂”）。"""
    return u"=== 役：%s（基线） vs %s（候选）  since=2026-09-23 03:13:44\n" % (base, cand)


def vfile(d, name, text, mtime):
    p = os.path.join(d, name)
    io.open(p, "w", encoding="utf-8").write(text)
    os.utime(p, (mtime, mtime))
    return p


class TestPure(unittest.TestCase):
    def test_mentions_word_boundary(self):
        self.assertTrue(C.mentions("已判正 speedvaluebc（副露层）", "speedvaluebc"))
        self.assertFalse(C.mentions("已判正 speedvaluebcvmeld（组合）", "speedvaluebc"))
        self.assertFalse(C.mentions("speedvaluebc_x", "speedvaluebc"))
        self.assertFalse(C.mentions("", "speedvaluebc"))

    def test_last_verdict_last_line_wins(self):
        t = M + "REFUSE 旧结论\n" + hdr("speedvaluebc") + M + "ADOPT speedvaluebc\n"
        self.assertTrue(C.last_verdict(t).startswith("ADOPT"))
        self.assertIsNone(C.last_verdict("这里没有判定行"))

    def test_arm_adopted_newest_file_decides(self):
        with tempfile.TemporaryDirectory() as d:
            old = vfile(d, "_verdict_役3.txt", hdr("speedvaluebc") + M + "ADOPT speedvaluebc\n", 1000.0)
            new = vfile(d, "_verdict_役4.txt", hdr("speedvaluebc") + M + "REFUSE / CONTINUE —— 护栏未过\n", 2000.0)
            self.assertIsNone(C.arm_adopted("speedvaluebc", C.load_verdicts([old, new])))
            io.open(new, "w", encoding="utf-8").write(hdr("speedvaluebc") + M + "ADOPT speedvaluebc\n")
            self.assertIsNotNone(C.arm_adopted("speedvaluebc", C.load_verdicts([old, new])))

    def test_load_verdicts_skips_bak_and_watch(self):
        with tempfile.TemporaryDirectory() as d:
            vfile(d, "_verdict_watch.py", hdr("speedvalue") + M + "ADOPT speedvalue\n", 1000.0)
            vfile(d, "_verdict_役2.txt.bak_20260101", hdr("speedvalue") + M + "ADOPT speedvalue\n", 1000.0)
            good = vfile(d, "_verdict_役2.txt", hdr("speedvalue") + M + "ADOPT speedvalue\n", 1000.0)
            got = C.load_verdicts([os.path.join(d, "_verdict_watch.py"),
                                   os.path.join(d, "_verdict_役2.txt.bak_20260101"), good])
            self.assertEqual(1, len(got))
            self.assertEqual("_verdict_役2.txt", got[0]["name"])

    def test_decide_prefers_adopted_layer(self):
        with tempfile.TemporaryDirectory() as d:
            p = vfile(d, "_verdict_役3.txt", hdr("speedvaluebc") + M + "ADOPT speedvaluebc\n", 1000.0)
            arm, elig, chosen = C.decide("speedvalue", ["speedvaluebc"], C.load_verdicts([p]))
            self.assertEqual("speedvaluebc", arm)
            self.assertEqual(1, len(elig))
            self.assertIsNotNone(chosen)

    def test_decide_falls_back_to_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            p = vfile(d, "_verdict_役3.txt", hdr("speedvaluebc") + M + "REFUSE / CONTINUE —— 护栏未过\n", 1000.0)
            arm, elig, chosen = C.decide("speedvalue", ["speedvaluebc"], C.load_verdicts([p]))
            self.assertEqual("speedvalue", arm)
            self.assertEqual([], elig)
            self.assertIsNone(chosen)

    def test_decide_no_verdict_files(self):
        arm, elig, _ = C.decide("speedvalue", ["speedvaluebcvmeld"], [])
        self.assertEqual("speedvalue", arm)
        self.assertEqual([], elig)

    def test_decide_multiple_adopted_newest_wins(self):
        with tempfile.TemporaryDirectory() as d:
            p3 = vfile(d, "_verdict_役3.txt", hdr("speedvaluebc") + M + "ADOPT speedvaluebc\n", 1000.0)
            p5 = vfile(d, "_verdict_役5.txt", hdr("speedvaluebcvmeld") + M + "ADOPT speedvaluebcvmeld\n", 3000.0)
            arm, elig, _ = C.decide("speedvalue", ["speedvaluebc", "speedvaluebcvmeld"],
                                    C.load_verdicts([p3, p5]))
            self.assertEqual("speedvaluebcvmeld", arm)
            self.assertEqual(2, len(elig))

    def test_decide_ignores_undecided(self):
        with tempfile.TemporaryDirectory() as d:
            p = vfile(d, "_verdict_役3.txt", hdr("speedvaluebc") + M + "UNDECIDED（和牌率 z=+0.9）⇒ 继续攒房\n", 1000.0)
            arm, elig, _ = C.decide("speedvalue", ["speedvaluebc"], C.load_verdicts([p]))
            self.assertEqual("speedvalue", arm)
            self.assertEqual([], elig)


    def test_digest_report_cannot_fake_adopt(self):
        """★ R1567（高危）：`_verdict_digest_*` 是**报告** —— 它提到过所有臂、末条判定又可能是别人的 ADOPT。
        旧实现会把**未判正**的 bc 当成“已判正”⇒ 10/7 会装上从未判正的臂（踩 §V.161 A.1）。"""
        with tempfile.TemporaryDirectory() as d:
            real = vfile(d, "_verdict_役3bc.txt",
                         hdr("speedvaluebc") + M + "UNDECIDED（和牌率 z=+0.40）⇒ 继续攒房\n", 1000.0)
            dig = os.path.join(d, "_verdict_digest_20260925_20260926.txt")
            io.open(dig, "w", encoding="utf-8").write(
                u"--baseline speedvalue --candidate speedvaluebc\n"
                + hdr("speedvaluebcmeldp45") + M + "ADOPT speedvalue（和牌率 z=+1.83）\n")
            os.utime(dig, (2000.0, 2000.0))
            vs = C.load_verdicts([real, dig])
            self.assertEqual(["_verdict_役3bc.txt"], [v["name"] for v in vs],
                             "摘要报告不能被当成判词文件")
            self.assertIsNone(C.arm_adopted("speedvaluebc", vs))
            self.assertEqual("speedvalue", C.decide("speedvalue", ["speedvaluebc"], vs)[0])

    def test_other_arms_adopt_line_does_not_qualify(self):
        """★ R1567：一份判词头行里同时出现基线名时，**不能把它的 ADOPT 算到基线头上**。"""
        with tempfile.TemporaryDirectory() as d:
            v = vfile(d, "_verdict_役4speedvaluebcmeldp45.txt",
                      hdr("speedvaluebcmeldp45", base="speedvaluebc") + M + "ADOPT speedvaluebcmeldp45\n", 1000.0)
            vs = C.load_verdicts([v])
            self.assertIsNotNone(C.arm_adopted("speedvaluebcmeldp45", vs))
            self.assertIsNone(C.arm_adopted("speedvaluebc", vs))

class TestMain(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = self._t.name
        self._saved = (C.LOG, C.OUT_TXT, C.UNRESOLVED)
        C.LOG = os.path.join(self.d, "log.txt")
        C.OUT_TXT = os.path.join(self.d, "receipt.txt")
        C.UNRESOLVED = os.path.join(self.d, ".UNRESOLVED")
        self.out = os.path.join(self.d, ".final_arm.txt")
        self.ab = os.path.join(self.d, ".ab_mode")
        self.keeper = os.path.join(self.d, "keeper.txt")
        self.ledger = os.path.join(self.d, "ledger.jsonl")
        io.open(self.ab, "w", encoding="utf-8").write(json.dumps(
            {"a": "speedvalue", "b": "speedvaluebc", "bundles": ["speedvalue"]}))

    def tearDown(self):
        C.LOG, C.OUT_TXT, C.UNRESOLVED = self._saved
        self._t.cleanup()

    def _argv(self, *extra):
        return ["--out", self.out, "--ab", self.ab, "--keeper", self.keeper,
                "--ledger", self.ledger] + list(extra)

    def test_human_file_not_overwritten(self):
        io.open(self.out, "w", encoding="utf-8").write("speedgangtakec151fixed\n")
        self.assertEqual(0, C.main(self._argv("--go", "--verdicts")))
        self.assertEqual("speedgangtakec151fixed",
                         io.open(self.out, encoding="utf-8").read().strip())

    def test_dry_run_does_not_write(self):
        self.assertEqual(0, C.main(self._argv("--dry-run", "--verdicts")))
        self.assertFalse(os.path.exists(self.out))

    def test_go_writes_baseline_when_nothing_adopted(self):
        self.assertEqual(0, C.main(self._argv("--go", "--verdicts")))
        self.assertEqual("speedvalue", io.open(self.out, encoding="utf-8").read().strip())
        self.assertTrue(os.path.exists(C.OUT_TXT))

    def test_go_writes_adopted_candidate(self):
        v = vfile(self.d, "_verdict_役3.txt", hdr("speedvaluebc") + M + "ADOPT speedvaluebc\n", 1000.0)
        self.assertEqual(0, C.main(self._argv("--go", "--verdicts", v)))
        self.assertEqual("speedvaluebc", io.open(self.out, encoding="utf-8").read().strip())

    def test_baseline_from_keeper_when_no_ab(self):
        os.remove(self.ab)
        io.open(self.keeper, "w", encoding="utf-8").write("speedvalue\n")
        self.assertEqual(0, C.main(self._argv("--go", "--verdicts")))
        self.assertEqual("speedvalue", io.open(self.out, encoding="utf-8").read().strip())

    def test_unregistered_arm_refuses_and_marks(self):
        io.open(self.ab, "w", encoding="utf-8").write(json.dumps(
            {"a": "not_a_real_arm", "b": "speedvaluebc", "bundles": ["not_a_real_arm"]}))
        self.assertEqual(2, C.main(self._argv("--go", "--verdicts")))
        self.assertFalse(os.path.exists(self.out))
        self.assertTrue(os.path.exists(C.UNRESOLVED))

    def test_no_baseline_refuses(self):
        os.remove(self.ab)
        self.assertEqual(2, C.main(self._argv("--go", "--verdicts")))
        self.assertFalse(os.path.exists(self.out))

    def test_refresh_respects_foreign_file(self):
        io.open(self.out, "w", encoding="utf-8").write("speedgangtakec151fixed\n")
        self.assertEqual(0, C.main(self._argv("--go", "--refresh", "--verdicts")))
        self.assertEqual("speedgangtakec151fixed",
                         io.open(self.out, encoding="utf-8").read().strip())

    def test_refresh_upgrades_own_baseline_when_layer_adopted(self):
        self.assertEqual(0, C.main(self._argv("--go", "--verdicts")))
        self.assertEqual("speedvalue", io.open(self.out, encoding="utf-8").read().strip())
        v = vfile(self.d, "_verdict_役3.txt", hdr("speedvaluebc") + M + "ADOPT speedvaluebc\n", 1000.0)
        self.assertEqual(0, C.main(self._argv("--go", "--refresh", "--verdicts", v)))
        self.assertEqual("speedvaluebc", io.open(self.out, encoding="utf-8").read().strip())

    def test_refresh_noop_when_unchanged(self):
        self.assertEqual(0, C.main(self._argv("--go", "--verdicts")))
        self.assertEqual(0, C.main(self._argv("--go", "--refresh", "--verdicts")))
        self.assertEqual("speedvalue", io.open(self.out, encoding="utf-8").read().strip())

    def test_refresh_never_downgrades_to_baseline(self):
        io.open(self.out, "w", encoding="utf-8").write("speedvaluebc\n")
        io.open(C.OUT_TXT, "w", encoding="utf-8").write("结论：speedvaluebc\n")
        self.assertEqual(0, C.main(self._argv("--go", "--refresh", "--verdicts")))
        self.assertEqual("speedvaluebc", io.open(self.out, encoding="utf-8").read().strip())


if __name__ == "__main__":
    unittest.main()
