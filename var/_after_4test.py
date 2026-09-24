# -*- coding: utf-8 -*-
"""`var/_after_4test.py` —— **四测结束后的自动收尾**：退出官方模式 ⇒ 恢复役 2 A/B（原窗口）。

为什么需要：`_switch_to_official.ps1` 写了 `.official_mode` ⇒ 测试房自愈被暂停；
比赛结束后若没人跑 `_exit_official.py`，**A/B 会整夜停摆**（役 2 判词后移）。

安全性：
  * `_exit_official.py` 自带保护：**任何 bot 链进程在跑就拒绝退出**（避 E002）⇒ 比赛还在进行时本脚本只会空转；
  * 已恢复则直接退出（幂等）；
  * 只做两件事：退官方模式 → `ab_ctl start`（**带原始 --started，不白跑役 2 窗口**）。

用法：
    python -X utf8 var/_after_4test.py --dry-run     # 只打印将做什么
    python -X utf8 var/_after_4test.py               # 真执行（空转也安全）
"""
from __future__ import annotations
import argparse, io, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OFFICIAL = os.path.join(ROOT, "var", ".official_mode")
AB = os.path.join(ROOT, "var", ".ab_mode")
STARTED_DEFAULT = "2026-09-23 03:13:44"  # 役 2 原窗口（兼容兜底）
ARMS_DEFAULT = "speedc151,speedvalue"
BUNDLES_DEFAULT = "speedc151"
RESUME_SPEC = os.path.join(ROOT, "var", ".resume_spec.json")


def _resume():
    """★ R1342：优先用 `var/.resume_spec.json`（入场前快照的当时在跑的战役）⇒ 任何事件收尾都能**原窗口/原臂**恢复。"""
    try:
        d = json.loads(io.open(RESUME_SPEC, encoding="utf-8-sig").read())
        return (str(d.get("started") or STARTED_DEFAULT),
                str(d.get("arms") or ARMS_DEFAULT),
                str(d.get("bundles") or BUNDLES_DEFAULT))
    except Exception:
        return STARTED_DEFAULT, ARMS_DEFAULT, BUNDLES_DEFAULT


STARTED, ARMS, BUNDLES = STARTED_DEFAULT, ARMS_DEFAULT, BUNDLES_DEFAULT


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    STARTED, ARMS, BUNDLES = _resume()
    print("状态：.official_mode=%s  .ab_mode=%s" % (os.path.exists(OFFICIAL), os.path.exists(AB)))
    if not os.path.exists(OFFICIAL) and os.path.exists(AB):
        print("已恢复（无官方模式且 A/B 在跑）⇒ 无事可做")
        return 0
    if not os.path.exists(OFFICIAL):
        print("无 .official_mode（可能尚未切换或已退出）⇒ 仅尝试恢复 A/B")
    cmds = []
    if os.path.exists(OFFICIAL):
        cmds.append([sys.executable, "-X", "utf8", os.path.join(ROOT, "var", "_exit_official.py")])
    if not os.path.exists(AB):
        cmds.append([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "ab_ctl.py"),
                     "start", ARMS, "1", "--bundles=" + BUNDLES, "--started=" + STARTED])
    for c in cmds:
        print("  " + " ".join(os.path.basename(x) if i == 0 else x for i, x in enumerate(c)))
    if a.dry_run:
        print("（dry-run：未执行）")
        return 0
    for c in cmds:
        p = subprocess.run(c, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
        print("→ rc=%s" % p.returncode)
        print((p.stdout or "")[-400:])
        if p.returncode != 0:
            print("⇒ 此步未成功（例：比赛还在跑），停在这里，等下一次定时重试")
            return 0
    print("完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
