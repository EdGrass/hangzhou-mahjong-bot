# -*- coding: utf-8 -*-
"""C036/C037 SpeedTUG —— SpeedTU + 弃胡换爆头（EV 版）。

来源（2026-09-10 真机复盘实证，544 次爆头到达全量统计）：
- 爆头到达路径：吃碰后被迫弃牌 52.4% / **摸牌后弃牌 47.6%**；
- 其中「摸牌后弃牌」的 **248/259 弃牌前 14 张本来就是胡牌** →
  **顶级 bot 近一半的爆头是主动弃胡换来的**；我方 37/37 全来自吃碰、弃胡 0 次；
- 服务端 fan-calc 权威复核 28 个门清样本：**28/28 认定可胡，多数 fan=1（平胡）**。

决策（与 SpeedTU 的唯一差异）：已可胡时，若存在一张弃牌能让 13 张变成爆头形，
且 **P_conv × fan_baotou > fan_now**，则弃胡改打该张；否则照常胡。

- `P_conv = 0.71`：真机实测「弃胡后本局仍由我们胡回」的转化率（7 样本 5 中）；
- `fan_baotou`：该爆头形下一摸胡的番（4 面子形=平胡×爆头=×2；6 对+白形=七对×爆头=×4），
  用代表性摸牌算得；链（杠/财飘）沿用当前 chain。

sim 对照（3 seed × 192 局）：
  speedTU 听牌 66.5%/胡 27.4%/爆头 3.8%/fan 1.139/得分代理 0.312；
  SpeedTUG(fan<=1)                       爆头 8.3%/fan 1.282/代理 0.340；
  **SpeedTUG(EV)                          爆头 8.7%/fan 1.308/代理 0.347**；违规 0。
真机：房 a_d4f52cfde98e rank2 +56；两房合并真机弃胡 7 次、5 次（71%）胡回。
"""
from __future__ import annotations

from mahjong.fan import calc as calc_fan
from mahjong.hu import is_baotou, is_win
from mahjong.tiles import TILE_IDS

from .model import my_turn, window_pending
from .speedtu import SpeedTU

P_CONV_DEFAULT = 0.71          # 真机实测转化率（弃胡后仍由我们胡回）


class SpeedTUG(SpeedTU):
    def __init__(self, name="speedTUG", p_conv=P_CONV_DEFAULT, min_fan=None):
        super().__init__(name)
        self.p_conv = float(p_conv)
        # min_fan 保留为「仅当番<=N 才考虑弃胡」的兼容开关；None=纯 EV 判据
        self.min_fan = None if min_fan is None else int(min_fan)

    def _baotou_fan(self, hand13, exposed, gangs, chain):
        """该爆头形下一摸胡的番（取代表性摸牌；形状决定分支，故恒定）。"""
        for t in sorted(TILE_IDS):
            try:
                r = calc_fan(list(hand13), t, chain, base=1,
                             exposed_melds=exposed, gangs=gangs)
            except Exception:
                continue
            if r.get("hu"):
                return r.get("fan")
        return None

    def _best_giveup(self, hand, exposed, gangs, fan_now, chain):
        """返回 (弃牌, 该弃法下一摸的番)；不划算则 None。"""
        best, best_fan = None, None
        for d in sorted(set(hand)):
            after = list(hand)
            after.remove(d)
            try:
                if not is_baotou(after, allow_qidui=(exposed == 0 and gangs == 0),
                                 exposed_melds=exposed, gangs=gangs):
                    continue
            except ValueError:
                continue
            fb = self._baotou_fan(after, exposed, gangs, chain)
            if fb is None:
                continue
            if best_fan is None or fb > best_fan:
                best, best_fan = d, fb
        if best is None:
            return None
        if self.p_conv * best_fan > fan_now:
            return best
        return None

    def decide(self, view):
        if my_turn(view) and not (window_pending(view) and view.get("offer_tile")):
            hand = list(view["my_hand"])
            melds = view.get("melds") or []
            exposed = len(melds)
            gangs = sum(1 for m in melds if m["type"] == "gang")
            drawn = view.get("drawn_tile")
            if drawn and len(hand) == 14 - 3 * exposed - gangs:
                try:
                    win_now = is_win(hand, exposed_melds=exposed, gangs=gangs)
                except ValueError:
                    win_now = False
                if win_now:
                    god = view.get("god") or {}
                    chain = {"count": int(god.get("chain_count") or 0),
                             "piao": int(god.get("piao_count") or 0)}
                    fan_now = None
                    try:
                        pre = list(hand)
                        pre.remove(drawn)
                        r = calc_fan(pre, drawn, chain, base=1,
                                     exposed_melds=exposed, gangs=gangs)
                        if r.get("hu"):
                            fan_now = r.get("fan")
                    except Exception:
                        fan_now = None
                    if fan_now is not None and \
                            (self.min_fan is None or fan_now <= self.min_fan):
                        d = self._best_giveup(hand, exposed, gangs, fan_now, chain)
                        if d is not None:
                            return {"action": "discard", "tile": d}
                    return {"action": "hu", "tile": ""}
        return super().decide(view)
