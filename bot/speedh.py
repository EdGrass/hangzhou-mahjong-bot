"""SpeedH —— 杠/链 EV 候选（v1：补杠/暗杠安全门控纯函数）。

设计：docs/superpowers/specs/2026-09-07-window-ab-base-strategy-design.md
P0 探针（2026-09-07，docs/iter/reports/P0-probe.md）：
- 服务器接受 draw 回合暗杠，但 game.py 长度模型需适配杠后补牌（协议层
  子任务 T5b；本模块的暗杠判据在该适配落地后按实测口径校准）；
- 过胡合法（v2 打点候选前提成立）。

API 约定：safe_gang 的 hand 为【不含刚摸】的核心手牌，长度必须恰为
13-3e-g（e=副露面子数含杠、g=杠数）；任何长度/引擎异常一律 None→False
（不杠最安全），不做裁牌改写（对齐 bot/speed.py 的长度纪律）。
v1 门控：补杠/暗杠后形态向听 ≤ 杠前向听 + GANG_TOL（补 1 张的保守容忍）；
多 quad 时只判 sorted 序首个候选（其余留待下一决策），docstring 已声明。
sim 无法建模杠后补牌（sim v2 不补牌）→ 强度判据只信真机。
"""
from __future__ import annotations

from mahjong.shanten_exact import shanten as exact_shanten

GOD = "白"                 # 财神=白板，禁杠
GANG_TOL = 2               # 暗杠补 1 张语义的保守容忍（T5b 实测后校准）


def _shanten(hand, exposed, gangs):
    """严格长度口径的向听：长度≠13-3e-g 或引擎异常 → None（调用方按不安全处理）。"""
    if len(hand) != 13 - 3 * exposed - gangs:
        return None
    try:
        return exact_shanten(hand, qidui=(exposed == 0 and gangs == 0),
                             exposed_melds=exposed, gangs=gangs)
    except ValueError:
        return None


def within_tolerance(before, after, tol=GANG_TOL):
    """杠后向听是否在容忍内（纯数值比较，独立可测）。"""
    if before is None or after is None:
        return False
    return after <= before + tol


def safe_gang(hand, exposed, gangs, meld_4th=None, tol=GANG_TOL):
    """杠是否结构安全（保守 v1 门控）。

    hand：不含刚摸的核心手牌，长度须恰为 13-3e-g（长度不符→False）；
    meld_4th：补杠目标碰牌牌面（该牌应在 melds 外且手中恰有第 4 张）；
    None 表示暗杠（核心手牌含 4 张同码非白）。
    补杠：移除手中第 4 张后（碰组原位升杠：e 不变、g+1）向听在容忍内；
    暗杠：移除 4 张后（e+1、g+1）向听在容忍内；多 quad 只判 sorted 序首个。
    白板两种杠恒 False。
    """
    hand = list(hand)
    if meld_4th == GOD:
        return False
    if meld_4th is not None:
        if hand.count(meld_4th) < 1:
            return False
        before = _shanten(hand, exposed, gangs)
        rem = list(hand)
        rem.remove(meld_4th)
        after = _shanten(rem, exposed, gangs + 1)     # 碰升杠：e 不变
        return within_tolerance(before, after, tol)
    quads = [t for t in sorted(set(hand)) if t != GOD and hand.count(t) == 4]
    if not quads:
        return False
    before = _shanten(hand, exposed, gangs)
    rem = [x for x in hand if x != quads[0]]
    after = _shanten(rem, exposed + 1, gangs + 1)     # 暗杠：新面子 + 杠
    return within_tolerance(before, after, tol)


def bugang_value(chain):
    """杠的 chain 增量结构价值：服务器每级 chain ×2 番（占位 v1：按 ×2 表达）。"""
    return float(2 ** max(0, int(chain)))
