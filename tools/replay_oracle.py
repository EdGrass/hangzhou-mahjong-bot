"""tools/replay_oracle —— 服务器复盘的离线决策 oracle（真实人类对局决策级评估）。

输入：服务器"复盘 JSON"（一场真实 4 人对局 = 一个文件，内含 16 局）。文件顶：
  {"blocks": [...], "rounds": [..], "seats":[{"user_id","name"}x4], "status"}
每个"逻辑局"由**若干个相邻 block** 组成（相邻 block 的 round_no 相同；同一局
events 被切成连续 block、块间 seq 连续不重叠），需把同一 round_no 相邻块的事件
按 seq 拼接成一局事件流。rounds[] 是每局的汇总（winner/dealer/is_draw 等）。
我方 = user_id == u_7a3fba48d70b（昵称 蔡宇欣），座位号每场 0/3 不同。

统计口径：
1) 事件流级重建【我方座位】的每一"摸牌后决策局面" = 我 tile_drawn 之后到
   我方下一次动作（tile_discarded / 局终胡）之前的 14 张快照；弃出的牌必须
   在手牌（校验失败打印并跳过该局）。抓打圈循弃白者本人摸至解除。
2) 用 run_bot.STRATEGY_FACTORIES 的策略（speedE/speedu/speedv/speedp/speedk）
   对每决策点重决策，分歧=动作+牌全等不一致。对"实际 hu"用 mahjong.fan.calc
   校验（g 值不正确仅告警并统计，不中止）。
3) 进度代理（仅 draw 自由弃牌、且 human 弃牌与 E 所选不同 → 同为弃）：
   弃后 exact_shanten 与活等待（剔除河见4）;报告差异的方向。
4) 触发统计：human 实胡次数/爆头/爆头且摸白/各策略重放时"杀白(财飘)"计数。

用法：
  python tools/replay_oracle.py --dir var/replays/t_dee58824c308 \
      [--strategies speedE,speedp] [--limit 2] [--json]
（在仓库根目录下运行，-X utf8）
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_THIS_DIR)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from mahjong.fan import calc as fan_calc                    # noqa: E402
from mahjong.hu import is_baotou                             # noqa: E402
from mahjong.shanten import waits                            # noqa: E402
from mahjong.shanten_exact import shanten as exact_shanten   # noqa: E402

MY_UID = "u_7a3fba48d70b"
WHITE = "白"


# ---------------------------------------------------------------------------
# 同一 round 相邻 block 归并成一局事件流
# ---------------------------------------------------------------------------
def group_blocks_into_rounds(file_data):
    groups = []
    for bb in file_data.get("blocks", []):
        rn = bb.get("round_no")
        if groups and groups[-1]["round_no"] == rn:
            groups[-1]["blocks"].append(bb)
        else:
            groups.append({"round_no": rn, "blocks": [bb]})

    out = []
    for g in groups:
        evs, start_hands, first = [], None, g["blocks"][0]
        for bb in g["blocks"]:
            evs.extend(bb.get("events", []))
            if start_hands is None:
                start_hands = bb.get("start_hands")
        evs.sort(key=lambda e: e.get("seq", 0))
        out.append({
            "round_no": g["round_no"],
            "dealer": first.get("dealer"),
            "start_hands": [list(h) for h in start_hands] if start_hands else None,
            "events": evs,
            "truncated": bool(any(b.get("truncated") for b in g["blocks"])),
        })
    return out


class SkipRound(Exception):
    """本局数据违反自检不变量 → 跳过整局并计数，不中断全量。"""


# ---------------------------------------------------------------------------
# 单局事件流重建（只精确维护我方座）
# ---------------------------------------------------------------------------
def replay_round(round_ev, my_seat):
    """重建该局【我方】每摸牌决策局面。返回 (decision_points, end_hand_len)。

    决策点字段：
      drawn        刚摸的牌
      my_hand      决策时刻 14 张（含刚摸）
      concealed13  摸牌前 13 张（= my_hand[:-1]，供爆头/胡校验）
      river        决策时刻弃牌河（含此前全部）
      catch_play   抓打圈激活且我方非弃白者
      baotou       爆头（摸牌前13任意摸皆胡）
      actual       我方实际动作 {"action":"discard|hu","tile":...}
    抛 SkipRound：手牌不变量违例（弃牌不在手、起手张数非法等）。

    说明（corpus 实测）：非庄起手 13 张；**当我是庄时** start_hands[我方] 已含
    首摸为 14 张（另三家 13）——庄的首弃发生在无 tile_drawn 事件、也不成"摸后
    决策局面"，直接以该 14 减一处理。
    """
    start_hands = round_ev.get("start_hands")
    if not start_hands or len(start_hands) != 4:
        raise SkipRound("start_hands 非 4 家")
    hand = [t for t in start_hands[my_seat]]
    dealer = round_ev.get("dealer")
    is_dealer = (dealer == my_seat)
    if len(hand) != 13 and not (is_dealer and len(hand) == 14):
        raise SkipRound("起手张数非法(须13,庄14): %d dealer=%s" %
                        (len(hand), is_dealer))
    river = []
    decision_points = []
    end_hand_len = len(hand)     # 会随事件变化，default 即最终（非法时抛）
    open_dec = None            # 当前"摸牌后未动作"的我方决策（候补,未定动作）
    last_white_discarder = None

    def clear_catch(seat):
        """弃白者本人下一次摸 → 抓打圈解除。"""
        nonlocal last_white_discarder
        if last_white_discarder is not None and seat == last_white_discarder:
            last_white_discarder = None

    for e in round_ev["events"]:
        typ = e.get("type")
        seat = e.get("seat")
        tile = e.get("tile")

        if typ == "tile_drawn":
            if seat == my_seat:
                hand.append(tile)                       # 13 -> 14
                # 抓打圈：若我恰为刚弃白者本人则已解除（一般我在牌河后才摸）
                clear_catch(my_seat)
                catch = (last_white_discarder is not None
                         and last_white_discarder != my_seat)
                if open_dec is not None:
                    raise SkipRound("我方连续摸却未弃（状态错乱）")
                try:
                    bao = is_baotou(hand[:-1], allow_qidui=True,
                                    exposed_melds=0, gangs=0)
                except ValueError:
                    bao = False
                open_dec = {
                    "drawn": tile, "my_hand": list(hand),
                    "concealed13": list(hand[:-1]), "river": list(river),
                    "catch_play": catch, "baotou": bao,
                }
            else:
                clear_catch(seat)          # 弃白者本人摸牌，抓打圈解除
        elif typ == "tile_discarded":
            river.append(tile)
            if seat == my_seat:
                if open_dec is None:
                    # 我当庄首弃（摸牌前，从起手13里弃一张）：非决策局面
                    if tile not in hand:
                        raise SkipRound("首弃 %s 不在手中 hand=%s" %
                                        (tile, sorted(hand)))
                    hand.remove(tile)
                    continue
                if tile not in hand:
                    raise SkipRound("弃 %s 不在手中 hand=%s" %
                                    (tile, sorted(hand)))
                hand.remove(tile)
                dp = open_dec
                open_dec = None
                dp["actual"] = {"action": "discard", "tile": tile}
                decision_points.append(dp)
            if tile == WHITE:
                last_white_discarder = seat
        elif typ == "chi":            # 我方从不（corpus 扫描），防御
            if seat == my_seat:
                raise SkipRound("我方吃（未预案,防错）")
        elif typ == "peng":
            if seat == my_seat:
                raise SkipRound("我方碰（未预案,防错）")
        elif typ == "gang":
            if seat == my_seat:
                raise SkipRound("我方杠（未预案,防错）")
        elif typ == "round_ended":
            # 我摸后未动作直至局终 → 若我胡该局则 actual=hu
            if open_dec is not None:
                if e.get("seat") == my_seat:
                    dp = open_dec
                    open_dec = None
                    dp["actual"] = {"action": "hu", "tile": ""}
                    decision_points.append(dp)
                    end_hand_len = len(hand)
                else:
                    # 局终胜者非我但有我未弃的开决策点：不应出现（我方摸后必弃
                    # 除非自摸胡）；若非自摸我胡则无 open。保守：跳过该局。
                    raise SkipRound("局终胜者非我而我方开决策点未动作")
            else:
                end_hand_len = len(hand)
            break                      # 一局事件到此结束
        elif typ in ("pass", "timeout", "game_ended"):
            pass                       # 不改我方牌河
        else:
            pass                       # 未知类型:静默容忍
    else:
        # for 循环自然结束仍未 round_ended：该局被截断，无法作为完整局使用
        if round_ev.get("truncated"):
            raise SkipRound("局 truncated 缺 round_ended")
        end_hand_len = len(hand)
    return decision_points, end_hand_len


# ---------------------------------------------------------------------------
# 工具 / 进度代理（本地纯实现，不耦合 tools/oracle_audit）
# ---------------------------------------------------------------------------
def _proxy(hand14_with_drawn, river, discard_tile):
    """弃牌后的进度：弃后的 exact_shanten 与活等待数（河见剔除 4 张）。
    返回 (s, live) 或 None（长度/非法）。exposed/gangs 恒 0。"""
    if discard_tile not in hand14_with_drawn:
        return None
    rem = [t for t in hand14_with_drawn]
    rem.remove(discard_tile)
    try:
        s = exact_shanten(rem, qidui=True, exposed_melds=0, gangs=0)
    except ValueError:
        return None
    live = 0
    if s == 0:
        try:
            ws = waits(rem, exposed_melds=0, gangs=0)
        except ValueError:
            ws = []
        seen = {}
        for t in list(rem) + list(river or []):
            seen[t] = seen.get(t, 0) + 1
        live = sum(1 for t in ws if seen.get(t, 0) < 4)
    return (s, live)


def make_view(dp, my_seat):
    return {
        "seat": my_seat, "phase": "draw", "turn": my_seat,
        "responding_seats": [],
        "drawn_tile": dp["drawn"],
        "my_hand": list(dp["my_hand"]),
        "melds": [],
        "god": {"baotou": dp["baotou"], "chain_count": 0,
                "piao_count": 0, "catch_play": dp["catch_play"]},
        "offer_tile": None,
        "river": list(dp["river"]),
    }


# ---------------------------------------------------------------------------
# 全量跑
# ---------------------------------------------------------------------------
def run(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="var/replays/t_dee58824c308")
    ap.add_argument("--file", default="")
    ap.add_argument("--strategies", default="speedE")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args(argv)

    from run_bot import STRATEGY_FACTORIES
    names = [n.strip() for n in ns.strategies.split(",") if n.strip()]
    out_names = []
    for n in names:
        if n not in STRATEGY_FACTORIES:
            raise SystemExit("未知策略: %s" % n)
        out_names.append(n)
    strats = [STRATEGY_FACTORIES[n]() for n in out_names]
    if not strats:
        raise SystemExit("无指定策略")

    files = [ns.file] if ns.file else sorted(
        glob.glob(os.path.join(ns.dir, "t_*.json")))
    if ns.limit:
        files = files[: ns.limit]

    agg = {
        "files": 0, "rounds": 0, "decision_points": 0,
        "self_check_fail": 0, "warn": 0,
        "hand_len_ok": 0, "hand_len_bad": 0,
        "human_hu": 0, "hu_ok": 0, "baotou": 0, "baotou_white": 0,
        "rounds_winner_self": 0,
    }
    div = {n: {"n": 0, "diff": 0, "by_phase": {}} for n in out_names}
    vsE = {n: {"n": 0, "diff": 0, "by_phase": {}}
           for n in out_names if n != "speedE"}
    discard_white = {n: 0 for n in out_names}
    proxy = {"n": 0, "agree": 0, "disagree": 0,
             "human_keeps_tenpai": 0, "E_keeps_tenpai": 0,
             "both_tenpai_pairs": 0, "sum_a_live": 0.0, "sum_e_live": 0.0}

    for path in files:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        seats = data.get("seats", [])
        my_seat = next((i for i, s in enumerate(seats)
                        if s.get("user_id") == MY_UID), None)
        if my_seat is None:
            print("[skip-file] %s: 未找到我方" % os.path.basename(path))
            continue
        agg["files"] += 1
        # 顶层 rounds 与我方座位对照（hu 局对照）
        agg["rounds_winner_self"] += sum(
            1 for r in data.get("rounds", [])
            if r.get("winner") == my_seat)

        for round_ev in group_blocks_into_rounds(data):
            try:
                dps, end_hand_len = replay_round(round_ev, my_seat)
            except SkipRound as ex:
                agg["self_check_fail"] += 1
                print("  [skip-round] %s r%s: %s" %
                      (os.path.basename(path), round_ev["round_no"], ex))
                continue
            # 局终我方手牌长度应合法：普通 13/14（无杠时）或本局已胡我方清下
            # （本 oracle 不跟踪副露，故只接受 13/14/12 底线以外计为不合法）。
            if end_hand_len in (13, 14):
                agg["hand_len_ok"] += 1
            else:
                agg["hand_len_bad"] += 1
            agg["rounds"] += 1
            agg["decision_points"] += len(dps)

            for dp in dps:
                act = dp["actual"]
                # 触发统计 —— 实际 hu
                if act["action"] == "hu":
                    agg["human_hu"] += 1
                    try:
                        fc = fan_calc(dp["concealed13"], dp["drawn"],
                                      {"count": 0, "piao": 0})
                    except ValueError:
                        fc = {"hu": False}
                    if fc.get("hu"):
                        agg["hu_ok"] += 1
                    else:
                        agg["warn"] += 1
                        print("  [warn] human hu 判定失败 r%s hand=" %
                              round_ev["round_no"],
                              dp["concealed13"] + [dp["drawn"]], "")
                    if dp["baotou"]:
                        agg["baotou"] += 1
                        if dp["drawn"] == WHITE:
                            agg["baotou_white"] += 1
                # 各策略重决策
                view = make_view(dp, my_seat)
                decided = {}
                for st, n in zip(strats, out_names):
                    try:
                        a = st.decide(view)
                    except Exception as e:      # noqa: BLE001
                        agg["warn"] += 1
                        a = None
                    decided[n] = a
                    if a is None:
                        continue
                    d = div[n]
                    d["n"] += 1
                    if a != act:
                        d["diff"] += 1
                        key = act["action"] if act["action"] in ("hu", "discard") \
                            else "other"
                        d["by_phase"][key] = d["by_phase"].get(key, 0) + 1
                    if a.get("action") == "discard" and a.get("tile") == WHITE:
                        discard_white[n] += 1

                # E 基准动作（供 vsE 与进度代理共用；decided 已含全部策略）
                ae = decided.get("speedE") if "speedE" in out_names else None

                # 候选 vs E 配对分歧（同一真机局面上两策略的差异——执行面宽度）
                if "speedE" in out_names and ae is not None:
                    for st, n in zip(strats, out_names):
                        if n == "speedE":
                            continue
                        a = decided.get(n)
                        if a is None:
                            continue
                        ve = vsE[n]
                        ve["n"] += 1
                        if a != ae:
                            ve["diff"] += 1
                            key = a.get("action", "?") if isinstance(a, dict) \
                                else "?"
                            ve["by_phase"][key] = ve["by_phase"].get(key, 0) + 1

                # 进度代理：draw 自由弃牌 && E 也弃 → 比较 (同择 / 异择)
                # 异择且弃后都进一步到听(向听0)：记活等待差 (E - actual)，
                # 正=实际保留的更少等待→E 在 ukeire 口径更优。
                if act["action"] == "discard" and ae is not None and \
                        ae.get("action") == "discard":
                    atile, etile = act["tile"], (ae.get("tile") or "")
                    if atile == etile:
                        proxy["n"] += 1
                        proxy["agree"] += 1
                        continue
                    pa = _proxy(dp["my_hand"], dp["river"], atile)
                    pe = _proxy(dp["my_hand"], dp["river"], etile)
                    proxy["n"] += 1
                    proxy["disagree"] += 1
                    if pa and pe:
                        sa, la = pa
                        se, le = pe
                        if sa == 0:
                            proxy["human_keeps_tenpai"] += 1
                        if se == 0:
                            proxy["E_keeps_tenpai"] += 1
                        if sa == 0 and se == 0:
                            proxy["both_tenpai_pairs"] += 1
                            proxy["sum_a_live"] += la
                            proxy["sum_e_live"] += le

    # ----------------------- 汇总输出 -----------------------
    def pct(a, b):
        return 100.0 * a / b if b else 0.0

    print("=========================================================")
    print("== 复盘离线 oracle 结论 ==")
    print("文件数=%d  局数=%d  决策点=%d  自检失败(跳过局)=%d"
          % (agg["files"], agg["rounds"], agg["decision_points"],
             agg["self_check_fail"]))
    print("局终我方手牌长度合法(13/14)=%d  不合法=%d"
          % (agg["hand_len_ok"], agg["hand_len_bad"]))
    print("顶层 rounds winner==我 局数=%d" % agg["rounds_winner_self"])
    print("我方实际动作 hu=%d（其中经 mahjong.fan.calc 判 hu 合法=%d；不合法即"
          "弃胡/超时自动胡差异告警=%d）"
          % (agg["human_hu"], agg["hu_ok"], agg["warn"]))
    print("  hu 中爆头=%d,  爆头且摸白=%d" % (agg["baotou"], agg["baotou_white"]))
    print("-- 分歧(我方 实际动作 vs 策略重放) --")
    for n in out_names:
        d = div[n]
        print("  %-8s 可比=%d  分歧=%d (%.1f%%)  by_action=%s"
              % (n, d["n"], d["diff"], pct(d["diff"], d["n"]),
                 json.dumps(d["by_phase"])))
    if vsE:
        print("-- 候选 vs E（同一真机局面重放的策略对差异 = 执行面宽度） --")
        for n, d in vsE.items():
            print("  %-8s 可比=%d  差异=%d (%.1f%%)  by_cand_action=%s"
                  % (n, d["n"], d["diff"], pct(d["diff"], d["n"]),
                     json.dumps(d["by_phase"])))
    print("-- 财飘(重放返回 discard 白)触发次数 --")
    for n in out_names:
        print("  %-8s discard_white=%d" % (n, discard_white[n]))
    print("-- 进度代理(实际弃 vs E 弃; free-draw 弃) --")
    if proxy["n"]:
        pa_ = proxy
        if not pa_["disagree"]:
            m = "无同时弃且异选样本"
        else:
            m = ("异选 n=%d: 弃后仍听 人类=%d E=%d | 两者都听的 %d 对平均活等待 "
                 "人类=%.2f E=%.2f" % (pa_["disagree"],
                                        pa_.setdefault("human_keeps_tenpai", 0),
                                        pa_.setdefault("E_keeps_tenpai", 0),
                                        pa_["both_tenpai_pairs"],
                                        pa_["sum_a_live"] / pa_["both_tenpai_pairs"]
                                        if pa_["both_tenpai_pairs"] else 0,
                                        pa_["sum_e_live"] / pa_["both_tenpai_pairs"]
                                        if pa_["both_tenpai_pairs"] else 0))
        print("  比较对=%d  同选=%d  异选=%d | %s"
              % (pa_["n"], pa_["agree"], pa_["disagree"], m))
    else:
        print("  无数据")

    if ns.json:
        summary = {
            **agg,
            "divergence": {k: dict(v) for k, v in div.items()},
            "vsE": {k: dict(v) for k, v in vsE.items()},
            "discard_white": {k: v for k, v in discard_white.items()},
            "proxy_agg": dict(proxy),
        }
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(run())
