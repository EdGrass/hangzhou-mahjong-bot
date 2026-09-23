"""本地模拟器 v2（对局推进 + 副露窗口）—— Arena/自对弈公共内核。

物理恒等式：每名玩家随身牌 = 暗牌 + 副露牌（吃/碰 3 张、杠 4 张）= 13（待摸前）
/ 14（摸牌或副露补牌后）。面子数 e（杠亦计 1 组）、杠数 g：
    暗牌待摸前 = 13-3e-g；摸后 = 14-3e-g。
胡判/番型按 3(4-e)+2-g（杠的第四张 = 结构万能位，见 mahjong.hu/fan gangs 参数）。

规则要点（v2）：
- 窗口：碰/直杠（出牌者下家起按座序单探）→ 吃（仅下家且 ≤2 摊）；抓打圈内无窗口；
  白板弃出无人可吃碰杠；
- 杠：暗杠（自摸 4 张同码，白板禁杠）/补杠（碰组 + 第 4 张）→ 补牌一张后继续行动
  （杠上花/连杠路径）；直杠（抢弃牌）→ 不补牌，随后直接出牌；
  牌墙余量 ≤21 禁杠（保最后 20 张保留区）；抓打圈内别家仅可暗杠；
- 抓打圈：弃白后一圈内，别家只能打刚摸的牌，直至弃白者本人再次摸牌解除；
- 动作链：杠/财飘（爆头态弃白）每动作 chain+1 且 ×2 番、财飘 piao+1；
  普通出牌断链；胡时以当前 chain 计番。
"""
from __future__ import annotations

import random

from .fan import calc as calc_fan
from .hu import is_baotou, is_win
from .shanten_exact import shanten as _exact_shanten
from .tiles import GOD_TILE

WALL_RESERVE = 20                            # 最后 20 张保留不摸
GANG_MIN = WALL_RESERVE + 2                   # 杠需保证补牌后余量 ≥20
ALL_CODES = ["%d%s" % (n, s) for s in "wbt" for n in range(1, 10)] + \
            ["东", "南", "西", "北", "中", "发", GOD_TILE]
DECK = ALL_CODES * 4


def _minus(hand, tile, k=1):
    out = list(hand)
    for _ in range(k):
        out.remove(tile)
    return out


def make_view(seat, phase, turn, hand, drawn=None, melds=None, offer=None,
              responding=None, god=None, scores=None, can_gang=True,
              river=None, all_melds=None, dealer=None):
    """与协议层 snap_view 同构的本人视角（模拟器扩展键仅本地填充）。"""
    melds = melds or []
    god = dict(god or {"baotou": False, "chain_count": 0, "catch_play": False,
                       "piao_count": 0})
    if phase == "draw" and drawn is not None and turn == seat:
        gangs = sum(1 for m in melds if m["type"] == "gang")
        god["baotou"] = is_baotou(_minus(hand, drawn), exposed_melds=len(melds),
                                  gangs=gangs)
    return {
        "seat": seat, "phase": phase, "turn": turn,
        "responding_seats": list(responding or []),
        "drawn_tile": drawn, "my_hand": list(hand),
        "god": god, "scores": scores,
        "melds": list(melds),
        "offer_tile": offer,
        "can_gang": can_gang,
        "river": list(river or []),     # 当前局公开弃牌河（真机 game.py 同口径）
        "dealer": dealer,              # 当前局庄家（C063 赔付评估用）
        # 2026-09-10 C021：四家副露（公开信息）——用于按剩余张数评估听牌宽度
        "all_melds": [list(m) for m in all_melds] if all_melds else [],
    }


