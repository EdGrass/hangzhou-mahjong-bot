# -*- coding: utf-8 -*-
"""并发交替真机 A/B 的控制台。

用法：
    python -X utf8 tools/ab_ctl.py start speedtugc speedc130 [rooms=1]
    python -X utf8 tools/ab_ctl.py status
    python -X utf8 tools/ab_ctl.py stop

start 会：写 var/.ab_mode（含起始时间）→ 停掉 keeper → 拉起 var/_ab_driver.py。
stop 会：删哨兵 → 杀掉驱动 → 剩下的交给 watchdog（≤90s 把 keeper 拉回来）。
"""
from __future__ import annotations
import io
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
AB = os.path.join(ROOT, "var", ".ab_mode")
DRIVER = os.path.join(ROOT, "var", "_ab_driver.py")


def _procs(name):
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
                if os.path.basename(str(a).replace("\\", "/")) == name:
                    out.append(p.info["pid"]); break
        except Exception:
            pass
    return out


def _kill_idle_match_super():
    """房与房之间（match_super 在、run_bot 不在）时杀掉它，让 A/B 立刻接管排批。

    为什么需要（2026-09-16 实测）：keeper 是**4 房一批**，`ab_ctl start` 若碰上批次中段，
    A/B 驱动要等整批（最长 ~1h）才开始轮转；期间房间仍按基线跑，而且会被
    `ab_readout` 的"本战役"口径**误算成战役房**。
    安全边界：**只要 run_bot 存活（正在打）就什么都不做**——绝不中断在途对局。
    """
    try:
        import psutil
    except Exception:
        return
    rb = _procs("run_bot.py")
    if rb:
        return                      # 有对局在打：不动
    for pid in _procs("match_super.py"):
        try:
            import psutil as _p
            _p.Process(pid).kill()
            print("停空闲 match_super pid=%d（房与房之间，A/B 立刻接管）" % pid)
        except Exception as e:
            print("停空闲 match_super 失败（不影响后续）:", e)


def build_cfg(arms, rooms, bundles=None, started=None, arm_opts=None):
    """构造 `.ab_mode` 配置（纯函数，可单测）。

    - 2 臂用 `{"a","b"}`（兼容旧格式与 `_ab_driver`），≥3 臂用 `{"arms":[...]}`；
    - **`bundles` 两种格式都必须写**：组合臂的终点判据是 t≥1.50/150 房，单变量是 1.96/100 房，
      一旦丢掉这个字段，读表与采用工具就会把组合臂当单变量 ⇒ 用更严的阈值 ⇒ **战役白跑**
      （2026-09-16 实测：`start()` 原来只在 ≥3 臂分支里写 bundles）。
    """
    arms = [str(x).strip() for x in (arms or []) if str(x).strip()]
    cfg = ({"a": arms[0], "b": arms[1]} if len(arms) == 2 else {"arms": arms})
    cfg["rooms"] = int(rooms or 1)
    cfg["started"] = started or time.strftime("%Y-%m-%d %H:%M:%S")
    b = [str(x).strip() for x in (bundles or []) if str(x).strip()]
    if b:
        cfg["bundles"] = b
    # ★ 2026-09-16：逐臂选项（如 {"speedtugc_w50": {"wait_until_second": 50}}）——
    # 供"入席秒 ↔ 同桌强度"预登记实验（STATUS §9.87）；`_ab_driver.arm_extra_args` 翻成命令行参数。
    if arm_opts:
        cfg["arm_opts"] = {str(k): dict(v or {}) for k, v in arm_opts.items()}
    return cfg


