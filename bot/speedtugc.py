# -*- coding: utf-8 -*-
"""SpeedTUGC —— C045 真机候选：SpeedTUG + 「未听时副露必须严格改善向听」。

来源（2026-09-11，E021 门禁口径更正后）：
- 把 sim 门禁对手从 3×SpeedTM（弱场）换成 3×SpeedTUG（强场=我方同级）后，
  同一批候选结果完全翻转：C045 代理 0.409 vs 基线 0.334（+0.075，5 seed 稳定）；
  听牌 66.2% vs 58.8%、胡 32.5% vs 25.3%、副露 1.20 vs 1.55。
- 共同点「少副露」与真机事实吻合：顶级席副露 1.128/局 < 我方 1.241/局（E020）。

与 SpeedTUG 的唯一差异 = 窗口判据（before > 0 时）：
  原 SpeedTU：want_claim_mild(allow_equal=True)  —— 向听【不恶化】即副露；
  本候选：   允许 equal=False                —— 向听必须【严格下降】；
  已听(before == 0) 分支与 SpeedTUG 完全一致（C019 换听升级：副露后仍听且等待更多）。
其余 100% 继承 SpeedTUG（出牌 tie、C036 弃胡换爆头、胡/抓打圈逻辑）。
"""
from __future__ import annotations

from mahjong.hu import is_win
from mahjong.shanten import waits
from mahjong.shanten_exact import shanten as exact_shanten, _qidui_shanten

from .model import my_turn, window_pending
from .speed import _chi_pairs, _melds_info
from .speedm import want_claim_mild
from .speedt import _best_discard_t
from .speedtu import _best_after_claim
from .speedtug import SpeedTUG


def want_claim_strict_meld(view, kind, pair=None):
    """未听：向听必须严格下降才副露；已听：沿用 C019 换听升级。"""
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
        return want_claim_mild(view, kind, allow_equal=False)
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


