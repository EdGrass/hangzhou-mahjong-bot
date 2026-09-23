"""tools/replay_audit —— 决策审计器（离线 oracle 对比）。

输入：logs/bot_live.log 中 [audit] 行（HM_AUDIT=1 时产生）。
对每个 draw 态出牌决策：用本地引擎重算"oracle 最优弃牌"（SpeedA 语义：
向听最小→等待最多→保留刚摸），与实际打出对比：
  - 一致率 = 策略执行度（若 ~100% → 协议无损耗，差距在策略本身）
  - 输出不一致样例（前 10 条）供人工研判
用法：python tools/replay_audit.py [--log logs/bot_live.log] [--oracle speedB]
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speed import _best_discard          # noqa: E402
from bot.speedb import _want_claim, _claim_value, _chi_pairs  # noqa: E402
from mahjong.hu import is_win                # noqa: E402
from mahjong.shanten_exact import shanten as exact_shanten  # noqa: E402

AUDIT_RE = re.compile(
    r"\[audit\] gid=(\S+) seat=(\d+) phase=(\S+) turn=(\d+) "
    r"hand=([\w,]+) drawn=(\S*) melds=(\d+) act=(\S+)")
ACT_RE = re.compile(r"^(\w+):?(.*)$")


def parse_audit(line):
    m = AUDIT_RE.search(line)
    if not m:
        return None
    gid, seat, phase, turn, hand, drawn, melds, act = m.groups()
    return {"gid": gid, "seat": int(seat), "phase": phase, "turn": int(turn),
            "hand": hand.split(",") if hand else [],
            "drawn": drawn if drawn else None,
            "melds": int(melds), "act": act}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=os.path.join("logs", "bot_live.log"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = []
    with open(args.log, encoding="utf-8") as f:
        for l in f:
            r = parse_audit(l)
            if r:
                rows.append(r)
    if args.limit:
        rows = rows[-args.limit:]
    print("审计行总数: %d" % len(rows))

    disc = [r for r in rows if r["act"].startswith("discard")]
    hu = [r for r in rows if r["act"].startswith("hu")]
    claims = [r for r in rows if r["act"] in ("peng:", "chi:", "gang:")
              or r["act"].startswith("peng") or r["act"].startswith("chi")
              or r["act"].startswith("gang")]
    print("出牌决策: %d | 胡提交: %d | 副露提交: %d" % (len(disc), len(hu), len(claims)))

    # oracle 对比（仅无副露局面可精确复算；副露>0 时弃牌基准含 e/g，也支持）
    match = 0
    samples = []
    for r in disc:
        m = ACT_RE.match(r["act"])
        if not m:
            continue
        tile = m.group(2)
        hand = r["hand"]
        drawn = r["drawn"]
        # oracle：与策略同口径
        try:
            oracle = _best_discard(list(hand), drawn, r["melds"], 0)
        except Exception:
            continue
        if tile == oracle:
            match += 1
        else:
            samples.append((r, oracle))
    total = len([r for r in disc if ACT_RE.match(r["act"])])
    if total:
        print("弃牌 oracle 一致率: %d/%d = %.1f%%" % (
            match, total, match / total * 100))
    print("不一致样例（前 8）:")
    for r, oracle in samples[:8]:
        print("  hand=%s drawn=%s melds=%d → 实际打出 %s, oracle 应打 %s [gid %s]" %
              (",".join(sorted(r["hand"])), r["drawn"], r["melds"],
               r["act"].split(":")[1], oracle, r["gid"]))


if __name__ == "__main__":
    main()
