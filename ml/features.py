"""ml —— 学习线 v0（M3）数据管道：特征编码 + 教师样本。

规划（蓝图 §5/§6）：
- 教师先行 = MCTS + 启发式（v0 先以 HeuristicA 动作作标签跑通管道）；
- 样本 = 每个摸牌决策点的 特征 + 教师动作标签（34 弃牌 + 1 胡 = 35 类）；
- 训练时合法掩码由 counts 派生（在手牌中的牌种才可弃；可胡才可 hu）。

特征（定长 int 向量，JSON 紧凑落盘）：
  hand_counts[34]  melds[e,g,chi]  god[baotou,catch,chain,piao]
  seat  drawn[34 onehot]
"""
from __future__ import annotations

ACTION_HU = 34                                # 动作空间：0..33 弃某牌种，34=胡


def counts_of(hand):
    c = [0] * 34
    for t in hand:
        c[_id(t)] += 1
    return c


def _id(t):
    from mahjong.tiles import id_of
    return id_of(t)


def encode(view):
    """把 draw 决策视图编码为 (features dict, action_space 说明)。

    features 顺序即列顺序（管道约定，训练/回放一致）：
      hand_counts34 + melds3 + god4 + seat1 + drawn34
    """
    from mahjong.tiles import id_of
    hand = view["my_hand"]
    counts = [0] * 34
    for t in hand:
        counts[id_of(t)] += 1
    melds = view.get("melds") or []
    e = len(melds)
    g = sum(1 for m in melds if m["type"] == "gang")
    chi = sum(1 for m in melds if m["type"] == "chi")
    god = view.get("god") or {}
    drawn = [0] * 34
    dt = view.get("drawn_tile")
    if dt:
        drawn[id_of(dt)] = 1
    feat = {"hand_counts": counts,
            "melds": [e, g, chi],
            "god": [int(god.get("baotou")), int(god.get("catch_play")),
                    int(god.get("chain_count") or 0),
                    int(god.get("piao_count") or 0)],
            "seat": int(view.get("seat") or 0),
            "drawn": drawn}
    return feat


def legal_mask(counts):
    """可弃牌种（在手牌中）+ hu 位（调用方另行判定胡合法性时再置位）。"""
    m = [1 if c > 0 else 0 for c in counts] + [0]
    return m


def label_of(action, counts):
    """教师动作 → 标签索引。弃牌：kind；hu：ACTION_HU。
    返回 None 表示动作不在动作空间（如 pass/窗口动作，样本不采）。"""
    a = (action or {}).get("action")
    if a == "hu":
        return ACTION_HU
    if a == "discard":
        from mahjong.tiles import id_of
        t = action.get("tile", "")
        try:
            idx = id_of(t)
        except ValueError:
            return None
        return idx if counts[idx] > 0 else None
    return None


def feature_row(view, action, meta):
    """一行训练样本（JSON 序列化友好）。meta: {seed,game,seat,hu_ok}。"""
    feat = encode(view)
    row = dict(meta)
    row["hand_counts"] = feat["hand_counts"]
    row["melds"] = feat["melds"]
    row["god"] = feat["god"]
    row["seat"] = feat["seat"]
    row["drawn"] = feat["drawn"]
    lab = label_of(action, feat["hand_counts"])
    row["action"] = lab
    row["hu_ok"] = int(meta.get("hu_ok", 0))
    return row
