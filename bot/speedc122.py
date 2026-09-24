# -*- coding: utf-8 -*-
"""C122 学生策略：C073-w4 弃牌网 + **副露门控放宽一档**（单变量变体）。

来源（2026-09-15，tools/profile_audit.py，同房配对 n=707 房次）：
- 我方 副露/轮 **0.866**，达线对手（77 人）**1.07+**，顶级 1.09-1.32；
  逐房配对差 **+0.203/轮，t=11.81**（72% 的房间对手副露更多），分/轮差 +0.610，t=5.05。
- 该结论**推翻 E020**（E020 记「我方 1.241 / 顶级 1.128」→ 顶级副露更少）；
  本工具重算的我方每房总分与 var/auto_ranking.jsonl 逐房一致 287/289（99.3%），
  而 E020 的顶级值 1.128 与本次独立复算 1.143 吻合、我方值 1.241 与 0.866 不符。
  → 现行 SpeedTUGC 的「未听副露必须严格下降向听」（其设计依据正是 E020 的
    「顶级副露比我们少」）建立在一个**方向相反**的测量上。

与 speedc073w4 的**唯一差异** = 未听(before>0)时的窗口判据：
  SpeedTUGC：want_claim_mild(allow_equal=False) —— 向听必须【严格下降】；
  本策略：  want_claim_mild(allow_equal=True)  —— 向听【不恶化】即副露。
已听(before==0)仍走 C019 换听升级（爆头 34 张万能听必然通过），
出牌/抓打圈/弃胡换爆头 100% 继承 C068/C073（学生网与候选区间不变）。

风险与判据（务必遵守 docs/iter/reports/field-audit-20260915.md §6）：
- sim 均值与本策略族长期不迁移（sim Δ+3~+16/房 vs 真机房 SD≈146），
  **sim 通过不代表可用**；必须真机 A/B ≥40 房，用 tools/profile_audit.py 看
  「副露/轮 ↑ 且 爆头/胡 不下降 且 分/轮 ↑」三项。
- 回滚线：累计 ≥15 房净胜显著低于当日基线（>60/房）→ 立即回退 speedc073w4。
"""
from __future__ import annotations

from mahjong.hu import is_win
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten

from .model import my_turn, window_pending
from .speed import _chi_pairs, _melds_info
from .speedc068 import C068Policy
from .speedt import _best_discard_t
from .speedtu import _best_after_claim


def want_claim_relaxed(view, kind, pair=None):
    """未听：向听不恶化(allow_equal)即副露；已听：仍要求 C019 换听升级。"""
    offer = view.get("offer_tile")
    if not offer:
        return False
    hand = list(view["my_hand"])
    exposed, gangs = _melds_info(view)
    if len(hand) != 13 - 3 * exposed - gangs:
        return False
    try:
        before = exact_shanten(hand, qidui=(exposed == 0 and gangs == 0),
                               exposed_melds=exposed, gangs=gangs)
    except ValueError:
        return False
    if before > 0:
        from .speedm import want_claim_mild
        return want_claim_mild(view, kind, allow_equal=True)
    after = _best_after_claim(hand, exposed, gangs, kind, offer, pair)
    if after is None:
        return False
    _, _, s_after, w_after, _bb = after
    if s_after != 0:
        return False
    try:
        w_before = len(waits(hand, exposed_melds=exposed, gangs=gangs))
    except ValueError:
        return False
    return w_after > w_before


class C122Policy(C068Policy):
    def __init__(self, name="speedc122", **kw):
        kw.setdefault("lo", 0)
        kw.setdefault("hi", 2)
        super().__init__(name=name, **kw)

    def decide(self, view):
        # 只接管窗口响应；出牌/胡/抓打圈仍走 C067/C068 学生网路径
        if window_pending(view) and view.get("offer_tile"):
            offer = view["offer_tile"]
            cnt = view["my_hand"].count(offer)
            if view["phase"] == "response_peng":
                if cnt >= 3 and want_claim_relaxed(view, "gang_ming"):
                    return {"action": "gang", "tile": offer}
                if cnt >= 2 and want_claim_relaxed(view, "peng"):
                    return {"action": "peng", "tile": offer}
                return {"action": "pass", "tile": ""}
            if view["phase"] == "response_chi":
                hand = list(view["my_hand"])
                exposed, gangs = _melds_info(view)
                chi_cnt = sum(1 for m in (view.get("melds") or [])
                              if isinstance(m, dict) and m.get("type") == "chi")
                if chi_cnt < 2 and len(hand) == 13 - 3 * exposed - gangs:
                    for pair in _chi_pairs(hand, offer):
                        if want_claim_relaxed(view, "chi", pair):
                            return {"action": "chi", "tile": offer}
                return {"action": "pass", "tile": ""}
            return {"action": "pass", "tile": ""}
        if not my_turn(view) and window_pending(view):
            return {"action": "pass", "tile": ""}
        return super().decide(view)
