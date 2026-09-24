# -*- coding: utf-8 -*-
"""批次守夜人：保证「始终恰好一个 match_super」在跑（严格互斥，避免 E002 双实例）。
每 120s 检查：若无 match_super 且无 _chain.py 接续器 → 启动 12 房批次。"""
import os, sys, time, subprocess, io
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import psutil
sys.path.insert(0, os.path.join(ROOT, "var"))
import _feature_mode as _fm  # noqa: E402

STRATEGY = sys.argv[1] if len(sys.argv) > 1 else "speedtug"
try:
    io.open(os.path.join(ROOT, "var", "_keeper_strategy.txt"), "w", encoding="utf-8").write(STRATEGY)
except Exception:
    pass
ROOMS = sys.argv[2] if len(sys.argv) > 2 else "12"
LOG = os.path.join(ROOT, "var", "_keeper.out")
LOCK = os.path.join(ROOT, "var", ".keeper.lock")
AB_FLAG = os.path.join(ROOT, "var", ".ab_mode")
OFFICIAL_FLAG = os.path.join(ROOT, "var", ".official_mode")
TAG = "keeper-%d" % os.getpid()


def _is_script_proc(p, names):
    """精确匹配：可执行名含 python 且 argv 中存在基名为 names 的脚本参数。
    防止把命令行里恰好包含这些字符串的无关进程（如 agent 的 shell）算进来。"""
    try:
        exe = os.path.basename(p.info.get("exe") or "").lower()
        if "python" not in exe:
            return False
        argv = p.info.get("cmdline") or []
        for a in argv[1:]:
            base = os.path.basename(str(a).replace("\\", "/")).lower()
            if base in names:
                return True
    except Exception:
        return False
    return False


def others(names):
    me = os.getpid()
    out = []
    for p in psutil.process_iter(["pid", "cmdline", "exe"]):
        if p.info["pid"] == me:
            continue
        if _is_script_proc(p, set(names)):
            out.append((p.info["pid"], " ".join(p.info.get("cmdline") or [])[:80]))
    return out

def log(msg):
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    print(msg, flush=True)

# ★★ 2026-09-19 修（生产中断）：该模块在 `tools/wait_policy.py`，但本脚本的 sys.path 只有
#    ROOT 与 ROOT/var（脚本目录）⇒ `from wait_policy import ...` 一直抛 ModuleNotFoundError，
#    keeper 一启动就死 ⇒ **watchdog 反复"拉起"却永远起不来 = 生产停摆**（A/B 期间被掩盖）。
sys.path.insert(0, os.path.join(ROOT, "tools"))
from wait_policy import wait_args          # noqa: E402  ★ 安全模块（无副作用，见 tools/wait_policy.py）


def main():
    if os.path.exists(LOCK):
        try:
            old = int(io.open(LOCK, encoding="utf-8").read().strip())
            if old > 0 and psutil.pid_exists(old):
                print("已有守夜人在跑 pid=%s，退出" % old, flush=True)
                return
        except Exception:
            pass
    io.open(LOCK, "w", encoding="utf-8").write(str(os.getpid()))
    log("守夜启动 pid=%d strategy=%s rooms=%s" % (os.getpid(), STRATEGY, ROOMS))
    while True:
        if _fm.pause_requested():
            log("平台暂停模式（.pause_mode）→ keeper 退出")
            try:
                if os.path.exists(LOCK): os.remove(LOCK)
            except Exception:
                pass
            return
        # ★ 2026-09-17 修：A/B 或正式赛模式在跑时，keeper **必须立刻停手**
        #   （否则它会先起一个 4 房批次，把 A/B 的第一房推迟最长 ~2 小时——已发生两次）
        if os.path.exists(AB_FLAG) or os.path.exists(OFFICIAL_FLAG):
            log("检测到 .ab_mode/.official_mode → keeper 退出（把排批让给 _ab_driver/正式赛 keepalive）")
            try:
                if os.path.exists(LOCK):
                    os.remove(LOCK)
            except Exception:
                pass
            return
        ms = others(["match_super.py"])
        ch = others(["_chain.py", "_keeper.py"])   # 精确匹配
        if ms:
            time.sleep(120)
            continue
        if [c for c in ch if "keeper" not in c[1]]:
            log("接续器在工作，等待")
            time.sleep(120)
            continue
        argv = [sys.executable, "-X", "utf8", "-u",
                os.path.join(ROOT, "tools", "match_super.py"),
                "--rooms", ROOMS, "--strategy", STRATEGY] + wait_args()
        stamp = time.strftime("%Y%m%d_%H%M%S")
        outp = os.path.join(ROOT, "var", "_run_%s.out" % stamp)
        with io.open(outp, "a", encoding="utf-8") as f:
            subprocess.Popen(argv, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        log("已启动新批次 %s 房 → %s" % (ROOMS, outp))
        time.sleep(180)

main()
