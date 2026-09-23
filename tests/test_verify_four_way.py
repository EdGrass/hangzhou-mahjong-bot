# -*- coding: utf-8 -*-
"""`tools/verify_four_way.py` 单测：**静默用错策略**这一族风险必须被拦住。

背景：R647 实测过 `.official_spec.json`（重启路径的上游）与 `_keeper_strategy.txt` 脱钩 ——
整机重启时 `_ensure_all.py` 会按 spec 拉起一个**已弃用**的策略。本测试把各分支钉住。
"""
import importlib.util, io, json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec_ = importlib.util.spec_from_file_location("v4", os.path.join(ROOT, "tools", "verify_four_way.py"))
v4 = importlib.util.module_from_spec(spec_)
spec_.loader.exec_module(v4)


class TestVerifyFourWay(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="v4_")
        self.spec = os.path.join(self.d, "spec.json")
        self.kstr = os.path.join(self.d, "k.txt")
        self.ab = os.path.join(self.d, ".ab_mode")
        self.off = os.path.join(self.d, ".official_mode")

    def _write(self, spec_strategy, kfile_strategy):
        io.open(self.spec, "w", encoding="utf-8").write(json.dumps({"strategy": spec_strategy}))
        io.open(self.kstr, "w", encoding="utf-8").write(kfile_strategy)

    def _ab(self, arms):
        io.open(self.ab, "w", encoding="utf-8").write(json.dumps({"arms": arms}))

    def test_ok_in_ab_when_arm_in_roster(self):
        self._write("speedtugc", "speedtugc"); self._ab(["speedtugc", "speedc151"])
        ok, rows, bad, mode = v4.check(self.spec, self.kstr, self.ab, self.off,
                                       {"keeper": [], "match_super": ["speedc151"], "run_bot": ["speedc151"]})
        self.assertTrue(ok, bad); self.assertTrue(mode["ab"])

    def test_fails_when_arm_not_in_roster(self):
        self._write("speedtugc", "speedtugc"); self._ab(["speedtugc", "speedc151"])
        ok, rows, bad, mode = v4.check(self.spec, self.kstr, self.ab, self.off,
                                       {"keeper": [], "match_super": ["speedc211"], "run_bot": ["speedc211"]})
        self.assertFalse(ok); self.assertTrue(any("roster" in b for b in bad), bad)

    def test_fails_when_spec_and_keeper_file_diverge(self):
        """★ R647 的静默风险：spec 写 c211 而 keeper 文件是 speedtugc。"""
        self._write("speedc211", "speedtugc")
        ok, rows, bad, mode = v4.check(self.spec, self.kstr, self.ab, self.off,
                                       {"keeper": [], "match_super": [], "run_bot": []})
        self.assertFalse(ok); self.assertTrue(any("①↔②" in b for b in bad), bad)

    def test_fails_when_keeper_runs_other_strategy_in_normal_mode(self):
        self._write("speedtugc", "speedtugc")
        ok, rows, bad, mode = v4.check(self.spec, self.kstr, self.ab, self.off,
                                       {"keeper": ["speedc151"], "match_super": ["speedc151"], "run_bot": ["speedc151"]})
        self.assertFalse(ok); self.assertTrue(any("keeper 在跑" in b for b in bad), bad)

    def test_fails_in_official_mode_when_runbot_differs(self):
        self._write("speedtugc", "speedtugc")
        io.open(self.off, "w", encoding="utf-8").write("{}")
        ok, rows, bad, mode = v4.check(self.spec, self.kstr, self.ab, self.off,
                                       {"keeper": [], "match_super": [], "run_bot": ["speedc148"]})
        self.assertFalse(ok); self.assertTrue(any("官方模式" in b for b in bad), bad)

    def test_ok_when_everything_consistent(self):
        self._write("speedtugc", "speedtugc")
        ok, rows, bad, mode = v4.check(self.spec, self.kstr, self.ab, self.off,
                                       {"keeper": ["speedtugc"], "match_super": ["speedtugc"], "run_bot": ["speedtugc"]})
        self.assertTrue(ok, bad)


if __name__ == "__main__":
    unittest.main()
