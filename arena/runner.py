"""Arena —— 本地数据工厂（M2.5）：批次自对弈 → JSONL 落盘 + 指标历史。

设计：
- 策略注册表：按名取 4 座策略工厂（naive/heuristicA；未来 model 版本插槽同构）；
- 座位轮换消除偏差；每批跑完 append 一行指标历史 + 每局一行战绩日志；
- 循环模式：--every N 秒持续跑（面板实时看趋势）；--once 跑一批即退（CI/脚本用）。

数据目录（默认 var/arena/）：
  metrics.json          当前汇总快照（面板总览读这个）
  history.jsonl         批次历史（趋势图数据源）
  games.jsonl           每局战绩（最近对局表数据源，环形保留 N 行）
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from mahjong.sim import SimGame                       # noqa: E402

STRATEGIES = {}


def _reg(name):
    def deco(fn):
        STRATEGIES[name] = fn
        return fn
    return deco


@_reg("naive")
def _naive():
    from bot.strategy import NaiveStrategy
    return NaiveStrategy()


@_reg("heuristicA")
def _heuristic():
    from bot.heuristic import HeuristicA
    return HeuristicA()


@_reg("speedA")
def _speed():
    from bot.speed import SpeedA
    return SpeedA()


@_reg("heuristicA2")
def _heuristic2():
    from bot.heuristic2 import HeuristicA2
    return HeuristicA2()


@_reg("v0")
def _v0():
    """学习线 v0 模型策略（读 var/ml/model_v0.pt；不存在时报错提示先训练）。"""
    import os
    ckpt = os.path.join(HERE, "..", "var", "ml", "model_v0.pt")
    if not os.path.exists(ckpt):
        raise ValueError("模型 %s 不存在：先 python -m ml.train" % ckpt)
    from bot.model_policy import V0Policy
    return V0Policy(ckpt)


@_reg("rl1")
def _rl1():
    import os
    ckpt = os.path.join(HERE, "..", "var", "ml", "model_rl1.pt")
    if not os.path.exists(ckpt):
        raise ValueError("模型 %s 不存在（先 python -m ml.rl）" % ckpt)
    from bot.model_policy import V0Policy
    return V0Policy(ckpt, name="rl1")


@_reg("v4sr")
def _v4sr():
    """v4s + 引擎胡规则（hu_rule）：弃牌学 SpeedA、胡由引擎即时接管。"""
    import os
    ckpt = os.path.join(HERE, "..", "var", "ml", "model_v4s.pt")
    from bot.model_policy import V0Policy
    return V0Policy(ckpt, name="v4sr", hu_rule=True)


@_reg("v4s")
def _v4s():
    import os
    ckpt = os.path.join(HERE, "..", "var", "ml", "model_v4s.pt")
    from bot.model_policy import V0Policy
    return V0Policy(ckpt, name="v4s")


@_reg("v4a")
def _v4a():
    import os
    ckpt = os.path.join(HERE, "..", "var", "ml", "model_v4a.pt")
    from bot.model_policy import V0Policy
    return V0Policy(ckpt, name="v4a")


@_reg("v3")
def _v3():
    import os
    ckpt = os.path.join(HERE, "..", "var", "ml", "model_v3.pt")
    if not os.path.exists(ckpt):
        raise ValueError("模型 %s 不存在" % ckpt)
    from bot.model_policy import V0Policy
    return V0Policy(ckpt, name="v3")


@_reg("v2a")
def _v2a():
    import os
    ckpt = os.path.join(HERE, "..", "var", "ml", "model_v2a.pt")
    if not os.path.exists(ckpt):
        raise ValueError("模型 %s 不存在" % ckpt)
    from bot.model_policy import V0Policy
    return V0Policy(ckpt, name="v2a")


@_reg("v2b")
def _v2b():
    import os
    ckpt = os.path.join(HERE, "..", "var", "ml", "model_v2b.pt")
    if not os.path.exists(ckpt):
        raise ValueError("模型 %s 不存在" % ckpt)
    from bot.model_policy import V0Policy
    return V0Policy(ckpt, name="v2b")


@_reg("v1")
def _v1():
    """v1（更大数据集训练版，var/ml/model_v1.pt）。"""
    import os
    ckpt = os.path.join(HERE, "..", "var", "ml", "model_v1.pt")
    if not os.path.exists(ckpt):
        raise ValueError("模型 %s 不存在" % ckpt)
    from bot.model_policy import V0Policy
    return V0Policy(ckpt, name="v1")


def parse_combo(combo):
    """'heuristicAx4' | 'naivex2+heuristicAx2'（兼容 × 全角）。"""
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
    """组合描述 → 4 座策略（每次轮换座位）。"""
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

    # -- 批次 ----------------------------------------------------------------
    def run_batch(self, combo, games, rounds, seed0=0):
        rng = random.Random(seed0)
        ids = {}                              # 策略名 → [tot, hu, fan, 出现座位次]
        agg = {"draw": 0, "chi": 0, "peng": 0, "gang": 0, "viol": 0, "fb": 0}
        t0 = time.time()
        for g in range(games):
            strategies, seat_names = make_seats(combo, rng)
            res = SimGame(strategies, rounds=rounds, base=1,
                          seed=seed0 * 100000 + g).run()
            st = res["stats"]
            for i in range(4):
                e = ids.setdefault(seat_names[i], [0, 0, 0, 0])
                e[0] += res["totals"][i]
                e[1] += st["hu_count"][i]
                e[2] += st["fan_total"][i]
                e[3] += 1
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
                "avg_fan": round(fs / hu, 2) if hu else 0.0,
            } for name, (tot, hu, fs, cnt) in sorted(ids.items())],
            "draw_rate": round(agg["draw"] / per_round, 4),
            "chi": agg["chi"], "peng": agg["peng"], "gang": agg["gang"],
            "viol": agg["viol"], "fallbacks": agg["fb"],
        }
        self._write_batch(batch)
        return batch

    # -- 落盘 ----------------------------------------------------------------
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
        # 并发多写进程（连续流 + 临时评估）可能冲突：唯一临时名 + 重试原子替换
        tmp = "%s.tmp.%d.%d" % (self.metrics_path, os.getpid(),
                                int(time.time() * 1000))
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=1)
        for attempt in range(8):
            try:
                os.replace(tmp, self.metrics_path)
                return
            except PermissionError:
                time.sleep(0.05)
        raise PermissionError("metrics 写入持续冲突: %s" % self.metrics_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", default="heuristicAx4")
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
        sys.stdout.write("batch %s: games=%d 耗时%ss 身份[%s] 流局=%s%%\n" % (
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
