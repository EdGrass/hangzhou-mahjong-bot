# -*- coding: utf-8 -*-
"""SpeedK（C007）—— K1 全向听级一步有效牌 tie + K2 副露 ukeire 判据。

纯自摸竞速变体（对照 SpeedE，行为面说明书见 docs/iter/design/SpeedK-K1K2.md）：

- 弃牌 K1：SpeedE 同向听 tie 只做〔孤张字牌优先/留摸〕启发；SpeedK 把次键升级为
  〔一步有效牌〕——主键 exact_shanten 相同组的候选，s==0 比 waits 数、s>=1 比
  effective_tiles(rem)；仅在最小向听组才付 ukeire 二次成本。
- 副露 K2：SpeedBase 旧规则「副露后 faster(s_a<s_before) 才要」被本类升级为
  四档〔同向听也要比进张，更大才打破现状；s_a>s_before 绝不倒退〕：
      s_a <  s_before          -> 要（提速）
      s_a == s_before          -> 要 当且仅当 after 的 (waits/ukeire) > before
      s_a >  s_before          -> 不要
- 胡优先/抓打圈/窗口 pass 与去重全继承 SpeedE/SpeedCore 原逻辑。

调用方注意：want_claim_k/effective_tiles/_ukeire/_candidate_tiles/_best_discard_k
为纯函数可单测；SpeedK.decide 覆盖父类只改〔弃牌 K1〕与〔窗口 K2 谓词〕两处。
配合 bot/run_bot.py 的 "speedk" 入口做真机窗口对比（如 window_audit）。
"""
from __future__ import annotations

import random
import time

from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn, window_pending
from .speed import HONOR, _chi_pairs, _melds_info
from .speede import SpeedE, _best_discard

_HONOR_TILES = "东南西北中发白"      # 含白板（财神）——永远是可摸候选


# ===========================================================================
# 纯函数
# ===========================================================================
def _candidate_tiles(hand):
    """预过滤候选集：set(hand) ∪ 每张数牌同花色 ±1/±2（1..9 界内）∪ 全部字牌(含白)。"""
    cand = set(hand)
    for t in hand:
        if t in _HONOR_TILES:
            continue                       # 字牌（含白）无花色邻域
        n, suit = int(t[0]), t[1]
        for m in range(max(1, n - 2), min(9, n + 2) + 1):
            cand.add("%d%s" % (m, suit))
    cand.update(_HONOR_TILES)
    return cand


def _plausible_draw(hand13):
    """一次有效判定的必要预过滤：候选 t 若不能构成结构性补强则不可能降向听。

    安全侧导出（必要不充分）：抽到的 t 要促成向听下降，务须能把已有邻域补成可用
    块、或把自己补成对子/与白板组块。若 t 与手牌无任何邻接（±2 内）且自身也不在
    手（无法成对），则无论弃哪张都只能得到一个孤立新张 —— 不可能让完整结构更近，
    直接剔除可大幅省 exact_shanten。该过滤是必要约束，绝不错杀有效进张。

    例外：白板在 exact_shanten 中是财神（万能牌），抽白可与任意孤张/散牌补成对子或
    组块而降向听，即使手牌本身无白也必须放行（作候选）—— 是否真的有效仍交由后续
    exact_shanten 判定把关。
    """
    have = set(hand13)
    own_counts = {}
    for t in hand13:
        own_counts[t] = own_counts.get(t, 0) + 1
    nei = set()
    for t in have:
        if t in _HONOR_TILES:
            continue
        n, s = int(t[0]), t[1]
        for m in range(max(1, n - 2), min(9, n + 2) + 1):
            nei.add("%d%s" % (m, s))
    has_white = "白" in have

    def ok(t):
        if t == "白":                          # 财神万能：无条件放行（内层 exact 把关）
            return True
        if own_counts.get(t, 0) >= 1:            # 可成对（含白可补）
            return True
        if t in nei:                              # 邻接已有数牌，可补块
            return True
        if has_white:                             # 白作万能可补任意牌的单张成对
            return True
        return False

    return ok


