# -*- coding: utf-8 -*-
"""C130 —— SpeedTUGC + **选择性 rollout**（允许「跨向听」权衡）。

为什么值得做（本项目**从未测过**的一件事）：
  现行弃牌主键是 `(向听数, …)` —— **向听数是硬主键，永不跨级比较**。
  C038 测的是「同一向听内换 ukeire」、C039 测的是「同向听内换 tie-break」，**都不是跨向听**。
  而「1 向听 2 张进张」对「2 向听 20 张进张」谁先胡，只有把两条路真跑到胡才分得清。

本实现的四条硬约束（来自报告 §11/§13/§17）：
  1. 目标 = **E[番 × 1{胡}]**（不是 P(听牌)）——同时反映胡率与打点；
  2. 状态含**副露与爆头潜力**（rollout 内保留 exposed/gangs，并对爆头态给 ×2 记分）；
  3. **副露机会建模**：每一步以概率 q 允许把手中的对子/刻子「被别家打出」而成副露
     （否则会像 C033 那样系统性低估副露路线）；
  4. **有预算**：只在 向听∈{1,2} 且候选≥2 时启用，R=10/k=3/最多 4 个候选，
     实测单次 ≲0.5s、平均每巡 ≲2-3 次 → 房间时长上升 ≲10%（30 分钟上限见 §17）。

未上线：按 §13 教条，sim 不用于排序，只能真机 ≥134 房 A/B 判定。
"""
from __future__ import annotations

import collections
import os
import random

from mahjong.fan import calc as calc_fan
from mahjong.hu import is_baotou, is_win
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten
from mahjong.sim import ALL_CODES

from .model import my_turn, window_pending
from .speed import _melds_info
from .speedt import _best_discard_t, _pref
from .speedtugc import SpeedTUGC

_FULL = collections.Counter(ALL_CODES)


