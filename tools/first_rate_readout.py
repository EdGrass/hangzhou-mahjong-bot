# -*- coding: utf-8 -*-
"""first_rate_readout —— **同窗口按臂读数**（第一率 / 末位率 / 均分 / 正分率 + 分辨力）。

为什么单做一个（用户口径与判词口径的**分工**）：
  * 用户口径：**只看第一率**（第一率 = 每房名次里的 rank==1 占比；4 人房随机线 = 25%）。
  * 判词口径：`var/_gate2.py`（各臂 >=80 房有复盘；主端点=复盘和牌率/房、副端点=复盘番/房，z>=1.50）。
  * 两者**功率差一个量级**：一房只有 1 个名次（第一率样本量=房数），而一房有 ~几十局（和牌率样本量=局数）。
    所以"第一率看着涨了"往往**还没到能分辨的样本量**——本工具把这句话**算出来**（需要多少房/臂）。

数据源：`var/auto_ranking.jsonl`（本地台账，`status=finished` 的房），**只读、不联网**。

用法：
    python -X utf8 tools/first_rate_readout.py                      # 自动取本役（读 .ab_mode）的臂 + since
    python -X utf8 tools/first_rate_readout.py --since "2026-09-23 03:13:44" --arms speedc151,speedvalue
    python -X utf8 tools/first_rate_readout.py --since "" --min-rooms 10     # 全部历史、按房数过滤
"""
from __future__ import annotations
import argparse
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "var", "auto_ranking.jsonl")
AB = os.path.join(ROOT, "var", ".ab_mode")
ME_DEFAULT = "u_7a3fba48d70b"


def ab_ctx(path=None):
    """从 `.ab_mode` 取 (arms, since)；取不到就返回 ([], "")。"""
    try:
        d = json.loads(io.open(path or AB, encoding="utf-8-sig").read())
    except Exception:
        return [], ""
    arms = [x for x in (d.get("a"), d.get("b")) if x]
    arms += [x for x in (d.get("arms") or []) if x and x not in arms]
    return arms, str(d.get("started") or "")


def load(ledger=None, since="", arms=(), me=ME_DEFAULT):
    """返回 [(ts, arm, my_row)]（只保留 `status=finished`、时间戳 >= since、臂在白名单里）。"""
    want = tuple(arms) if arms else None
    out = []
    try:
        fh = io.open(ledger or LEDGER, encoding="utf-8-sig")
    except OSError:
        return out
    with fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("status") != "finished":
                continue
            ts = str(d.get("ts") or "")
            if since and ts < since:
                continue
            arm = d.get("strategy")
            if want is not None and arm not in want:
                continue
            row = None
            for p in (d.get("ranking") or []):
                if p.get("user_id") == me:
                    row = p
                    break
            if row is None:
                continue
            out.append((ts, arm, row))
    return out


def summarize(items):
    """按臂汇总：n / 均分/房 / SE95 / 第一率 / 末位率 / 正分率 / 平均名次。"""
    import collections
    by = collections.defaultdict(list)
    for _ts, arm, row in items:
        by[arm].append(row)
    out = {}
    for arm, rows in by.items():
        n = len(rows)
        sc = [r.get("total_score") or 0 for r in rows]
        rk = [r.get("rank") or 0 for r in rows]
        mean = sum(sc) / n
        sd = ((sum((x - mean) ** 2 for x in sc) / (n - 1)) ** 0.5) if n > 1 else 0.0
        out[arm] = {
            "n": n, "mean": mean, "sd": sd,
            "se95": 1.96 * sd / (n ** 0.5) if n else 0.0,
            "first_rate": sum(1 for r in rk if r == 1) / n,
            "last_rate": sum(1 for r in rk if r == 4) / n,
            "pos_rate": sum(1 for s in sc if s > 0) / n,
            "mean_rank": sum(rk) / n,
        }
    return out