def effective_tiles(hand13, exposed=0, gangs=0):
    """弃后 rem（13−3e−g 张，本函数只服务 s>=1）一步有效牌类数。

    cur = exact_shanten(rem)；对每个候选 t：nt = rem+[t]（14−3e−g）；若
    ∃x∈set(nt) 使 shanten(nt−x) < cur 则该 t 记一个有效类（每 t 只判到发现
    第一个改善即 break）。已听(cur==0)由调用方走 waits，本函数返回 0。
    长度/异常安全返回 0。
    """
    e, g = int(exposed or 0), int(gangs or 0)
    if len(hand13) != 13 - 3 * e - g:
        return 0
    try:
        cur = exact_shanten(hand13, qidui=(e == 0 and g == 0),
                            exposed_melds=e, gangs=g)
    except ValueError:
        return 0
    if cur == 0:
        return 0
    cnt = 0
    possible = _plausible_draw(hand13)
    for t in _candidate_tiles(hand13):
        if hand13.count(t) >= 4:           # 4 张全在手 → 摸不上
            continue
        if not possible(t):                # 无结构性补强可能 → 无法降向听
            continue
        nt = hand13 + [t]
        for x in set(nt):
            rem = list(nt)
            rem.remove(x)
            if len(rem) != 13 - 3 * e - g:
                continue
            try:
                s = exact_shanten(rem, qidui=(e == 0 and g == 0),
                                  exposed_melds=e, gangs=g)
            except ValueError:
                continue
            if s < cur:
                cnt += 1
                break
    return cnt


def _before_w(hand13, sb, exposed=0, gangs=0):
    """某手在 (暴露,杠) 口径下"s==0 -> waits 数，否则一步有效牌数"。"""
    if sb == 0:
        return len(waits(hand13, exposed_melds=exposed, gangs=gangs))
    return effective_tiles(hand13, exposed, gangs)


def _ukeire(hand13, exposed=0, gangs=0):
    """进程向量：s==0 -> len(waits)；s>=1 -> effective_tiles。异常回 0。"""
    e, g = int(exposed or 0), int(gangs or 0)
    if len(hand13) != 13 - 3 * e - g:
        return 0
    try:
        s = exact_shanten(hand13, qidui=(e == 0 and g == 0),
                          exposed_melds=e, gangs=g)
    except ValueError:
        return 0
    if s == 0:
        return len(waits(hand13, exposed_melds=e, gangs=g))
    return effective_tiles(hand13, e, g)


def _min_after(overfull, exposed, gangs):
    """overfull（长 14−3e−g，副露摘完后的"尚需弃 1 张"手）弃 1 张后最优终态。

    与 K1 同构：向听最小；同向听组再比 waits/ukeire。返回 (s, w, rem)；
    无合法候选回 (None, None, None)。
    """
    best = None
    for d in sorted(set(overfull)):
        rem = list(overfull)
        rem.remove(d)
        if len(rem) != 13 - 3 * exposed - gangs:
            continue
        try:
            s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                              exposed_melds=exposed, gangs=gangs)
        except ValueError:
            continue
        w = _before_w(rem, s, exposed, gangs)
        # −w 即取 w 最大：同 s 组里比较 waits/ukeire 谁更高
        if best is None or (s, -w) < (best[1], -best[2]):
            best = ((s, -w), s, w, rem)
    if best is None:
        return None, None, None
    return best[1], best[2], best[3]


