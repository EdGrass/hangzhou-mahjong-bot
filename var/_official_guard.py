# -*- coding: utf-8 -*-
"""`var/_official_guard.py` —— 官方 keepalive 的 60 秒级存活看护（**只新增**，不改既有链路）。

背景（journal R1161）：2026-09-23 20:40:40 官方 keepalive 与 run_bot **同时"无日志消失"**
（`_official_console.err` 为空、无退出码），仓库内三条自愈路径（watchdog 官方分支 / keepalive
守卫 / `_ensure_all`）全部排除，判为**外部终止**。当时唯一兜底是计划任务
`HangzhouMajAutoHeal` → `_ensure_all.py`（**每 5 分钟**）⇒ 最坏掉线 ~5 分钟。

本脚本由**独立计划任务每 60 秒**调用，把最坏掉线从 5 分钟压到 ~1 分钟：

- **非官方模式**（`var/.official_mode` 不存在）⇒ **严格 no-op**（连进程表都不查）✓
- **官方模式**：若本机无 `_official_keepalive.py`，按 `var/.official_spec.json` 的
  `official_argv()` 拉起（与 `_ensure_all.py` **同口径**，绝不自己拼参数）；
- 每次动作写一行到 `var/_official_guard.log`（静默期不写，避免日志膨胀）。

红线遵守：不杀任何进程、不改任何配置、仅在"官方模式 + keepalive 缺失"这一条路径上**新增**
一个 keepalive 进程；与既有 `_ensure_all` 互为幂等（两者都用 `_has()` 判存在，不会双开）。
"""
from __future__ import annotations
import datetime as dt
import importlib.util
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAG = os.path.join(ROOT, "var", ".official_mode")
LOG = os.path.join(ROOT, "var", "_official_guard.log")
# ★ R1537：keepalive **自己**的 stdout/stderr 落点（run_bot 的输出仍由 keepalive 自己写 _official_1024.out）
KEEPALIVE_OUT = os.path.join(ROOT, "var", "_official_keepalive.out")


def _log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def _has(name):
    try:
        import psutil
    except Exception:
        return None
    # ★ R1394：**必须一并要 "pid"** —— 下文用 `p.info.get("pid")` 自排除、并用 `p.info["pid"]` 返回；
    #   只请求 "cmdline" 时这两处会拿到 None / 抛 KeyError，而 KeyError 被 `except` 吞掉
    #   ⇒ `_has()` **永远返回 None**（即使 keepalive 正在跑）⇒ 60s 看护每分钟都以为“缺失”并去 spawn。四测实测：psutil 能看到 pid 49516，`_has()` 却返回 None。
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            argv = p.info.get("cmdline") or []
            base = [os.path.basename(str(x).replace("\\", "/")).lower() for x in argv]
            if name in base and p.info.get("pid") != os.getpid():
                return p.info["pid"]
        except Exception:
            pass
    return None


def _load_ensure_all():
    spec = importlib.util.spec_from_file_location(
        "_ensure_all_guard", os.path.join(ROOT, "var", "_ensure_all.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["_ensure_all_guard"] = m
    spec.loader.exec_module(m)      # main() 有 __main__ 守卫
    return m


SPEC = os.path.join(ROOT, "var", ".official_spec.json")


def spec_freshness(max_hours=12.0):
    """★ R1214：官方 spec 的**新鲜度**检查（返回 (ok, 说明)）。

    为什么：`.official_spec.json` 是 `_switch_to_official.ps1` 写的、**用完不自动删**。
    实测本机现在就留着一份**三测的旧 spec**（strategy=speedgangtakec151fixed、
    token_file=var/.token_3test_20260923）。平时无碍（非官方模式严格 no-op），
    但**只要有人/某流程创建了 `.official_mode`**，本守卫就会按这份旧 spec 拉起
    ⇒ **用旧令牌 + 旧策略**去打正式赛（最坏情况：开赛被剔出分桌）。

    规则：spec 的 `ts` 必须在 `max_hours` 小时内（正式赛切换时会写新 ts）；
    否则**拒绝拉起**并记日志（宁可交 5 分钟兜底链，也不用旧令牌上场）。
    """
    try:
        if not os.path.exists(SPEC):
            return False, "spec 不存在"
        import json
        import datetime as _dt
        with io.open(SPEC, encoding="utf-8-sig") as fh:   # ★ R1344：顺手修掉未关闭句柄
            d = json.load(fh)
        ts = (d or {}).get("ts") or ""
        if not ts:
            return False, "spec 无 ts"
        t = _dt.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        age_h = (_dt.datetime.now() - t).total_seconds() / 3600.0
        if age_h > max_hours:
            return False, ("spec 过期 %.1f 小时（>%.0f）strategy=%s token_file=%s"
                           % (age_h, max_hours, d.get("strategy"), d.get("token_file")))
        return True, "spec 新鲜（%.1f 小时）" % age_h
    except Exception as e:
        return False, "spec 解析失败：%s" % e


def main():
    # ① 非官方模式：严格 no-op
    if not os.path.exists(FLAG):
        return 0
    # ② 官方模式：keepalive 在就不动作
    if _has("_official_keepalive.py"):
        return 0
    # ②′ 官方模式 + keepalive 缺失 ⇒ 先验 spec 新鲜度（防"旧令牌/旧策略"上场）
    fresh, why = spec_freshness()
    if not fresh:
        _log("⚠ 官方模式但 %s ⇒ 不动作（避免用旧令牌/旧策略；交 _ensure_all 兜底并等待人工确认）" % why)
        return 1
    # ③ 官方模式 + keepalive 缺失 ⇒ 按 spec 拉起
    try:
        ea = _load_ensure_all()
        argv = ea.official_argv()
    except Exception as e:
        _log("⚠ 无法读取 official_argv: %s ⇒ 不动作（交 _ensure_all 5 分钟兜底）" % e)
        return 1
    if not argv:
        _log("⚠ 官方模式但 .official_spec.json 缺失/无效 ⇒ 不动作（避免用错令牌/策略）")
        return 1
    try:
        # ★ R1537：本脚本由计划任务用 **pythonw**（无控制台）起 ⇒ 原实现只 Popen、不重定向，
        #   子进程的输出直接落进虚空：**“启动即崩”时日志只剩一句「✓ 已按 spec 拉起」，下一条证据都没有**
        #   （本项目反复抓的“看着成功其实没跑”）。这里把 keepalive 自己的生命周期/异常留下来；
        #   `_official_1024.out` 仍然只装 run_bot 的输出，两者互补。
        with io.open(KEEPALIVE_OUT, "a", encoding="utf-8") as _out:
            subprocess.Popen([sys.executable, "-X", "utf8", "-u",
                              os.path.join(ROOT, "var", "_official_keepalive.py")] + argv,
                             cwd=ROOT, stdout=_out, stderr=subprocess.STDOUT,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        _log("✓ 官方模式且 keepalive 缺失 ⇒ 已按 spec 拉起：%s" % " ".join(argv))
    except Exception as e:
        _log("✗ 拉起失败: %s" % e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
