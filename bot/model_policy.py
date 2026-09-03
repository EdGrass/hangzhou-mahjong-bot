"""模型策略接入（学习线 v0）：加载 checkpoint 作 Strategy。

决策：特征编码 → 模型输出 35 logits → 合法掩码（手牌含该牌种；hu 位需引擎判
可胡）内取 argmax（或可配采样温度）。
接入点：arena.runner 注册 'v0'（--combo "v0x4" 等）→ 与 heuristicA/naive 混编评估。
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import torch                                  # noqa: E402

from ml.features import encode                # noqa: E402
from ml.train import ACT_DIM, FEAT_DIM, PolicyNet  # noqa: E402
from .model import my_turn, window_pending    # noqa: E402
from .strategy import Strategy                # noqa: E402


class V0Policy(Strategy):
    """checkpoint 驱动的 v0 策略（协议 view 同构）。"""

    def __init__(self, ckpt_path, name="v0", device=None, greedy=True,
                 hu_rule=False):
        self.name = name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = PolicyNet().to(self.device)
        data = torch.load(ckpt_path, map_location=self.device)
        self.model.load_state_dict(data["state"])
        self.model.eval()
        self.greedy = greedy
        self.ckpt = ckpt_path
        self.hu_rule = hu_rule       # True：可胡即胡由引擎接管（hu 槽不参与）

    def decide(self, view):
        from mahjong.hu import is_win
        from mahjong.tiles import id_of, tile_of
        if window_pending(view):
            return {"action": "pass", "tile": ""}   # v0 窗口策略未训：全过
        if not my_turn(view) or not view.get("drawn_tile"):
            return None
        feat = encode(view)
        x = torch.tensor([feat["hand_counts"] + feat["melds"] + feat["god"] +
                          [feat["seat"]] + feat["drawn"]],
                         dtype=torch.float32, device=self.device)
        with torch.no_grad():
            logits, _ = self.model(x)
            logits = logits[0].cpu()
        melds = view.get("melds") or []
        try:
            hu_ok = is_win(view["my_hand"], exposed_melds=len(melds),
                           gangs=sum(1 for m in melds if m["type"] == "gang"))
        except ValueError:
            hu_ok = False
        counts = feat["hand_counts"]
        if self.hu_rule:
            # 引擎接管胡：可胡即胡；否则在 34 弃牌槽内 argmax
            if hu_ok:
                return {"action": "hu", "tile": ""}
            mask = [1 if c > 0 else 0 for c in counts] + [0]
        else:
            mask = [1 if c > 0 else 0 for c in counts] + [int(hu_ok)]
        logits = logits + (1.0 - torch.tensor(mask)) * -1e9
        act = int(logits.argmax().item())
        if act == ACT_DIM - 1:                  # hu 槽 = 34
            return {"action": "hu", "tile": ""}
        return {"action": "discard", "tile": tile_of(act)}


# 方便 arena.runner 注册：需要文件路径，见 register_v0()
def make_from(ckpt_path, **kw):
    return V0Policy(ckpt_path, **kw)
