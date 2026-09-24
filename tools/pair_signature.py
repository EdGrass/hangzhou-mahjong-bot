# -*- coding: utf-8 -*-
"""pair_signature —— c151 的**机制签名核对**：我方"弃牌时刻的持对数"分布（逐臂）。

依据 STATUS §4c-66/67/68：
  - 第 8 巡**持对数**与听牌率强负相关：1 对 63~72% / 2 对 39~51% / **3~4 对 13~30%**；
  - 强玩家几乎不停在 ≥3 对；我们 57~72% 的回合停在 ≥2 对；
  - c151 的机制 = **惩罚多对子**（把对数压回 ≤2）⇒ 核对方式：**c151 臂的"≥3 对"比例应下降**。

数据源：本地 `var/replays/auto_*/*.dec.jsonl`。每条 `a.action == "discard"` 的记录里 `h` 是**弃牌前的暗牌**
⇒ 直接数对子数，**不用等门户发布**。

⚠ 注意：本地流的 `t` 是**座位号**（实测只有 0~3），**不是巡次**——不要拿它当"第几巡"。

臂归属：`var/_ab_log.jsonl` 的排批时刻（权威）。

用法：python -X utf8 tools/pair_signature.py [--since "YYYY-MM-DD HH:MM:SS"]
"""
from __future__ import annotations
import argparse, collections, glob, io, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pairs_of(hand):
    c = collections.Counter(hand)
    return sum(1 for v in c.values() if v >= 2)


def arm_launches():
    out = []
    p = os.path.join(ROOT, "var", "_ab_log.jsonl")
    if os.path.exists(p):
        for ln in io.open(p, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("arm") and d.get("ts"):
                out.append((d["ts"], str(d["arm"])))
    out.sort()
    return out


def dir_ts(name):
    try:
        return "%s-%s-%s %s:%s:%s" % (name[5:9], name[9:11], name[11:13],
                                      name[14:16], name[16:18], name[18:20])
    except Exception:
        return ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="", help="只看该时间之后的房（缺省用 .ab_mode 的 started）")
    a = ap.parse_args(argv)
    since = a.since
    if not since:
        try:
            since = json.loads(io.open(os.path.join(ROOT, "var", ".ab_mode"), encoding="utf-8-sig").read()).get("started") or ""
        except Exception:
            since = ""
    launches = arm_launches()
    per = collections.defaultdict(collections.Counter)
    for d in sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*"))):
        name = os.path.basename(d)
        ts = dir_ts(name)
        if since and ts and ts < since:
            continue
        arm = None
        for lts, larm in launches:
            if lts <= ts:
                arm = larm
        if not arm:
            continue
        for f in glob.glob(os.path.join(d, "*.dec.jsonl")):
            try:
                for ln in io.open(f, encoding="utf-8"):
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        r = json.loads(ln)
                    except Exception:
                        continue
                    act = (r.get("a") or {}).get("action")
                    if act != "discard":
                        continue
                    h = [str(x) for x in (r.get("h") or [])]
                    if len(h) < 8:
                        continue
                    per[arm][min(pairs_of(h), 4)] += 1
            except Exception:
                pass
    if not per:
        print("（没有数据；先等本轮战役出房）")
        return
    print("=" * 74)
    print("我方**弃牌时刻**持对数分布（本地决策流，逐臂）  窗口 since=%s" % (since or "-"))
    print("-" * 74)
    print("%-14s %6s %7s %7s %7s %7s %10s" % ("arm", "n", "0对", "1对", "2对", "3对+", ">=2对占比"))
    for arm in sorted(per):
        c = per[arm]
        n = sum(c.values())
        if not n:
            continue
        ge2 = sum(v for k, v in c.items() if k >= 2)
        print("%-14s %6d %6.1f%% %6.1f%% %6.1f%% %6.1f%% %9.1f%%" % (
            arm, n, 100.0 * c[0] / n, 100.0 * c[1] / n, 100.0 * c[2] / n,
            100.0 * c[3] / n, 100.0 * ge2 / n))
    print("=" * 74)


if __name__ == "__main__":
    main()