def parse_start_args(args):
    """解析 `start` 的参数（纯函数，可单测）：形态 `<臂1[,臂2...]> [rooms] [--bundles=A,B] [--arm-opt=策略.键=值 ...]`。"""
    args = [str(x) for x in (args or [])]
    if not args:
        raise SystemExit("用法: ab_ctl.py start <基线[,候选2,候选3...]> [rooms=1] [--bundles=候选X,候选Y]")
    arms = [x.strip() for x in args[0].split(",") if x.strip()]
    bundles, rooms, arm_opts, started = [], 1, {}, None
    for x in args[1:]:
        if x.startswith("--bundles="):
            bundles = [y.strip() for y in x.split("=", 1)[1].split(",") if y.strip()]
        elif x.startswith("--arm-opt="):
            spec = x.split("=", 1)[1]
            if "." not in spec or "=" not in spec:
                raise SystemExit("--arm-opt 形态应为 --arm-opt=<策略>.<键>=<值>")
            who, rest = spec.split(".", 1)
            k, v = rest.split("=", 1)
            try:
                v2 = int(v)
            except ValueError:
                v2 = v
            arm_opts.setdefault(who.strip(), {})[k.strip()] = v2
        elif x.startswith("--started="):
            # ★ 2026-09-17：**跨中断保留战役身份**。正式赛/测试赛会打断 A/B（19:00 切、22:00 恢复），
            #   而 `ab_readout` 的判定是**按 started 过滤**的 ⇒ 若恢复时重置 started，
            #   前面已积累的房会被判为"不属于本役"⇒ 12 房机制闸门与 150 房采用计数**全部清零**。
            #   恢复同一战役时请显式传回**原 started**。
            started = x.split("=", 1)[1].strip() or None
        elif not x.startswith("--") and x.isdigit():
            rooms = int(x)
    return arms, rooms, bundles, arm_opts, started


