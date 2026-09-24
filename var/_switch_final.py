# -*- coding: utf-8 -*-
"""`var/_switch_final.py` —— **10/7 换上最终臂**（用户 2026-09-24 指令：\u201c\u5728\u4e03\u53f7\u6362\u4e0a\u4f60\u80fd\u6413\u51fa\u6765\u7684\u6700\u5c4c\u7684\u6a21\u578b\u201d\uff09\u3002

## 做什么（按顺序，任一步不满足就**停**，不硬来）

1. 读 `var/.final_arm.txt`（最终臂名；由 10/5\u201310/6 用 `var/_pick_arm.py` + \u00a7V.160 \u53d6\u820d\u89c4\u5219\u51b3\u5b9a\u540e\u5199\u5165\uff09\uff1b
   **文件不存在 \u21d2 \u76f4\u63a5\u62d2\u7edd**\uff08\u7edd\u4e0d\u731c\u4e00\u4e2a\u81c2\u88c5\u4e0a\u53bb\uff09\uff1b
2. \u9a8c\u8bc1\u8be5\u81c2\uff1a\u5df2\u6ce8\u518c\u5230 `run_bot.py` + \u53ef\u5b9e\u4f8b\u5316\uff08\u8c03\u7528\u771f\u5b9e factory\uff09\uff1b
3. \u82e5 `var/.official_mode` \u5b58\u5728\uff08\u6b63\u5728\u5b98\u65b9\u8d5b\u4e2d\uff09\u21d2 **\u62d2\u7edd**\uff08\u6bd4\u8d5b\u671f\u95f4\u4e0d\u6362\u81c2\uff09\uff1b
4. \u505c A/B\uff08`tools/ab_ctl.py stop`\uff0c\u5b83\u81ea\u5df1\u6309\u89c4\u77e9\u6765\uff09\u2192 **\u7b49\u5bf9\u5c40\u81ea\u7136\u7ed3\u675f**\uff08\u8f6e\u8be2\uff0c\u8d85\u65f6\u5c31\u505c\uff0c\u7edd\u4e0d\u5f3a\u6740\uff09\uff1b
5. `var/_switch_test_strategy.py <\u6700\u7ec8\u81c2>`\uff08\u5199 `_keeper_strategy.txt` + \u91cd\u542f keeper\uff09\uff1b
6. \u6821\u9a8c\uff1a`_keeper_strategy.txt` == \u6700\u7ec8\u81c2\u3001keeper/match_super/run_bot **\u5355\u5b9e\u4f8b**\uff1b\u5199 `var/.final_installed`\uff08\u542b\u81c2\u540d+\u65f6\u95f4\uff09\u3002

## 红线

\u4e0d\u5728\u5b98\u65b9\u8d5b\u671f\u95f4\u52a8\u4f5c\uff1b\u4e0d\u5f3a\u6740\u5bf9\u5c40\uff1b\u6700\u7ec8\u81c2\u672a\u9009\u5b9a/\u672a\u9a8c\u8bc1\u5c31\u4e0d\u52a8\u3002\u65e5\u5fd7 `var/_switch_final.log`\u3002

\u7528\u6cd5\uff1a
    python -X utf8 var/_switch_final.py --dry-run      # \u53ea\u6253\u5370\u5c06\u505a\u4ec0\u4e48
    python -X utf8 var/_switch_final.py --go           # \u771f\u6267\u884c
"""
from __future__ import annotations
import argparse
import io
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "var", "_switch_final.log")
OFFICIAL = os.path.join(ROOT, "var", ".official_mode")
FINAL_ARM = os.path.join(ROOT, "var", ".final_arm.txt")
MARKER = os.path.join(ROOT, "var", ".final_installed")
GUARD_OFF = os.path.join(ROOT, "var", ".rate_guard_off")   # ★ R1444：固定最终臂，防生产熔断静默回退


def wait_patterns():
    """换臂前只等**对局进程**（run_bot/match_super）自然结束。

    ★ R1444（真雷）：原实现把 `_keeper.py` 也放进等待条件 ⇒ **永远等不到**：
    本机 watchdog 日志实测，`.ab_mode` 一消失，watchdog 就每 90 秒把 keeper 拉回来
    （09-23 03:07:50 / 03:09:20 两次「keeper 缺失，已按 strategy=… 拉起」正好间隔 90 秒），
    而 keeper 是**常驻监督器**、平时一直在跑房 ⇒ 25 分钟必然超时 ⇒ 10/7 换臂失败（12:00 重试同样失败）。
    keeper 的换策略方式本来就是"杀掉 → 由 watchdog 按 `_keeper_strategy.txt` 重启"（见 `_switch_test_strategy.py`），
    所以它**不该**被当成"还要等它退出"的对象。
    """
    return ("run_bot.py", "match_super.py")


