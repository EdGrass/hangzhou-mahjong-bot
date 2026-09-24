# -*- coding: utf-8 -*-
"""长跑看门狗：只在「明确卡死」时动作，避免误杀正在打的对局。

判定（每 90s）：
  卡死 = 最近房日志 mtime > STALL_MIN 且 auto_ranking.jsonl mtime > STALL_MIN
动作：
  1) 若 match_super 存活且其输出尾部出现 >=3 次「match 失败」→ 判为鉴权/网络卡死：
     轮换全局令牌 → 杀掉该 match_super 与其 run_bot 子进程 → 交给 _keeper.py 重启
  2) 若无 run_bot 存活（监督器卡住）→ 杀 match_super，交给 keeper
  3) 其余情况只记日志，不动任何进程
"""
import io, os, sys, time, glob, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import psutil
sys.path.insert(0, os.path.join(ROOT, "var"))
import _feature_mode as _fm  # noqa: E402

STALL_MIN = 20          # 分钟
NOCHILD_NEED = 5        # 连续 N 次（N*90s）都「无 match_super 且无 run_bot」→ 判 keeper 卡死


def decide_action(ms_n, rb_n, fails, nochild_streak):
    """卡死时的动作决策（纯函数，便于单测）。

    返回 (action, new_streak)：
      rotate       —— match_super 存活且尾部 >=3 次 match 失败（鉴权/网络卡死）
      kill_ms      —— match_super 存活但无 run_bot（监督器卡住）
      restart_kpr  —— **match_super 与 run_bot 都不在**：keeper 卡死，需杀掉交自愈重拉
      none         —— 其余（可能在长局中）
    """
    if ms_n and fails >= 3:
        return "rotate", 0
    if ms_n and not rb_n:
        return "kill_ms", 0
    if not ms_n and not rb_n:
        streak = nochild_streak + 1
        if streak >= NOCHILD_NEED:
            return "restart_kpr", 0
        return "none", streak
    return "none", 0

LOG = os.path.join(ROOT, "var", "_watchdog.out")
LOCK = os.path.join(ROOT, "var", ".watchdog.lock")
ME_TAG = "watchdog-%d" % os.getpid()


def log(msg):
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    print(msg, flush=True)


def age_min(path):
    try:
        return (time.time() - os.path.getmtime(path)) / 60.0
    except OSError:
        return None



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


def procs(name):
    out = []
    for p in psutil.process_iter(["pid", "cmdline", "create_time", "exe"]):
        if _is_script_proc(p, {name}):
            out.append((p.info["pid"], " ".join(p.info.get("cmdline") or []),
                        p.info["create_time"]))
    return out


def newest(pattern):
    fs = glob.glob(pattern)
    return max(fs, key=os.path.getmtime) if fs else None


def kill(pid, why):
    try:
        psutil.Process(pid).kill()
        log("  已杀 pid=%d（%s）" % (pid, why))
    except Exception as e:
        log("  杀 pid=%d 失败: %s" % (pid, e))


OFFICIAL_FLAG = os.path.join(ROOT, "var", ".official_mode")
AB_FLAG = os.path.join(ROOT, "var", ".ab_mode")


def official_mode():
    """官方赛期间为 True：测试房自愈全部暂停（防与正式赛同账号并发 E002）。"""
    return os.path.exists(OFFICIAL_FLAG)


def ab_mode():
    """并发交替 A/B 期间为 True：排批交给 var/_ab_driver.py，watchdog 不碰 keeper。"""
    return os.path.exists(AB_FLAG)
KEEPER_STRAT_FILE = os.path.join(ROOT, "var", "_keeper_strategy.txt")
KEEPER_ROOMS = "4"


def keeper_strategy():
    try:
        v = io.open(KEEPER_STRAT_FILE, encoding="utf-8").read().strip()
        if v:
            return v
    except OSError:
        pass
    return "speedc073w2"


