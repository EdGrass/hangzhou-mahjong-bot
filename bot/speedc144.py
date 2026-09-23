# -*- coding: utf-8 -*-
"""SpeedC144 —— **明杠门控**（`speedtugc` 的单变量候选）：第 4 张是死牌时把明杠收下来。

背景（2026-09-16 真机实测）：
1) **真机明杠会补牌**：`var/replays/*` 全部 603/603 个 `gang` 事件后面紧跟**同一座位的
   `tile_drawn`（`gang_replenish: true`）** ⇒ 明杠 = 把手里的死牌换成**一次额外摸牌**。
   （注意：`mahjong/sim.py` 写的是「直杠不补牌」——**这是 sim 的口径错误**，也是本族
   一直没走这条路的原因之一。）
2) ⚠ **更正（2026-09-16 22:50）**：此处原写「真机不限制晚盘杠」，**是错的**——
   指南 §1.1 明确「最后 10 墩（20 张）保留不摸；**最后 10 墩之内禁止杠牌**」。
   当时用「杠事件的进度 p50=0.67 / p90=0.96 / max=1.00」推断"不限杠"，但那个分母把**保留区**也算进去了，
   口径不成立。现在 `_want_ming_gang` 与自杠共用同一道**河长守卫**（`SELF_GANG_MAX_RIVER`，保守起见到线不杠）。
3) **我们几乎不用**：`杠/轮` 我方 **0.010** vs 全场 **0.024–0.077**；`杠开` 占胡牌
   我方 **0.2%** vs 全场 0.9–2.3%。
4) **机会不小**：最近 200 场 dec 记录里，我方遇到「手上有 3 张、别家打出第 4 张」的窗口 **58 次**
   （≈ **2.9 次/房**），实际只杠了 **5 次**（pass 45 / 碰 8）——因为这里的门控是
   `want_claim_strict_meld`（要求向听**严格下降**），而**杠根本不可能改变向听** ⇒ 结构与「永远拒绝」等价。

本候选 = 把 `response_peng` 窗口里的**明杠**判据换成**按路线**判断（与 `_maybe_gang` 同一套逻辑）：
  - 抓打圈（`god.catch_play`）内别家禁明杠 → 拒绝（指南）；
  - 已有副露 ⇒ 七对已不可能 ⇒ **收**（第 4 张本来是死牌，杠 = 白赚一张）；
  - 门清 ⇒ 比较一般形/七对向听：已听牌（一般形 0 向听）或七对明显更差 ⇒ **收**；否则保留七对路线。
**唯一代价**是七对路线，其余（胡/出牌/碰/吃判据）100% 继承 `speedtugc`。
"""
from __future__ import annotations

from mahjong.shanten_exact import _qidui_shanten
from mahjong.shanten_exact import shanten as exact_shanten
from mahjong.tiles import counts_of

from .speedtugc import SpeedTUGC


class SpeedC144(SpeedTUGC):
    def __init__(self, name="speedc144"):
        super().__init__(name)

    def _want_ming_gang(self, view):
        """明杠是否收下（纯函数，可单测）。"""
        offer = view.get("offer_tile")
        if not offer or offer == "白":
            return False
        god = view.get("god") or {}
        if god.get("catch_play"):                 # 抓打圈内别家禁明杠
            return False
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        e = len(melds)
        g = sum(1 for m in melds if isinstance(m, dict) and m.get("type") == "gang")
        if hand.count(offer) < 3:
            return False
        # 指南 §1.1：「最后 10 墩（20 张）保留不摸；**最后 10 墩之内禁止杠牌**」。
        # 快照没有牌墙余量 ⇒ 用「本局公开弃牌河长度」当摸牌数的廉价代理（与自杠的
        # SELF_GANG_MAX_RIVER 同一口径，宁可保守：到线就不杠，避免 409 丢机会）。
        _rl = view.get("river_len")
        if _rl is None:
            _rl = len(view.get("river") or [])
        try:
            if int(_rl) >= int(self.SELF_GANG_MAX_RIVER):
                return False
        except Exception:
            pass
        if e > 0:                                 # 七对已不可能 ⇒ 死牌换一摸
            return True
        try:
            # 窗口里手牌是 13 张（未含被吃碰的牌）⇒ 先并进 offer 得到 14 张，
            # 再按「留哪 13 张」评估路线（与 _maybe_gang 的 14 张口径一致）
            h14 = list(hand) + [offer]
            g_best, q_best = 99, 99
            for d in sorted(set(h14)):
                rem = list(h14)
                rem.remove(d)
                gg = exact_shanten(rem, qidui=False, exposed_melds=0, gangs=0)
                qq = _qidui_shanten(counts_of(list(rem)))
                g_best = min(g_best, gg)
                q_best = min(q_best, qq)
        except Exception:
            return False
        return g_best == 0 or q_best > g_best + 1

    def _want_claim(self, view, kind, pair=None):
        if kind == "gang_ming" and self._want_ming_gang(view):
            return True
        return super()._want_claim(view, kind, pair)
