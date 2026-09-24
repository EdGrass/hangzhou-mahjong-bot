# -*- coding: utf-8 -*-
"""var/_schedule_guard.py —— 排期护栏（只读；把"会不会赶不上 10/7"量出来）。

## 为什么（本机实测的教训）

§V.66 的功率分析说：效应量小的时候 z 只按 √n 涨 ⇒ **多数役到 120 房/臂（役盒）仍不可判定**，
真正收口靠破平。而本机实测吞吐 = **3.16 房/小时**（房与房之间只剩 ~40 秒，无可回收空档，见 §V.187）。
于是"全到盒"的排期是：役2 到盒 + 役3(3臂×120) + 役4(2臂×120) + 役5(2臂×120) ≈ **12 天** ⇒
**正好撞上 10/7 换臂时刻**，没有任何余量。

计划里已有丢弃顺序（§V.160：先丢 V 剂量档 → 再丢组合验证 → 最后才动副露剂量），
但**没有机械触发** ⇒ 本工具把它变成一条读数 + 一个标记：

- 按最近实测吞吐，算"**全到盒**"与"**只到正式线 80/臂**"两种情形的预计收口时间；
- 若"全到盒"晚于 **10/7 08:30**（最终臂确认时刻）⇒ 写 `var/.SCHEDULE_TIGHT`，
  并打印**按 §V.160 丢弃顺序**该丢哪一役后的预计收口。

## 只读

不碰任何进程、不改 `.ab_mode`、不自行丢役（丢役是人的决定，本工具只把数摆出来）。
用法：`python -X utf8 var/_schedule_guard.py [--deadline "2026-10-07 08:30:00"]`
"""
from __future__ import annotations
import argparse
import datetime as dt
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "var", "auto_ranking.jsonl")
AB = os.path.join(ROOT, "var", ".ab_mode")
MARK = os.path.join(ROOT, "var", ".SCHEDULE_TIGHT")
LOG = os.path.join(ROOT, "var", "_schedule_guard.log")
BOX = 120      # 役盒（房/臂）
FORMAL = 80    # 正式判词线（房/臂）


