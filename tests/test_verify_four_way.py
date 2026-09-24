# -*- coding: utf-8 -*-
"""`tools/verify_four_way.py` 单测：**静默用错策略**这一族风险必须被拦住。\n\nR1338 语义变更：**①↔② 不一致只在 `.official_mode` 存在时才算 FAIL**（非官方模式下 spec 被自愈路径读取的概率为 0；以下两条用例把这个分界钉死）。

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

    @staticmethod
    def _w(path, text):
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def _write(self, spec_strategy, kfile_strategy):
        self._w(self.spec, json.dumps({"strategy": spec_strategy}))
        self._w(self.kstr, kfile_strategy)

    def _ab(self, arms):
        self._w(self.ab, json.dumps({"arms": arms}))

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

    def test_diverge_is_dormant_without_official_mode(self):
        """★ R1338：spec 与策略文件不一致，但**无** `.official_mode` ⇒ **不算失败**。

        依据（本轮实测四处消费者）：
          · `var/_ensure_all.py` 的 `official_argv()` 只在 `main()` 的 `if official_mode():` 分支内被调用；
          · `var/_official_guard.py` 非官方模式**严格 no-op**；
          · `var/_official_keepalive.py` 只**写** spec，从不读它取策略。
        ⇒ 非官方模式下 spec 不被任何自愈路径读取，下次切换会直接覆盖它。
        旧语义（无条件 FAIL）在 A/B 期间**不可能满足**（② 本来就每批轮换），只造成警报疲劳。
        """
        self._write("speedc211", "speedtugc")
        ok, rows, bad, mode = v4.check(self.spec, self.kstr, self.ab, self.off,
                                       {"keeper": [], "match_super": [], "run_bot": []})
        self.assertTrue(ok, bad)
        self.assertTrue(any("dormant" in str(k) for k, _ in rows),
                        "非官方模式下应以 dormant 提示行呈现差异，而不是静默丢弃：%s" % rows)

    def test_fails_when_spec_and_keeper_file_diverge_in_official_mode(self):
        """★ R647 的静默风险**本体**：官方模式下 spec 写 c211 而策略文件是 speedtugc。

        这才是真风险：有 `.official_mode` ⇒ 整机重启时 `_ensure_all.official_argv()`
        会按这份 spec 拉起一个**已弃用**的策略。
        """
        self._write("speedc211", "speedtugc")
        self._w(self.off, "{}")
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
        self._w(self.off, "{}")
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
