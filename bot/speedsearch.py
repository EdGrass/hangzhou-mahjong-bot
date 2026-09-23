# -*- coding: utf-8 -*-
"""C063 SpeedSearch —— 同向听关键弃牌的配对 rollout 搜索。

只在「本人摸牌后的弃牌回合」且存在多张同向听候选时启用；其余动作
（副露窗口、胡、抓打圈、无并列候选）100% 回退到 C045/SpeedTUGC。

搜索特征：
- 候选：最小向听并列弃牌，最多取 C045 静态键最优的若干张；
- 牌墙：公开信息构造的不放回牌池（手牌 + 河 + 四家副露）；
- 配对：同一随机摸牌序列同时评估所有候选，降低比较方差；
- 目标：自摸真实赔付（庄 24×番 / 闲 10×番）+ 听牌宽度叶值；
- 预算：超时或样本不足直接回退，不改变 C045 行为。

参数偏保守：默认最多 3 个候选、8 个样本、6 步前瞻、350ms 预算。

2026-09-17 复核（补上当年没做的一步）：本候选**从未注册进 run_bot**，所以从没跑过正式赛
M=10 门禁。补跑结果（10 线程共享同一策略实例，与正式赛同构）：
  · 默认 time_budget_ms=350：**尾部可变且贴边**——一次 n=100 给出 p95=1561ms / max=**4134ms** / **2 条超 3s**；
    另一次同样本量给出 max=2071ms / 0 超。⇒ 该配置**不能用于正式赛**。
  · 预算扫描（p95/max）：350→728/2072ms；120→6.3/561ms；60→5.6/263ms；30→2.3/**5.2ms**。
  · **通用教训**：`time.monotonic()` 墙钟预算**挡不住 GIL 争用**——10 线程共享策略实例时，
    "350ms 预算"的一次决策实测可达 4.1 秒（线程在等 GIL，预算检查根本没机会执行）。
    任何计算型候选都必须用**与正式赛同构的 M=10 并发门禁**验收，不能只看单线程 latency_bench。
⇒ 结论：**该方向暂不可用**（质量证据来自 350ms 配置、而它在 sim 里已不如 C045 的 0.331；小预算只会更弱）。
   若将来要复活，必须在 ≤120ms 预算下**重新建立质量证据**，而不是沿用旧的 350ms 结论。

2026-09-12 门禁结论：5 seed × 4 房强场中，随机配对 rollout 代理
0.306 vs C045 0.331、房均分 −1.2 vs −0.8；确定性 look1 在当前样本上
只能打平或回退。**未晋级生产，C045 仍是唯一默认竞技策略。**
"""
from __future__ import annotations

import collections
import functools
import random
import time

from mahjong.fan import calc as calc_fan
from mahjong.hu import is_win
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten
from mahjong.sim import ALL_CODES
from mahjong.tiles import (counts_of, from_counts, id_of,
                           is_suit_tile, suit_and_num, tile_of)

from .model import my_turn, window_pending
from .speedt import _best_discard_t, _pref
from .speedtugc import SpeedTUGC
from .speedtw import _visible

FALLBACK_NAME = "speedTUGC"


@functools.lru_cache(maxsize=32768)
def _best_discard_cached(counts, drawn_id, exposed, gangs):
    """按 34 维计数缓存 C045 的下一弃牌，rollout 内高频复用。"""
    hand = from_counts(counts)
    drawn = tile_of(drawn_id) if drawn_id is not None else None
    return _best_discard_t(hand, drawn, exposed, gangs)


@functools.lru_cache(maxsize=32768)
def _win_cached(counts, exposed, gangs):
    """按 34 维计数缓存自摸胡判。"""
    return is_win(from_counts(counts), exposed_melds=exposed, gangs=gangs)