def start(arms, rooms, bundles=None, arm_opts=None, force=False, started=None):
    """arms: 策略名列表（>=2）。第 1 个是基线，其余是候选。
    bundles: 预先声明为「组合臂」的策略名（读数时用 |t|≥1.50 的低阈值；单变量 1.96）。"""
    from run_bot import STRATEGY_FACTORIES as F
    arms = [x.strip() for x in arms if x.strip()]
    if len(arms) < 2:
        raise SystemExit("至少需要 2 个策略")
    for s in arms:
        if s not in F:
            raise SystemExit("策略未注册：%s" % s)
    for b in (bundles or []):
        if b not in arms:
            raise SystemExit("bundles 里的 %r 不在本战役臂 %s 内" % (b, arms))
    for who in (arm_opts or {}):
        if who not in arms:
            raise SystemExit("arm_opts 里的 %r 不在本战役臂 %s 内" % (who, arms))
    # ★★ 2026-09-17 加护栏（E002）：**已有一个 `_ab_driver` 在跑时拒绝启动新战役**。
    #   为什么：旧实现直接覆盖 `.ab_mode` 并再拉一个驱动 ⇒ 两个驱动都看到新配置、都排批 ⇒
    #   同账号两房并发 = E002。正确做法是先 `ab_ctl.py stop`（等驱动自然退出）再 start。
    running = _procs("_ab_driver.py")
    if running and not force:
        print("⚠ 已有 _ab_driver 在跑（pid=%s）：**拒绝启动新战役**（否则两个驱动会同时排批 ⇒ E002）"
              % ",".join(str(x) for x in running))
        print("   请先 `python -X utf8 tools/ab_ctl.py stop`（它会等当前对局自然结束，最多 20 分钟），确认驱动退出后再 start。")
        return 2
    cfg = build_cfg(arms, rooms, bundles, started=started, arm_opts=arm_opts)
    with io.open(AB, "w", encoding="utf-8") as f:
        f.write(json.dumps(cfg, ensure_ascii=False))
    print("已写 var/.ab_mode:", cfg)
    for pid in _procs("_keeper.py"):
        try:
            import psutil; psutil.Process(pid).kill(); print("停 keeper pid=%d" % pid)
        except Exception as e:
            print("停 keeper 失败:", e)
    _kill_idle_match_super()
    subprocess.Popen([sys.executable, "-X", "utf8", "-u", DRIVER], cwd=ROOT,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    print("已拉起 _ab_driver.py；它将等待当前对局结束，然后按 %s 轮转排批" % " / ".join(arms))
    print("用 `python -X utf8 tools/ab_readout.py` 看两臂对比。")


def _baseline_from_ab():
    """读 .ab_mode 取基线（第 1 臂）。删哨兵前调用。"""
    try:
        cfg = json.loads(io.open(AB, encoding="utf-8").read())
    except Exception:
        return None
    arms = cfg.get("arms") if isinstance(cfg.get("arms"), list) else [cfg.get("a"), cfg.get("b")]
    arms = [str(x) for x in (arms or []) if x]
    return arms[0] if arms else None


def stop(force=False):
    """停 A/B。

    顺序很重要（2026-09-15 修）：**先删哨兵、等驱动自己退出**，再考虑强杀。
    _ab_driver.py 只在「看到 .ab_mode 消失」的正常退出路径里把基线写回
    var/_keeper_strategy.txt；旧版 stop() 直接 kill 驱动 ⇒ 清理代码永远不执行 ⇒
    策略文件停在最后一个**候选臂**上，watchdog 90s 内把它拉成生产策略
    （实测：2026-09-15 停在 speedc130，一个 p95 决策 3s / 250 条超窗口的候选）。
    """
    base = _baseline_from_ab()
    if os.path.exists(AB):
        os.remove(AB)
        print("已删 var/.ab_mode")
    else:
        print("var/.ab_mode 不存在")
    # ★★ 2026-09-17 修（E002 窗口）：原来只等 ~45s 就**强杀驱动**。
    #   但一房要跑 ~14 分钟 ⇒ 若驱动正"房中对局"（它对 match_super 是阻塞 wait），45s 根本等不到边界：
    #   强杀驱动**不会**杀掉在跑的 run_bot，而 watchdog 会在 ≤90s 内按策略文件拉起 keeper ⇒
    #   keeper 的 `/api/match` 幂等、会**回到同一房** ⇒ 第二个 run_bot 进场 = **同账号双活 = E002**。
    #   正确做法：**等得足够久**（默认 20 分钟 > 一房时长），到点仍不退出就**拒绝强杀**并返回非零，
    #   由人来确认（要强杀必须显式 --force，且必须自己在杀掉后立刻停掉在跑的 run_bot/等它结束）。
    waited = 0
    deadline = int(os.environ.get("AB_STOP_WAIT_SEC", "1200"))     # 20 分钟
    pids = _procs("_ab_driver.py")
    if pids:
        print("等待 _ab_driver 自行退出（它会写回基线 %s，最多 %ds）…" % (base, deadline))
        while waited < deadline:
            if not _procs("_ab_driver.py"):
                break
            time.sleep(5)
            waited += 5
            if waited % 60 == 0:
                print("  …已等 %ds（房中对局要等自然结束，绝不能杀 run_bot）" % waited)
    left = _procs("_ab_driver.py")
    if left and not force:
        print("⚠ 驱动在 %ds 内未退出：**拒绝强杀**（强杀会留下在跑的 run_bot ⇒ watchdog 拉起 keeper ⇒ E002）" % deadline)
        print("   请等当前对局自然结束后重跑本命令；确需强杀请用 --force 并自行处理在跑的 run_bot。")
        return 2
    for pid in left:
        try:
            import psutil; psutil.Process(pid).kill(); print("停 _ab_driver pid=%d（--force 强杀）" % pid)
        except Exception as e:
            print("停驱动失败（它会自行退出）:", e)
    # 兜底：无论上面走哪条路，都显式确认策略文件是基线
    if base:
        cur = ""
        try:
            cur = io.open(os.path.join(ROOT, "var", "_keeper_strategy.txt"), encoding="utf-8").read().strip()
        except Exception:
            pass
        if cur != base:
            try:
                io.open(os.path.join(ROOT, "var", "_keeper_strategy.txt"), "w", encoding="utf-8").write(base)
                print("已把 var/_keeper_strategy.txt 从 %r 写回基线 %r" % (cur, base))
            except Exception as e:
                print("!! 写回基线失败：%s —— 手工把 var/_keeper_strategy.txt 改成 %s" % (e, base))
        else:
            print("策略文件已是基线 %s" % base)
    else:
        print("⚠ 未能从 .ab_mode 读出基线，请手工确认 var/_keeper_strategy.txt")
    print("watchdog 将在 ≤90s 内按 var/_keeper_strategy.txt 恢复 keeper")


def status():
    if not os.path.exists(AB):
        print("A/B 未启用（无 var/.ab_mode）")
    else:
        print("A/B 配置:", io.open(AB, encoding="utf-8").read().strip())
    st = os.path.join(ROOT, "var", "_ab_state_v2.json")
    if os.path.exists(st):
        print("进度:", io.open(st, encoding="utf-8").read().strip())
    print("驱动进程:", _procs("_ab_driver.py"))
    print("keeper:", _procs("_keeper.py"), " match_super:", _procs("match_super.py"))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "start":
        _arms, _rooms, _bundles, _arm_opts, _started = parse_start_args(sys.argv[2:])
        start(_arms, _rooms, _bundles, _arm_opts, force=("--force" in sys.argv[2:]),
              started=_started)
    elif cmd == "stop":
        stop(force=("--force" in sys.argv[2:]))
    else:
        status()