def ensure_ab_driver():
    """A/B 模式下：保证 _ab_driver.py 活着（它就是这一层的「keeper」）。

    与 ensure_keeper 同一思路 —— 否则驱动一死，排批就停了，而 watchdog 在 A/B 模式下
    什么也不做 ⇒ 又是一个「没人管」的洞。"""
    if procs("_ab_driver.py"):
        return
    try:
        subprocess.Popen([sys.executable, "-X", "utf8", "-u",
                          os.path.join(ROOT, "var", "_ab_driver.py")],
                         cwd=ROOT, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        log("  → A/B 驱动缺失，已按 var/.ab_mode 拉起")
    except Exception as e:
        log("  → A/B 驱动拉起失败: %s" % e)


def run_rate_guard():
    """调用 tools/rate_guard.py（自行处理官方模式/开关/阈值）。静默失败。"""
    try:
        subprocess.run([sys.executable, "-X", "utf8",
                        os.path.join(ROOT, "tools", "rate_guard.py")],
                       cwd=ROOT, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def ensure_keeper():
    """守夜人自愈：keeper 不在就按 var/_keeper_strategy.txt 的策略拉起（幂等，keeper 自带锁）。"""
    ks = [p for p in procs("_keeper.py")]
    if ks:
        return
    strat = keeper_strategy()
    try:
        lock = os.path.join(ROOT, "var", ".keeper.lock")
        io.open(lock, "w", encoding="utf-8").write("0")
        subprocess.Popen([sys.executable, "-X", "utf8", "-u",
                          os.path.join(ROOT, "var", "_keeper.py"), strat, KEEPER_ROOMS],
                         cwd=ROOT, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        log("  → keeper 缺失，已按 strategy=%s 拉起" % strat)
    except Exception as e:
        log("  → keeper 拉起失败: %s" % e)


def main():
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    if os.path.exists(LOCK):
        try:
            old = int(io.open(LOCK, encoding="utf-8").read().strip())
            if old > 0 and psutil.pid_exists(old):
                print("已有看门狗 pid=%s" % old, flush=True)
                return
        except Exception:
            pass
    io.open(LOCK, "w", encoding="utf-8").write(str(os.getpid()))
    log("看门狗启动 pid=%d（卡死阈值 %d 分钟）" % (os.getpid(), STALL_MIN))
    last_state = ""
    nochild = 0
    while True:
        if _fm.pause_requested():
            if _fm.feature_match_enabled():
                try:
                    os.remove(_fm.PAUSE_FLAG)
                except OSError:
                    pass
                log("match_enabled=true → 解除平台暂停模式")
            else:
                if last_state != "平台暂停模式":
                    log("平台暂停模式（.pause_mode，match_enabled=false）：不启/不杀任何进程")
                    last_state = "平台暂停模式"
                time.sleep(90)
                continue
        # 官方赛模式：正式赛期间**绝不能**拉起测试房 keeper（同账号并发 → E002 冲突）。
        # 由 var/_switch_to_official.ps1 写入哨兵；赛后删哨兵即恢复正常自愈。
        if official_mode():
            if last_state != "官方模式":
                ms0 = procs("match_super.py")
                rb0 = procs("run_bot.py")
                kp0 = procs("_keeper.py")
                log("官方模式（.official_mode 存在）：暂停测试房自愈，不启/不杀任何进程"
                    "（keeper=%d match_super=%d run_bot=%d）" % (len(kp0), len(ms0), len(rb0)))
                if kp0 or ms0:
                    log("  ⚠ 官方模式下仍有测试房进程在跑，请确认是否与正式赛冲突（E002）")
                last_state = "官方模式"
            time.sleep(90)
            continue
        if ab_mode():
            # A/B 驱动自己管理排批；这里**既不自愈 keeper 也不杀任何进程**，
            # 否则会起 keeper → 双开 match_super → E002。
            if last_state != "A/B模式":
                log("A/B 模式（.ab_mode 存在）：排批交给 _ab_driver.py")
                last_state = "A/B模式"
            ensure_ab_driver()
            time.sleep(90)
            continue
        lg = newest(os.path.join(ROOT, "logs", "auto_*.log"))
        a_rank = os.path.join(ROOT, "var", "auto_ranking.jsonl")
        a_log = age_min(lg) if lg else None
        a_arc = age_min(a_rank)
        ms = procs("match_super.py")
        rb = procs("run_bot.py")
        stalled = (a_log is not None and a_log > STALL_MIN
                   and a_arc is not None and a_arc > STALL_MIN)
        state = "卡死" if stalled else "正常"
        if state != last_state:
            log("状态=%s（房日志 %.1f 分钟前；归档 %.1f 分钟前；match_super=%d run_bot=%d）"
                % (state, a_log or -1, a_arc or -1, len(ms), len(rb)))
            last_state = state
        if not stalled:
            nochild = 0          # 已恢复：清空「双缺」计数，避免陈旧计数触发误杀
        if stalled:
            # 只告警、绝不杀：run_bot 存活但其 --log 文件长时间不更新 ⇒ 疑卡死。
            # （历史上 1504 次「暂不动作」全部是 run_bot=0 的双缺，此情形尚未出现过，
            #   因此这里保持零风险：仅写日志提示人工/后续处理，不动任何进程。）
            if ms and rb:
                for _pid, _cl, _ct in rb:
                    _lp = ""
                    _argv = str(_cl).split()
                    for _i, _a in enumerate(_argv):
                        if _a == "--log" and _i + 1 < len(_argv):
                            _lp = _argv[_i + 1].strip('"')
                    _age = age_min(_lp) if _lp else None
                    if _age is not None and _age > STALL_MIN:
                        log("  ⚠ run_bot pid=%s 存活但日志 %.0f 分钟未更新（疑卡死，仅告警不杀）"
                            % (_pid, _age))
            run_out = newest(os.path.join(ROOT, "var", "_run*.out"))
            fails = 0
            if run_out:
                try:
                    tail = io.open(run_out, encoding="utf-8", errors="replace").read().splitlines()[-30:]
                    fails = sum(1 for l in tail if "match 失败" in l)
                except Exception:
                    pass
            log("  诊断：run_out=%s match失败行=%d run_bot=%d"
                % (os.path.basename(run_out) if run_out else "无", fails, len(rb)))
            action, nochild = decide_action(len(ms), len(rb), fails, nochild)
            if action == "none" and not ms and not rb:
                log("  → 无 match_super 且无 run_bot（%d/%d 次），待确认后重启 keeper"
                    % (nochild, NOCHILD_NEED))
            elif action == "restart_kpr":
                log("  → 监督器与对局进程双缺超过 %d 次：判 keeper 卡死，杀掉交自愈重拉"
                    % NOCHILD_NEED)
                for pid, cl, ct in procs("_keeper.py"):
                    kill(pid, "keeper 卡死（无 match_super/run_bot）")
            elif action == "rotate":
                log("  → 判为鉴权/网络卡死，轮换令牌")
                try:
                    r = subprocess.run([sys.executable, "-X", "utf8",
                                        os.path.join(ROOT, "var", "_rotate_token.py")],
                                       cwd=ROOT, capture_output=True, text=True, timeout=60)
                    log("  轮换结果: %s" % ((r.stdout or r.stderr or "").strip()[:200]))
                except Exception as e:
                    log("  轮换异常: %s" % e)
                for pid, cl, ct in ms:
                    kill(pid, "match_super 卡死")
                for pid, cl, ct in rb:
                    kill(pid, "残留 run_bot")
            elif action == "kill_ms":
                log("  → 监督器卡死（无 run_bot），杀掉交给 keeper 重启")
                for pid, cl, ct in ms:
                    kill(pid, "监督器卡死")
            else:
                log("  → 暂不动作（可能在长局中）")
        # 生产策略熔断：最近 6 房净胜崩坏即回退已验证策略。
        # **必须先于 ensure_keeper**：若熔断器杀掉了 keeper，本轮 ensure_keeper
        # 就会立刻按回退后的策略把它重拉起来（否则要等下一个 90s）。
        run_rate_guard()
        ensure_keeper()
        time.sleep(90)


def _supervised_main():
    """守护壳：main() 是无限循环；一旦它因任何未预期异常退出，不要让 watchdog 就此消失
    （watchdog 死掉 = 整层失去兜底，这正是 E023 那类事故的根源）。
    捕获后写日志并重启循环。"""
    import traceback
    while True:
        try:
            return main()
        except KeyboardInterrupt:
            return
        except Exception:
            try:
                log("!! watchdog 主循环异常退出，5s 后重启：\n%s" % traceback.format_exc()[-800:])
            except Exception:
                pass
            time.sleep(5)


if __name__ == "__main__":
    _supervised_main()
