"""胡牌判定（mahjong 引擎 v1：3n+2 张纯手牌，含财神百搭）。

规则依据（接入指南 §1.2）：
- 普通胡 = (len-2)/3 组面子（顺子/刻子/杠形）+ 1 对将；
- 七对 = len/2 个对子（财神可补对：单张实体牌 + 财神 = 一对；财神成对）；
- 白板财神可替代任意牌（v1 通配实现，纯财神面子的允许度
  以 PURE_JOKER_MELDS 开关控制，待 fan-calc 对齐用例收敛）；
- 七对与杠/副露互斥由调用方约束（本模块只判纯手牌结构）。

实现：标准形 = 枚举将（实体对/实体+财神/双财神）+ 数牌逐花色 DP
（顺子/刻子 需求覆盖该位全部实体牌，缺口用财神补）+ 字牌三连消；
七对 = 奇零实体单张数 ≤ 财神数 且剩余财神可两两成对。
"""
from __future__ import annotations

from .tiles import (JOKER_ID, counts_of, is_suit_tile, suit_and_num,
                    validate_hand)

# 是否允许"纯财神面子"（如 白白白 当任意刻子）参与普通胡。
# True = 宽松通配；False = 每面子至少含 1 张实体牌。对齐阶段收敛。
PURE_JOKER_MELDS = True


def _meld_usage_masks_suit(c, joker_budget):
    """数牌单花色：所有可行面子拆解消耗的财神数集合。

    c: 该花色 1..9 的计数（9 个）；返回 set[int]（消耗财神张数）。
    规则：从左到右，每张实体牌必须被 顺子起头 / 前位顺子需求 / 刻子 恰好消耗；
    缺额由财神补。顺子只能从 1..7 起头。
    """
    # (u, v) = 上一位起的顺子尚需本位的张数(u)、上上位起的顺子尚需本位的张数(v)
    # 用 dict[(i, u, v)] = 可行财神消耗集合 做递推；i: 当前处理到点数 i（1..9）
    cur = {(0, 0): {0}}
    for pos in range(1, 10):
        cnt = c[pos - 1]
        nxt = {}
        for (u, v), used_set in cur.items():
            # 该位需求 = 顺子继承(u+v) + 新顺子起头 s + 刻子 3t
            # s 仅当 pos<=7 可起头；t>=0
            max_s = 2 if pos <= 7 else 0
            for s in range(0, max_s + 1):
                # 新顺子 1 张/个；额外刻子
                for t in range(0, 3):
                    d = u + v + s + 3 * t
                    if d < cnt:
                        continue            # 实体牌用不完
                    extra = d - cnt         # 缺口用财神
                    for used in used_set:
                        total = used + extra
                        if total > joker_budget:
                            continue
                        nxt.setdefault((s, u), set()).add(total)
        cur = nxt
    # 结束时顺子继承必须清零（u/v 无残留）
    return set().union(*(s for (u, v), s in cur.items() if u == 0 and v == 0)) \
        if cur else set()


def _honor_masks(c_honors, joker_budget):
    """字牌（不含白板）：每种字牌只能组成刻子（3 张/组，缺额财神补）。

    返回可行财神消耗集合。每种字牌消耗 = 使其总数成 3 的倍数的最小补
    + 3k（多补一组刻子）。
    """
    cur = {0}
    for c in c_honors:
        nxt = set()
        base = (-c) % 3                      # 补齐到 3 的倍数所需最少财神
        for used in cur:
            add = base
            while used + add <= joker_budget:
                nxt.add(used + add)
                add += 3                     # 可整体多凑一组 刻子
        cur = nxt
    return cur


def _standard_win(real_counts, jokers):
    """普通胡判定。real_counts: 33 维（不含白板）；jokers: 白板数。

    枚举将后对剩余实体牌做 面子 DP；返回是否可行。
    纯财神面子开关：面子结构消耗财神后，若仍剩余财神且允许，
    剩余财神须能 3 张一组（纯财神面子）消耗。
    """
    for pair_kind in range(33):
        if real_counts[pair_kind] >= 2:
            rem = real_counts.copy()
            rem[pair_kind] -= 2
            if _win_after_pair(rem, jokers):
                return True
    if jokers >= 1:
        for pair_kind in range(33):
            if real_counts[pair_kind] >= 1:
                rem = real_counts.copy()
                rem[pair_kind] -= 1
                if _win_after_pair(rem, jokers - 1):
                    return True
    if jokers >= 2 and _win_after_pair(real_counts, jokers - 2):
        return True
    return False


def _win_after_pair(real_counts, jokers):
    """将已选定：剩余实体牌拆面子，检查财神预算可行。"""
    if jokers < 0:
        return False
    # 数牌各花色独立 DP 的消耗集合 → 汇总位掩码简化交集判断
    ok = set()
    # 先算各数牌花色集合
    masks = []
    for si in range(3):
        c = real_counts[si * 9:(si + 1) * 9]
        masks.append(_meld_usage_masks_suit(c, jokers))
    masks.append(_honor_masks(real_counts[27:33], jokers))
    # 遍历 4 组消耗组合（每组 ≤ 5 种，总量很小）
    for a in masks[0]:
        for b in masks[1]:
            for c in masks[2]:
                for d in masks[3]:
                    total = a + b + c + d
                    if total > jokers:
                        continue
                    rest = jokers - total
                    if rest == 0:
                        return True
                    if PURE_JOKER_MELDS and rest % 3 == 0:
                        return True        # 剩余财神以纯财神面子消耗
    return False


def _qidui_win(real_counts, jokers):
    """七对判定：实体牌中奇零单张（%2==1）各需 1 个财神补对；
    剩余财神两两成对。"""
    singles = sum(1 for i in range(33) if real_counts[i] % 2 == 1)
    if singles > jokers:
        return False
    rest = jokers - singles
    return rest % 2 == 0


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
    jokers = counts[JOKER_ID]
    real = list(counts[:JOKER_ID])
    if allow_qidui and _qidui_win(real, jokers):
        return True
    return _standard_win(real, jokers)