class SimGame:
    def __init__(self, strategies, rounds=1, base=1, seed=0, deck=None,
                 wall_reserve=None):
        if len(strategies) != 4:
            raise ValueError("需要恰好 4 个策略，实际 %d" % len(strategies))
        self.strategies = list(strategies)
        self.rounds = rounds
        self.base = base
        # 牌墙保留量（评估口径参数，C003）：None→模块默认 20；真机短局
        # 校准经验值 60（见 docs/iter/queue.md 口径表与 C003 报告卡）
        self.wall_reserve = WALL_RESERVE if wall_reserve is None \
            else int(wall_reserve)
        self.gang_min = self.wall_reserve + 2
        self.rng = random.Random(seed)
        self.fixed_deck = list(deck) if deck else None   # 测试注入：完整 136 张
        self.totals = [0, 0, 0, 0]
        z = [0] * 4
        self.stats = {"rounds_played": 0, "hu_count": list(z),
                      "fan_total": list(z), "draw_count": 0,
                      "violations": 0, "fallbacks": 0,
                      "chi": list(z), "peng": list(z), "gang": list(z),
                      "chain_hu": 0, "catch_rounds": 0, "viol_sites": [],
                      "tenpai_ever": list(z),       # 曾听牌的局数（每座）
                      "tenpai_at_sum": list(z),     # 听牌时摸牌序号累计
                      "bao_ever": list(z)}          # 曾到达爆头态（任意摸胡）的局数

    def _viol(self, seat, site):
        self.stats["violations"] += 1
        self.stats["viol_sites"].append((site, seat, self.stats["rounds_played"]))

    # ---------- 状态 ----------
    def _new_round(self):
        wall = list(self.fixed_deck) if self.fixed_deck else list(DECK)
        if not self.fixed_deck:
            self.rng.shuffle(wall)
        self.hands = [sorted(wall[i * 13:(i + 1) * 13]) for i in range(4)]
        del wall[:52]
        self.wall = wall
        self.melds = [[] for _ in range(4)]
        self.chain = [0] * 4
        self.piao = [0] * 4
        self.catch_at = None
        self.river = []                     # 当前局公开弃牌河（新局清空）

    def _e(self, s):
        return len(self.melds[s])

    def _g(self, s):
        return sum(1 for m in self.melds[s] if m["type"] == "gang")

    def _chi_cnt(self, s):
        return sum(1 for m in self.melds[s] if m["type"] == "chi")

    def _draw_ok(self):
        return len(self.wall) > self.wall_reserve

    def _gang_ok(self):
        return len(self.wall) >= self.gang_min

    def _hu_check(self, s):
        return is_win(self.hands[s], exposed_melds=self._e(s), gangs=self._g(s))

    def _view(self, seat, phase="draw", turn=None, drawn=None, offer=None,
              responding=None):
        return make_view(seat, phase, turn if turn is not None else seat,
                         self.hands[seat], drawn=drawn, melds=self.melds[seat],
                         offer=offer, responding=responding,
                         god={"baotou": False,
                              "chain_count": self.chain[seat],
                              "catch_play": (self.catch_at is not None
                                             and seat != self.catch_at),
                              "piao_count": self.piao[seat]},
                         can_gang=self._gang_ok(), river=self.river,
                         all_melds=self.melds,
                         dealer=getattr(self, "_dealer", None))

    # ---------- 决策 ----------
    def _decide(self, seat, view):
        try:
            return self.strategies[seat].decide(view)
        except Exception:
            self._viol(seat, "decide_exc")
            return None

    # ---------- 结算 ----------
    def _pay_hu(self, winner, dealer, fan):
        mult = self.base * fan
        if winner == dealer:
            pay = [mult * 8] * 3
            others = [s for s in range(4) if s != winner]
        else:
            pay = [mult * 8] + [mult] * 2
            others = [dealer] + [s for s in range(4) if s not in (winner, dealer)]
        for seat, amt in zip(others, pay):
            self.totals[seat] -= amt
            self.totals[winner] += amt

    def _finish_hu(self, seat, dealer, drawn):
        pre = _minus(self.hands[seat], drawn)
        chain = {"count": self.chain[seat], "piao": self.piao[seat]}
        fan = calc_fan(pre, drawn, chain, base=self.base,
                       exposed_melds=self._e(seat), gangs=self._g(seat))["fan"]
        if chain["count"]:
            self.stats["chain_hu"] += 1
        self._pay_hu(seat, dealer, fan)
        self.stats["hu_count"][seat] += 1
        self.stats["fan_total"][seat] += fan

    # ---------- 副露 ----------
    def _chi_options(self, seat, t):
        if self._chi_cnt(seat) >= 2 or t == GOD_TILE or t[-1] not in "wbt":
            return []
        n = int(t[0])
        suit = t[1]
        hset = set(self.hands[seat])
        out = []
        for a, b in ((n - 2, n - 1), (n - 1, n + 1), (n + 1, n + 2)):
            ta, tb = "%d%s" % (a, suit), "%d%s" % (b, suit)
            if 1 <= a <= 9 and 1 <= b <= 9 and ta in hset and tb in hset:
                out.append([ta, tb])
        return out

    def _respond_windows(self, discarder, t):
        """碰/直杠窗口（下家起）→ 吃窗口（仅下家）。返回 (kind, actor, act) 或 None。"""
        if self.catch_at is not None or t == GOD_TILE:
            return None
        for step in (1, 2, 3):
            s = (discarder + step) % 4
            if self.hands[s].count(t) < 2:
                continue
            view = self._view(s, "response_peng", turn=discarder, offer=t,
                              responding=[s])
            act = self._decide(s, view)
            a = act.get("action") if act else None
            if a == "gang" and self.hands[s].count(t) >= 3:
                return ("gang_ming", s, act)
            if a == "peng":
                return ("peng", s, act)
        s = (discarder + 1) % 4
        if self._chi_options(s, t):
            view = self._view(s, "response_chi", turn=discarder, offer=t,
                              responding=[s])
            act = self._decide(s, view)
            if act and act.get("action") == "chi":
                return ("chi", s, act)
        return None

    def _apply_claim(self, kind, actor, t, act):
        if kind == "peng":
            self.hands[actor] = _minus(self.hands[actor], t, 2)
            self.melds[actor].append({"type": "peng", "tile": t, "tiles": [t] * 3})
            self.stats["peng"][actor] += 1
        elif kind == "chi":
            opts = self._chi_options(actor, t)
            want = act.get("tiles") if isinstance(act, dict) else None
            if want not in opts:
                want = opts[0]
            for x in want:
                self.hands[actor].remove(x)
            run = sorted([want[0], t, want[1]], key=lambda x: int(x[0]))
            self.melds[actor].append({"type": "chi", "tile": t, "tiles": run})
            self.stats["chi"][actor] += 1
        else:                                 # gang_ming 直杠：不补牌，随后出牌
            self.hands[actor] = _minus(self.hands[actor], t, 3)
            self.melds[actor].append({"type": "gang", "tile": t, "tiles": [t] * 4})
            self.stats["gang"][actor] += 1
            self.chain[actor] += 1
        return True

    def _own_gang(self, seat):
        """自杠（暗杠/补杠）：成功则补牌并返回 True。"""
        hand = self.hands[seat]
        if not self._gang_ok():
            return False
        catch_ban = self.catch_at is not None and seat != self.catch_at
        if not catch_ban:
            for m in self.melds[seat]:
                if m["type"] == "peng":
                    t = m["tile"]
                    if t != GOD_TILE and hand.count(t) >= 1:
                        self.hands[seat].remove(t)
                        m.update(type="gang", tiles=[t] * 4)
                        self.stats["gang"][seat] += 1
                        self.chain[seat] += 1
                        return True
        for t in sorted(set(hand)):
            if t != GOD_TILE and hand.count(t) == 4:
                self.hands[seat] = _minus(hand, t, 4)
                self.melds[seat].append({"type": "gang", "tile": t,
                                         "tiles": [t] * 4})
                self.stats["gang"][seat] += 1
                self.chain[seat] += 1
                return True
        return False

    # ---------- 单局 ----------
    def _play_round(self, dealer):
        self._dealer = dealer
        self._new_round()
        seat = dealer
        state = "ready"                       # ready: 已摸牌待行动; discard: 副露/杠后出牌
        drawn = None
        tenpai_seen = [False] * 4             # 本局各座是否已听牌（出牌后判）
        bao_seen = [False] * 4                # 本局各座是否到达爆头态
        seat_draws = [0] * 4                  # 本局各座摸牌序号
        while True:
            if state == "ready":
                if seat == self.catch_at:
                    self.catch_at = None      # 抓打圈随本人摸牌解除
                if not self._draw_ok():
                    self.stats["draw_count"] += 1
                    self._tenpai_end(tenpai_seen)
                    return None               # 流局
                drawn = self.wall.pop(0)
                self.hands[seat].append(drawn)
                self.hands[seat].sort()
                seat_draws[seat] += 1
            # --- 行动：胡 / 自杠（仅 ready）；随后统一出牌 ---
            view = self._view(seat, "draw", drawn=drawn)
            act = self._decide(seat, view)
            a = act.get("action") if act else None
            if state == "ready":
                if a == "hu" and self._hu_check(seat):
                    self._finish_hu(seat, dealer, drawn)
                    self._tenpai_end(tenpai_seen)
                    return seat
                if a == "gang" and self._own_gang(seat):
                    state = "discard"         # 暗杠/补杠后必须出牌（本版不补牌）
                    drawn = None
                    continue
                if a in ("hu", "gang"):
                    self._viol(seat, "hu_or_gang_invalid")
            elif a in ("hu", "gang"):
                self._viol(seat, "hu_or_gang_no_draw")  # 未摸牌不可胡/杠
            # --- 出牌（ready/discard 统一入口） ---
            hand = self.hands[seat]
            if act is None or a == "hu":
                act = {"action": "discard",
                       "tile": hand[0] if hand else None}
            tile = act.get("tile")
            if not hand:
                self._viol(seat, "empty_hand")
                tile = None
            elif tile not in hand:
                self._viol(seat, "tile_not_in_hand")
                tile = hand[0]
            if tile is None:                  # 防御：无牌可出
                self.stats["draw_count"] += 1
                self._tenpai_end(tenpai_seen)
                return None
            if state == "ready":
                must = (self.catch_at is not None and seat != self.catch_at)
                if must and tile != drawn:
                    self._viol(seat, "catch_must_drawn")
                    tile = drawn
            # 链/抓打圈：弃白（ready 态爆头 = 财飘）否则断链
            if tile == GOD_TILE:
                if state == "ready" and view["god"].get("baotou"):
                    self.chain[seat] += 1
                    self.piao[seat] += 1
                else:
                    self.chain[seat] = 0
                    self.piao[seat] = 0
                if state == "ready":
                    self.catch_at = seat
                    self.stats["catch_rounds"] += 1
            else:
                self.chain[seat] = 0
                self.piao[seat] = 0
            hand.remove(tile)
            self.river.append(tile)         # 弃牌公开入河（含被碰/吃走者，与真机事件同口径）
            # 听牌统计（2026-09-09）：出牌后 13-3e-g 张存在任何补入即胡 =
            # 听牌；用 is_win（_core_win lru 缓存）快速判定，避免 exact_shanten
            # 高成本插桩。每座每局只记首次（摸牌序号 = 听牌速度代理）。
            if not tenpai_seen[seat] or \
                    (not bao_seen[seat] and hand.count(GOD_TILE) >= 1):
                ee, gg = self._e(seat), self._g(seat)
                try:
                    win_cnt = 0
                    for t in ALL_CODES:
                        if t == GOD_TILE and hand.count(t) >= 4:
                            continue
                        if is_win(hand + [t], exposed_melds=ee, gangs=gg):
                            win_cnt += 1
                    if win_cnt == 34 and not bao_seen[seat]:
                        bao_seen[seat] = True       # 任意摸皆胡 = 爆头态
                        self.stats["bao_ever"][seat] += 1
                    if win_cnt > 0 and not tenpai_seen[seat]:
                        tenpai_seen[seat] = True
                        self.stats["tenpai_at_sum"][seat] += seat_draws[seat]
                except ValueError:
                    pass
            # --- 窗口 ---
            claim = self._respond_windows(seat, tile)
            if claim is None:
                seat = (seat + 1) % 4
                state = "ready"
                drawn = None
                continue
            kind, actor, act = claim
            self._apply_claim(kind, actor, tile, act)
            seat = actor
            state = "discard"
            drawn = None

    def _tenpai_end(self, tenpai_seen):
        """局终：曾听牌各座累计（供听牌率/听牌速度统计）。"""
        for s in range(4):
            if tenpai_seen[s]:
                self.stats["tenpai_ever"][s] += 1

    # ---------- 场次 ----------
    def run(self):
        dealer = 0
        for _ in range(self.rounds):
            winner = self._play_round(dealer)
            self.stats["rounds_played"] += 1
            if winner is None:
                continue
            if winner != dealer:
                dealer = winner
        return {"totals": list(self.totals), "stats": dict(self.stats)}
