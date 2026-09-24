# -*- coding: utf-8 -*-
"""**BOM 门**（R1344）：PS 5.1 写 BOM × 裸 utf-8 读取方 = 一类静默故障。

背景（本轮实测）：`var/_switch_to_official.ps1` 用
`Set-Content -Path $specPath -Value $specObj -Encoding UTF8` 写 `.official_spec.json`，
而 **Windows PowerShell 5.1 的 `-Encoding UTF8` 会写 BOM**（实测首 3 字节 = EF BB BF）；
同一份内容带 BOM 时，裸 utf-8 读取方的 `json.loads` 会抛
`JSONDecodeError: Unexpected UTF-8 BOM (decode using utf-8-sig)`。后果链：

  1. `_ensure_all.official_argv()` 读不到 spec ⇒ 误判“spec 缺失” ⇒ **不带参数**拉起
     `_official_keepalive.py` ⇒ 回落默认策略 + 默认令牌（即 R647 类静默风险，正式赛当天白给）；
  2. `_official_guard.spec_freshness()` ⇒ “spec 解析失败” ⇒ 拒绝自愈拉起 keepalive；
  3. `tools/verify_four_way.py`（T-1h 核查）⇒ 误报“spec 不可读”。

本门用**两道**钉死：
  ① 源码级：状态文件的**读取方一律 `utf-8-sig`**（对无 BOM 文件行为不变），写入方一律普通 `utf-8`（不得自己写 BOM）；
  ② 行为级：拿**真带 BOM 的** spec 去跑三个真消费者，必须读得到正确策略。
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

# 只盯**状态文件**（它们由 .ps1 / 由人手改，不受仓库 BOM 约定保护）
TARGETS = (".official_spec.json", "_keeper_strategy.txt", ".ab_mode")
SKIP_DIRS = {"__pycache__", "_scratch", ".git", "replays", "logs"}


def _src_files():
    out = []
    for sub in ("var", "tools"):
        base = os.path.join(ROOT, sub)
        for dp, dn, fn in os.walk(base):
            dn[:] = [d for d in dn if d not in SKIP_DIRS]
            for f in fn:
                if f.endswith(".py") and ".bak" not in f and not f.startswith("_scratch"):
                    out.append(os.path.join(dp, f))
    return out


def _open_calls(src):
    """返回 (offset, call_text)：逐个 `open(` 取**括号配对的**调用文本。"""
    key = "open("
    i = src.find(key)
    while i != -1:
        j = i + len(key) - 1
        depth, k = 0, j
        while k < len(src):
            c = src[k]
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        yield i, src[i:k + 1]
        i = src.find(key, k + 1)


class TestStateFileEncoding(unittest.TestCase):
    def test_readers_use_utf8_sig(self):
        bad = []
        for p in _src_files():
            with io.open(p, encoding="utf-8-sig", errors="replace") as fh:
                src = fh.read()
            for off, call in _open_calls(src):
                if not any(t in call for t in TARGETS):
                    continue
                if '"w"' in call or "'w'" in call or '"a"' in call or "'a'" in call:
                    # 写入方：**不得**自己写 BOM
                    if "utf-8-sig" in call:
                        bad.append((p, off, "写入方不得用 utf-8-sig（会写 BOM）", call))
                    continue
                if "utf-8-sig" not in call:
                    ln = src[:off].count("\n") + 1
                    bad.append((p, ln, "读取方必须 utf-8-sig", call))
        self.assertEqual([], [b for b in bad], "状态文件编码不达标：\n" +
                         "\n".join("  %s:%s %s\n    %s" % (os.path.relpath(b[0], ROOT), b[1], b[2], " ".join(b[3].split()))
                                   for b in bad))

    def test_scan_finds_both_kinds(self):
        """反向保护：扫描器本身必须能看到读取方与写入方，否则本门是空跑。"""
        caps = []
        for p in _src_files():
            with io.open(p, encoding="utf-8-sig", errors="replace") as fh:
                src = fh.read()
            for _, call in _open_calls(src):
                if any(t in call for t in TARGETS):
                    caps.append(call)
        self.assertTrue(any("utf-8-sig" in c for c in caps), "应至少看到一个 utf-8-sig 读取方")
        self.assertTrue(any(('"w"' in c or "'w'" in c) for c in caps), "应至少看到一个写入方")


class TestPsWriterNoBom(unittest.TestCase):
    PS1 = os.path.join(ROOT, "var", "_switch_to_official.ps1")

    @unittest.skipUnless(os.path.exists(PS1), "var/ 不在仓库里（gitignore）")
    def test_spec_written_without_bom(self):
        with io.open(self.PS1, encoding="utf-8-sig") as fh:
            s = fh.read()
        # 新写法必须在位；旧写法（PS 5.1 会写 BOM）必须消失
        self.assertIn("WriteAllText($specPath", s,
                      ".official_spec.json 必须用 .NET 写**无 BOM** UTF-8")
        self.assertNotRegex(s, r"Set-Content\s+-Path\s+\$specPath",
                            "不得用 Set-Content 写 spec（PS 5.1 的 -Encoding UTF8 会带 BOM）")


class TestBomSpecStillParsed(unittest.TestCase):
    """行为级：真正带 BOM 的 spec，三个真消费者都必须读对。"""

    def _bom_spec(self, obj):
        fd, p = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "wb") as f:
            f.write(("\ufeff" + json.dumps(obj, ensure_ascii=False)).encode("utf-8"))
        self.addCleanup(os.unlink, p)
        with io.open(p, "rb") as fh:
            head = fh.read(3)
        self.assertEqual(head, b"\xef\xbb\xbf", "夹具本身必须真带 BOM")
        return p

    def _load(self, name, rel):
        spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
        return m

    def test_ensure_all_official_argv(self):
        ens = self._load("bom_ensure_all", "var/_ensure_all.py")
        p = self._bom_spec({"strategy": "speedvalue", "token_file": "var/.token_x",
                            "tournament_id": "t_6266386bfd56",
                            "server": "https://10.240.169.190:18080"})
        self.assertEqual(ens.official_argv(p),
                         ["--strategy", "speedvalue", "--token-file", "var/.token_x",
                          "--server", "https://10.240.169.190:18080"],
                         "带 BOM 的 spec 不能被误判为“缺失”（否则自愈会用默认策略/令牌）")

    def test_official_guard_spec_freshness(self):
        g = self._load("bom_official_guard", "var/_official_guard.py")
        import datetime
        p = self._bom_spec({"strategy": "speedvalue", "token_file": "var/.token_x",
                            "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        old, g.SPEC = g.SPEC, p
        try:
            fresh, why = g.spec_freshness()
        finally:
            g.SPEC = old
        self.assertTrue(fresh, "带 BOM 的 spec 不能被判“解析失败”而拒绝自愈：%s" % why)

    def test_verify_four_way_reads_bom_spec(self):
        v4 = self._load("bom_verify_four_way", "tools/verify_four_way.py")
        p = self._bom_spec({"strategy": "speedvalue"})
        d = os.path.dirname(p)
        k = os.path.join(d, "k.txt")
        with io.open(k, "w", encoding="utf-8") as f:
            f.write("speedvalue")
        ok, rows, bad, _ = v4.check(p, k, os.path.join(d, ".no_ab"), os.path.join(d, ".no_off"),
                                    {"keeper": [], "match_super": [], "run_bot": []})
        self.assertTrue(ok, bad)
        self.assertEqual(rows[0][1], "speedvalue", "① spec.strategy 必须读出真值，而不是 None")


if __name__ == "__main__":
    unittest.main()