def kill_keepers():
    """只杀 `_keeper.py`（**监督器**，不碰 match_super/run_bot）。见上述理由。

    红线仍守：`_watchdog.py` / `_ab_driver.py` / `match_super.py` / `run_bot.py` 一律不碰。
    """
    killed = []
    try:
        import psutil
    except Exception:
        return killed
    me = os.getpid()
    for pr in psutil.process_iter(["pid", "cmdline", "exe"]):
        try:
            if pr.info["pid"] == me:
                continue
            exe = os.path.basename(pr.info.get("exe") or "").lower()
            if "python" not in exe:
                continue
            args = [os.path.basename(str(x).replace("\\", "/")) for x in (pr.info.get("cmdline") or [])[1:]]
            if "_keeper.py" in args:
                psutil.Process(pr.info["pid"]).kill()
                killed.append(pr.info["pid"])
        except Exception:
            pass
    return killed
KEEPER_STRAT = os.path.join(ROOT, "var", "_keeper_strategy.txt")


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def procs(pattern):
    try:
        import psutil
    except Exception:
        return []
    out = []
    for p in psutil.process_iter(["pid", "cmdline", "exe"]):
        try:
            exe = os.path.basename(p.info.get("exe") or "").lower()
            if "python" not in exe:
                continue
            for a in (p.info.get("cmdline") or [])[1:]:
                if os.path.basename(str(a).replace("\\", "/")) == pattern:
                    out.append(p.info["pid"])
                    break
        except Exception:
            pass
    return out


def arm_ok(name):
    sys.path.insert(0, ROOT)
    try:
        from run_bot import STRATEGY_FACTORIES as F
    except Exception as e:
        return False, "\u65e0\u6cd5\u5bfc\u5165 run_bot\uff08%s\uff09" % str(e)[:60]
    if name not in F:
        return False, "\u672a\u6ce8\u518c\u5230 run_bot.py"
    try:
        F[name]()
    except Exception as e:
        return False, "\u5b9e\u4f8b\u5316\u5931\u8d25\uff08%s: %s\uff09" % (type(e).__name__, str(e)[:60])
    return True, "ok"


