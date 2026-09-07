"""SpeedH —— 杠/链 EV 候选（v1：补杠/暗杠安全门控纯函数）。

设计：docs/superpowers/specs/2026-09-07-window-ab-base-strategy-design.md
P0 探针（2026-09-07）：服务器接受 draw 回合暗杠，但 game.py 长度模型需适配
杠后补牌（协议层子任务 T5b）。本模块不依赖协议层，只做结构安全判据（离线可测）。

向听底盘语义：exact_shanten 要求 hand 长度恰为 13-3e-g，否则抛 ValueError。
本模块 v1 的 hand 参数按「碰/暗杠决策时全盘在手的 13 张竞争牌」传入（真机原始
长度口径随 T5b 校准）；在做结构比较前，把手牌缩减到 shanten 底盘长度 13-3e-g
再判向听，避免对 fixture/真机边缘长度直接抱错。长度不足（结构性残破）一律视为
不安全（返回 False）——保守不杠。强度判据只信真机；本模块不产出 EV 数值。
GOD/白 语义：白板不可作杠（规则硬禁）。
"""
from __future__ import annotations

from mahjong.shanten_exact import shanten as exact_shanten

GOD = "白"


def _s(hand, exposed, gangs):
    """长度容错的 shanten：先裁到引擎底盘 13-3e-g 张再判；过短→99（不安全）。"""
    need = 13 - 3 * exposed - gangs
    if len(hand) < need:
        return 99                       # 真机边缘/结构性残破 → 视为不安全
    core = sorted(hand)[-need:]         # v1 启发：保留满 13 竞争组合的底盘张
    try:
        return exact_shanten(core, qidui=(exposed == 0 and gangs == 0),
                             exposed_melds=exposed, gangs=gangs)
    except ValueError:
        return 99                       # 引擎异常（真机边缘）→ 视为不安全


def safe_gang(hand, drawn, exposed, gangs, meld_4th=None):
    """杠是否结构安全（保守 v1 门控）。

    meld_4th：补杠目标碰牌牌面；None=暗杠（手牌 4 张同码非白）。
    补杠：手中确有第 4 张，且移除并入已有碰组后（面子不变、g+1）向听 ≤ 杠前
    （sim/meldtrack 口径：补杠不改面子数）。
    暗杠：4 张同码（非白）在手，自槓占独立面子（e+1,g+1），去掉 4 张后形态
    不劣于当前 +2 容忍（杠后补 1 张语义 T5b 真机校准）。任何引擎异常一律 False。
    白板杠恒 False。
    """
    if meld_4th == GOD:
        return False
    hand = list(hand)
    if meld_4th is not None:                     # ---- 补杠 ----
        if hand.count(meld_4th) < 1:             # 手中无第 4 张 → 拒绝
            return False
        before = _s(hand, exposed, gangs)
        if before == 99:
            return False
        rem = list(hand)
        rem.remove(meld_4th)                     # 第 4 张并入既有碰组(hit peng) → 面子不变、g+1
        after = _s(rem, exposed, gangs + 1)
        return after <= before
    quads = [t for t in sorted(set(hand))        # ---- 暗杠 ----
             if t != GOD and hand.count(t) == 4]
    if not quads:
        return False                             # 无 4 张同码 → 拒绝
    before = _s(hand, exposed, gangs)
    if before == 99:
        return False
    rest = [x for x in hand if x != quads[0]]    # 4 张可视自槓 → 独占一个面子：e+1,g+1
    after = _s(rest, exposed + 1, gangs + 1)
    return after <= before + 2


def bugang_value(chain):
    """chain×2 的结构性正收益占位（v1 恒正；数值化 EV 留 v2）。"""
    return 1.0 + float(chain)
