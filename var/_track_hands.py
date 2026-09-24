# -*- coding: utf-8 -*-
"""**四家手牌跟踪器（含副露）** —— 给 selfev/其它离线分析用。
逐事件维护 (hand, e_cnt, g_cnt, meld_tiles)，并做长度一致性自检。
用法：
    from _track_hands import track
    st = track(evs)          # st[i] = [(hand,e,g,melds) x4]，表示"处理完第 i 个事件后"的状态
"""
import collections

def track(evs, start=None):
    # ★ 必须用该局的 start_hands 起手（否则长度自检全 FAIL —— 第一版就踩了这个）
    hands=[list(x or []) for x in (start if start else [[],[],[],[]])]
    e=[0]*4; g=[0]*4
    ml=[collections.Counter() for _ in range(4)]
    states=[]
    def snap():
        return [(list(hands[s]), e[s], g[s], dict(ml[s])) for s in range(4)]
    for ev in evs:
        states.append(snap())
        t=ev.get("type"); s=ev.get("seat")
        if s is None or not (0<=s<4): continue
        d=ev.get("data") or {}
        if t=="tile_drawn":
            tl=ev.get("tile")
            if tl: hands[s].append(tl)
        elif t=="tile_discarded":
            tl=ev.get("tile")
            if tl in hands[s]: hands[s].remove(tl)
        elif t=="chi":
            tiles=d.get("tiles") or []
            add=[x for x in tiles if x and x!=ev.get("tile")]
            for x in add:
                if x in hands[s]: hands[s].remove(x)
                ml[s][x]+=1
            if ev.get("tile"): ml[s][ev["tile"]]+=1
            e[s]+=1
        elif t=="peng":
            tl=ev.get("tile")
            for _ in range(2):
                if tl in hands[s]: hands[s].remove(tl)
            if tl: ml[s][tl]+=3
            e[s]+=1
        elif t=="gang":
            kind=d.get("kind"); tl=ev.get("tile")
            if kind=="bu":
                # R922 FIX: 加杠 = 已有【碰】的 3 张 -> 4 张。
                #   旧实现无条件 ml+=4（叠加在碰的 3 上 => 同一张牌记 7 份），且 e-=1。
                #   正确约定（与 meld_ukeire_audit 的 ex=nm+ng 一致）：
                #   e = **面子槽总数（含杠）**，g = **杠数**（每杠多 1 张），恒有 手牌长 == 13-3e-g。
                if tl in hands[s]: hands[s].remove(tl)
                if tl: ml[s][tl]+=1          # 3 -> 4
            else:
                # R922 FIX2: 暗杠手里持 4 张；明杠是手里 3 张 + 副露 1 张。
                #   旧实现对两者都扣 3 ⇒ 暗杠第 4 张留在手里又进副露（同一张记 5 份）。
                _need = 4 if kind == "an" else 3
                for _ in range(_need):
                    if tl in hands[s]: hands[s].remove(tl)
                if tl: ml[s][tl]+=4
                e[s]+=1
            g[s]+=1
    return states

def check(sh4, evs):
    """一致性自检：返回 (ok, bad_reason)。在每个'摸牌前'状态，手的长度应 == 13-3e-g。

    R922: 该式仅在 **e = 面子槽总数（含杠）、g = 杠数** 的约定下成立；旧 track 对杠不增 e
    （加杠还 e-=1）⇒ 有杠局恒 FAIL（实测 0.00% 通过）。现已按上述约定修正。
    """
    st=track(evs, sh4)
    for i,ev in enumerate(evs):
        if ev.get("type")!="tile_drawn": continue
        s=ev.get("seat")
        if s is None: continue
        if st[i][s][0] is None: continue
        h,e,g,_=st[i][s]
        if len(h)!=13-3*e-g:
            return False, "idx=%d seat=%d len=%d expect=%d"%(i,s,len(h),13-3*e-g)
    return True, ""
