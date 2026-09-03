"""胡牌判定（mahjong 引擎 v1：3n+2 张纯手牌，含财神百搭）。

规则依据（接入指南 §1.2）：
- 普通胡 = (len-2)/3 组面子（顺子/刻子/杠形）+ 1 对将；
- 七对 = len/2 个对子（财神可补对：单张实体牌 + 财神 = 一对；财神两两成对）；
- 白板财神可替代任意牌（宽松通配语义经 fan-calc 实测确认）；
- 七对与杠/副露互斥由调用方约束（本模块只判纯手牌结构）。

实现（性能优化版）：
- 标准形 = 枚举将（实体对/实体+财神/双财神）+ 数牌逐花色 DP
  （顺子/刻子需求覆盖该位全部实体牌，缺口用财神补，财神消耗集用 5bit 位掩码）
  + 字牌三连消（同样位掩码）；核心判定按计数元组 lru_cache；
- 七对 = 奇零实体单张数 ≤ 财神数 且剩余财神可两两成对。
"""
from __future__ import annotations

from functools import lru_cache

from .tiles import (FULL_TILES, JOKER_ID, counts_of, is_suit_tile, suit_and_num,
                    validate_hand)

# 是否允许"纯财神面子"（如 白白白 当任意刻子）参与普通胡。
# True = 宽松通配（fan-calc 实测 P1/P3 确认服务器允许）。
PURE_JOKER_MELDS = True

_FULL_BITS = (1 << 5) - 1                    # 财神消耗 0..4 的位掩码


def _meld_bits_suit(c, budget):
    """数牌单花色：可行的面子拆解财神消耗集合 → 5bit 位掩码。

    c: 该花色 1..9 计数。递推 (u,v) = 上一位起顺子尚需本位张数(u)、
    上上位起顺子尚需本位张数(v)；每层做 位或 累积。
    """
    maxmask = (1 << (budget + 1)) - 1
    cur = {(0, 0): 1}                        # bit0 置位：消耗 0 可行
    for pos in range(1, 10):
        cnt = c[pos - 1]
        nxt = {}
        for (u, v), bits in cur.items():
            for s in range(0, 3 if pos <= 7 else 1):
                for t in range(0, 3):
                    d = u + v + s + 3 * t
                    if d < cnt:
                        continue
                    extra = d - cnt
                    if extra > budget:
                        continue
                    key = (s, u)
                    nxt[key] = (nxt.get(key, 0) | ((bits << extra) & maxmask))
        cur = nxt
    out = 0
    for (u, v), bits in cur.items():
        if u == 0 and v == 0:
            out |= bits
    return out & _FULL_BITS


def _honor_bits(c_honors, budget):
    """字牌（不含白板）：每种只能组刻子（3 张/组，缺额财神补）。"""
    bits = 1
    maxmask = (1 << (budget + 1)) - 1
    for c in c_honors:
        nxt = 0
        base = (-c) % 3
        add = base
        while add <= budget:
            nxt |= (bits << add) & maxmask
            add += 3
        bits = nxt
    return bits & _FULL_BITS


@lru_cache(maxsize=200000)
def _core_win(counts14, jokers, allow_qidui):
    """核心判定：counts14 = 34 维计数元组（含白板位）。返回 bool。"""
    real = list(counts14[:JOKER_ID])
    if allow_qidui and _qidui_ok(real, jokers):
        return True
    return _standard_ok(real, jokers)


def _qidui_ok(real, jokers):
    singles = sum(1 for i in range(33) if real[i] % 2 == 1)
    if singles > jokers:
        return False
    return (jokers - singles) % 2 == 0


def _standard_ok(real, jokers):
    """普通胡：枚举将（含财神补对/双财神对）后做面子位掩码判定。"""
    # 将 = 实体对
    for p in range(33):
        if real[p] >= 2:
            rem = list(real)
            rem[p] -= 2
            if _masks_fit(*_masks_of(rem, jokers), jokers):
                return True
    # 将 = 实体 + 财神
    if jokers >= 1:
        for p in range(33):
            if real[p] >= 1:
                rem = list(real)
                rem[p] -= 1
                if _masks_fit(*_masks_of(rem, jokers - 1), jokers - 1):
                    return True
    # 将 = 双财神（无需改 real）
    if jokers >= 2 and _masks_fit(*_masks_of(real, jokers - 2), jokers - 2):
        return True
    return False


def _masks_of(real, jokers):
    return (_meld_bits_suit(real[0:9], jokers),
            _meld_bits_suit(real[9:18], jokers),
            _meld_bits_suit(real[18:27], jokers),
            _honor_bits(real[27:33], jokers))


def _masks_fit(w, b, t, h, jokers):
    """4 组面子财神消耗位掩码能否在预算内拼出合法总消耗。"""
    if jokers < 0:
        return False
    maxsum = 1 << (jokers + 1)
    ab = 0
    for i in range(jokers + 1):
        if (w >> i) & 1:
            ab |= b << i
    ab &= maxsum - 1
    abc = 0
    for i in range(jokers + 1):
        if (ab >> i) & 1:
            abc |= t << i
    abc &= maxsum - 1
    for i in range(jokers + 1):
        if (abc >> i) & 1:
            comb = h << i
            for total in range(jokers + 1):
                if (comb >> total) & 1:
                    rest = jokers - total
                    if rest == 0:
                        return True
                    if PURE_JOKER_MELDS and rest % 3 == 0:
                        return True
    return False


def is_win(hand, allow_qidui=True):
    """判定 3n+2 张手牌是否可胡（含财神百搭）。

    - len(hand) % 3 != 2 或含非法牌码 → ValueError；
    - allow_qidui=False 时仅判普通胡（供副露/杠后手牌用）。
    """
    validate_hand(hand)
    n = len(hand)
    if n % 3 != 2:
        raise ValueError("可胡手牌张数须为 3n+2，实际 %d" % n)
    counts = counts_of(hand)
    return _core_win(tuple(counts), counts[JOKER_ID], allow_qidui)


def is_baotou(hand13, allow_qidui=True):
    """爆头判定（摸牌前 13 张）：摸任意 1 张牌上来都能胡。

    接入指南 §1.2：「听牌态摸任意 1 张牌上来即胡」——即任意摸牌均成胡，
    典型形态：4 面子 + 单钓财神、六对半 + 财神（七对形）等。
    边界（正好 4 张白板不视为爆头）经 fan-calc 实测确认。
    """
    validate_hand(hand13)
    if len(hand13) != 13:
        raise ValueError("爆头判定需要摸牌前 13 张，实际 %d" % len(hand13))
    if hand13.count("白") == 4:
        return False
    for t in FULL_TILES:                 # 34 种摸牌（含摸白）
        if not is_win(hand13 + [t], allow_qidui=allow_qidui):
            return False
    return True
