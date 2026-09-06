"""SpeedX1 —— 自迭代候选 C001（实验名，未晋级不得作竞技默认）。

假设（docs/iter/queue.md C001，来源 PROJECT.md §7.1 / 复盘差异#2）：
正式赛 TOP 玩家在同向听 tie 里倾向【打刚摸的新张】，而我们（SpeedE）倾向
【保留刚摸的牌】。若信息/牌河因素使"弃新张"更优，则 tie 内弃新张应带来场分收益。

与 SpeedE 的唯一差异：弃牌 tie-break 末键翻转——
  SpeedE : (s, -wcnt, 孤字优先, 保留刚摸)
  SpeedX1: (s, -wcnt, 孤字优先, 弃刚摸优先)   # 仅在 (s,wcnt,孤字) 全 tie 时生效
其余（可胡即胡/抓打圈强制打刚摸/副露判据/不暗杠）完全继承 SpeedE/SpeedCore。

判定路径：Arena 同桌面 speedx1x2+speedEx2（tools/ab_gate.py，晋级线 δ≥2/场，
CI 排除 0）；L1 WIN 才送 L2 真机同桌。裁决见 docs/iter/reports/C001.md。
"""
from __future__ import annotations

from mahjong.hu import is_win
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn
from .speed import HONOR, SpeedCore, _best_discard  # noqa: F401
from .speede import SpeedE


def _best_discard_newfirst(hand, drawn, exposed, gangs):
    """弃牌：向听最小 → 听牌等待最大 → 孤张字牌优先 → 【弃刚摸优先】。"""
    best_tile, best_key = None, None
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                          exposed_melds=exposed, gangs=gangs)
        wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs)) if s == 0 \
            else 0
        is_honor = d in HONOR
        # 末键与 SpeedE 相反：刚摸的牌最后才考虑（全 tie 时弃新张）
        key = (s, -wcnt, 0 if is_honor else 1, 0 if d == drawn else -1)
        if best_key is None or key < best_key:
            best_key, best_tile = key, d
    return best_tile if best_tile is not None else hand[0]


class SpeedX1(SpeedE):
    """候选 C001：SpeedE + tie 内弃刚摸优先（见模块 docstring）。"""

    def __init__(self, name="speedx1"):
        super().__init__(name)

    def decide(self, view):
        if my_turn(view):
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
                    tile = _best_discard_newfirst(hand, drawn, exposed, gangs)
                except ValueError:
                    tile = _best_discard(hand, drawn, exposed, gangs)
                return {"action": "discard", "tile": tile}
            return None
        return super().decide(view)