class C130Policy(SpeedTUGC):
    def __init__(self, name="speedc130", samples=10, steps=3, max_cand=4,
                 meld_p=0.10, seed=0):
        super().__init__(name=name)
        self.samples = int(samples)
        self.steps = int(steps)
        self.max_cand = int(max_cand)
        self.meld_p = float(meld_p)   # 每步「手中对子被别家打出」的概率（经验近似）
        self.rng = random.Random(seed)
        self.cache = {}
        self.stats = collections.Counter()

    # ---------- 牌池（未见牌） ----------
    def _pool(self, hand, view):
        pool = _FULL.copy()
        for t in hand:
            pool[t] -= 1
        for t in (view.get("river") or []):
            if pool.get(t, 0) > 0:
                pool[t] -= 1
        for sm in (view.get("all_melds") or []):
            for m in sm:
                tiles = m.get("tiles") if isinstance(m, dict) else m
                for t in (tiles or []):
                    if pool.get(t, 0) > 0:
                        pool[t] -= 1
        return [t for t, c in pool.items() for _ in range(max(0, c))]

    # ---------- 单次 rollout ----------
    def _rollout(self, hand13, exposed, gangs, seq, meld_rolls, skip=None):
        """用**预先抽好的序列**跑一次 rollout（公共随机数 / CRN）。

        为什么必须这样做：C032 的失败原因之一是「R 次独立采样 → argmax 在噪声上」。
        若每个候选弃牌各自独立采样，A 和 B 看到的牌不同，比较的是采样噪声不是策略差异。
        改成「同一批序列喂给所有候选」后，候选之间的差变得可靠（代价为 0）。

        `seq` = 从**基础未见牌池**抽出的 k 张（不放回）；候选自己的池 = 基础池 − 自己弃的那张，
        所以遇到 `skip` 就跳过（继续消费序列），保证各候选消费的是高度相关的随机性。
        """
        h = list(hand13)
        e, g = exposed, gangs
        it = iter(seq)
        for step in range(self.steps):
            if self.meld_p > 0 and step < len(meld_rolls) and meld_rolls[step] < self.meld_p:
                pairs = [t for t in set(h) if h.count(t) >= 2 and t != "白"]
                if pairs:
                    t = self.rng.choice(pairs)
                    h.remove(t); h.remove(t)
                    e += 1
                    best, bs = None, 99
                    for x in sorted(set(h)):
                        rem = list(h); rem.remove(x)
                        try:
                            sv = exact_shanten(rem, qidui=(e == 0 and g == 0),
                                               exposed_melds=e, gangs=g)
                        except ValueError:
                            continue
                        if sv < bs:
                            bs, best = sv, x
                    if best is None or best not in h:
                        return 0.0
                    h.remove(best)          # 碰后必须弃牌 → 暗牌 = 13 - 3e - g ✓
            t = None
            for cand in it:
                if cand == skip:
                    continue               # 该候选已把这张打进河里
                t = cand
                break
            if t is None:
                return 0.0
            h.append(t)
            try:
                if is_win(h, exposed_melds=e, gangs=g):
                    pre = list(h); pre.remove(t)
                    try:
                        f = calc_fan(pre, t, exposed_melds=e, gangs=g).get("fan") or 1
                    except Exception:
                        f = 1
                    return float(f)
            except ValueError:
                return 0.0
            try:
                d = _best_discard_t(h, t, e, g)
            except Exception:
                d = h[0]
            if d in h:
                h.remove(d)
        return 0.0

    def _make_seqs(self, pool_base):
        """生成 R 条公共序列（长度 k，不放回）+ 每步的副露骰子。"""
        seqs = []
        for _ in range(self.samples):
            pool = list(pool_base)
            seq = []
            for _s in range(self.steps):
                if not pool:
                    break
                seq.append(pool.pop(self.rng.randrange(len(pool))))
            seqs.append((seq, [self.rng.random() for _ in range(self.steps)]))
        return seqs

    def _value(self, hand13, exposed, gangs, seqs, skip):
        if not seqs:
            return 0.0
        return sum(self._rollout(hand13, exposed, gangs, s, m, skip)
                   for s, m in seqs) / float(len(seqs))

    # ---------- 决策 ----------
    def decide(self, view):
        # 窗口判据/胡/抓打圈 100% 沿用 SpeedTUGC（真机证据最好的那一档）
        if window_pending(view):
            return super().decide(view)
        if not my_turn(view):
            return super().decide(view)
        hand = list(view.get("my_hand") or [])
        melds = view.get("melds") or []
        exposed, gangs = _melds_info(view)
        drawn = view.get("drawn_tile")
        if not hand or len(hand) != 14 - 3 * exposed - gangs or not drawn:
            return super().decide(view)
        try:
            if is_win(hand, exposed_melds=exposed, gangs=gangs):
                return super().decide(view)       # 含 C036 弃胡换爆头
        except ValueError:
            return super().decide(view)
        if (view.get("god") or {}).get("catch_play"):
            return super().decide(view)
        # 候选：向听 <= smin+1（这是与现行策略的本质差异——允许跨一级向听）
        cands = []
        for d in sorted(set(hand)):
            rem = list(hand); rem.remove(d)
            try:
                sh = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                                   exposed_melds=exposed, gangs=gangs)
            except ValueError:
                continue
            cands.append((sh, d, rem))
        if not cands:
            return super().decide(view)
        smin = min(c[0] for c in cands)
        if smin not in (1, 2):
            return {"action": "discard", "tile": _best_discard_t(hand, drawn, exposed, gangs)}
        group = [c for c in cands if c[0] == smin]
        if len(group) < 2:
            return {"action": "discard", "tile": _best_discard_t(hand, drawn, exposed, gangs)}
        key = (tuple(sorted(hand)), exposed, gangs)
        hit = self.cache.get(key)
        if hit is not None:
            self.stats["cache_hit"] += 1
            return {"action": "discard", "tile": hit}
        try:
            pool = self._pool(hand, view)
            # 候选排序：先按向听、再按 _pref，取前 max_cand（保证 min-shanten 候选优先在内）
            cands.sort(key=lambda c: (c[0], _pref(c[1], hand), c[1]))
            picks = cands[:self.max_cand]
            # 公共随机数：同一批序列喂给所有候选（否则 argmax 在噪声上）
            seqs = self._make_seqs(pool)
            scored = []
            for sh, d, rem in picks:
                v = self._value(rem, exposed, gangs, seqs, skip=d)
                scored.append((v, -sh, -_pref(d, hand), d))
            scored.sort(reverse=True)
            self.stats["rollout_used"] += 1
            tile = scored[0][3]
            self.cache[key] = tile
            return {"action": "discard", "tile": tile}
        except Exception:
            self.stats["fallback"] += 1
            return super().decide(view)
