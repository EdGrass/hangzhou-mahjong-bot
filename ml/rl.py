"""ml/rl —— S4 最小自对弈策略梯度（REINFORCE-lite，让模型自选速度×打点）。

机制：
- PolicyPlayer 包装 checkpoint 模型：摸牌决策时按策略分布【采样】并记录
  (特征, 动作, logp)；hu 槽与弃牌槽同训 —— 胡的时机（早胡=速度 /
  弃胡等更大番=打点）由 reward 驱动自行权衡；
- 每轮：自对弈 B 局（4 座同模型，座位轮换）→ 局末 totals[seat] 作 reward，
  优势 = 座位得分 − 该局四座均值（零和校准）→ 策略梯度更新；
- reward 即总得分（底分×番×庄闲 的自然产物）：模型学到的正是
  「期望得分最大化 = 速度与打点的最优中间位置」；
- hu_ok/合法掩码沿用引擎；温度采样保探索。

用法：
    python -m ml.rl --ckpt var/ml/model_v4s.pt --games 32 --iters 120 \
        --lr 1e-4 --out var/ml/model_rl1.pt
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import torch                                    # noqa: E402
import torch.nn.functional as F                 # noqa: E402

from mahjong.sim import SimGame                 # noqa: E402
from ml.features import encode                  # noqa: E402
from ml.train import ACT_DIM, FEAT_DIM, PolicyNet  # noqa: E402


class PolicyPlayer:
    """采样策略玩家：记录 (logp, 特征向量) 供 REINFORCE 用。"""

    def __init__(self, model, device, temp=1.0, seed=0):
        self.model = model
        self.device = device
        self.temp = temp
        self.rng = random.Random(seed)
        self.logs = []          # (feat_vec, action, logp)

    def decide(self, view):
        from mahjong.hu import is_win
        from mahjong.tiles import tile_of
        from bot.model import my_turn, window_pending
        if window_pending(view):
            return {"action": "pass", "tile": ""}
        if not my_turn(view) or not view.get("drawn_tile"):
            return None
        melds = view.get("melds") or []
        try:
            hu_ok = is_win(view["my_hand"], exposed_melds=len(melds),
                           gangs=sum(1 for m in melds if m["type"] == "gang"))
        except ValueError:
            hu_ok = False
        feat = encode(view)
        x = torch.tensor([[feat["hand_counts"] + feat["melds"] +
                           feat["god"] + [feat["seat"]] + feat["drawn"]]],
                         dtype=torch.float32, device=self.device)
        with torch.no_grad():
            logits, _ = self.model(x)
            logits = logits[0].cpu().double() / max(self.temp, 1e-3)
        counts = feat["hand_counts"]
        mask = [1 if c > 0 else 0 for c in counts] + [int(hu_ok)]
        logits = logits + (1.0 - torch.tensor(mask)) * -1e9
        probs = F.softmax(logits, dim=0)
        # 采样
        p = probs.numpy()
        act = self.rng.choices(range(ACT_DIM), weights=p.tolist())[0]
        self.logs.append((x[0].tolist(), act, math.log(max(float(p[act]), 1e-12))))
        if act == ACT_DIM - 1:
            return {"action": "hu", "tile": ""}
        return {"action": "discard", "tile": tile_of(act)}


def selfplay_batch(model, device, games, rounds, seed):
    """自对弈 games 局 → (轨迹汇总, rewards)。座位轮换消除偏差。"""
    rng = random.Random(seed)
    all_rows = []               # (feat_vec, act, logp, adv)
    for g in range(games):
        players = [PolicyPlayer(model, device, seed=seed + g * 4 + i)
                   for i in range(4)]
        order = list(range(4))
        rng.shuffle(order)
        strategies = [players[order[i]] for i in range(4)]
        res = SimGame(strategies, rounds=rounds, base=1,
                      seed=seed * 100000 + g).run()
        mean = sum(res["totals"]) / 4.0
        for i in range(4):
            # 玩家 players[i] 实际坐在 order.index(i)
            seat = order.index(i)
            adv = (res["totals"][seat] - mean) / 8.0   # 缩放到 ±10 量级
            for fv, a, lp in players[i].logs:
                all_rows.append((fv, a, lp, adv))
    return all_rows


def train(ckpt_path, out_path, games=32, rounds=8, iters=120, lr=1e-4,
          temp=1.0, seed=1, log_every=10, save_every=0):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = PolicyNet().to(device)
    data = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(data["state"])
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    history = []
    t0 = time.time()
    for it in range(iters):
        rows = selfplay_batch(model, device, games, rounds, seed + it * 7)
        if not rows:
            continue
        X = torch.tensor([r[0] for r in rows], dtype=torch.float32,
                         device=device)
        A = torch.tensor([r[1] for r in rows], dtype=torch.long, device=device)
        L = torch.tensor([r[2] for r in rows], dtype=torch.float32,
                         device=device)
        Adv = torch.tensor([r[3] for r in rows], dtype=torch.float32,
                           device=device)
        logits, _ = model(X)
        # 合法掩码从特征重建（hu 槽可胡性未编码 → 训练中仅对采样到的动作求
        # logp，掩码只影响采样（已在采样侧完成），这里直接取采样动作的 logp）
        logp_all = F.log_softmax(logits, dim=1)
        logp_act = logp_all.gather(1, A.unsqueeze(1)).squeeze(1)
        # REINFORCE + 熵正则（鼓励探索），baseline 已用局内均值
        adv_mean = Adv.mean()
        adv_std = Adv.std().clamp(min=1e-3)
        adv_norm = (Adv - adv_mean) / adv_std
        pg_loss = -(logp_act * adv_norm).mean()
        ent = -(logp_all.exp() * logp_all).sum(dim=1).mean()
        loss = pg_loss - 0.01 * ent
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if (it + 1) % log_every == 0 or it == 0:
            print("iter %d  rows=%d  pg=%.4f ent=%.3f adv_mean=%.3f (%.0fs)"
                  % (it + 1, len(rows), pg_loss.item(), ent.item(),
                     adv_mean.item(), time.time() - t0), flush=True)
        if save_every and (it + 1) % save_every == 0:
            mid = out_path.replace(".pt", "_step%d.pt" % (it + 1))
            torch.save({"state": model.state_dict(),
                        "meta": {"base_ckpt": ckpt_path, "iters": it + 1}},
                       mid)
            print("中途存档 → %s" % mid, flush=True)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    torch.save({"state": model.state_dict(),
                "meta": {"base_ckpt": ckpt_path, "iters": iters,
                         "games": games, "rounds": rounds, "lr": lr,
                         "temp": temp}}, out_path)
    print("RL checkpoint → %s" % out_path)
    return history


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=os.path.join("var", "ml", "model_v4s.pt"))
    ap.add_argument("--out", default=os.path.join("var", "ml", "model_rl1.pt"))
    ap.add_argument("--games", type=int, default=32)
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--iters", type=int, default=120)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--temp", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--save-every", type=int, default=0, help="每 N iter 中途存档")
    args = ap.parse_args()
    train(args.ckpt, args.out, args.games, args.rounds, args.iters, args.lr,
          args.temp, args.seed, save_every=args.save_every)


if __name__ == "__main__":
    main()