# ===========================================================================
# K2 副露谓词
# ===========================================================================
def want_claim_k(hand13, offer, kind, exposed=0, gangs=0, chi_pair=None):
    """K2 判据：本次(facing offer)副露到底划不划算。返回 bool。

    before：sb = exact_shanten(hand13, e, g)；wb 按 sb(0=waits 否则一步有效)。
    after ：peng 摘 2×offer / gang_ming 摘 3×offer / chi 摘 chi_pair(2 张) 得
            长 14−3(e+1)−g 的 overfull → _min_after 得 sa/wa。规则：
            sa<sb 要、sa==sb 要当且仅当 wa>wb、sa>sb 不要。
    长度/ValueError/offer 为白/候选不足 → False。
    """
    if not isinstance(hand13, (list, tuple)) or not hand13:
        return False
    if offer == "白":
        return False
    e, g = int(exposed or 0), int(gangs or 0)
    h = list(hand13)
    if len(h) != 13 - 3 * e - g:
        return False
    try:
        sb = exact_shanten(h, qidui=(e == 0 and g == 0),
                           exposed_melds=e, gangs=g)
    except ValueError:
        return False
    if kind == "peng":
        if h.count(offer) < 2:
            return False
        for _ in range(2):
            h.remove(offer)
        ne, ng = e + 1, g
    elif kind == "gang_ming":
        if h.count(offer) < 3:
            return False
        for _ in range(3):
            h.remove(offer)
        ne, ng = e + 1, g + 1
    elif kind == "chi":
        if not chi_pair:
            return False
        for tt in chi_pair:
            if h.count(tt) <= 0:
                return False
            h.remove(tt)
        ne, ng = e + 1, g
    else:
        return False
    sa, wa, _rem = _min_after(h, ne, ng)
    if sa is None:
        return False
    wb = _before_w(hand13, sb, e, g)
    if sa == sb:
        return wa is not None and wb is not None and wa > wb
    if sa < sb:
        return True
    return False


