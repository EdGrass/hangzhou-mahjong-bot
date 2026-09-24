# -*- coding: utf-8 -*-
"""Hybrid /state predicate: is the seq=0 snapshot alone enough to decide RIGHT NOW?

Context (bot/game.py:109-119 + R1068): with the 2-hop path every decision costs
2x /state and the platform's token bucket queues ~625 ms each => ~1.25 s per cycle >
the 1 s claim window => claims arrive late (historically 67% of 吃 and 78% of 碰 were
409-rejected; today ~20% of legal 碰 windows get no in-time response).
The single-hop fast path (`HM_FAST_STATE=1`) halves the demand but pushed the DISCARD
409 rate to 14.5% because the snapshot does not always carry `drawn_tile`.

`snapshot_covers()` is the pure decision rule for the hybrid fix: take the snapshot-only
path only when it carries every field the CURRENT phase needs; otherwise the caller
falls back to the second (incremental) /state call.  Keeping it pure makes it unit
testable before any production edit.
"""
from __future__ import annotations

REQUIRED_COMMON = ("my_hand", "melds")


def snapshot_covers(snap, seat=None):
    """Return (ok, reason) for deciding from this snapshot alone.

    Requirements by phase:
      draw / deal        : my_hand, melds, and a non-empty drawn_tile when it is our
                           turn (the discarded tile must come from the drawn tile set)
      response_peng      : my_hand, melds, offer_tile, and our seat in responding_seats
      response_chi       : same as response_peng
      settled / finished : always ok (no decision needed)
    """
    if not isinstance(snap, dict):
        return False, "no_snapshot"
    phase = str(snap.get("phase") or "")
    if phase in ("finished", "settled", "closed", "void"):
        return True, "terminal"
    for k in REQUIRED_COMMON:
        if snap.get(k) is None:
            return False, "missing_" + k
    my_seat = snap.get("seat", seat)
    if phase in ("draw", "deal"):
        if my_seat is not None and snap.get("turn") == my_seat:
            dt = snap.get("drawn_tile")
            if not dt:
                return False, "draw_needs_drawn_tile"
        return True, "draw_ok"
    if phase.startswith("response_"):
        # 快照从不带 offer_tile：窗口必由 turn 座弃牌触发，牌面在 last_discard
        # （game.py 的视图构造同样用 last_discard 兜底）⇒ 两者取其一即可判定。
        if not (snap.get("offer_tile") or snap.get("last_discard")):
            return False, "response_needs_offer_tile"
        rs = snap.get("responding_seats")
        if rs is None:
            return False, "response_needs_responding_seats"
        if my_seat is not None and my_seat not in rs:
            return False, "response_seat_not_listed"
        return True, "response_ok"
    return True, "other_phase"
