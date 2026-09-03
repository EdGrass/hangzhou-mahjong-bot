"""番型/结算计算（与服务器 fan-calc 口径对齐，黄金集 testdata/fan_calc_golden.json 回归）。

已对齐结论（2026-09-03 实测 fan-calc）：
- 总番 = 分支倍率 × 2^链动作数 ×(4白板 ×2)×(爆头 ×2)，次序：分支→链→4白→爆头；
- 分支：平胡 ×1；七对 ×2；豪华七对×N = 2^(N+1)（N = 四张组数，
  实体 4 张与 白×4 各算 1 组——白×4 同时再计 4白板 ×2，两者叠加）；
- 链命名按 piao：0→杠开（杠上花），1→财飘，2→双财飘，3→三财飘；倍率恒 2^count；
- 4个白板：手牌白 + piao 白 == 4 → ×2；
- 爆头：摸牌前 13 张任意摸皆胡 → ×2（正好 4 张白板形态除外，见 hu.is_baotou）；
- 结算：庄胡三家各付 base×番×8；闲胡 庄付 ×8、闲 ×1；
- detail 顺序：[分支, 链名?, 4个白板?, 爆头?]。

已知口径差异（KNOWN-DELTA）沿用 tools/align_fan_calc.py 清单，此处不保证一致。
"""
from __future__ import annotations

from .hu import is_baotou, is_win
from .tiles import counts_of

# piao 命名的实际键：piao==0 → 杠开（若 count>0）；piao>=1 → 财飘家族
PIAO_NAMES = {0: "杠开", 1: "财飘", 2: "双财飘", 3: "三财飘"}


def _qidui_groups(counts):
    """七对路径的四张组数：实体 4 张每组 1 + 白×4 算 1 组。"""
    n = sum(1 for c in counts[:33] if c == 4)
    if counts[33] == 4:
        n += 1
    return n


def branch_of(hand14, exposed_melds=0):
    """分支识别：无副露且可七对 → 七对家族（含组数）；否则平胡。
    返回 (倍率, detail名)。hand14 = 暗牌计数形态（含摸牌），张数 14-3e。"""
    counts = counts_of(hand14)
    real = list(counts[:33])
    jokers = counts[33]
    if exposed_melds == 0:
        singles = sum(1 for i in range(33) if real[i] % 2 == 1)
        if singles <= jokers and (jokers - singles) % 2 == 0:
            n = _qidui_groups(counts)
            return 2 ** (n + 1), ("七对" if n == 0 else "豪华七对×%d" % n)
    return 1, "平胡"


def calc(hand_pre, draw, chain=None, base=1, exposed_melds=0, gangs=0):
    """本地 fan-calc 等价实现（支持副露/杠）。

    hand_pre = 摸牌前暗牌（3(4-e)+1-g 张）；draw 恰 1 张；
    e = 已亮面子数；g = 其中杠组数。chain: {"count", "piao"}。
    """
    from .tiles import validate_hand
    validate_hand(hand_pre)
    if not isinstance(draw, str):
        raise ValueError("draw 必须是单张牌码")
    e = int(exposed_melds or 0)
    g = int(gangs or 0)
    if not (0 <= e <= 4 and 0 <= g <= e):
        raise ValueError("副露/杠数非法: e=%d g=%d" % (e, g))
    need_pre = 3 * (4 - e) + 1 - g
    if len(hand_pre) != need_pre:
        raise ValueError("副露 %d 组（杠 %d）时摸牌前暗牌须 %d 张，实际 %d" % (
            e, g, need_pre, len(hand_pre)))
    hand14 = hand_pre + [draw]
    chain = chain or {"count": 0, "piao": 0}
    count = int(chain.get("count") or 0)
    piao = int(chain.get("piao") or 0)
    if not (0 <= count <= 6 and 0 <= piao <= count):
        raise ValueError("chain 非法: %r" % (chain,))

    hu = is_win(hand14, exposed_melds=e, gangs=g)
    if not hu:
        return {"hu": False, "baotou": False, "fan": 0, "detail": None}

    baotou = is_baotou(hand_pre, exposed_melds=e, gangs=g)
    branch, branch_name = branch_of(hand14, exposed_melds=e)

    detail = [branch_name]
    fan = branch
    if count > 0:
        fan *= 2 ** count
        detail.append(PIAO_NAMES.get(piao, "杠开"))
    whites_hand = hand14.count("白")
    if whites_hand + piao == 4:
        fan *= 2
        detail.append("4个白板")
    if baotou:
        fan *= 2
        detail.append("爆头")

    mult = base * fan
    return {
        "hu": True,
        "baotou": baotou,
        "fan": fan,
        "detail": detail,
        "scores": {
            "dealer_hu":    {"win": mult * 8 * 3, "lose": [mult * 8] * 3},
            "nondealer_hu": {"win": mult * 8 + mult * 2, "lose": [mult * 8, mult, mult]},
        },
    }