def _meld_tiles(m):
    """兼容副露 {'tiles': [...]} 与旧式列表形态。"""
    if isinstance(m, dict):
        ts = m.get("tiles")
        if ts:
            return list(ts)
        t = m.get("tile")
        n = 4 if m.get("type") == "gang" else 3
        return [t] * n if t else []
    return list(m or [])


def _unseen_pool(hand, view):
    """返回公开未见牌池（每个物理副本一项，不放回采样）。"""
    vis = _visible(hand, view.get("river") or [],
                   view.get("all_melds") or [])
    out = []
    for t in ALL_CODES:
        out.extend([t] * max(0, 4 - int(vis.get(t, 0))))
    return out


def _neighborhood_tiles(hand):
    """可能在一摸内改变向听的牌种：手牌自身 + 数牌 ±2 邻域 + 白。"""
    out = set(hand)
    for tile in set(hand):
        try:
            idx = id_of(tile)
        except ValueError:
            continue
        if is_suit_tile(idx):
            suit, num = suit_and_num(idx)
            for delta in (-2, -1, 1, 2):
                n = num + delta
                if 1 <= n <= 9:
                    out.add("%d%s" % (n, "wbt"[suit]))
    out.add("白")
    return out


def _payout(fan, dealer, seat):
    """自摸赔付：庄家 24×番，闲家 10×番；dealer 未知时按闲家保守估。"""
    mult = 24 if dealer is not None and dealer == seat else 10
    return float(mult) * float(fan or 1)


def _live_wait_count(hand, exposed, gangs, view):
    """等待牌的剩余副本数；使用当前公开信息，保守估计。"""
    try:
        ws = waits(hand, exposed_melds=exposed, gangs=gangs)
    except ValueError:
        return 0
    # 这里的 hand 是 rollout 内的暗手；河/四家副露仍用当前视图。
    vis = _visible(hand, view.get("river") or [],
                   view.get("all_melds") or [])
    return sum(max(0, 4 - int(vis.get(t, 0))) for t in ws)


def _expected_fan(hand, exposed, gangs, view, chain):
    """听牌后的活等加权期望番数；用于 rollout 叶值保护打点。"""
    try:
        ws = waits(hand, exposed_melds=exposed, gangs=gangs)
    except ValueError:
        return 1.0
    vis = _visible(hand, view.get("river") or [],
                   view.get("all_melds") or [])
    total = 0.0
    weight = 0
    for t in ws:
        live = max(0, 4 - int(vis.get(t, 0)))
        if not live:
            continue
        try:
            r = calc_fan(hand, t, chain, base=1,
                         exposed_melds=exposed, gangs=gangs)
        except Exception:
            continue
        if r.get("hu"):
            total += live * float(r.get("fan") or 1)
            weight += live
    return total / weight if weight else 1.0


def _candidate_key(d, hand, s, exposed, gangs, drawn):
    """与 C045 静态弃牌键同构，用于限制搜索候选数量。"""
    wcnt = 0
    if s == 0:
        rem = list(hand)
        rem.remove(d)
        try:
            wcnt = len(waits(rem, exposed_melds=exposed, gangs=gangs))
        except ValueError:
            wcnt = 0
    return (s, -wcnt, _pref(d, hand), -1 if d == drawn else 0)


