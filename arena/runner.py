"""arena —— SpeedA 评估台（本地自对弈跑分，精简版）。

策略注册表当前仅 SpeedA 及其实战/开发变体；评估组合语法见 parse_combo。
数据：var/arena/{metrics.json, history.jsonl, games.jsonl} + FastAPI 面板
（arena.dashboard，localhost:8088）只读展示。

用法：
    python -m arena.runner --combo "speedAx4" --games 200 --rounds 8   # 单批
    python -m arena.runner --combo "speedBx2+speedAx2" --games 300 ...  # 变体对决
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mahjong.sim import SimGame                       # noqa: E402

STRATEGIES = {}


def _reg(name):
    def deco(fn):
        STRATEGIES[name] = fn
        return fn
    return deco


@_reg("speedA")
def _speed():
    from bot.speed import SpeedA
    return SpeedA()


@_reg("speedB")
def _speedb():
    """SpeedA 变体：副露收益判定（碰/杠/吃仅在更快成型时响应）。"""
    from bot.speedb import SpeedB
    return SpeedB()


@_reg("speedC")
def _speedc():
    """SpeedB 变体：+自杠收益判定（暗杠/补杠仅在更快成型时执行）。"""
    from bot.speedc import SpeedC
    return SpeedC()


def parse_combo(combo):
    """'speedAx4' | 'speedAx2+speedBx2'（兼容 × 全角）。"""
    names = []
    for part in combo.replace("×", "x").split("+"):
        part = part.strip()
        if not part:
            continue
        if "x" in part:
            name, cnt = part.rsplit("x", 1)
            names += [name.strip()] * int(cnt)
        else:
            names.append(part)
    return names


def make_seats(combo, rng):
    names = parse_combo(combo)
    if len(names) != 4:
        raise ValueError("组合需 4 座: %s（实际 %d）" % (combo, len(names)))
    for n in names:
        if n not in STRATEGIES:
            raise ValueError("未知策略 %r（可用 %s）" % (n, sorted(STRATEGIES)))
    order = list(range(4))
    rng.shuffle(order)
    makers = [STRATEGIES[n] for n in names]
    strategies = [makers[o]() for o in order]
    seat_names = [names[o] for o in order]
    return strategies, seat_names


class Arena:
    def __init__(self, out_dir):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.history_path = os.path.join(out_dir, "history.jsonl")
        self.games_path = os.path.join(out_dir, "games.jsonl")
        self.metrics_path = os.path.join(out_dir, "metrics.json")
        self._games_kept = []

    def run_batch(self, combo, games, rounds, seed0=0):
        rng = random.Random(seed0)
        ids = {}
        agg = {"draw": 0, "chi": 0, "peng": 0, "gang": 0, "viol": 0, "fb": 0}
        t0 = time.time()
        for g in range(games):
            strategies, seat_names = make_seats(combo, rng)
            res = SimGame(strategies, rounds=rounds, base=1,
                          seed=seed0 * 100000 + g).run()
            st = res["stats"]
            for i in range(4):
                e = ids.setdefault(seat_names[i], [0, 0, 0])
                e[0] += res["totals"][i]
                e[1] += st["hu_count"][i]
                e[2] += 1
            agg["draw"] += st["draw_count"]
            agg["chi"] += sum(st["chi"])
            agg["peng"] += sum(st["peng"])
            agg["gang"] += sum(st["gang"])
            agg["viol"] += st["violations"]
            agg["fb"] += st["fallbacks"]
            self._keep_game({"ts": time.time(), "combo": combo,
                             "seat_names": seat_names,
                             "seed": seed0 * 100000 + g,
                             "totals": res["totals"], "stats": st})
        dt = time.time() - t0
        per_round = games * rounds
        batch = {
            "ts": time.time(), "combo": combo, "games": games, "rounds": rounds,
            "secs": round(dt, 2),
            "identities": [{
                "name": name,
                "avg_tot": round(tot / cnt, 2),
                "hu_rate": round(hu / cnt / rounds, 4),
            } for name, (tot, hu, cnt) in sorted(ids.items())],
            "draw_rate": round(agg["draw"] / per_round, 4),
            "chi": agg["chi"], "peng": agg["peng"], "gang": agg["gang"],
            "viol": agg["viol"], "fallbacks": agg["fb"],
        }
        self._write_batch(batch)
        return batch

    def _keep_game(self, rec):
        self._games_kept.append(rec)
        if len(self._games_kept) > 300:
            del self._games_kept[:len(self._games_kept) - 300]
        with open(self.games_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _write_batch(self, batch):
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(batch, ensure_ascii=False) + "\n")
        self._write_metrics()

    def _write_metrics(self):
        batches = []
        if os.path.exists(self.history_path):
            with open(self.history_path, encoding="utf-8") as f:
                batches = [json.loads(l) for l in f if l.strip()]
        by_combo = {}
        for b in batches:
            by_combo.setdefault(b["combo"], []).append(b)
        combos = {}
        for name, bs in by_combo.items():
            n = sum(x["games"] for x in bs)
            rnd = bs[0]["rounds"]
            ids = {}
            for x in bs:
                for ident in x.get("identities", []):
                    e = ids.setdefault(ident["name"], [0.0, 0, 0])
                    e[0] += ident["avg_tot"] * x["games"]
                    e[1] += ident["hu_rate"] * x["games"] * rnd
                    e[2] += x["games"]
            combos[name] = {
                "batches": len(bs), "games": n,
                "identities": [{
                    "name": k,
                    "avg_tot": round(v[0] / v[2], 2),
                    "hu_rate": round(v[1] / v[2] / rnd, 4),
                } for k, v in sorted(ids.items())],
                "draw_rate": round(sum(x["draw_rate"] * x["games"] for x in bs) / n, 4),
                "secs": round(sum(x["secs"] for x in bs), 1),
            }
        snap = {"updated_at": time.time(), "total_batches": len(batches),
                "combos": combos}
        tmp = "%s.tmp.%d" % (self.metrics_path, int(time.time() * 1000))
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=1)
        for attempt in range(8):
            try:
                os.replace(tmp, self.metrics_path)
                return
            except PermissionError:
                time.sleep(0.05)
        raise PermissionError("metrics 写入冲突: %s" % self.metrics_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", default="speedAx4")
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--every", type=float, default=0, help="循环间隔秒（0=单批退出）")
    ap.add_argument("--out", default=os.path.join("var", "arena"))
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    arena = Arena(args.out)
    seed = args.seed
    while True:
        try:
            b = arena.run_batch(args.combo, args.games, args.rounds, seed0=seed)
        except KeyboardInterrupt:
            break
        seed += 1
        ids = ",".join("%s:%+.1f/%s%%" % (i["name"], i["avg_tot"],
                                          round(i["hu_rate"] * 100, 1))
                       for i in b["identities"])
        sys.stdout.write("batch %s: games=%d 耗时%ss [%s] 流局=%s%%\n" % (
            args.combo, b["games"], b["secs"], ids,
            round(b["draw_rate"] * 100, 1)))
        sys.stdout.flush()
        if not args.every:
            break
        try:
            time.sleep(args.every)
        except KeyboardInterrupt:
            break
    print("arena 退出（数据在 %s）" % args.out)


if __name__ == "__main__":
    main()
