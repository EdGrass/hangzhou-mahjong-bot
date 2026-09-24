# -*- coding: utf-8 -*-
"""`var/_strong_veto.py` —— **强手房否决**（§V.156 的机械闸）。

## 为什么

§V.156 定案：**混场能打、强场打不动**；正式赛（10/10）对手密度 ≈ 强手房。
§V.66 破平链第 ① 条就是**强手房分/房**；役 3 的预登记更是把
"**主端点过但强手房两列任一显著劣 ⇒ 记 B2、该轴不采用**"写成硬要求。

但 `_gate2.py` 的主/副端点**不分层**（`_verdict_by_elite.py` 的 docstring 已写明），
本工具就是那道"显著劣"的判据：只看**强手房**（房里有 top32 对手），对
**净分/房**与**第1率**各做一次房间级显著性检验。

## 判据（写死）

- 强手房 = 该房里除我方外有榜单 topN；
- **净分/房**：Welch z（se=√(var_a/n_a+var_b/n_b)）；候选 **z ≤ −1.96** ⇒ 显著劣；
- **第1率**：两比例池化 z；候选 **z ≤ −1.96** ⇒ 显著劣；
- 任一显著劣 ⇒ **VETO**；两侧都拿不到足够强手房（各 < `--min-rooms`）⇒ **UNKNOWN**；否则 **OK**。

退出码：0=OK（无否决）／3=VETO（显著劣，该轴不采用）／2=UNKNOWN（数据不足，**不阻塞**）。
只读台账 + 复盘 + 门户榜；不写任何状态文件、不碰任何进程。

用法：
    python -X utf8 var/_strong_veto.py --since "<起役ts>" --baseline speedvalue --candidate speedvaluebc
"""
from __future__ import annotations
import argparse
import glob
import io
import json
import math
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "var", "auto_ranking.jsonl")
RECENT = os.path.join(ROOT, "var", "replays", "recent")
ME = "u_7a3fba48d70b"
ROOM_RX = re.compile(r"^(a_[0-9a-f]+)_")
Z_BAD = -2.0   # ★ 与预登记逐字一致：§7「候选 − 基线 < −2×SE合并」 ⟺ z < −2.0


def _welch(a, b):
    """候选 − 基线 的差、se、z（房间级）。"""
    if len(a) < 2 or len(b) < 2:
        return None
    d = statistics.mean(b) - statistics.mean(a)
    se = math.sqrt(statistics.variance(a) / len(a) + statistics.variance(b) / len(b))
    return d, se, (d / se if se else 0.0)


def _prop_z(ka, na, kb, nb):
    """第1率的两比例池化 z。"""
    if na < 2 or nb < 2:
        return None
    pa, pb = ka / na, kb / nb
    p = (ka + kb) / (na + nb)
    se = math.sqrt(p * (1 - p) * (1 / na + 1 / nb))
    return pb - pa, (pb - pa) / se if se else 0.0


def veto_of(zn, zp):
    """判据（纯函数）：返回显著劣的列名列表。zn/zp 任一 <= -2.0 ⇒ 该列显著劣。

    阈值必须是 **−2.0**（= 预登记 §7 的「< −2×SE合并」），不是 −1.96。
    """
    bad = []
    if zn is not None and zn <= Z_BAD:
        bad.append("净分/房")
    if zp is not None and zp <= Z_BAD:
        bad.append("第1率")
    return bad


def read_ledger(since, arms):
    """-> [(room, arm, net, is_first)]，只取 since 之后、臂在 arms 里的行。"""
    out = []
    with io.open(LEDGER, encoding="utf-8", errors="ignore") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("status") != "finished" or (d.get("ts") or "") < since:
                continue
            st = d.get("strategy")
            if st not in arms:
                continue
            mine = [x for x in (d.get("ranking") or []) if x.get("user_id") == ME]
            if not mine:
                continue
            room = d.get("room") or ""
            out.append((room, st, float(mine[0].get("total_score") or 0),
                        int(mine[0].get("rank") or 0) == 1))
    return out


