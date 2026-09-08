# -*- coding: utf-8 -*-
"""SpeedV —— SpeedE + 真机 river-aware 舍张（河见死等待/死进张剔除）。

SpeedV 与 SpeedE/SpeedU(K1) 的唯一差异 = 把〔已见牌〕(公开弃牌河)纳进进度度量：
等待/有效牌只在"该牌物理未摸完（已见 < 4 张）"时才计入 —— 真机公开弃牌皆见，
河见满 4 的 等待/进张 类别已不可能再摸到，应整体剔除（死等）。

- 弃牌：主键 exact_shanten；同最小向听组再比"活等待/活有效牌"——s==0 用
  _live_waits(rem, seen)（waits 中 seen[t]<4 的类数）、s>=1 用 _live_effective
  （摸 t 可降向听且 seen[t]<4 类数）；末键孤张字牌优先/保留刚摸不变 == SpeedE。
- 窗口/副露/胡优先/抓打圈一律 super()/继承 SpeedE（不覆盖 = 副露原判据）。
- 空河退化：河全空时 seen[t]=手牌持有数，_live==_same 速与原 waits/effective，
  SpeedV 等价于 SpeedK 的 K1(=SpeedU) 键序（而非 SpeedE；见 _live_* 推导）。

财神=白板（百搭）；`view["river"]` = 当局公开弃牌河（round 内累积，见
bot/game.py：game 层已把 tile_discarded 公开牌面 append 进 river）。

对比参考：
  SpeedX2/SpeedG 当年对"听牌等待扣已见"的尝试（C002，L1 DRAW）只对 s==0
  waits 扣；本类把 seen 扣减统一覆盖 s>=1 有效牌，并对 sim/真机口径保持一致。
"""
from __future__ import annotations

import os  # noqa: F401（HM_VLOG 执行验证插桩）

from mahjong.hu import is_win  # noqa: F401
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn
from .speed import HONOR, _best_discard  # noqa: F401
from .speede import SpeedE
from .speedk import _candidate_tiles, _plausible_draw


# ===========================================================================
# 纯函数（单测钉死）
# ===========================================================================
def _seen(hand, river):
    """已见计数：手牌 + 公开河（真机口径：公开弃牌皆见）。返回 tile->count dict。"""
    seen = {}
    for t in list(hand) + list(river or []):
        seen[t] = seen.get(t, 0) + 1
    return seen


def _live_waits(hand13, e, g, seen):
    """已听手（13−3e−g 张）的【活】等待类数：waits 中 seen[t]<4 者才计入。

    waits() 只排除"手牌同种已满 4 张"，不含河口径；故还需按 seen 再剔除
    （河贡献把某等待牌推到 4= 死等，摸不到且他人也不可再打出 = 永不和）。
    """
    if len(hand13) != 13 - 3 * e - g:
        return 0
    try:
        raw = waits(hand13, exposed_melds=e, gangs=g)
    except ValueError:
        return 0
    cnt = 0
    for t in raw:
        if seen.get(t, 0) < 4:
            cnt += 1
    return cnt


def _live_effective(hand13, e, g, seen):
    """仿 speedk.effective_tiles 的"摸 t 后向听下降"计数，但 t 仅在物理可摸
    （seen[t]<4）时计入。复用 _candidate_tiles/_plausible_draw 预过滤。

    财神(白)口径：_plausible_draw 对白无条件放行的修复语义保留（白作候选），
    但白也遵循 seen 检查 —— 河/手已见满 4 的白同样摸不到、不得计为有效进张
    （白不特殊，统一在此层拦）。
    """
    e, g = int(e or 0), int(g or 0)
    if len(hand13) != 13 - 3 * e - g:
        return 0
    try:
        cur = exact_shanten(hand13, qidui=(e == 0 and g == 0),
                            exposed_melds=e, gangs=g)
    except ValueError:
        return 0
    if cur == 0:
        return 0
    possible = _plausible_draw(hand13)
    cnt = 0
    for t in _candidate_tiles(hand13):
        if seen.get(t, 0) >= 4:          # 已见满 4：物理摸不到（含白）→ 不计
            continue
        if hand13.count(t) >= 4:         # 冗余防御（seen 已含手牌，见上）
            continue
        if not possible(t):              # 无结构性补强可能 → 无法降向听
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


def _live_w_of(hand13, s, e, g, seen):
    """某手在 (暴露,杠) 口径下"s==0 -> 活等待数，否则活有效牌数"。"""
    if s == 0:
        return _live_waits(hand13, e, g, seen)
    return _live_effective(hand13, e, g, seen)


def _best_discard_v(hand14, drawn, exposed, gangs, seen):
    """弃牌：向听最小 → (s==0 活等待/s>=1 活有效牌) 最大 → 孤字优先 → 留摸。

    &注意 seen 口径&：seen 应描述"判断候选弃后的 rem 活等待/有效牌时，哪些牌已
    不再可摸"。弃牌 d 之后 d 也公开（入河），但 d 不在 rem —— 直接取
    "hand(弃前，含 d) + river 作 seen"对候选间 w 的相对单调性无扭曲（d 一旦
    公开，seen[d] 由 hand 的实例转为河实例，总数不变；其余牌不变），故这里沿用
    调用方 SpeedV 传入的 seen（= 弃前整手 + 河）即可，不必为每个候选重算。

    与 SpeedE._best_discard_honor 相比唯一差别 = 第二键用活度度量；其余同构。
    正确性需全候选比较：先取最小向听候选组（含 wait-tie），再只对其付活度成本。
    """
    if not hand14:
        return None
    drawn = drawn or None
    best_s = None
    cand = []                      # [(s, d, rem)]
    for d in sorted(set(hand14)):
        rem = list(hand14)
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
        return _best_discard(hand14, drawn, exposed, gangs)
    best_d, best_key = None, None
    for s, d, rem in cand:
        w = _live_w_of(rem, s, exposed, gangs, seen)
        key = (s, -w, 0 if d in HONOR else 1, -1 if d == drawn else 0)
        if best_key is None or key < best_key:
            best_key, best_d = key, d
    return best_d if best_d is not None else hand14[0]


# ===========================================================================
# 类
# ===========================================================================
class SpeedV(SpeedE):
    """SpeedE + 真机 river-aware 舍张（河见死等/死进张剔除）。窗口/副露=SpeedE。"""

    def __init__(self, name="speedV"):
        super().__init__(name)

    def decide(self, view):
        if not my_turn(view):
            # 窗口/副露/非本人回合 100% 继承 SpeedE（即 SpeedCore 原判据，K2 类
            # 激进覆盖一律不叠加）；胡优先/抓打由父类 decide 一并处理。
            return super().decide(view)
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
        if not hand:
            return None
        if view.get("god", {}).get("catch_play") and drawn:
            return {"action": "discard", "tile": drawn}
        river = list(view.get("river") or [])
        seen = _seen(hand, river)          # 已见 = 弃前整手 + 河
        try:
            tile = _best_discard_v(hand, drawn, exposed, gangs, seen)
        except ValueError:
            tile = _best_discard(hand, drawn, exposed, gangs)
        if os.environ.get("HM_VLOG") == "1":
            # 执行验证插桩：若 river-aware 选择与 raw（无河）K1 选择不同 → 计数
            try:
                from .speedk import _best_discard_k as _raw_k1
                raw = _raw_k1(hand, drawn, exposed, gangs)
                if raw is not None and raw != tile:
                    from .util import log as _log
                    _log("[vlog] V-diverged live=%s raw=%s river_len=%d",
                         tile, raw, len(river))
            except Exception:
                pass
        return {"action": "discard", "tile": tile}
