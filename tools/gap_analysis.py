"""tools/gap_analysis —— 自动房差距结构分析（读 var/auto_ranking.jsonl）。

每房 ranking = 4 家 {rank,user_id,total_score,place_points,god_count,games_played}。
我方 uid = u_7a3fba48d70b。输出：
- 逐房：我方 rank/score vs 同房冠军与第三名；
- 汇总：我方 rank 分布、场均差（vs 冠军 / vs 同桌均值）、名次分/白板键差；
- 对手榜：压过我们的对手身份与次数（结合 9月4日赛 16 强名单标注）。
用法：python tools/gap_analysis.py [--rooms N]
"""
from __future__ import annotations

import argparse
import json
import os

ME_UID = "u_7a3fba48d70b"
F16 = {  # 9月4日赛 16 强名单（rank2 李兆坤等在列，含 user_id 前 12 位标注）
    "u_8d0c351479bd": "李兆坤(16强#2)", "u_0147bf95a127": "陈博瑞(16强#1)",
    "u_68a61f564b6d": "吴汉瑜(16强#3)", "u_56c05b161292": "覃博祥(16强#4)",
    "u_e31925f5d675": "严欣(16强#5)", "u_85320cb18b85": "李映(16强#6)",
    "u_e441bd45e1d9": "颜子淋(16强#7)", "u_7e350b75c716": "成子谦(16强#8)",
    "u_380da525337c": "姚金毅(16强候补)", "u_5d04b4811ff6": "沈瑞恩(16强候补)",
    "u_0f5eeb6b39b7": "罗诚(16强候补)", "u_d37f57067936": "黄长玉(16强候补)",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="var/auto_ranking.jsonl")
    args = ap.parse_args()
    if not os.path.exists(args.file):
        raise SystemExit("无数据: %s" % args.file)
    rooms = []
    for line in open(args.file, encoding="utf-8"):
        line = line.strip()
        if line:
            rooms.append(json.loads(line))
    print("已归档房数: %d" % len(rooms))
    me_ranks, me_scores, champ_scores, room_rows = [], [], [], []
    beaten_by = {}
    for rec in rooms:
        ranking = rec.get("ranking") or []
        me = next((r for r in ranking
                   if str(r.get("user_id", "")).startswith(ME_UID)), None)
        if not me:
            continue
        others = [r for r in ranking if r is not me]
        champ = min(others, key=lambda r: r.get("rank", 9))
        third = [r for r in others if r.get("rank") == 3]
        me_ranks.append(me.get("rank"))
        me_scores.append(me.get("total_score", 0))
        champ_scores.append(champ.get("total_score", 0))
        # 名次分/白板对照
        row = {"ts": rec.get("ts", "?"), "room": rec.get("room", "?")[-10:],
               "me_rank": me.get("rank"), "me_score": me.get("total_score"),
               "me_place": me.get("place_points"), "me_god": me.get("god_count"),
               "champ_rank": champ.get("rank"),
               "champ_score": champ.get("total_score"),
               "champ_place": champ.get("place_points"),
               "champ_god": champ.get("god_count"),
               "champ_user": str(champ.get("user_id", ""))[:12]}
        room_rows.append(row)
        # 谁压过我们（冠军名）
        if champ.get("rank", 9) < me.get("rank", 9):
            uid = str(champ.get("user_id", ""))[:12]
            tag = F16.get(uid, uid)
            beaten_by[tag] = beaten_by.get(tag, 0) + 1
    n = len(me_ranks)
    if not n:
        print("无我方记录")
        return 1
    print("有效房数: %d" % n)
    print("\n逐房：")
    for r in room_rows:
        print("  %s %s | 我 rank%s %+d (place%+d god%d) | 冠军 rank%s %+d"
              " (place%+d god%d) %s" % (
                  r["ts"][11:16], r["room"], r["me_rank"], r["me_score"],
                  r["me_place"], r["me_god"], r["champ_rank"],
                  r["champ_score"], r["champ_place"], r["champ_god"],
                  F16.get(r["champ_user"], r["champ_user"][:8])))
    avg = lambda xs: sum(xs) / len(xs)
    print("\n汇总（%d 房）：" % n)
    print("  我方 rank 分布: %s（均值 %.2f）" %
          (dict((r, me_ranks.count(r)) for r in sorted(set(me_ranks))),
           avg(me_ranks)))
    print("  我方场均 %+.2f | 冠军场均 %+.2f | 场均差 %+.2f" %
          (avg(me_scores), avg(champ_scores), avg(me_scores) - avg(champ_scores)))
    mp = avg([r["me_place"] for r in room_rows])
    cp = avg([r["champ_place"] for r in room_rows])
    mg = avg([r["me_god"] for r in room_rows])
    cg = avg([r["champ_god"] for r in room_rows])
    print("  名次分 我方 %+.2f vs 冠军 %+.2f | 白板 我方 %.1f vs 冠军 %.1f" %
          (mp, cp, mg, cg))
    if beaten_by:
        print("  压过我们的对手: %s" % beaten_by)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