class SpeedSearch(SpeedTUGC):
    """C063：在 C045 基础上增加一组保守的配对 rollout 搜索。"""

    def __init__(self, name="speedsearch", mode="look1", samples=8, horizon=6,
                 max_candidates=3, min_samples=4, min_gain=2.0,
                 look1_min_gain=0.5, time_budget_ms=350,
                 allowed_shanten=(1,), seed=None):
        super().__init__(name=name)
        self.samples = max(1, int(samples))
        self.horizon = max(1, int(horizon))
        self.max_candidates = max(2, int(max_candidates))
        self.min_samples = max(1, min(self.samples, int(min_samples)))
        self.mode = str(mode)
        self.min_gain = float(min_gain)
        self.look1_min_gain = float(look1_min_gain)
        self.time_budget_ms = max(1, int(time_budget_ms))
        self.allowed_shanten = tuple(sorted(set(int(x) for x in allowed_shanten)))
        self._rng = random.Random(seed)
        self.stats = collections.Counter()

    def _rollout_one(self, hand, discard, exposed, gangs, view, seq, chain):
        """一个候选 + 一个固定随机序列的收益；序列由所有候选共享。"""
        h = list(hand)
        h.remove(discard)
        tenpai_at = None
        for step, tile in enumerate(seq):
            h2 = h + [tile]
            try:
                won = _win_cached(tuple(counts_of(h2)), exposed, gangs)
            except Exception:
                won = False
            if won:
                try:
                    r = calc_fan(h, tile, chain, base=1,
                                 exposed_melds=exposed, gangs=gangs)
                    fan = r.get("fan") if r.get("hu") else 1
                except Exception:
                    fan = 1
                return _payout(fan, view.get("dealer"), view.get("seat"))
            try:
                d2 = _best_discard_cached(tuple(counts_of(h2)), id_of(tile),
                                          exposed, gangs)
            except Exception:
                d2 = h2[0]
            if d2 not in h2:
                d2 = h2[0]
            h2.remove(d2)
            h = h2
            try:
                s2 = exact_shanten(h, qidui=(exposed == 0 and gangs == 0),
                                   exposed_melds=exposed, gangs=gangs)
            except ValueError:
                s2 = 2
            if s2 == 0 and tenpai_at is None:
                tenpai_at = step
        try:
            s = exact_shanten(h, qidui=(exposed == 0 and gangs == 0),
                              exposed_melds=exposed, gangs=gangs)
        except ValueError:
            s = 2
        if s == 0:
            val = 1.0 + 0.20 * _live_wait_count(h, exposed, gangs, view)
        else:
            val = -2.0 * s
        if tenpai_at is not None:
            # 早到听牌比晚到更有竞速价值，但权重很小，避免压过真实赔付。
            val += 0.25 * (len(seq) - tenpai_at)
        return val

    def _leaf13(self, hand, exposed, gangs, view, chain):
        """13 张手的叶值：听牌看活等/期望番，非听看向听。"""
        try:
            s = exact_shanten(hand, qidui=(exposed == 0 and gangs == 0),
                              exposed_melds=exposed, gangs=gangs)
        except ValueError:
            return -4.0
        if s == 0:
            live = _live_wait_count(hand, exposed, gangs, view)
            fan = _expected_fan(hand, exposed, gangs, view, chain)
            return 1.0 + 0.20 * live + 0.50 * fan
        return -2.0 * s

    def _look1_score(self, hand, discard, exposed, gangs, view, chain):
        """确定性一摸前瞻：枚举未见牌 + C045 后续最优弃牌。"""
        rem = list(hand)
        rem.remove(discard)
        try:
            s0 = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                               exposed_melds=exposed, gangs=gangs)
        except ValueError:
            return -999.0
        if s0 == 0:
            return self._leaf13(rem, exposed, gangs, view, chain)
        vis = _visible(rem, view.get("river") or [],
                       view.get("all_melds") or [])
        neigh = _neighborhood_tiles(rem)
        weighted = 0.0
        total = 0
        base_leaf = self._leaf13(rem, exposed, gangs, view, chain)
        for tile in ALL_CODES:
            live = max(0, 4 - int(vis.get(tile, 0)))
            if live <= 0:
                continue
            total += live
            if tile not in neigh:
                weighted += live * base_leaf
                continue
            h14 = rem + [tile]
            try:
                d2 = _best_discard_cached(tuple(counts_of(h14)), id_of(tile),
                                          exposed, gangs)
            except Exception:
                d2 = tile
            if d2 not in h14:
                d2 = tile
            h13 = list(h14)
            h13.remove(d2)
            weighted += live * self._leaf13(h13, exposed, gangs, view, chain)
        return weighted / total if total else -999.0

    def _decide_look1(self, hand, base, chosen, exposed, gangs, view, chain):
        t0 = time.monotonic()
        scores = {}
        for d in chosen:
            scores[d] = self._look1_score(hand, d, exposed, gangs, view, chain)
            if (time.monotonic() - t0) * 1000.0 > self.time_budget_ms:
                self.stats["timeout"] += 1
                self.stats["fallback"] += 1
                return base
        best = max(chosen, key=lambda d: scores[d])
        if scores[best] > scores[base] + self.look1_min_gain:
            self.stats["changed"] += 1
            return best
        return base

    def decide(self, view):
        # 窗口、已胡、抓打圈等全部交给 C045 原逻辑。
        if not my_turn(view) or (window_pending(view) and view.get("offer_tile")):
            return super().decide(view)

        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        exposed = len(melds)
        gangs = sum(1 for m in melds if m.get("type") == "gang")
        drawn = view.get("drawn_tile")
        if len(hand) != 14 - 3 * exposed - gangs:
            return super().decide(view)

        try:
            hu = _win_cached(tuple(counts_of(hand)), exposed, gangs)
        except Exception:
            hu = False
        if hu and drawn:
            return super().decide(view)   # C036 弃胡换爆头
        if (view.get("god") or {}).get("catch_play") and drawn:
            return {"action": "discard", "tile": drawn}

        base = _best_discard_t(hand, drawn, exposed, gangs)
        cands = []
        for d in sorted(set(hand)):
            rem = list(hand)
            rem.remove(d)
            try:
                s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                                  exposed_melds=exposed, gangs=gangs)
            except ValueError:
                continue
            cands.append((_candidate_key(d, hand, s, exposed, gangs, drawn),
                          d, s))
        if not cands:
            return {"action": "discard", "tile": base}

        smin = min(x[2] for x in cands)
        if smin not in self.allowed_shanten:
            return {"action": "discard", "tile": base}
        tied = [x for x in cands if x[2] == smin]
        if len(tied) < 2:
            return {"action": "discard", "tile": base}
        tied.sort(key=lambda x: x[0])
        chosen = [x[1] for x in tied[:self.max_candidates]]
        if base not in chosen:
            chosen[-1] = base
        if len(chosen) < 2:
            return {"action": "discard", "tile": base}
        self.stats["search_used"] += 1
        self.stats["used_s%d" % smin] += 1
        chain = {
            "count": int((view.get("god") or {}).get("chain_count") or 0),
            "piao": int((view.get("god") or {}).get("piao_count") or 0),
        }
        if self.mode == "look1":
            return {"action": "discard",
                    "tile": self._decide_look1(hand, base, chosen, exposed,
                                               gangs, view, chain)}

        pool = _unseen_pool(hand, view)
        if not pool:
            return {"action": "discard", "tile": base}
        seq_len = min(self.horizon, len(pool))
        scores = {d: 0.0 for d in chosen}
        used = 0
        t0 = time.monotonic()
        for _ in range(self.samples):
            if used and (time.monotonic() - t0) * 1000.0 > self.time_budget_ms:
                self.stats["timeout"] += 1
                break
            seq = list(pool)
            self._rng.shuffle(seq)
            seq = seq[:seq_len]
            for d in chosen:
                scores[d] += self._rollout_one(hand, d, exposed, gangs,
                                               view, seq, chain)
            used += 1
        if used < self.min_samples:
            self.stats["fallback"] += 1
            return {"action": "discard", "tile": base}

        best = max(chosen, key=lambda d: scores[d])
        if scores[best] > scores[base] + self.min_gain:
            self.stats["changed"] += 1
            self.stats["changed_s%d" % smin] += 1
            return {"action": "discard", "tile": best}
        return {"action": "discard", "tile": base}