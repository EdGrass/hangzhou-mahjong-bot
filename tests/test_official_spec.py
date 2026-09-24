# -*- coding: utf-8 -*-
"""`var/_ensure_all.py::official_argv` 的契约单测 —— **整机重启后的自愈路径**。

为什么必须钉住（2026-09-16 的真实缺口）：旧实现自愈拉起 keepalive 时**不带参数** ⇒ 换赛事令牌后
整机重启会**静默用旧策略/旧令牌参赛**。现在参数以 `var/.official_spec.json` 为准；
而 `_switch_to_official.ps1` 写出的 spec **比 keepalive 自己写的多一个 `tournament_id`**（本会话新增）
⇒ 必须验证"多出来的键被忽略、不影响 argv"，否则自愈路径会在正式赛当天出问题。
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)          # main() 有 __main__ 守卫 ⇒ import 安全
    return m


ens = _load("ensure_all_spec", "var/_ensure_all.py")


class TestOfficialArgv(unittest.TestCase):
    def _spec(self, obj):
        fd, p = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            if isinstance(obj, str):
                f.write(obj)
            else:
                f.write(json.dumps(obj, ensure_ascii=False))
        self.addCleanup(os.unlink, p)
        return p

    def test_full_spec(self):
        p = self._spec({"strategy": "speedtugc", "token_file": "var/.token_x",
                        "server": "https://10.240.169.190:18080"})
        self.assertEqual(ens.official_argv(p),
                         ["--strategy", "speedtugc", "--token-file", "var/.token_x",
                          "--server", "https://10.240.169.190:18080"])

    def test_extra_key_ignored(self):
        """`_switch_to_official.ps1` 会多写 `tournament_id` ⇒ 必须被忽略而不是报错/污染 argv。"""
        p = self._spec({"strategy": "speedc148", "token_file": "var/.token_1024_20260917",
                        "tournament_id": "t_65d538e905c5",
                        "server": "https://10.240.169.190:18080",
                        "ts": "2026-09-17 19:00:00"})
        argv = ens.official_argv(p)
        self.assertEqual(argv, ["--strategy", "speedc148", "--token-file", "var/.token_1024_20260917",
                                "--server", "https://10.240.169.190:18080"])
        self.assertNotIn("tournament_id", " ".join(argv))
        self.assertNotIn("t_65d538e905c5", " ".join(argv))

    def test_partial_spec(self):
        p = self._spec({"strategy": "speedc151"})
        self.assertEqual(ens.official_argv(p), ["--strategy", "speedc151"])

    def test_missing_or_bad(self):
        self.assertEqual(ens.official_argv(os.path.join(ROOT, "var", ".no_such_spec")), [])
        self.assertEqual(ens.official_argv(self._spec("{not json")), [])
        self.assertEqual(ens.official_argv(self._spec({})), [])


if __name__ == "__main__":
    unittest.main()