class SpeedTUGC(SpeedTUG):
    # 弃牌搜索里「白板是否可当面子牌用」。True = 允许（现状）；False = 白只作万能听
    # （不补面子）⇒ 搜索倾向**保留白板**、朝「4 面子 + 白孤 = 爆头（摸任意即胡）」走。
    # 抽成类属性是为了让候选只改一行（见 bot/speedc131.py），避免复制 decide 逻辑。
    GOD_MELD = True
    # SELF_GANG：是否在**自己的摸牌回合**考虑**暗杠/补杠**。
    #   False = 现状（本族**完全没有**自杠路径：唯一的 gang 在 response_peng，且被
    #           「向听必须严格下降」挡住——杠不改变面子数，永远不可能满足该条件）。
    #   True  = 见 _maybe_gang()。真机实测：我方 257,284 个摸牌决策里可杠机会 2,897 个，
    #           实际杠 21 个（0.7%），speedtugc 为 **0/1,373**；而全场 杠/轮 0.0375–0.0887。
    SELF_GANG = False
    # 「最后 10 墩禁止杠」的保守前置线：一局可摸 ≈64 张（136-13*4 的墙里最后 20 张保底），
    # 用「本局公开弃牌总数」当摸牌数的廉价代理（每次弃牌≈一次摸牌），留足余量。
    # 注意：view["turn"] 是**行动座位号**不是巡次，不能用它当时间守卫。
    SELF_GANG_MAX_RIVER = 56

    def __init__(self, name="speedTUGC"):
        super().__init__(name)

    def _want_claim(self, view, kind, pair=None):
        """窗口（碰/吃/明杠）判据的**唯一钩子**（子类只改这一处，保证单变量）。

        默认 = 本族一直以来的严格判据：副露后向听必须**严格下降**
        （见 `want_claim_strict_meld`）。子类可换成"质量感知"版本。
        """
        return want_claim_strict_meld(view, kind, pair)

    def _maybe_gang(self, hand, exposed, gangs, melds, turn=None,
                    river_len=None, god=None, seat=-1):
        """自己的摸牌回合：有可杠的牌就返回 {"action":"gang","tile":...}，否则 None。

        机械依据：全场同种只有 4 张 ⇒ 手里同种 **4 张**时第 4 张**无法再参与任何面子或对子**
        （3 张已成刻子），补杠同理（碰已成型，第 4 张是死牌）。杠 = 把死牌换成**一次补牌**。

        唯一真实代价：杠会**关闭七对路线**（七对 ×2、豪华七对 ×4）。所以按**路线**判断，
        而不是做长度敏感的向听手术：
          · 已有副露 ⇒ 七对不可能 ⇒ 直接杠；
          · 门清 ⇒ 比较 **一般形向听 g_sh** 与 **七对向听 q_sh**（都在 13 张口径上算，
            对每个可弃牌取最优）：
              - g_sh == 0（已听牌）⇒ 杠是免费的补牌且不破坏当前听形 ⇒ 杠；
              - q_sh > g_sh + 1（七对明显更差）⇒ 不心疼那条路线 ⇒ 杠；
              - 否则保留七对路线，不杠。
        另：白板不能杠；river_len 到线不做（规避「最后 10 墩禁止杠」，服务端才是权威）。
        """
        if not self.SELF_GANG:
            return None
        if river_len is not None and int(river_len) >= int(self.SELF_GANG_MAX_RIVER):
            return None          # 可能已进最后 10 墩，不冒被判 409 的险
        from collections import Counter
        cnt = Counter(t for t in hand if t != "白")
        cands = []
        for t, n in cnt.items():
            if n >= 4:
                cands.append((0, t))                       # 暗杠优先
        pengs = set()
        for m in (melds or []):
            if isinstance(m, dict) and m.get("type") == "peng" and m.get("tile"):
                pengs.add(m["tile"])
        for t in pengs:
            if t != "白" and cnt.get(t, 0) >= 1:
                cands.append((1, t))                       # 补杠次之
        if god and god.get("catch_play"):
            # 抓打圈（指南）：其余玩家不能吃/碰/**明杠**，但**暗杠与自摸胡**允许；
            # 打财神者本人不受此限。补杠是否算「明杠」指南未写明 ⇒ 非豁免方只做暗杠。
            if int(god.get("god_discarder_seat", -1)) != int(seat):
                cands = [c for c in cands if c[0] == 0]
        if not cands:
            return None
        if exposed > 0:                                    # 七对已不可能
            cands.sort()
            return {"action": "gang", "tile": cands[0][1]}
        # 门清：13 张口径下比较一般形与七对
        import collections as _c
        from mahjong.tiles import counts_of
        try:
            g_best, q_best = 99, 99
            for d in sorted(set(hand)):
                rem = list(hand)
                rem.remove(d)
                g = exact_shanten(rem, qidui=False, exposed_melds=0, gangs=0)
                q = _qidui_shanten(counts_of(list(rem)))
                g_best = min(g_best, g)
                q_best = min(q_best, q)
        except Exception:
            return None
        if g_best == 0 or q_best > g_best + 1:
            cands.sort()
            return {"action": "gang", "tile": cands[0][1]}
        return None

    def _pick_discard(self, hand, drawn, exposed, gangs, view=None):
        """弃牌选择的**唯一钩子**（子类只改这一处，保证单变量）。

        view 传入是为了让子类能看到**公开信息**（弃牌河 + 四家副露），
        用于「真进张」的 live 张数（`bot/ukeire.py`）。基线实现不用它。
        """
        return _best_discard_t(hand, drawn, exposed, gangs, god_meld=self.GOD_MELD)

    def decide(self, view):
        if window_pending(view) and view.get("offer_tile"):
            offer = view["offer_tile"]
            cnt = view["my_hand"].count(offer)
            if view["phase"] == "response_peng":
                if cnt >= 3 and self._want_claim(view, "gang_ming"):
                    return {"action": "gang", "tile": offer}
                if cnt >= 2 and self._want_claim(view, "peng"):
                    return {"action": "peng", "tile": offer}
                return {"action": "pass", "tile": ""}
            if view["phase"] == "response_chi":
                hand = list(view["my_hand"])
                exposed, gangs = _melds_info(view)
                chi_cnt = sum(1 for m in (view.get("melds") or [])
                              if isinstance(m, dict) and m.get("type") == "chi")
                if chi_cnt < 2 and len(hand) == 13 - 3 * exposed - gangs:
                    for pair in _chi_pairs(hand, offer):
                        if self._want_claim(view, "chi", pair):
                            return {"action": "chi", "tile": offer}
                return {"action": "pass", "tile": ""}
            return {"action": "pass", "tile": ""}
        if my_turn(view):
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
                return super().decide(view)          # C036 弃胡换爆头
            if hand:
                # 自杠先于「抓打圈强制摸切」：指南明确「仅暗杠与自摸胡」在圈内被允许，
                # 而 _maybe_gang 在圈内(非豁免方)只返回暗杠 ⇒ 不会违规，只多赚一次补牌。
                g = self._maybe_gang(hand, exposed, gangs, melds, view.get("turn"),
                                     river_len=view.get("river_len"),
                                     god=view.get("god"), seat=view.get("seat", -1))
                if g is not None:
                    return g
                if view.get("god", {}).get("catch_play") and drawn:
                    return {"action": "discard", "tile": drawn}
                try:
                    tile = self._pick_discard(hand, drawn, exposed, gangs, view=view)
                except Exception:
                    from .speed import _best_discard
                    tile = _best_discard(hand, drawn, exposed, gangs)
                return {"action": "discard", "tile": tile}
            return None
        return super().decide(view)
