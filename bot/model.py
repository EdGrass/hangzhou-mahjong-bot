"""牌码工具与快照字段解析（纯函数，可离线单测）。

牌码与对局 API 一致：1w-9w / 1b-9b / 1t-9t / 东南西北中发白（白板=财神）。
"""
from __future__ import annotations

# 全部合法牌码
SUITS = ("w", "b", "t")                      # 万 / 筒 / 条
HONORS = ("东", "南", "西", "北", "中", "发", "白")
GOD_TILE = "白"                              # 白板 = 财神（百搭）

VALID_TILES = frozenset(
    ["%d%s" % (n, s) for s in SUITS for n in range(1, 10)] + list(HONORS)
)


def is_valid_tile(tile):
    """判断牌码是否合法（不含格式，纯牌面）。"""
    return tile in VALID_TILES


def validate_hand(hand, expect=None):
    """校验手牌列表；expect 为期望张数（如 13/14），None 不校验张数。
    非法抛 ValueError（中文原因，便于定位）。"""
    if not isinstance(hand, list):
        raise ValueError("手牌必须是列表")
    if expect is not None and len(hand) != expect:
        raise ValueError("手牌张数 %d != 期望 %d" % (len(hand), expect))
    for t in hand:
        if not is_valid_tile(t):
            raise ValueError("非法牌码: %r" % (t,))
    return hand


def hand_without(hand, tiles):
    """手牌减去若干张牌（每张减 1），用于出牌后的局面推算。"""
    out = list(hand)
    for t in tiles:
        if t in out:
            out.remove(t)
        else:
            raise ValueError("要移除的牌不在手牌中: %r" % (t,))
    return out


def tile_kind(tile):
    """返回 (花色/类别, 点数)：('w',3)、('honor',7)。非法抛 ValueError。"""
    if not is_valid_tile(tile):
        raise ValueError("非法牌码: %r" % (tile,))
    if tile in HONORS:
        return ("honor", HONORS.index(tile))
    return (tile[-1], int(tile[0]))


def sort_key(tile):
    """排序键：字牌在最后（与常规手牌摆放一致）；同一花色按点数。"""
    kind, num = tile_kind(tile)
    if kind == "honor":
        return (1, num)
    return (0, SUITS.index(kind), num)


# ---------------------------------------------------------------------------
# 快照字段解析（对指南 §2.1 文档化字段的防御性读取；未知字段一律 .get 容忍）
# ---------------------------------------------------------------------------
PHASES = ("deal", "draw", "response_peng", "response_chi", "settled", "finished")

# 锦标赛终态 / 需要退出的状态
TERMINAL_STATUSES = ("finished", "closed", "void")


def snap_god(snap):
    """快照 god 字段（本人视角）：baotou / chain_count / catch_play。"""
    god = snap.get("god") or {}
    if not isinstance(god, dict):
        return {}
    return {
        "baotou": bool(god.get("baotou")),
        "chain_count": int(god.get("chain_count") or 0),
        "catch_play": bool(god.get("catch_play")),
    }


def _int_or(v, default):
    """int 转换；None 才用默认值（注意 0 是合法值，不能用 `x or default`）。"""
    return int(v) if v is not None else default


def snap_view(snap):
    """从快照提炼本人视角视图（策略层输入），字段缺失时取安全默认。"""
    god = snap_god(snap)
    seat = _int_or(snap.get("seat"), -1)
    return {
        "seat": seat,                       # 本人座位（观赛 -1）
        "phase": snap.get("phase") or "",   # deal|draw|response_*|settled|finished
        "turn": _int_or(snap.get("turn"), -1),
        "responding_seats": list(snap.get("responding_seats") or []),
        "drawn_tile": snap.get("drawn_tile") or None,   # 仅本人刚摸的牌
        "my_hand": list(snap.get("my_hand") or []),
        "god": god,
        "scores": snap.get("scores"),
    }


def window_pending(view):
    """当前是否处于本人有响应权的窗口（碰/吃/明杠等，一律 response_ 前缀）。"""
    if not view["phase"].startswith("response_"):
        return False
    if view["seat"] < 0:
        return False
    return view["seat"] in view["responding_seats"]


def my_turn(view):
    """当前是否轮到我摸牌后行动（draw 且 turn==seat）。"""
    return view["phase"] == "draw" and view["seat"] >= 0 and view["turn"] == view["seat"]