def strong_rooms(rooms):
    """给定房间 id 集合 ⇒ {房: 房里**别的** topN 对手个数}（读每房第一份复盘；只留 >=1 的）。"""
    try:
        sys.path.insert(0, os.path.join(ROOT, "var"))
        import _strong_slice as SS
        tops = SS.board_top(32)
    except Exception as e:
        return None, "榜单不可达（%s）" % str(e)[:60]
    seen, strong = set(), {}
    for p in sorted(glob.glob(os.path.join(RECENT, "*.json"))):
        m = ROOM_RX.match(os.path.basename(p))
        if not m:
            continue
        r = m.group(1)
        if r in seen or r not in rooms:
            continue
        seen.add(r)
        try:
            with io.open(p, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        uids = [(s.get("user_id") or "") for s in (d.get("seats") or [])]
        if ME not in uids:
            continue
        n = sum(1 for u in uids if u and u != ME and u in tops)
        if n >= 1:
            strong[r] = n
    return strong, None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--min-rooms", type=int, default=15)
    a = ap.parse_args(argv)

    rows = read_ledger(a.since, {a.baseline, a.candidate})
    if not rows:
        print("❌ 该窗口没有两臂的台账行 ⇒ 无法判定")
        return 2
    layers, err = strong_rooms({r for r, _, _, _ in rows})
    if layers is None:
        print("⚠ 强手房分层不可得：%s ⇒ UNKNOWN（不阻塞）" % err)
        return 2

    # 预登记 §7（>=1 名 top32）与 §8（>=2 名 top32 = 决赛相似层）；两层各判一次。
    allbad, judged_any = [], False
    for label, need in (("强手房(>=1 top32)", 1), ("强手房(>=2 top32)", 2)):
        A = [(n, f) for r, s, n, f in rows if s == a.baseline and layers.get(r, 0) >= need]
        B = [(n, f) for r, s, n, f in rows if s == a.candidate and layers.get(r, 0) >= need]
        na, nb = len(A), len(B)
        print("%s：%s %d 房 / %s %d 房" % (label, a.baseline, na, a.candidate, nb))
        if na < a.min_rooms or nb < a.min_rooms:
            print("   ⇒ 样本不足 %d 房/臂 ⇒ 只记录，不据此翻转（预登记 §7.3/§8）" % a.min_rooms)
            continue
        judged_any = True
        va, vb = [x[0] for x in A], [x[0] for x in B]
        d, se, zn = _welch(va, vb)
        dp, zp = _prop_z(sum(1 for x in A if x[1]), na, sum(1 for x in B if x[1]), nb)
        print("   净分/房：%.1f vs %.1f  差 %+.1f  se %.1f  z %+.2f  %s"
              % (statistics.mean(va), statistics.mean(vb), d, se, zn,
                 "**显著劣**" if zn <= Z_BAD else "不显著"))
        print("   第1率 ：%.1f%% vs %.1f%%  差 %+.1fpp  z %+.2f  %s"
              % (100 * sum(1 for x in A if x[1]) / na, 100 * sum(1 for x in B if x[1]) / nb,
                 100 * dp, zp, "**显著劣**" if zp <= Z_BAD else "不显著"))
        for col in veto_of(zn, zp):
            allbad.append("%s 的 %s" % (label, col))
    if allbad:
        print("★ 强手房否决：VETO（%s 显著劣于 %s）⇒ 按预登记该轴不采用" % ("、".join(allbad), a.baseline))
        return 3
    if not judged_any:
        print("⇒ UNKNOWN（哪一层都不足 %d 房/臂，不阻塞；只作提示）" % a.min_rooms)
        return 2
    print("★ 强手房否决：OK（已判层无显著劣；主端点通过即可采用）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
