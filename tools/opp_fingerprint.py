"""tools/opp_fingerprint —— 自动房对手公开行为指纹（我方 vs 同桌对比）。

数据：自动房录制事件流（var/replays/auto_<ts>/<gid>.jsonl，我们视角）——
他人摸牌不可见（tile 仅自己），但公开行为全可见。指纹：副露（chi/peng/
gang）、弃白、超时（代打率）、pass。逐场输出四席副露量（我方已知座位），
房间级汇总我方 vs 同桌（3 席合计与均分）。

用法：python tools/opp_fingerprint.py [--dirs var/replays/auto_*]
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys


def _my_seat(dec_file):
    try:
        for line in open(dec_file, encoding="utf-8"):
            r = json.loads(line)
            if r.get("k") == "d" and r.get("s") is not None:
                return r["s"]
    except OSError:
        pass
    return None


def _fingerprint(gid_json):
    dp = gid_json.replace(".jsonl", ".dec.jsonl")
    my_seat = _my_seat(dp) if os.path.exists(dp) else None
    if my_seat is None:
        return None
    st = collections.defaultdict(lambda: {"discard": 0, "white": 0, "chi": 0,
                                          "peng": 0, "gang": 0,
                                          "tmo_discard": 0, "tmo_resp": 0,
                                          "pass": 0})
    for line in open(gid_json, encoding="utf-8"):
        e = json.loads(line)
        t, seat = e.get("type"), e.get("seat")
        if seat is None:
            continue
        s = st[seat]
        if t == "tile_discarded":
            s["discard"] += 1
            if e.get("tile") == "白":
                s["white"] += 1
        elif t == "chi":
            s["chi"] += 1
        elif t == "peng":
            s["peng"] += 1
        elif t == "gang":
            s["gang"] += 1
        elif t == "pass":
            s["pass"] += 1
        elif t == "timeout":
            kind = (e.get("data") or {}).get("kind")
            if kind == "discard":
                s["tmo_discard"] += 1
            elif kind == "response":
                s["tmo_resp"] += 1
    return my_seat, dict(st)


def main():
    dirs = sys.argv[1:] or sorted(glob.glob("var/replays/auto_*"))
    agg_me = collections.defaultdict(float)
    agg_opp = collections.defaultdict(float)
    n_me = n_opp = 0
    for d in dirs:
        gids = sorted(g for g in glob.glob(os.path.join(d, "*.jsonl"))
                      if not g.endswith(".dec.jsonl"))
        if not gids:
            continue
        me_tot = collections.defaultdict(float)
        opp_tot = collections.defaultdict(float)
        print("== %s（%d 场）==" % (os.path.basename(d), len(gids)))
        for gid in gids:
            res = _fingerprint(gid)
            if not res:
                continue
            my_seat, st = res
            parts = []
            for seat in sorted(st):
                s = st[seat]
                tag = "我" if seat == my_seat else "O%d" % seat
                parts.append("%s弃%d吃%d碰%d杠%d" % (
                    tag, s["discard"], s["chi"], s["peng"], s["gang"]))
                base = me_tot if seat == my_seat else opp_tot
                for k, v in s.items():
                    base[k] += v
            print("   ", os.path.basename(gid)[-18:], " | ".join(parts))
        print("   合计 我: 吃%d碰%d杠%d 弃%d 白%d 超时弃%d | 同桌3席: 吃%d碰%d杠%d 弃%d 白%d（席均 吃%.1f碰%.1f杠%.1f）" % (
            me_tot["chi"], me_tot["peng"], me_tot["gang"], me_tot["discard"],
            me_tot["white"], me_tot["tmo_discard"], opp_tot["chi"],
            opp_tot["peng"], opp_tot["gang"], opp_tot["discard"],
            opp_tot["white"], opp_tot["chi"] / 3, opp_tot["peng"] / 3,
            opp_tot["gang"] / 3))
        for k in me_tot:
            agg_me[k] += me_tot[k]
            agg_opp[k] += opp_tot[k]
        n_me += len(gids)
        n_opp += len(gids) * 3
    print("=" * 30)
    if n_me:
        print("跨房每场均值：我（%d 场） vs 同桌席均（%d 席场）：" % (n_me, n_opp))
        for k in ("discard", "white", "chi", "peng", "gang", "tmo_discard",
                  "pass"):
            print("  %-12s 我 %.2f | 同桌 %.2f" %
                  (k, agg_me[k] / n_me, agg_opp[k] / n_opp if n_opp else 0))


if __name__ == "__main__":
    main()
