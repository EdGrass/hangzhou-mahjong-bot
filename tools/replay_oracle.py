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
  python tools/replay_oracle.py --dir var/replays/<tournament_id> \
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
def replay_round(round_ev, target_seat):
    """重建该局【目标座】每摸牌决策局面 + 副露行为统计。返回
    (decision_points, end_hand_len, meld_stats)。支持目标座有副露
    （chi/peng/gang 从手牌扣减并记入 melds，暗牌基准 13-3e-g）。

    决策点字段：
      drawn / my_hand(14-3e-g 含刚摸) / concealed(摸前 13-3e-g) / river /
      catch_play / baotou(is_baotou 带 e,g) / melds / e / g / actual
    抛 SkipRound：手牌不变量违例（弃牌不在手、claim 扣减失败等）。

    说明（corpus 实测）：非庄起手 13 张；庄家 start_hands 已含首摸为 14 张
    （另三家 13）——庄的首弃无 tile_drawn 事件，不构成"摸后决策局面"。
    副露事件形态：chi{tile=被吃张,data:{tiles:[整组3]}}；peng{tile,data:null}；
    gang{tile,data:{kind:bu|ming|an}}（bu=补杠=碰组升级拿第4张；明/暗杠移除
    3/4 张，明杠的弃牌 tile 同 tile_discarded 已公开）。
    """
    start_hands = round_ev.get("start_hands")
    if not start_hands or len(start_hands) != 4:
        raise SkipRound("start_hands 非 4 家")
    hand = [t for t in start_hands[target_seat]]
    dealer = round_ev.get("dealer")
    is_dealer = (dealer == target_seat)
    if len(hand) != 13 and not (is_dealer and len(hand) == 14):
        raise SkipRound("起手张数非法(须13,庄14): %d dealer=%s" %
                        (len(hand), is_dealer))
    river = []
    decision_points = []
    melds = []                       # [{"type","tile"}]；杠组计入 e 且 g+1
    meld_stats = {"chi": 0, "peng": 0, "gang": 0, "decline": 0}
    end_hand_len = len(hand)
    open_dec = None
    last_white_discarder = None

    def e_g():
        e = len(melds)
        g = sum(1 for m in melds if m["type"] == "gang")
        return e, g

    def _rm(t, k=1):
        """从手牌移除 k 张 t；不足 → SkipRound。"""
        nonlocal hand
        for _ in range(k):
            if t in hand:
                hand.remove(t)
            else:
                raise SkipRound("扣减失败 %s×%d hand=%s" % (t, k, sorted(hand)))

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
            if seat == target_seat:
                hand.append(tile)
                clear_catch(target_seat)
                catch = (last_white_discarder is not None
                         and last_white_discarder != target_seat)
                if open_dec is not None:
                    raise SkipRound("目标座连续摸却未弃（状态错乱）")
                e_, g_ = e_g()
                if len(hand) != 14 - 3 * e_ - g_:
                    raise SkipRound("摸后长度非法 len=%d e=%d g=%d" %
                                    (len(hand), e_, g_))
                try:
                    bao = is_baotou(hand[:-1], allow_qidui=True,
                                    exposed_melds=e_, gangs=g_)
                except ValueError:
                    bao = False
                open_dec = {
                    "drawn": tile, "my_hand": list(hand),
                    "concealed": list(hand[:-1]), "river": list(river),
                    "catch_play": catch, "baotou": bao,
                    "melds": [dict(m) for m in melds], "e": e_, "g": g_,
                }
            else:
                clear_catch(seat)
        elif typ == "tile_discarded":
            river.append(tile)
            if seat == target_seat:
                if open_dec is None:
                    if tile not in hand:      # 庄首弃（无摸事件）或副露后出牌
                        raise SkipRound("首弃/出牌 %s 不在手中 hand=%s" %
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
        elif typ == "chi":
            if seat == target_seat:
                got = (e.get("data") or {}).get("tiles") or []
                if len(got) != 3 or tile not in got:
                    raise SkipRound("chi 结构异常 %s" % json.dumps(e,
                                    ensure_ascii=False)[:200])
                for t in got:
                    if t != tile:
                        _rm(t)
                melds.append({"type": "chi", "tile": tile})
                meld_stats["chi"] += 1
        elif typ == "peng":
            if seat == target_seat:
                if not tile:
                    raise SkipRound("peng 无 tile")
                _rm(tile, 2)
                melds.append({"type": "peng", "tile": tile})
                meld_stats["peng"] += 1
        elif typ == "gang":
            if seat == target_seat:
                kind = (e.get("data") or {}).get("kind")
                if kind == "bu":               # 补杠：碰组 + 手牌第 4 张
                    _rm(tile, 1)
                    found = False
                    for m in melds:
                        if m["type"] == "peng" and m["tile"] == tile:
                            m["type"] = "gang"
                            found = True
                            break
                    if not found:
                        raise SkipRound("补杠无对应碰组 tile=%s" % tile)
                elif kind == "ming":           # 明杠（抢弃牌）：移除 3 张
                    _rm(tile, 3)
                    melds.append({"type": "gang", "tile": tile})
                else:                          # an/暗杠或缺省：移除 4 张
                    _rm(tile, 4)
                    melds.append({"type": "gang", "tile": tile})
                meld_stats["gang"] += 1
        elif typ == "round_ended":
            if open_dec is not None:
                if e.get("seat") == target_seat:
                    dp = open_dec
                    open_dec = None
                    dp["actual"] = {"action": "hu", "tile": ""}
                    decision_points.append(dp)
                    end_hand_len = len(hand)
                else:
                    raise SkipRound("局终胜者非目标座而目标座开决策点未动作")
            else:
                end_hand_len = len(hand)
            break                      # 一局事件到此结束
        elif typ == "pass":
            if seat == target_seat:
                meld_stats["decline"] += 1     # 目标座放弃窗口（近似拒绝数）
        elif typ in ("timeout", "game_ended"):
            if typ == "timeout" and seat == target_seat and \
                    (e.get("data") or {}).get("kind") == "response":
                meld_stats["decline"] += 1
        else:
            pass                       # 未知类型:静默容忍
    else:
        if round_ev.get("truncated"):
            raise SkipRound("局 truncated 缺 round_ended")
        end_hand_len = len(hand)
    return decision_points, end_hand_len, meld_stats


# ---------------------------------------------------------------------------
# 工具 / 进度代理（本地纯实现，不耦合 tools/oracle_audit）
# ---------------------------------------------------------------------------
def _proxy(hand_with_drawn, river, discard_tile, e=0, g=0):
    """弃牌后的进度：弃后的 exact_shanten 与活等待数（河见剔除 4 张）。
    返回 (s, live) 或 None（长度/非法）。e/g = 副露组数/杠组数。"""
    if discard_tile not in hand_with_drawn:
        return None
    rem = [t for t in hand_with_drawn]
    rem.remove(discard_tile)
    try:
        s = exact_shanten(rem, qidui=(e == 0 and g == 0),
                          exposed_melds=e, gangs=g)
    except ValueError:
        return None
    live = 0
    if s == 0:
        try:
            ws = waits(rem, exposed_melds=e, gangs=g)
        except ValueError:
            ws = []
        seen = {}
        for t in list(rem) + list(river or []):
            seen[t] = seen.get(t, 0) + 1
        live = sum(1 for t in ws if seen.get(t, 0) < 4)
    return (s, live)


def make_view(dp, seat):
    return {
        "seat": seat, "phase": "draw", "turn": seat,
        "responding_seats": [],
        "drawn_tile": dp["drawn"],
        "my_hand": list(dp["my_hand"]),
        "melds": [dict(m) for m in dp.get("melds") or []],
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
    ap.add_argument("--dir", default="")
    ap.add_argument("--file", default="")
    ap.add_argument("--strategies", default="speedE")
    ap.add_argument("--seats", default="", help="分析座位（0-3 逗号分隔；空=全部）")
    ap.add_argument("--exclude-uid", default=MY_UID,
                    help="默认排除我方（人类分析）；设空串分析全部")
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
        glob.glob(os.path.join(ns.dir, "*.json")))
    if ns.limit:
        files = files[: ns.limit]

    seat_filter = None
    if ns.seats:
        seat_filter = set(int(x) for x in ns.seats.split(",") if x.strip() != "")

    # 聚合键 = (user_id, name, seat) —— 同一人类跨场同桌概率低，按 user 即可
    T = {}       # user_id -> agg
    skip_rounds = 0
    files_seen = 0

    def t_of(uid, name):
        return T.setdefault(uid, {
            "uid": uid, "name": name, "files": set(), "rounds": 0,
            "dps": 0, "hu": 0, "hu_ok": 0, "chi": 0, "peng": 0, "gang": 0,
            "decline": 0, "hand_bad": 0, "warn": 0,
            "div": {n: {"n": 0, "diff": 0} for n in out_names},
            "proxy": {"n": 0, "agree": 0, "disagree": 0, "a_tenpai": 0,
                      "e_tenpai": 0, "both": 0, "sa": 0.0, "se": 0.0},
        })

    for path in files:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        seats = data.get("seats", [])
        if not seats:
            continue
        files_seen += 1
        for round_ev in group_blocks_into_rounds(data):
            winner = round_ev.get("_winner")
            # round_ended 的胜者（=rounds 顶层或事件 seat）由各座 replay 内部处理
            for seat_idx in range(4):
                if seat_filter is not None and seat_idx not in seat_filter:
                    continue
                s = seats[seat_idx] if seat_idx < len(seats) else {}
                uid = (s or {}).get("user_id", "?")
                if ns.exclude_uid and uid == ns.exclude_uid:
                    continue
                t = t_of(uid, (s or {}).get("name", "?"))
                t["files"].add(os.path.basename(path))
                try:
                    dps, end_len, ms = replay_round(round_ev, seat_idx)
                except SkipRound as ex:
                    skip_rounds += 1
                    if skip_rounds <= 8:
                        print("  [skip-round] %s r%s seat%d: %s" %
                              (os.path.basename(path), round_ev["round_no"],
                               seat_idx, ex))
                    continue
                t["rounds"] += 1
                t["chi"] += ms["chi"]
                t["peng"] += ms["peng"]
                t["gang"] += ms["gang"]
                t["decline"] += ms["decline"]
                # 局终手牌合法性：13/14-3e-g 的容差范围 8..14（杠组多时偏小）
                if not (8 <= end_len <= 14):
                    t["hand_bad"] += 1
                t["dps"] += len(dps)
                for dp in dps:
                    act = dp["actual"]
                    if act["action"] == "hu":
                        t["hu"] += 1
                        try:
                            fc = fan_calc(dp["concealed"], dp["drawn"],
                                          {"count": 0, "piao": 0},
                                          exposed_melds=dp["e"],
                                          gangs=dp["g"])
                        except ValueError:
                            fc = {"hu": False}
                        if fc.get("hu"):
                            t["hu_ok"] += 1
                        else:
                            t["warn"] += 1
                    # E（及多策略）重放
                    view = make_view(dp, seat_idx)
                    decided = {}
                    for st, n in zip(strats, out_names):
                        try:
                            a = st.decide(view)
                        except Exception:      # noqa: BLE001
                            a = None
                        decided[n] = a
                        if a is None:
                            continue
                        d = t["div"][n]
                        d["n"] += 1
                        if a != act:
                            d["diff"] += 1
                    ae = decided.get("speedE") if "speedE" in out_names \
                        else None
                    # 进度代理：自由弃牌且 E 也弃
                    if act["action"] == "discard" and ae is not None and \
                            ae.get("action") == "discard":
                        atile, etile = act["tile"], (ae.get("tile") or "")
                        p = t["proxy"]
                        if atile == etile:
                            p["n"] += 1
                            p["agree"] += 1
                            continue
                        pa = _proxy(dp["my_hand"], dp["river"], atile,
                                    dp["e"], dp["g"])
                        pe = _proxy(dp["my_hand"], dp["river"], etile,
                                    dp["e"], dp["g"])
                        p["n"] += 1
                        p["disagree"] += 1
                        if pa and pe:
                            sa, la = pa
                            se_, le = pe
                            if sa == 0:
                                p["a_tenpai"] += 1
                            if se_ == 0:
                                p["e_tenpai"] += 1
                            if sa == 0 and se_ == 0:
                                p["both"] += 1
                                p["sa"] += la
                                p["se"] += le

    # ----------------------- 汇总输出 -----------------------
    def pct(a, b):
        return 100.0 * a / b if b else 0.0

    print("=" * 40)
    print("== 复盘离线 oracle（多目标座 = 人类）==")
    print("文件=%d  跳过局=%d  目标(用户)=%d" %
          (files_seen, skip_rounds, len(T)))
    for uid in sorted(T):
        t = T[uid]
        divE = t["div"].get("speedE") or {"n": 0, "diff": 0}
        p = t["proxy"]
        pp = "异选%d: 弃后仍听 人%d/E%d 双听%d对活等待 %.2f/%.2f" % (
            p["disagree"], p["a_tenpai"], p["e_tenpai"], p["both"],
            p["sa"] / p["both"] if p["both"] else 0,
            p["se"] / p["both"] if p["both"] else 0) if p["n"] else "无弃牌样本"
        print("-- %s(%s) 局%d 决策%d 胡%d/%d 吃%d碰%d杠%d 弃窗%d" %
              (t["name"], uid[:8], t["rounds"], t["dps"], t["hu"], t["hu_ok"],
               t["chi"], t["peng"], t["gang"], t["decline"]))
        print("   E分歧 %d/%d (%.1f%%)  | %s" %
              (divE["diff"], divE["n"], pct(divE["diff"], divE["n"]), pp))
    # 全体合并
    A = {"rounds": 0, "dps": 0, "hu": 0, "hu_ok": 0, "chi": 0, "peng": 0,
         "gang": 0, "decline": 0, "divn": 0, "divd": 0,
         "pn": 0, "pagree": 0, "pdis": 0, "a_ten": 0, "e_ten": 0,
         "both": 0, "sa": 0.0, "se": 0.0}
    for t in T.values():
        for k in ("rounds", "dps", "hu", "hu_ok", "chi", "peng", "gang",
                  "decline"):
            A[k] += t[k]
        de = t["div"].get("speedE") or {"n": 0, "diff": 0}
        A["divn"] += de["n"]
        A["divd"] += de["diff"]
        p = t["proxy"]
        A["pn"] += p["n"]
        A["pagree"] += p["agree"]
        A["pdis"] += p["disagree"]
        A["a_ten"] += p["a_tenpai"]
        A["e_ten"] += p["e_tenpai"]
        A["both"] += p["both"]
        A["sa"] += p["sa"]
        A["se"] += p["se"]
    print("=" * 40)
    print("【全体人类合并】局=%d 决策=%d 胡=%d/%d 吃=%d 碰=%d 杠=%d "
          "窗口拒绝=%d" % (A["rounds"], A["dps"], A["hu"], A["hu_ok"],
                         A["chi"], A["peng"], A["gang"], A["decline"]))
    print("E vs 人类弃牌分歧 %d/%d (%.1f%%) | 副露接受率 %.1f%% "
          "(%d/(%d+%d))" % (A["divd"], A["divn"],
                           pct(A["divd"], A["divn"]),
                           pct(A["chi"] + A["peng"] + A["gang"],
                               A["chi"] + A["peng"] + A["gang"] +
                               A["decline"]),
                           A["chi"] + A["peng"] + A["gang"],
                           A["chi"] + A["peng"] + A["gang"], A["decline"]))
    if A["pn"]:
        print("弃牌代理：异选=%d 弃后仍听 人类=%d E=%d | 双听 %d 对平均活等待 "
              "人类=%.2f E=%.2f" % (A["pdis"], A["a_ten"], A["e_ten"],
                                    A["both"],
                                    A["sa"] / A["both"] if A["both"] else 0,
                                    A["se"] / A["both"] if A["both"] else 0))
    if ns.json:
        out = {}
        for uid, t in T.items():
            out[uid] = {k: (sorted(v) if isinstance(v, set) else v)
                        for k, v in t.items() if k != "div"}
            out[uid]["div_speedE"] = t["div"].get("speedE")
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(run())