def first_rate_z(p1, n1, p2, n2):
    """两独立二项比例之差的标准误与 z（候选 − 基线）。"""
    se = ((p1 * (1 - p1) / n1) + (p2 * (1 - p2) / n2)) ** 0.5 if (n1 and n2) else 0.0
    return ((p2 - p1) / se if se else 0.0), se


def rooms_needed(delta, p=0.25, z=1.96):
    """要在 z 下分辨 delta 的第一率差，每臂需要多少房（两独立二项、p 取随机线附近）。"""
    if delta <= 0:
        return None
    return int((2 * z * z * p * (1 - p)) / (delta * delta)) + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default="")
    ap.add_argument("--since", default=None, help="缺省：取 .ab_mode 的 started；给空串=全部历史")
    ap.add_argument("--arms", default="", help="逗号分隔；缺省：取 .ab_mode 的 a/b")
    ap.add_argument("--me", default=ME_DEFAULT)
    ap.add_argument("--min-rooms", type=int, default=0)
    a = ap.parse_args()

    ab_arms, ab_since = ab_ctx()
    arms = [x.strip() for x in a.arms.split(",") if x.strip()] if a.arms else ab_arms
    since = (ab_since if a.since is None else a.since) or ""
    items = load(a.ledger or None, since, arms, a.me)
    tab = summarize(items)
    if not tab:
        print("⚠ 未命中任何房（since=%r arms=%s ledger=%s）" % (since, arms or "全部", a.ledger or LEDGER))
        return 2
    if a.min_rooms:
        tab = {k: v for k, v in tab.items() if v["n"] >= a.min_rooms}

    print("窗口：%s   臂：%s" % (since or "(全部历史)", ", ".join(tab)))
    print("%-16s %5s %9s %8s %9s %9s %8s %9s"
          % ("arm", "n", "均分/房", "SE95", "第一率", "末位率", "正分率", "平均名次"))
    order = sorted(tab, key=lambda k: -tab[k]["n"])
    for k in order:
        v = tab[k]
        print("%-16s %5d %9.1f %8.1f %8.1f%% %8.1f%% %7.1f%% %9.2f"
              % (k, v["n"], v["mean"], v["se95"], 100 * v["first_rate"],
                 100 * v["last_rate"], 100 * v["pos_rate"], v["mean_rank"]))
    if len(order) == 2:
        # ★ 方向必须**稳定**：始终打印 "候选 − 基线"（即 --arms 的第 2 个 − 第 1 个；默认就是 .ab_mode 的 b − a）。
        #   为什么：若按"房数降序"取对，两臂房数接近时方向会**随机翻转**，读数会被误读（实测：同一工具在三个窗口里打出了两种方向）。
        pair = [x for x in arms if x in tab]
        if len(pair) == 2:
            b, c = pair[0], pair[1]
        else:
            b, c = order[0], order[1]
        v1, v2 = tab[b], tab[c]
        z, se = first_rate_z(v1["first_rate"], v1["n"], v2["first_rate"], v2["n"])
        d = v2["first_rate"] - v1["first_rate"]
        print("\n%s − %s：均分 %+.1f/房；第一率 %+.1fpp（z=%+.2f，SE=%.1fpp）"
              % (c, b, v2["mean"] - v1["mean"], 100 * d, z, 100 * se))
        need = rooms_needed(abs(d))
        if need:
            print("  分辨力：要在 z>=1.96 下分辨 %.1fpp 的第一率差，**每臂约需 %d 房**（当前 %d/%d）"
                  % (100 * abs(d), need, v1["n"], v2["n"]))
        else:
            print("  分辨力：第一率差为 0 或方向相反，無需房数估算")
    print("\n口径提醒：本工具只算**同窗口台账**（第一率样本量 = 房数）；"
          "**役判词权威仍是 `var/_gate2.py`**（复盘和牌率/番，样本量 = 局数，功率高一个量级）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
