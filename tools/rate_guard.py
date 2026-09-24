# -*- coding: utf-8 -*-
"""生产策略熔断（rate guard）：当前策略若真机净胜崩坏，自动回退到已验证策略。

动机（史）：项目多次把实验策略放进**计分池**，坏策略的代价是 -100 ~ -300/房
（speedE -197、speedm -170、speedc070 -180 且 320 局 0 胡），而这类崩坏在
4-8 房内就已显著。历史累计：93 房实验 = -7,391 分。

判据（只用榜单权威数据，不需要复盘）：
  取 auto_ranking.jsonl **末尾连续属于当前策略** 的房间，算
  净胜/房 = 我方总分 - 同房另三家均分；
  当 房数 >= MIN_ROOMS 且 净胜 < THRESHOLD  → 判为崩坏 → 回退 FALLBACK。

阈值为何是 -120/房：真机房级 SD≈146 → 8 房的标准误≈52/房，-120 约 2.3σ，
真实均值 0 的策略误伤率≈1%；而真崩坏（-180/房）在 8 房内必然触发。

开关：`var/.official_mode` 存在时不动（正式赛）；`var/.rate_guard_off` 存在时停用熔断。
用法：
    python -X utf8 tools/rate_guard.py            # 检查并按需回退
    python -X utf8 tools/rate_guard.py --dry-run  # 只看判定
    python -X utf8 tools/rate_guard.py --status   # 打印当前画像
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RANKING = os.path.join(ROOT, "var", "auto_ranking.jsonl")
STRAT_FILE = os.path.join(ROOT, "var", "_keeper_strategy.txt")
OFFICIAL_FLAG = os.path.join(ROOT, "var", ".official_mode")
# A/B 模式：排批与「候选熔断」都归 var/_ab_driver.py（它有自己的 guard_candidate）。
# 本工具**必须让路**：否则它会把 _keeper_strategy.txt 回退成 FALLBACK，
# 并在「match_super 存活、run_bot 不在」的房与房之间**杀掉 A/B 正在轮转的那一批**
# ⇒ 破坏两臂平衡，让实验报废。2026-09-16 实测：慢档已触发（近 40 房 −47.6），
# 只差一次误调用就会动手（watchdog 在 ab_mode 分支里恰好不调它，属于偶然保护）。
AB_FLAG = os.path.join(ROOT, "var", ".ab_mode")
GUARD_OFF = os.path.join(ROOT, "var", ".rate_guard_off")
LOG = os.path.join(ROOT, "var", "_rate_guard.log")
ME = "u_7a3fba48d70b"

FALLBACK = "speedtugc"     # 真机证据最厚（141 房 / +17.2 房 / 正分率 48.2%）
WINDOW = 6                 # 快档：最近 6 房（滑动，**跨策略**）
THRESHOLD = -150.0         # 快档阈值（6 房 SE≈60 → -150 约 2.5σ，误伤≈0.6%）——抓崩坏
LONG_WINDOW = 40           # 慢档：最近 40 房 —— 抓「不崩但持续失血」
LONG_THRESHOLD = -40.0     # 慢档阈值（40 房 SE≈23 → -40 约 1.7σ，误伤≈4%，代价仅回退到已验证策略）

# 为什么是「跨策略滑动窗口」而不是「当前策略的连续窗口」：
# 历史回放（var/_guard_backtest.py / _guard_bt2.py）显示，真正的崩坏来自
# **短命实验策略的快速轮换**（speedE 6 房、speedm 3 房、speedv 2 房…），
# 单个策略根本攒不到 8 房 → 按策略连续统计的熔断器**一次都不会触发**（实测 0 次）。
# 改看「最近 6 房整体净胜」后，回放在 09-09 12:31（speedE，-263/房）即触发。


def log(msg):
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def recent_nets(n, path=None):
    """最近 n 房（跨策略）的净胜序列；不足 n 则返回全部。"""
    path = path or RANKING          # 运行时取模块全局（便于测试替换）
    rows = []
    try:
        for ln in io.open(path, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except Exception:
                continue
    except OSError:
        return []
    out = []
    for rec in reversed(rows):
        if len(out) >= n:
            break
        rk = rec.get("ranking") or []
        mine = next((x for x in rk if x.get("user_id") == ME), None)
        others = [x.get("total_score") or 0 for x in rk if x.get("user_id") != ME]
        if mine is None or len(others) != 3:
            continue
        out.append((mine.get("total_score") or 0) - sum(others) / 3.0)
    out.reverse()
    return out


def verdict(nets, threshold=THRESHOLD, window=WINDOW,
            long_window=LONG_WINDOW, long_threshold=LONG_THRESHOLD):
    """纯函数：返回 (是否熔断, 展示用净胜均值, 房数)。

    两档：
      快档 —— 最近 6 房均值 < -150/房：抓「崩坏型」（如 speedE -263/房）
      慢档 —— 最近 40 房均值 < -40/房：抓「不崩但持续失血」（如 speedc068lo0 -60/房）
    慢档的意义：单靠快档永远抓不到 -60/房 这类策略（它不会触发 2.5σ 的 6 房窗口）。
    """
    nets = list(nets)
    if len(nets) >= window:
        tail = nets[-window:]
        m = sum(tail) / len(tail)
        if m < threshold:
            return True, m, len(tail)
    if len(nets) >= long_window:
        tail = nets[-long_window:]
        m = sum(tail) / len(tail)
        if m < long_threshold:
            return True, m, len(tail)
    n = min(len(nets), window)
    tail = nets[-n:] if n else []
    return False, (sum(tail) / len(tail) if tail else 0.0), n


def _ms_strategy(argv):
    """从 match_super 的 argv 里取 --strategy 值。"""
    for k, a in enumerate(argv):
        if str(a) == "--strategy" and k + 1 < len(argv):
            return str(argv[k + 1])
    return None


def kill_match_super_if_idle(expected=None):
    """熔断后加速生效：若 match_super 存活、**没有 run_bot**（房与房之间），
    且它仍在跑**非目标策略**，则杀掉它 → keeper 立刻用回退策略开新批次。

    绝不冒进：只要 run_bot 存活（正在打）就什么都不做，等这一房自然结束后的
    下一次 90s 巡检再处理。这样把回退生效延迟从「最多一个批次(4 房/约 1h)」
    压到「最多一房」。`expected` 用来避免对已经跑对策略的 match_super 反复动手。
    """
    try:
        import psutil
        ms, rb = [], []
        for p in psutil.process_iter(["pid", "cmdline", "exe"]):
            exe = os.path.basename(p.info.get("exe") or "").lower()
            if "python" not in exe:
                continue
            argv = [str(x) for x in (p.info.get("cmdline") or [])]
            base = [os.path.basename(x.replace("\\", "/")) for x in argv[1:]]
            if "run_bot.py" in base:
                rb.append(p.info["pid"])
            elif "match_super.py" in base:
                ms.append((p.info["pid"], _ms_strategy(argv)))
        if not ms:
            return
        if rb:
            print("run_bot 在跑（对局中）→ 不杀 match_super，等本房结束后自动收尾")
            return
        killed = 0
        for pid, st in ms:
            if expected is not None and st == expected:
                continue
            psutil.Process(pid).kill()
            print("killed match_super pid=%d (strategy=%s -> %s，房与房之间)" % (pid, st, expected))
            killed += 1
        if not killed:
            print("match_super 已在目标策略上，无需处理")
    except Exception as e:
        print("kill match_super 失败（不影响策略文件回退）：%s" % e)


def kill_keeper():
    """杀掉 keeper（由 watchdog 的 ensure_keeper 按新策略重拉）。抽成函数便于测试。"""
    try:
        import psutil
        for p in psutil.process_iter(["pid", "cmdline", "exe"]):
            exe = os.path.basename(p.info.get("exe") or "").lower()
            if "python" not in exe:
                continue
            for arg in (p.info.get("cmdline") or [])[1:]:
                if os.path.basename(str(arg).replace("\\", "/")) == "_keeper.py":
                    psutil.Process(p.info["pid"]).kill()
                    print("killed keeper pid=%d" % p.info["pid"])
                    break
    except Exception as e:
        print("kill keeper 失败（watchdog ≤90s 内仍会按新策略拉起）：%s" % e)


def current_strategy():
    try:
        return io.open(STRAT_FILE, encoding="utf-8").read().strip()
    except OSError:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    cur = current_strategy()
    nets = recent_nets(max(WINDOW, LONG_WINDOW))
    trip, mean, n = verdict(nets)
    line = ("策略=%s 近%d房 净胜/房=%+.1f  [快档 6房<%.0f | 慢档 40房<%.0f]  熔断=%s"
            % (cur or "(空)", n, mean, THRESHOLD, LONG_THRESHOLD, "是" if trip else "否"))
    print(line)
    if a.status:
        return 0
    if os.path.exists(OFFICIAL_FLAG):
        print("官方赛模式：熔断停用"); return 0
    if os.path.exists(AB_FLAG):
        print("A/B 模式（var/.ab_mode 存在）：熔断交给 _ab_driver.py 的候选熔断，本工具停用")
        return 0
    if os.path.exists(GUARD_OFF):
        print("熔断已由 var/.rate_guard_off 停用"); return 0
    if not trip:
        return 0
    if a.dry_run:
        print("[dry-run] 熔断：当前=%s → 将回退 %s 并重启 keeper/match_super" % (cur, FALLBACK))
        return 0

    if cur != FALLBACK:
        log("[%s] 熔断触发：%s -> %s（最近 %d 房，净胜 %+.1f/房）"
            % (__import__("time").strftime("%Y-%m-%d %H:%M:%S"), cur, FALLBACK, n, mean))
        with io.open(STRAT_FILE, "w", encoding="utf-8") as f:
            f.write(FALLBACK)
        print("已回退策略文件 -> %s；杀掉 keeper 交自愈按新策略重拉" % FALLBACK)
        kill_keeper()
    else:
        print("策略文件已是 %s；只收尾仍在跑旧策略的 match_super（若其处于房与房之间）" % FALLBACK)
    # 关键：即使策略文件已回退，也要把「仍跑旧策略且当前空闲」的 match_super 收掉，
    # 否则回退要等整个批次（最多 4 房 ≈ 1h）才生效。
    kill_match_super_if_idle(expected=FALLBACK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
