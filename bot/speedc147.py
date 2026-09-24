# -*- coding: utf-8 -*-
"""SpeedC147 —— **条件组合臂**：C073w4（BC 弃牌模型）+ C146 的四个机制钩子。

**什么时候用**：只有当战役 #1（`speedtugc` vs `speedc073w4`）判定 **采用 c073w4** 时，
下一个战役才该打这个臂（`speedc073w4` vs `speedc147`）——否则基线仍是 `speedtugc`，
应该直接上 `speedc146`（不含 BC 模型）。这样"新基线 + 新机制"一次到位，
避免先采用 c073w4 再花一个战役把机制补上。

**为什么能组合**：`C067Policy.decide()` 只覆盖**弃牌选择**，非弃牌路径一律 `super().decide(view)`；
而 c146 的四个机制都挂在 `SpeedTUGC.decide()` 调用的钩子上：
  - `_want_claim` → C144（明杠按路线）→ C136（吃碰质量感知）
  - `_best_giveup` → C141（弃白=财飘时链 +1 再估番）
  - `SELF_GANG=True` → C134 的暗杠/补杠开关（走 `SpeedTUGC._maybe_gang`）
MRO = SpeedC147 → C067Policy → … → SpeedC146 → C144 → C136 → C141 → SpeedTUGC
⇒ `decide` 取 C067 的弃牌模型、`super()` 落回 SpeedTUGC.decide（含全部机制钩子）。
"""
from __future__ import annotations

import os

from mahjong.hu import is_win

from .model import my_turn, window_pending
from .speedc067 import C067Policy
from .speedc146 import SpeedC146

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = os.path.join(ROOT, "var", "c073_orig_w4_net.pt")


class SpeedC147(C067Policy, SpeedC146):
    def __init__(self, name="speedc147", model_path=None, margin=0.0,
                 max_candidates=4, lo=0, hi=2, cand_order="pref"):
        super().__init__(name=name, model_path=model_path or DEFAULT_MODEL,
                         margin=margin, max_candidates=max_candidates,
                         cand_order=cand_order)
        self.shanten_range = (int(lo), int(hi))

    def decide(self, view):
        """⚠ 组合必需：`C067Policy.decide()` 覆盖整条弃牌路径、**不查 `_maybe_gang`**，
        会在模型接管弃牌时把 C134 的暗杠/补杠机制**静默旁路**（实测 1/600 个决策
        c146 会杠、c147 却出牌）。这里把「可胡」与「可自杠」两段补回来，再交给模型选弃牌。
        """
        if not (my_turn(view) and not (window_pending(view) and view.get("offer_tile"))):
            return super().decide(view)
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        exposed = len(melds)
        gangs = sum(1 for m in melds
                    if isinstance(m, dict) and m.get("type") == "gang")
        drawn = view.get("drawn_tile")
        if len(hand) != 14 - 3 * exposed - gangs:
            return super().decide(view)
        try:
            if is_win(hand, exposed_melds=exposed, gangs=gangs) and drawn:
                return super().decide(view)      # 走 C036/C141 的弃胡判据
        except ValueError:
            pass
        g = self._maybe_gang(hand, exposed, gangs, melds, view.get("turn"),
                             river_len=view.get("river_len"), god=view.get("god"),
                             seat=view.get("seat", -1))
        if g is not None:
            return g
        return super().decide(view)
