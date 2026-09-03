"""ml/train —— 小策略网监督训练（v0）。

数据：ml.gen_data 产出的 JSONL（每行 = 特征 + 教师动作标签 + hu_ok）。
模型：小型 MLP（76 维特征 → 35 logits 策略头 + 1 价值头雏形）。
损失：带合法掩码的交叉熵（掩码 = 手牌含该牌种 + hu 位需 hu_ok）。

用法：
    python -m ml.train --data var/ml/samples.jsonl --epochs 5 --batch 512 \
        --out var/ml/model_v0.pt --smoke   # --smoke 只取 2 万行快速验证链路
输出：checkpoint（模型+列序+元数据）+ 训练日志。
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

import torch                      # noqa: E402
import torch.nn as nn             # noqa: E402

FEAT_DIM = 34 + 3 + 4 + 1 + 34    # hand_counts + melds + god + seat + drawn
ACT_DIM = 35                      # 34 弃牌 + hu


def _tile_id(t):
    from mahjong.tiles import id_of
    return id_of(t)


def load_rows(path, max_rows=0):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            rows.append(r)
            if max_rows and len(rows) >= max_rows:
                break
    return rows


def row_to_tensors(r):
    x = (r["hand_counts"] + r["melds"] + r["god"] +
         [r["seat"]] + r["drawn"])
    return x, r["action"], r.get("hu_ok", 0)


class PolicyNet(nn.Module):
    """76 → 128 → 128 → 35(+1 价值)。"""

    def __init__(self, feat_dim=FEAT_DIM, act_dim=ACT_DIM, hidden=128):
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(feat_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
        )
        self.policy = nn.Linear(hidden, act_dim)
        self.value = nn.Linear(hidden, 1)

    def forward(self, x):
        h = self.body(x)
        return self.policy(h), self.value(h)


def make_batches(rows, batch, device):
    xs, ys, masks = [], [], []
    for r in rows:
        x, act, hu_ok = row_to_tensors(r)
        m = [1 if c > 0 else 0 for c in r["hand_counts"]] + [int(hu_ok)]
        xs.append(x)
        ys.append(act)
        masks.append(m)
    X = torch.tensor(xs, dtype=torch.float32, device=device)
    Y = torch.tensor(ys, dtype=torch.long, device=device)
    M = torch.tensor(masks, dtype=torch.float32, device=device)
    n = len(rows)
    idx = list(range(n))
    for i in range(0, n, batch):
        yield X[idx[i:i + batch]], Y[idx[i:i + batch]], M[idx[i:i + batch]]


def masked_loss(logits, y, mask):
    """mask 后 softmax 的 CE；掩码全 0（理论不出现）则跳过该样本。"""
    logits = logits + (1.0 - mask) * -1e9
    return nn.functional.cross_entropy(logits, y)


def evaluate(model, rows, batch, device):
    model.eval()
    tot = hits = n = 0
    with torch.no_grad():
        for X, Y, M in make_batches(rows, batch, device):
            logits, _ = model(X)
            loss = masked_loss(logits, Y, M)
            pred = (logits + (1.0 - M) * -1e9).argmax(dim=1)
            hits += (pred == Y).sum().item()
            n += Y.size(0)
            tot += loss.item() * Y.size(0)
    return tot / max(n, 1), hits / max(n, 1)


def train(data_path, epochs, batch, out_path, max_rows, seed=1, device="cpu"):
    torch.manual_seed(seed)
    rows = load_rows(data_path, max_rows)
    if len(rows) < 1000:
        raise SystemExit("样本过少（%d），先运行 ml.gen_data" % len(rows))
    split = int(len(rows) * 0.95)
    tr, va = rows[:split], rows[split:]
    model = PolicyNet().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    log = {"epochs": [], "train_loss": [], "val_loss": [], "val_top1": []}
    for ep in range(epochs):
        model.train()
        tl = n = 0
        for X, Y, M in make_batches(tr, batch, device):
            opt.zero_grad()
            logits, _ = model(X)
            loss = masked_loss(logits, Y, M)
            loss.backward()
            opt.step()
            tl += loss.item() * Y.size(0)
            n += Y.size(0)
        vl, vt = evaluate(model, va, batch, device)
        log["epochs"].append(ep)
        log["train_loss"].append(round(tl / max(n, 1), 4))
        log["val_loss"].append(round(vl, 4))
        log["val_top1"].append(round(vt, 4))
        print("epoch %d train_loss=%.4f val_loss=%.4f val_top1=%.3f" % (
            ep, tl / max(n, 1), vl, vt), flush=True)
    meta = {"feat_dim": FEAT_DIM, "act_dim": ACT_DIM, "samples": len(rows),
            "trained_at": time.time(), "log": log}
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    torch.save({"state": model.state_dict(), "meta": meta}, out_path)
    print("checkpoint → %s（val_top1=%.3f）" % (out_path, vt))
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join("var", "ml", "samples.jsonl"))
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--out", default=os.path.join("var", "ml", "model_v0.pt"))
    ap.add_argument("--max-rows", type=int, default=0)
    ap.add_argument("--smoke", action="store_true", help="2 万行快速链路验证")
    args = ap.parse_args()
    if args.smoke and not args.max_rows:
        args.max_rows = 20000
        args.epochs = min(args.epochs, 3)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("device:", device)
    train(args.data, args.epochs, args.batch, args.out, args.max_rows,
          device=device)


if __name__ == "__main__":
    main()
