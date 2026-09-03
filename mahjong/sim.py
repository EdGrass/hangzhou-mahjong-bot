"""本地模拟器 v1（对局推进）—— mahjong 引擎的可执行环境（Arena/自对弈公共内核）。

v1 范围（蓝图 M1 验收门）：
- 发牌/轮流摸打/自摸胡（客户端自判、可弃胡）/牌墙留 10 墩（20 张）/
  流局（庄家连庄）/番型结算（mahjong.fan）/局数 N 后场次结束；
- 动作合法性自检：策略提交非法动作 → 记 violation 并按「打刚摸的牌」兜底；
- 尚未实现：吃/碰/杠窗口、抓打圈、飘/杠动作链（piao>0）。窗口与链在 v2 加入
  （策略接口不变，仅引擎侧扩展阶段）。

快照视图与服务器协议层同构（bot/model.snap_view 的键），同一 Strategy 实现
可在 本地模拟 与 真机协议 间复用。
"""
from __future__ import annotations

import random

from .fan import calc as calc_fan
from .hu import is_baotou, is_win
from .tiles import GOD_TILE

WALL_RESERVE = 20                            # 最后 10 墩（20 张）保留不摸
ALL_CODES = ["%d%s" % (n, s) for s in "wbt" for n in range(1, 10)] + \
            ["东", "南", "西", "北", "中", "发", GOD_TILE]
DECK = ALL_CODES * 4                         # 136 张


def _minus(hand, tile):
    """移除手牌中的一张 tile（只移一张，即使同码多张）。"""
    out = list(hand)
    out.remove(tile)
    return out


def make_view(seat, phase, turn, hand14, drawn=None, scores=None):
    """构建与协议层 snap_view 同构的本人视角（模拟器与真机共用策略）。"""
    god = {"baotou": False, "chain_count": 0, "catch_play": False}
    if phase == "draw" and drawn is not None and turn == seat:
        god["baotou"] = is_baotou(_minus(hand14, drawn))
    return {
        "seat": seat, "phase": phase, "turn": turn,
        "responding_seats": [], "drawn_tile": drawn,
        "my_hand": list(hand14), "god": god, "scores": scores,
    }


class SimGame:
    """一场（rounds 局）本地对局。strategies: 4 个带 decide(view)->action 的对象。"""

    def __init__(self, strategies, rounds=1, base=1, seed=0):
        if len(strategies) != 4:
            raise ValueError("需要恰好 4 个策略（4 座），实际 %d" % len(strategies))
        self.strategies = list(strategies)
        self.rounds = rounds
        self.base = base
        self.rng = random.Random(seed)
        self.totals = [0, 0, 0, 0]
        self.stats = {"rounds_played": 0, "hu_count": [0] * 4,
                      "fan_total": [0] * 4, "draw_count": 0,
                      "violations": 0, "fallbacks": 0}
        self.hands = [[] for _ in range(4)]
        self.wall = []

    # -- 对局 -----------------------------------------------------------------
    def _deal_round(self):
        wall = list(DECK)
        self.rng.shuffle(wall)
        self.hands = [sorted(wall[i * 13:(i + 1) * 13]) for i in range(4)]
        del wall[:52]
        self.wall = wall

    def _pay_hu(self, winner, dealer, fan):
        """按结算表把三家付款落到 totals（庄/闲决定谁付多少）。"""
        mult = self.base * fan
        if winner == dealer:
            pay = [mult * 8] * 3              # 三家闲家各付 ×8
            others = [s for s in range(4) if s != winner]
        else:
            pay = [mult * 8] + [mult] * 2     # 庄付 ×8，闲 ×1
            order = [dealer] + [s for s in range(4) if s not in (winner, dealer)]
            others = order
        for seat, amt in zip(others, pay):
            self.totals[seat] -= amt
            self.totals[winner] += amt

    def _play_round(self, dealer):
        self._deal_round()
        seat = dealer
        while True:
            if not self.wall:                 # 无牌可摸 → 流局（庄家连庄）
                self.stats["draw_count"] += 1
                return None
            tcode = self.wall.pop(0)
            hand = self.hands[seat]
            hand.append(tcode)
            hand.sort()
            view = make_view(seat, "draw", seat, hand, drawn=tcode)
            act = self._decide(seat, view)
            if act is None:                   # 兜底：打刚摸的牌
                act = {"action": "discard", "tile": tcode}
                self.stats["fallbacks"] += 1
            action = act.get("action")
            if action == "hu":
                if not is_win(hand):
                    self.stats["violations"] += 1
                    hand.remove(tcode)        # 非法胡 → 打出刚摸的
                else:
                    pre13 = _minus(hand, tcode)
                    fan = calc_fan(pre13, tcode,
                                   {"count": 0, "piao": 0}, base=self.base)["fan"]
                    self._pay_hu(seat, dealer, fan)
                    self.stats["hu_count"][seat] += 1
                    self.stats["fan_total"][seat] += fan
                    return seat
            elif action == "discard":
                tile = act.get("tile", "")
                if tile not in hand:
                    self.stats["violations"] += 1
                    tile = tcode
                hand.remove(tile)
            else:                             # 其他动作 v1 未实现 → 违规
                self.stats["violations"] += 1
                if tcode in hand:
                    hand.remove(tcode)
            seat = (seat + 1) % 4

    def _decide(self, seat, view):
        try:
            return self.strategies[seat].decide(view)
        except Exception:                     # 策略异常不得卡死模拟器
            self.stats["violations"] += 1
            return None

    def run(self):
        dealer = 0
        for _ in range(self.rounds):
            winner = self._play_round(dealer)
            self.stats["rounds_played"] += 1
            if winner is None:                # 流局：庄家连庄
                continue
            if winner != dealer:              # 闲家胡：胜者上庄（近似规则）
                dealer = winner
        return {"totals": list(self.totals), "stats": dict(self.stats)}