# ===========================================================================
# K1 弃牌键（覆盖 SpeedE._best_discard_honor 的第二键，末键孤字/留摸不变）
# ===========================================================================
def _best_discard_k(hand, drawn, exposed, gangs):
    """弃牌：向听最小 → s==0 等待/s>=1 ukeire 最大 → 孤字优先 → 保留刚摸。

    与 SpeedE._best_discard_honor 的唯一差别在第二键（ukeire；SpeedE 此处用 0）。
    正确性需全候选比较，故即便最小向听组有 tie 也只对它付 ukeire（抽短样快）。
    """
    if not hand:
        return None
    drawn = drawn or None
    best_s = None
    cand = []                                   # [(s, d, rem)]
    for d in sorted(set(hand)):
        rem = list(hand)
        rem.remove(d)
        try:
            s = exact_shanten(rem, qidui=(exposed == 0 and gangs == 0),
                              exposed_melds=exposed, gangs=gangs)
        except ValueError:
            continue
        if best_s is None or s < best_s:
            best_s = s
            cand = [(s, d, rem)]
        elif s == best_s:
            cand.append((s, d, rem))
    if not cand:
        return _best_discard(hand, drawn, exposed, gangs)
    best_d, best_key = None, None
    for s, d, rem in cand:
        if s == 0:
            w = len(waits(rem, exposed_melds=exposed, gangs=gangs))
        else:
            w = effective_tiles(rem, exposed, gangs)
        key = (s, -w, 0 if d in HONOR else 1, -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_d = key, d
    return best_d if best_d is not None else hand[0]


# ===========================================================================
# 类
# ===========================================================================
_WARMUP_BUDGET_S = 0.6        # 整段预热总墙钟上限（避免冷进程首拆解巨慢时拖垮构造）


def _warmup(decider, n=30):
    """构造至多 n 手随机合法 14 张暗牌各跑一次弃牌决策，预热引擎计数缓存。

    SpeedK 冷启动首决策 84ms–1s+（真机窗口 1s 有超时风险）源于引擎 _shanten_counts
    @lru_cache 空转：新进程下各手拆解 _iter_decompositions 需递归全量枚举。这里用
    确定性随机源 random.Random(0xC007) 摊开不同计数向量、兼覆数牌/白(财神)万能路径，
    尽早把向听与 waits 判定写进 lru，命中后首决策压回暖态（4–10ms）。

    用真实 decide 的本人回合弃牌支（含 ukeire 计算，与首决策同路径）。逐手手牌是
    全 range 随机合法 14 张（各牌 ≤4，可含白）；随机向听偏高手牌的 cold 拆解可到数百
    ms/手 —— 若 30 手全做会在冷构造里烧数十秒（比要规避的首决策超时更糟），故加
    _WARMUP_BUDGET_S 总墙钟护栏：预算耗尽即停，构造开销总被压在亚秒量级（尽力而为、
    预算内能预热多少算多少）。异常一律静默吞掉。仅 SpeedK 实例构造时调用。
    """
    pool = (["%d%s" % (num, s) for s in "wbt" for num in range(1, 10)]
            + list("东南西北中发白"))
    r = random.Random(0xC007)
    deadline = time.monotonic() + _WARMUP_BUDGET_S
    for _ in range(max(0, int(n or 0))):
        if time.monotonic() >= deadline:      # 预算用尽：停（构造不能被拖垮）
            break
        try:
            h = []
            while len(h) < 14:
                t = r.choice(pool)
                if h.count(t) < 4:            # 各牌 ≤4（物理可持上限）
                    h.append(t)
            view = {
                "seat": 0, "phase": "draw", "turn": 0,
                "responding_seats": [],
                "drawn_tile": h[-1],          # 末张视为刚摸
                "my_hand": list(h),
                "melds": [],
                "offer_tile": None,
                "god": {},                    # 无抓打
                "river": [],
                "can_gang": False,
                "scores": None,
            }
            decider.decide(view)
        except Exception:
            pass


def _best_chi_pair(hand, offer, exposed, gangs):
    """从 hand 可得吃组合里选出副露后最优（向听最小、same 取进张大）。

    返回 chi_pair；没有可用组合回 None。
    """
    if offer == "白":
        return None
    out = list(hand)
    best = None
    for pair in _chi_pairs(list(hand), offer):
        rem = list(out)
        ok = True
        for tt in pair:                          # 摘每张一颗（chi 用法）
            try:
                rem.remove(tt)
            except ValueError:
                ok = False
                break
        if not ok:
            continue
        ne, ng = exposed + 1, gangs
        sa, wa, _ = _min_after(rem, ne, ng)
        if sa is None:
            continue
        # −wa 即取 wa 最大：同向听组里挑进张更大的 chi 组合
        if best is None or (sa, -wa) < (best[0], -best[1]):
            best = (sa, wa, pair)
    return best[2] if best else None


class SpeedK(SpeedE):
    """SpeedE + (K1 精确有效牌 tie) + (K2 副露 ukeire 判据)。"""

    def __init__(self, name="speedK"):
        super().__init__(name)
        # 构造即预热引擎计数缓存（尽力压低冷启动首决策，见 _warmup docstring）
        try:
            _warmup(self)
        except Exception:
            pass

    def decide(self, view):
        offer = view.get("offer_tile")
        # ---- 窗口：碰 / 直杠(peng 分支) / 吃 → K2 判据；其余回父类 ----
        if window_pending(view) and offer:
            if offer == "白":
                return {"action": "pass", "tile": ""}   # 财神 offer 拒副露
            hand = list(view.get("my_hand") or [])
            exposed, gangs = _melds_info(view)
            phase = view.get("phase")
            if phase == "response_peng":
                cnt = hand.count(offer)
                if cnt >= 3 and want_claim_k(hand, offer, "gang_ming",
                                             exposed, gangs):
                    return {"action": "gang", "tile": offer}
                if cnt >= 2 and want_claim_k(hand, offer, "peng",
                                             exposed, gangs):
                    return {"action": "peng", "tile": offer}
                return {"action": "pass", "tile": ""}
            if phase == "response_chi":
                pair = _best_chi_pair(hand, offer, exposed, gangs)
                if pair and want_claim_k(hand, offer, "chi", exposed, gangs,
                                         chi_pair=pair):
                    return {"action": "chi", "tile": offer}
                return {"action": "pass", "tile": ""}
            return super().decide(view)
        # ---- 本人回合：可胡即胡 / 抓打圈 / K1 弃牌 ----
        if my_turn(view):
            hand = list(view["my_hand"])
            melds = view.get("melds") or []
            exposed = len(melds)
            gangs = sum(1 for m in melds if m["type"] == "gang")
            drawn = view.get("drawn_tile")
            if not hand:
                return None
            try:
                from mahjong.hu import is_win
                if is_win(hand, exposed_melds=exposed, gangs=gangs) and drawn:
                    return {"action": "hu", "tile": ""}
            except ValueError:
                pass
            if view.get("god", {}).get("catch_play") and drawn:
                return {"action": "discard", "tile": drawn}
            discarded = _best_discard_k(hand, drawn, exposed, gangs)
            return {"action": "discard", "tile": discarded}
        # 其余（含无 offer 的非窗口他人回合）→ 事件 pass / 无提交
        return super().decide(view)
