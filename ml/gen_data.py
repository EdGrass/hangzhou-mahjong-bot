"""ml/gen_data —— 教师样本批量生成器（v0 教师 = HeuristicA；MCTS 教师后续替换）。

流程：SimGame 4 座跑局，Recording 包装策略在每次「摸牌决策」记录
（特征, 教师动作标签, 元信息）→ JSONL，逐局落盘。

用法：
    python -m ml.gen_data --games 300 --rounds 8 --out var/ml/samples.jsonl
吞吐参照：本机 ≈60 局×8 轮/7s → 每批数万决策样本。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mahjong.hu import is_win                       # noqa: E402
from mahjong.sim import SimGame                     # noqa: E402
from ml.features import feature_row                 # noqa: E402


class Recording:
    """包装教师策略：摸牌决策点（drawn 非空）记录样本。"""

    def __init__(self, inner, rows, meta):
        self.inner = inner
        self.rows = rows
        self.meta = meta

    def decide(self, view):
        action = self.inner.decide(view)
        if (action or {}).get("action") in ("discard", "hu") and \
                view.get("drawn_tile"):
            melds = view.get("melds") or []
            try:
                hu_ok = is_win(view["my_hand"], exposed_melds=len(melds),
                               gangs=sum(1 for m in melds
                                         if m["type"] == "gang"))
            except ValueError:
                hu_ok = False
            row = feature_row(view, action, self.meta)
            if row["action"] is not None:
                row["hu_ok"] = int(hu_ok)
                self.rows.append(row)
        return action


def gen(games, rounds, seed0, out_path, teacher_name="heuristicA"):
    """逐局跑 4 座同教师，落盘全部摸牌决策样本。"""
    from arena.runner import STRATEGIES
    if teacher_name not in STRATEGIES:
        raise ValueError("未知教师 %r（可用 %s）" % (teacher_name,
                                                  sorted(STRATEGIES)))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    t0 = time.time()
    written = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for g in range(games):
            rows = []
            strategies = [Recording(STRATEGIES[teacher_name](), rows,
                                    {"seed": seed0, "game": g, "seat": i})
                          for i in range(4)]
            SimGame(strategies, rounds=rounds, base=1,
                    seed=seed0 * 100000 + g).run()
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            written += len(rows)
            if (g + 1) % 25 == 0 or g == games - 1:
                print("game %d/%d 累计样本 %d (%.1fs)" % (
                    g + 1, games, written, time.time() - t0), flush=True)
    dt = time.time() - t0
    size = os.path.getsize(out_path) / 1e6
    print("完成: %d 样本 → %s (%.1f MB, 吞吐 %.0f 样本/s)"
          % (written, out_path, size, written / dt))
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--teacher", default="heuristicA")
    ap.add_argument("--out", default=os.path.join("var", "ml", "samples.jsonl"))
    args = ap.parse_args()
    gen(args.games, args.rounds, args.seed, args.out, args.teacher)


if __name__ == "__main__":
    main()
