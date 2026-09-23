"""牌张编码与计数工具（mahjong 引擎内部规范）。

牌码与对局 API 一致：1w-9w / 1b-9b / 1t-9t / 东南西北中发白。
白板（白）是财神 = 百搭，单独处理为 joker，不进入 33 种实体牌的计数。
"""
from __future__ import annotations

SUITS = ("w", "b", "t")                            # 万 / 筒 / 条
HONORS = ("东", "南", "西", "北", "中", "发", "白")  # 字牌，白板为财神
GOD_TILE = "白"

# 33 种实体牌（不含白板）：先数牌（每花色 9）后字牌（东南西北中发）
TILE_IDS = {}
for si, suit in enumerate(SUITS):
    for n in range(1, 10):
        TILE_IDS["%d%s" % (n, suit)] = si * 9 + (n - 1)
for hi, honor in enumerate(HONORS):
    if honor != GOD_TILE:
        TILE_IDS[honor] = 27 + hi            # 东南西北中发 → 27..32
ID_TILES = {v: k for k, v in TILE_IDS.items()}
NUM_TILE_KINDS = 33
JOKER_ID = 33                                 # 财神在完整 34 维中的位置

FULL_TILES = {t: TILE_IDS[t] for t in TILE_IDS}
FULL_TILES[GOD_TILE] = JOKER_ID


def is_valid(tile):
    return tile in FULL_TILES


def id_of(tile):
    """牌码 → 0..32（实体）/ 33（白板财神）；非法抛 ValueError。"""
    try:
        return FULL_TILES[tile]
    except KeyError:
        raise ValueError("非法牌码: %r" % (tile,))


def tile_of(i):
    """0..33 → 牌码。"""
    if i == JOKER_ID:
        return GOD_TILE
    try:
        return ID_TILES[i]
    except KeyError:
        raise ValueError("非法牌索引: %r" % (i,))


def is_suit_tile(i):
    """实体牌索引是否数牌（万筒条）。"""
    return 0 <= i < 27


def suit_and_num(i):
    """数牌索引 → (花色 0..2, 点数 1..9)。"""
    if not is_suit_tile(i):
        raise ValueError("非数牌: %d" % i)
    return i // 9, i % 9 + 1


def counts_of(hand):
    """手牌 → 34 维计数向量（末位为白板财神数）。"""
    c = [0] * 34
    for t in hand:
        c[id_of(t)] += 1
    return c


def from_counts(c):
    """34 维计数 → 展开的牌码列表。"""
    out = []
    for i, n in enumerate(c):
        out.extend([tile_of(i)] * n)
    return out


def validate_hand(hand, expect=None):
    """校验手牌；expect 指定张数（如 14），None 不校验。非法抛 ValueError。"""
    if not isinstance(hand, list):
        raise ValueError("手牌必须是列表")
    if expect is not None and len(hand) != expect:
        raise ValueError("手牌张数 %d != 期望 %d" % (len(hand), expect))
    for t in hand:
        if not is_valid(t):
            raise ValueError("非法牌码: %r" % (t,))
    return hand
