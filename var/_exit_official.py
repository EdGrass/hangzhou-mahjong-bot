# -*- coding: utf-8 -*-
"""退出官方赛模式：删哨兵并恢复测试房自愈。

用法：python -X utf8 var/_exit_official.py

⚠ 2026-09-17 加保护（演练前发现的操作隐患）：
   本脚本会**先删哨兵再调 `_ensure_all.py`**，而 `_ensure_all` 一旦看不到哨兵就会**拉起测试房 keeper**。
   若此时官方赛链（`_official_keepalive.py` / `run_bot.py`）还活着 ⇒ **同账号并发 = E002**。
   ⇒ 现在先检查这两个进程，**在跑就拒绝执行**并提示等对局自然结束。
"""
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAG = os.path.join(ROOT, "var", ".official_mode")


# ★ 2026-09-17 加固：**任何** bot 链的进程在跑都拒绝退出官方赛模式。
#   为什么：原实现只查 run_bot/_official_keepalive ⇒ 若在"批次间隙"（run_bot 恰好不在、
#   但 `_ab_driver`/`match_super`/`_keeper` 还活着）执行，删哨兵后 `_ensure_all` 会拉起 keeper
#   ⇒ 与在跑的 A/B 链**同账号并发 = E002**。现在把这些进程名一并纳入拒绝名单。
BUSY_NAMES = ("run_bot.py", "_official_keepalive.py", "match_super.py", "_ab_driver.py", "_keeper.py")


def busy_names(cmdlines):
    """纯函数：给一组命令行列表，返回其中属于"bot 链"的脚本名（供单测）。"""
    out = []
    for argv in cmdlines or []:
        for a in list(argv or [])[1:]:
            base = os.path.basename(str(a).replace("\\", "/")).lower()
            if base in BUSY_NAMES:
                out.append(base)
                break
    return out


def _busy_official():
    """返回仍在运行的 bot 链进程名列表（run_bot / keepalive / match_super / _ab_driver / _keeper）。"""
    out = []
    try:
        import psutil
    except Exception:
        return out
    for p in psutil.process_iter(["cmdline", "exe"]):
        try:
            exe = os.path.basename(p.info.get("exe") or "").lower()
            if "python" not in exe:
                continue
            out += busy_names([p.info.get("cmdline") or []])
        except Exception:
            pass
    return out


def main():
    busy = _busy_official()
    if busy:
        print("⚠ 检测到官方赛进程仍在运行：%s" % ", ".join(sorted(set(busy))))
        print("   为防同账号并发（E002），**暂不退出官方赛模式**（哨兵保持在线，测试房自愈继续停用）。")
        print("   请等对局自然结束（run_bot 退出 0 后 _official_keepalive 会自行结束），再重跑本脚本。")
        return 2
    if os.path.exists(FLAG):
        os.remove(FLAG)
        print("已删除哨兵：", FLAG)
    else:
        print("哨兵不存在（当前不在官方赛模式）：", FLAG)
    # 立刻触发一次自愈入口，把测试房 keeper 拉起（不必等计划任务）
    try:
        subprocess.run([sys.executable, "-X", "utf8",
                        os.path.join(ROOT, "var", "_ensure_all.py")], cwd=ROOT, timeout=120)
        print("已调用 _ensure_all.py：测试房自愈将恢复（watchdog 也会在 ≤90s 内生效）")
    except Exception as e:
        print("调用 _ensure_all 失败（计划任务仍会在 ≤5min 内恢复）：", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
