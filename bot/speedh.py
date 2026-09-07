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

from mahjong.hu import is_win
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn
from .speede import SpeedE

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


def _dark_quad(hand, tol=GANG_TOL):
    """返回暗杠候选 quad 牌面（sorted 序首个、非白、恰 4 张）；无则 None。

    与 safe_gang 的门控对象一致（同 sorted 序），decide 据此提交实际 quad 码。
    """
    for t in sorted(set(hand)):
        if t != GOD and hand.count(t) == 4:
            return t
    return None


def _core_without_drawn(view):
    """从视图核心手牌去掉刚摸牌得“不含刚摸”核心（长度须 13-3e-g）。

    返回 (core, e, g)；形状不一致（drawn 不在手 / 长度异常）→ 返回 (None,...)，
    调用方据此跳过杠分支（对齐 bot/speed.py 的长度纪律，不做裁牌改写）。
    """
    hand = list(view.get("my_hand") or [])
    melds = view.get("melds") or []
    exposed = len(melds)                          # e = 副露面子数（含杠）
    gangs = sum(1 for m in melds if m["type"] == "gang")
    drawn = view.get("drawn_tile")
    if not drawn or drawn not in hand:
        return None, exposed, gangs
    core = list(hand)
    core.remove(drawn)
    if len(core) != 13 - 3 * exposed - gangs:
        return None, exposed, gangs
    return core, exposed, gangs


class SpeedH(SpeedE):
    """杭州麻将自杠（补杠/暗杠）集成策略（v1：SafeGang 门控 + 409 节流）。

    设计：docs/superpowers/specs/2026-09-07-window-ab-base-strategy-design.md
    decide 语义（对齐 bot/speede.SpeedE 分支结构 + bot/speedprobe 观测）：
      0) my_turn 且 drawn_tile：
         a) 可胡即胡优先：整手（含刚摸，张数 14-3e-g）is_win → hu；
         b) god.catch_play（抓打圈）→ 不杠，直接 super()（SpeedE 强制打刚摸）；
         c) 杠决策（P0 实测定向：此回合提交 gang 服务器补牌转新 draw）：
            - 核心手牌 = view.my_hand 去掉 drawn（须恰 13-3e-g，否则跳过杠）；
            - 补杠优先：遍历 melds 中 type=peng，safe_gang(core, meld_4th=碰牌码)
              通过 → 提交 {"action":"gang","tile":<碰码>}；
            - 否则暗杠：safe_gang(core, meld_4th=None) 通过 → 提交 quad tile
              （sorted 序首个非白 quad）；
         d) **指纹节流**：实例记录最近一次实际提交杠时的局面指纹
            fp = (tuple(sorted(整手含刚摸)), exposed, gangs)；若再次进入 decide 且
            fp 与记录相同（= 409 后同局面重建重放）→ 放弃杠（走 SpeedE 弃牌），
            防服务器 409 重建后杠-409 死循环；fp 不同（= 同 (phase,turn) 内新的
            合法局面，如杠后补牌链杠）仍正常尝试杠并更新指纹，不吞跨局面合法杠。

    sim 无法建模杠后补牌（sim v2 不补牌）→ 强度判据交给真机；本类只做结构
    门控与 409 兜底，不触碰弃牌/胡/窗口选择（全继承 SpeedE）。
    """

    def __init__(self, name="speed_h"):
        super().__init__(name)
        self._gang_fp = None         # 最近一次实际提交杠时的局面指纹

    def decide(self, view):
        if not (my_turn(view) and view.get("drawn_tile")):
            return super().decide(view)
        if view.get("phase") != "draw":
            return super().decide(view)

        # (0) 可胡即胡：需在杠决策前判（含刚摸整手），避免胡形被 409 卡死窗口。
        melds = view.get("melds") or []
        exposed = len(melds)
        gangs = sum(1 for m in melds if m["type"] == "gang")
        drawn = view.get("drawn_tile")
        try:
            hu = is_win(view["my_hand"], exposed_melds=exposed, gangs=gangs)
        except ValueError:
            hu = False
        if hu and drawn:
            return {"action": "hu", "tile": ""}

        # (b) 抓打圈：强制打刚摸，不走杠、不过 safe_gang（交 SpeedE 唯一处理）。
        if view.get("god", {}).get("catch_play"):
            return super().decide(view)

        # 指纹节流：同一局面 fp 再次出现且上次恰为杠提交 → 视为 409 重建重放，弃杠。
        # （fp 由整手含刚摸 + 副露/杠数刻画；局面不同（如杠后补牌链杠）照常尝试杠。）
        fp = (tuple(sorted(view["my_hand"])), exposed, gangs)
        if self._gang_fp == fp:
            return super().decide(view)

        # (c) 杠决策，输入核心手牌（不含刚摸）。形状非法（drawn 缺/长度不符）
        #     直接跳过杠分支，交由 SpeedE 弃牌兜底。
        core, e, g = _core_without_drawn(view)
        if core is None:
            return super().decide(view)
        # 补杠优先：碰组升杠
        for m in melds:
            if m.get("type") == "peng" and safe_gang(
                    core, e, g, meld_4th=m.get("tile")):
                self._gang_fp = fp
                return {"action": "gang", "tile": m["tile"]}
        # 否则暗杠
        quad = _dark_quad(core)
        if quad is not None and safe_gang(core, e, g, meld_4th=None):
            self._gang_fp = fp
            return {"action": "gang", "tile": quad}
        return super().decide(view)
