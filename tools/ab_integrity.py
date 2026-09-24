# -*- coding: utf-8 -*-
"""`ab_integrity` —— 战役**数据完整性**自检（每条房记录只能属于一个臂、只能有一行）。

为什么必须（文档里的真实事故）：2026-09-16 房 `a_0aca4ad1f990` 在 `auto_ranking.jsonl` 里**有两行且策略不同**
（前 23 手候选、其余基线）⇒ 两个臂各丢一房、且读数被污染（t 从 0.60 虚高到 1.12）。
本工具在**每次读数前**跑一遍，把这类脏数据当场抓出来。

判据（任一不满足即异常，退出码 1）：
  ① 同一房**只能有一行**；② 同一房**只能属于一个臂**；③ 策略必须在**本役臂列表**内；
  ④ 状态必须 finished（未完成的行会被 `ab_readout` 排除，但这里要显式报出）；⑤ `exit_code` 必须为 0。

用法：
    python -X utf8 tools/ab_integrity.py                 # 用 var/.ab_mode 的 arms/started
    python -X utf8 tools/ab_integrity.py --since "2026-09-16 23:19:47" --arms speedtugc,speedtugc_w50
"""
from __future__ import annotations
import argparse
import collections
import glob
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AB = os.path.join(ROOT, "var", ".ab_mode")
RANKING = os.path.join(ROOT, "var", "auto_ranking.jsonl")


REPLAYS = os.path.join(ROOT, "var", "replays")


def room_start_times(root=ROOT):
    """房 -> 开房时刻（'YYYY-MM-DD HH:MM:SS'），来源 = 复盘目录名 `auto_YYYYMMDD_HHMMSS`。

    为什么需要（2026-09-17 真实故障）：`ab_ctl stop` 会**等当前房自然打完**，
    于是**上一役的最后一房**的结果行会落在**新役 `started` 之后**。
    只按结果 `ts` 过滤 ⇒ 它被当成"本役里的未知策略"⇒ integrity 硬失败
    ⇒ 而 `tools/tminus_check.py` 把它当硬门禁 ⇒ **19:00 的正式赛切换会被拒绝执行**。
    用开房时刻就能精确判定：开房 < `started` 的行是**跨役残留**，不是污染。
    （实测：`auto_ranking.jsonl` 466 行**全部**能从目录名定位到开房时刻，0 缺失。）
    """
    out = {}
    for dp in glob.glob(os.path.join(root, "var", "replays", "auto_*")):
        stamp = os.path.basename(dp).replace("auto_", "")
        if len(stamp) != 15 or stamp[8] != "_":
            continue
        launch = "%s-%s-%s %s:%s:%s" % (stamp[0:4], stamp[4:6], stamp[6:8],
                                       stamp[9:11], stamp[11:13], stamp[13:15])
        try:
            names = os.listdir(dp)
        except OSError:
            continue
        for fn in names:
            room = fn.split("_r")[0]
            if room:
                out.setdefault(room, launch)
    return out


def load_rows(path=RANKING):
    out = []
    try:
        with io.open(path, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except Exception:
                    continue
    except OSError:
        pass
    return out


def check_integrity(rows, since, arms, starts=None):
    """纯函数：返回 (ok, report)。rows 为 auto_ranking 记录列表。

    `starts`（可选）= `room_start_times()` 的结果。给了它，就会把**开房早于 `since`**
    的行判为「跨役残留」，从错误集里分出来单独报（不参与 ok/不参与 unknown 统计）；
    没给则维持旧行为（所有结果行都算本役）——保持既有单测契约不变。
    """
    cur = [r for r in rows if (r.get("ts") or "") >= (since or "")]
    residue = []
    if starts and since:
        keep = []
        for r in cur:
            launch = starts.get(r.get("room"))
            if launch and launch < since:
                residue.append((r.get("room"), r.get("strategy"), launch))
            else:
                keep.append(r)
        cur = keep
    per_room = collections.defaultdict(list)
    for r in cur:
        per_room[r.get("room")].append(r)
    dup_rows = {k: len(v) for k, v in per_room.items() if len(v) > 1}
    multi_strat = {k: sorted({x.get("strategy") for x in v}) for k, v in per_room.items()
                   if len({x.get("strategy") for x in v}) > 1}
    arm_set = set(arms or [])
    unknown = [r.get("strategy") for r in cur if arm_set and r.get("strategy") not in arm_set]
    not_finished = [r.get("room") for r in cur if r.get("status") != "finished"]
    bad_exit = [(r.get("room"), r.get("exit_code")) for r in cur
                if r.get("exit_code") not in (0, None)]
    per_arm = collections.Counter(r.get("strategy") for r in cur)
    rep = {
        "rows": len(cur), "rooms": len(per_room), "per_arm": dict(per_arm),
        "dup_rows": dup_rows, "multi_strategy": multi_strat,
        "unknown_strategies": collections.Counter(unknown),
        "not_finished": not_finished, "bad_exit": bad_exit,
        "residue": residue,
    }
    ok = not (dup_rows or multi_strat or unknown or not_finished or bad_exit)
    return ok, rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="")
    ap.add_argument("--arms", default="")
    a = ap.parse_args()
    since, arms = a.since, [x.strip() for x in a.arms.split(",") if x.strip()]
    since = since.strip().replace("T", " ") if since else since  # ISO T -> ledger SPACE form
    if not since or not arms:
        try:
            cfg = json.loads(io.open(AB, encoding="utf-8").read())
            arms = arms or [str(x) for x in (cfg.get("arms") or [cfg.get("a"), cfg.get("b")]) if x]
            since = since or cfg.get("started") or ""
        except Exception:
            pass
    ok, rep = check_integrity(load_rows(), since, arms, room_start_times())
    print("战役完整性自检：since=%s arms=%s" % (since or "-", ",".join(arms) or "-"))
    print("  行 %d / 房 %d ；按臂 %s" % (rep["rows"], rep["rooms"], rep["per_arm"]))
    print("  同一房多行 %d ；同一房多策略 %d ；未知策略 %d ；未完成 %d ；exit!=0 %d" % (
        len(rep["dup_rows"]), len(rep["multi_strategy"]), sum(rep["unknown_strategies"].values()),
        len(rep["not_finished"]), len(rep["bad_exit"])))
    if rep["dup_rows"]:
        print("   多行样例:", list(rep["dup_rows"].items())[:3])
    if rep["multi_strategy"]:
        print("   多策略样例:", list(rep["multi_strategy"].items())[:3])
    if rep["bad_exit"]:
        print("   exit!=0 样例:", rep["bad_exit"][:3])
    res = rep.get("residue") or []
    if res:
        print("  ⓘ 跨役残留 %d 房（开房早于本役 started，旧役最后一房自然打完；**不计入异常**）：%s"
              % (len(res), res[:3]))
    print("  => " + ("干净 ✓" if ok else "**有异常，先修数据再读数**"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
