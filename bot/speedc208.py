# -*- coding: utf-8 -*-
"""SpeedC208 = c152 + **可胡点上的"追加弃胡"**（用爆头值函数 V 判断，C036 之外的新路径）。

依据 R563：top32 的**取胡率比我们低 4.2pp**（81.1% vs 85.3%），而**爆头占胡高 4.6pp**
⇒ 他们在 C036 触发集之外**还多弃胡**。本候选就是补这条路径：
  - 先走原有 C036（`_best_giveup`）；它给了弃牌就照它；
  - 否则（C036 说"该胡"）再看：若**最优弃牌后的状态** `V ≥ 阈值`，且**当前胡的番不大**，则**也弃胡**；
  - 阈值由 `C208_VT` 控制，**保守起步**（目标：追加弃胡比例 2~5%）。
"""
from __future__ import annotations
import os
from mahjong.hu import is_win, is_baotou
from .speedc152 import SpeedC152
from .baotou_value import value as _V, load as _load_V

class SpeedC208(SpeedC152):
    # ★ 阈值**调用时**读环境变量（类体里求值会导致标定脚本改了没用 —— R564）
    @property
    def VT(self):
        return float(os.environ.get("C208_VT", "0.35"))
    MAX_FAN_NOW = int(os.environ.get("C208_MAXFAN", "1"))

    def __init__(self, name="speedc208"):
        super().__init__(name)
        self._vw = None
        try:
            _load_V()          # ★ 预热：把 torch 导入 + 模型加载放到"开局前"，否则第一次决策要付几秒（并发门禁实测 5/1000 超 3s、max 9.0s）
        except Exception:
            pass

    def decide(self, view):
        self._vw = view
        return super().decide(view)

    def _best_giveup(self, hand, exposed, gangs, fan_now, chain):
        d = super()._best_giveup(hand, exposed, gangs, fan_now, chain)
        if d is not None:
            return d
        vw = self._vw or {}
        if fan_now is None or fan_now > self.MAX_FAN_NOW:
            return None
        river = vw.get("river") or []
        all_melds = vw.get("all_melds") or []
        god = vw.get("god") or {}
        # ★ 只对**一张**候选算 V（默认=最优进张那张；可用 C208_MODE=all 回到全枚举）——
        #   全枚举在 M=10 并发下超 3s（5~6/1000，max 8.8s），而本臂只需要"我们本来要打哪张、它值不值"。
        mode = os.environ.get("C208_MODE", "one")
        # ★ 硬时限：超时就直接取胡（不做追加弃胡）—— 把尾延迟钉死，避免 M=10 并发下超 3s
        import time as _t
        deadline = _t.monotonic() + float(os.environ.get("C208_MS", "120")) / 1000.0
        try:
            from .speedc135 import _best_discard_realukeire
            first = _best_discard_realukeire(hand, None, exposed, gangs, god_meld=self.GOD_MELD, view=vw)
        except Exception:
            first = None
        if _t.monotonic() >= deadline:
            return None
        cand = sorted(set(hand)) if mode == "all" else ([first] if first else [])
        best_d, best_v = None, 0.0
        for d2 in cand:
            if d2 is None: continue
            aft = list(hand)
            aft.remove(d2)
            if len(aft) != 13 - 3 * exposed - gangs:
                continue
            try:
                v = _V(aft, exposed, gangs, river, all_melds, god, 0)
            except Exception:
                v = 0.0
            if v > best_v:
                best_d, best_v = d2, v
            if mode != "all":
                break
        if best_d is not None and best_v >= self.VT:
            return best_d
        return None