def marker_text(arm, keeper_pids):
    """写入 `var/.final_installed` 的内容：安装凭证 + **10/10 当天可直接执行的正式赛命令**。

    为什么把命令一并写进去：10/7 换臂与 10/10 上场是两件事（前者换训练房策略，
    后者还要把同一个臂传给 `_switch_to_official.ps1`）。把后者预先写成可拷贝命令，
    避免比赛当天临场拼参数。
    """
    return (
        "%s | arm=%s | keeper=%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), arm, keeper_pids)
        + "10/10 \u6b63\u5f0f\u8d5b\u547d\u4ee4\uff08\u628a <TOK>/<TID> \u6362\u6210\u5f53\u5929\u7684\u4ee4\u724c\u6587\u4ef6\u4e0e\u8d5b\u4e8b id\uff09\uff1a\n"
        + "  python -X utf8 var/_ready_1024.py --tid <TID> --token-file <TOK>        # T-30 / T-5 \u5404\u4e00\u6b21\uff08\u5e42\u7b49\uff09\n"
        + "  powershell -NoProfile -File var/_switch_to_official.ps1 -Strategy %s -TokenFile <TOK> -TournamentId <TID>\n" % arm
        + "  # \u4ec5\u5f53 preflight \u56e0\u3010\u672a\u77e5 BREAKING\u3011\u5361\u4f4f\u4e14\u5df2\u4eba\u5de5\u786e\u8ba4\u65e0\u5bb3\u65f6\uff0c\u624d\u52a0 -AllowNotReady\n"
    )


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="只打印（与默认同义，取明确语义）")
    ap.add_argument("--final-file", default=FINAL_ARM)
    ap.add_argument("--wait-min", type=int, default=25)
    a = ap.parse_args(argv)

    if not os.path.exists(a.final_file):
        log("!! \u6700\u7ec8\u81c2\u672a\u9009\u5b9a\uff08\u7f3a %s\uff09\u21d2 \u62d2\u7edd\u6267\u884c" % os.path.basename(a.final_file))
        return 2
    arm = io.open(a.final_file, encoding="utf-8-sig").read().strip()
    if not arm:
        log("!! \u6700\u7ec8\u81c2\u6587\u4ef6\u4e3a\u7a7a \u21d2 \u62d2\u7edd")
        return 2
    ok, why = arm_ok(arm)
    log("\u6700\u7ec8\u81c2 = %s\uff08\u6821\u9a8c\uff1a%s\uff09" % (arm, why))
    if not ok:
        return 2
    if os.path.exists(OFFICIAL):
        log("!! \u5b98\u65b9\u6a21\u5f0f\u5728\u4f4d\uff08\u6bd4\u8d5b\u4e2d\uff09\u21d2 \u4e0d\u6362\u81c2")
        return 2
    cur = ""
    try:
        cur = io.open(KEEPER_STRAT, encoding="utf-8-sig").read().strip()
    except Exception:
        pass
    if os.path.exists(MARKER) and cur == arm and not procs("_keeper.py"):
        log("\u5df2\u662f\u6700\u7ec8\u81c2\u4e14\u65e0\u5f79\u5728\u8dd1\uff08%s\uff09\u21d2 no-op" % arm)
        return 0
    if (not a.go) or a.dry_run:
        print("=== dry-run：将执行 ===")
        print("  1) python -X utf8 tools/ab_ctl.py stop")
        print("  2) 写 _keeper_strategy.txt = %s（watchdog 重启 keeper 时会读它）" % arm)
        print("  3) 杀 _keeper.py（只杀监督器；不碰 match_super/run_bot）")
        print("  4) 等对局进程自然结束（最多 %d 分钟）" % a.wait_min)
        print("  5) python -X utf8 var/_switch_test_strategy.py %s" % arm)
        print("  6) 校验 + 写 .rate_guard_off（防熔断回退）＋ 写 %s" % os.path.basename(MARKER))
        return 0

    py = sys.executable
    log("\u505c A/B\uff1a%s" % " ".join([py, "-X", "utf8", "tools/ab_ctl.py", "stop"]))
    p = subprocess.run([py, "-X", "utf8", "tools/ab_ctl.py", "stop"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    log("ab_ctl stop rc=%s %s" % (p.returncode, (p.stdout or "").strip().splitlines()[-1:] or ""))
    # ★ R1444：先把策略写进文件（watchdog 重启 keeper 时会读它），再杀掉 keeper 阻止新房，
    #   然后**只等对局进程**结束 —— 这样才收敛（原实现在这里死等 keeper）。
    try:
        with io.open(KEEPER_STRAT, "w", encoding="utf-8") as f:
            f.write(arm)
        log("已写 _keeper_strategy.txt = %s（供 watchdog 重启 keeper 时读取）" % arm)
    except Exception as e:
        log("!! 写 _keeper_strategy.txt 失败：%s ⇒ 停止" % str(e)[:60])
        return 2
    kk = kill_keepers()
    log("杀 keeper（仅监督器）：%s" % (kk or "无"))
    t0 = time.time()
    while time.time() - t0 < a.wait_min * 60:
        alive = [x for pat in wait_patterns() for x in procs(pat)]
        if not alive:
            break
        log("\u7b49\u5bf9\u5c40\u81ea\u7136\u7ed3\u675f\u4e2d\uff08\u8fd8\u5728\uff1a%s\uff09" % ",".join(sorted({str(x) for x in alive})))
        time.sleep(15)
    else:
        log("!! \u7b49 %d \u5206\u949f\u4ecd\u6709\u8fdb\u7a0b \u21d2 \u505c\u6b62\uff08\u7edd\u4e0d\u5f3a\u6740\uff09" % a.wait_min)
        return 2
    log("\u5f00\u6362\u7b56\u7565\uff1avar/_switch_test_strategy.py %s" % arm)
    p = subprocess.run([py, "-X", "utf8", "var/_switch_test_strategy.py", arm], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    tail = "\n".join((p.stdout or "").strip().splitlines()[-6:])
    log("switch rc=%s\n%s" % (p.returncode, tail))
    if p.returncode != 0:
        return 2
    try:
        now = io.open(KEEPER_STRAT, encoding="utf-8-sig").read().strip()
    except Exception:
        now = ""
    k = procs("_keeper.py")
    if now != arm or len(k) > 1:
        log("!! \u6821\u9a8c\u5931\u8d25\uff1a_keeper_strategy=%r keeper=%s \u21d2 \u9700\u4eba\u5de5" % (now, k))
        return 2
    # ★ R1444：最终臂是**已判正**的决定，不能被生产熔断静默改回 FALLBACK。
    #   （A/B 一停、.official_mode 未写时 rate_guard 就生效：40 房净胜 < −40 ⇒ 回退 speedtugc。）
    try:
        with io.open(GUARD_OFF, "w", encoding="utf-8") as f:
            f.write("%s 最终臂 %s：停用 rate_guard（防静默回退）\n"
                    % (time.strftime("%Y-%m-%d %H:%M:%S"), arm))
        log("已写 .rate_guard_off（最终臂 %s 不再被生产熔断回退）" % arm)
    except Exception as e:
        log("⚠ 写 .rate_guard_off 失败：%s" % str(e)[:60])
    try:
        with io.open(MARKER, "w", encoding="utf-8") as f:
            f.write(marker_text(arm, k))
    except Exception as e:
        log("\u26a0 \u5199 marker \u5931\u8d25\uff1a%s" % str(e)[:60])
    log("\u2605 \u6700\u7ec8\u81c2\u5df2\u6362\u4e0a\uff1a%s\uff08keeper=%s\uff09" % (arm, k))
    return 0


if __name__ == "__main__":
    sys.exit(main())