def say(msg):
    # 打印 + 追加日志（pythonw 任务没有控制台，不落日志等于读数丢失）
    print(msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass

def read_rows(path=None):
    rows = []
    with io.open(path or LEDGER, encoding="utf-8", errors="ignore") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            t = d.get("ts") or ""
            try:
                ts = dt.datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            rows.append((ts, d.get("strategy") or "?"))
    rows.sort()
    return rows


def throughput(rows, hours=24):
    """最近 N 小时的实测房/小时（不足则用全部）。"""
    if len(rows) < 2:
        return 0.0
    end = rows[-1][0]
    start = end - dt.timedelta(hours=hours)
    win = [r for r in rows if r[0] >= start]
    if len(win) < 2:
        win = rows[-min(len(rows), 40):]
    span = (win[-1][0] - win[0][0]).total_seconds() / 3600.0
    return (len(win) - 1) / span if span > 0 else 0.0


def arms_now(path=None):
    try:
        with io.open(path or AB, encoding="utf-8-sig") as f:
            cfg = json.loads(f.read())
    except Exception:
        return []
    if isinstance(cfg.get("arms"), list):
        return [str(x) for x in cfg["arms"]]
    return [x for x in (cfg.get("a"), cfg.get("b")) if x]


def rooms_left(rows, arms, target, since=None, per_arm=None):
    """本役到 target 还差多少房（按臂计最大缺口 × 臂数）。"""
    if not arms:
        return 0
    base = since or (rows[0][0] if rows else dt.datetime.now())
    cnt = {}
    for ts, st in rows:
        if ts < base:
            continue
        if st in arms:
            cnt[st] = cnt.get(st, 0) + 1
    # ★ 剩余量 = **各臂缺口之和**（用 max 缺口×臂数会少算：臂进度不齐时那种算法会把
    #   "领先的臂"当成所有臂的进度）。
    return sum(max(0, int(target) - cnt.get(x, 0)) for x in arms)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline", default="2026-10-07 08:30:00")
    ap.add_argument("--since", default="", help="本役起点（默认读 .ab_mode.started）")
    ap.add_argument("--hours", type=int, default=24, help="吞吐统计窗口（小时）")
    a = ap.parse_args(argv)
    rows = read_rows()
    thr = throughput(rows, a.hours)
    if thr <= 0:
        say("吞吐不足（窗口内房数太少）⇒ 不给结论")
        return 2
    since = a.since
    if not since:
        try:
            with io.open(AB, encoding="utf-8-sig") as f:
                since = str(json.loads(f.read()).get("started") or "")
        except Exception:
            since = ""
    try:
        base = dt.datetime.strptime(since, "%Y-%m-%d %H:%M:%S")
    except Exception:
        base = rows[0][0]
    arms = arms_now()
    dl = dt.datetime.strptime(a.deadline, "%Y-%m-%d %H:%M:%S")
    now = rows[-1][0]
    # 剩余：本役到盒 +（计划里的后续役，按臂数硬编码：役3=3臂、役4=2臂、役5=2臂）
    here_box = rooms_left(rows, arms, BOX, since=base)
    here_formal = rooms_left(rows, arms, FORMAL, since=base)
    say("实测吞吐：%.2f 房/小时（最近 %d 小时）" % (thr, a.hours))
    say("当前役：%s（%d 臂）｜到正式线 %d 还差 %d 房；到役盒 %d 还差 %d 房"
          % (",".join(arms) or "(无 .ab_mode)", len(arms), FORMAL, here_formal, BOX, here_box))
    plan = []            # (名称, 房数)——按臂数估算全到盒的总房数
    if arms:
        plan.append(("本役", here_box))
    for name, narm in (("役3", 3), ("役4", 2), ("役5", 2)):
        plan.append((name, BOX * narm))
    total_box = sum(n for _, n in plan)
    h_box = total_box / thr
    eta_box = now + dt.timedelta(hours=h_box)
    say("全到盒投影：剩余 %d 房 ⇒ %.1f 天 ⇒ 收口约 **%s**"
          % (total_box, h_box / 24.0, eta_box.strftime("%m/%d %H:%M")))
    drop = []
    remaining = list(plan)
    while remaining and (now + dt.timedelta(hours=sum(n for _, n in remaining) / thr)) > dl:
        # §V.160 丢弃顺序：先丢 V 剂量档（役5 之外的那一枪）→ 再丢组合验证（役5）
        if remaining and remaining[-1][0] == "役5":
            drop.append(remaining.pop()[0])
        elif remaining and remaining[-1][0] == "役4":
            drop.append(remaining.pop()[0])
        else:
            break
    if drop:
        keep = sum(n for _, n in remaining)
        eta = now + dt.timedelta(hours=keep / thr)
        say("按 §V.160 丢弃顺序丢掉 %s 后：剩余 %d 房 ⇒ 收口约 **%s**"
              % ("、".join(drop), keep, eta.strftime("%m/%d %H:%M")))
    ok = eta_box <= dl
    say("截止 %s ⇒ %s" % (dl.strftime("%m/%d %H:%M"), "**排期够**" if ok else "**排期不够（须按丢弃顺序减役）**"))
    try:
        if ok:
            if os.path.exists(MARK):
                os.remove(MARK)
        else:
            with io.open(MARK, "w", encoding="utf-8", newline="") as f:
                f.write("全到盒投影 %s > 截止 %s ⇒ 按 §V.160 丢弃顺序减役（建议丢：%s）"
                        % (eta_box.strftime("%m/%d %H:%M"), dl.strftime("%m/%d %H:%M"), "、".join(drop) or "役5"))
        
    except Exception:
        pass
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
