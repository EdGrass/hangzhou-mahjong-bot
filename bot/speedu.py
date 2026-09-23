# -*- coding: utf-8 -*-
"""SpeedU —— C007 修正版：K1 保留、K2 撤回（SpeedE + 一步有效牌 tie）。

SpeedK（K1+K2）经真机窗口证据复核后拆分：K1〔同向听一步有效牌 tie〕保留下来
正是本类的目标 —— SpeedU = SpeedE + K1，弃牌效率面与 SpeedK 同；而 K2〔副露
ukeire 判据〕被撤回，因 W2 窗口证据显示财神短局里额外副露呈负向（见
docs/iter/reports/ 待 W2 裁决卡）。故窗口（response_*）与副露判据一律不覆盖，
完全继承 SpeedE/SpeedCore 原逻辑（after<before 才副露、已听不碰）…… 此处仅弃
牌效率与 SpeedE 分化。

- 弃牌：主键 exact_shanten；同向听次键用〔一步有效牌〕——s==0 比 waits 数、
  s>=1 比 effective_tiles(rem)；仍在最小向听组内付 ukeire 二次成本；末键孤张
  字牌优先/保留刚摸。实现 = 复用 bot/speedk.K1（speedk._best_discard_k），其
  签名/语义已被 speedk 单测钉死，故不复制、不外挂 K2。
- 副露/窗口：不覆盖任何 K2 逻辑，decide 除弃牌支外照抄 SpeedE（含 super() 走
  SpeedCore 原判据）。
`_best_discard_u` 为纯函数可单测；SpeedU.decide 仅替换本回合弃牌、窗口交父类。
"""
from __future__ import annotations

from mahjong.hu import is_win  # noqa: F401

from .model import my_turn
from .speed import _best_discard
from .speede import SpeedE
from .speedk import _best_discard_k as _best_discard_u  # K1 纯函数（签名/语义已评审钉死）


class SpeedU(SpeedE):
    """SpeedE + (K1 一步有效牌 tie)。窗口与副露判据=SpeedE（K2 已撤回）。

    与 SpeedK 的行为差仅一句：SpeedK 还叠加 K2 副露激进/已听碰比较，SpeedU 全部
    交还 SpeedE/SpeedCore 原窗口判据，故响应级行为与 SpeedE 逐帧一致。
    """

    def __init__(self, name="speedu"):
        super().__init__(name)

    def decide(self, view):
        # 副露/窗口 100% 继承 SpeedE/SpeedCore（K2 不覆盖；super().decide 即 E 原判据）
        if not my_turn(view):
            return super().decide(view)
        # ---- 本人回合：胡优先 / 抓打圈继承 SpeedE ----
        hand = list(view["my_hand"])
        melds = view.get("melds") or []
        exposed = len(melds)
        gangs = sum(1 for m in melds if m["type"] == "gang")
        drawn = view.get("drawn_tile")
        try:
            hu = is_win(hand, exposed_melds=exposed, gangs=gangs)
        except ValueError:
            hu = False
        if hu and drawn:
            return {"action": "hu", "tile": ""}
        if hand:
            if view.get("god", {}).get("catch_play") and drawn:
                return {"action": "discard", "tile": drawn}
            try:
                tile = _best_discard_u(hand, drawn, exposed, gangs)
            except ValueError:
                tile = _best_discard(hand, drawn, exposed, gangs)
            return {"action": "discard", "tile": tile}
        return None
