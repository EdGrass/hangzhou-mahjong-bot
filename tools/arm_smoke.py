# -*- coding: utf-8 -*-
"""`arm_smoke` —— 上臂前的**冒烟测试**：每个臂都要能在**真实 dec 局面**上走通 `decide()`。

为什么（2026-09-17）：本役的 `speedc152` / `speedc159` / `speedc156` **从未被真机拉起过**
（历史上只有 c151 试跑过），而一房要跑 ~14 分钟——若某个臂一上来就抛异常，会白烧一房、甚至让战役卡住。
本工具用**我方 dec 记录里的真实局面**（我方自己的视图，含刚摸牌，已由尺子检验认可）逐个臂跑 `decide()`：
  · 不写任何状态、不启任何进程；
  · 输出每臂的 成功/异常数、动作类型与耗时（p50/max）；
  · 任一臂有异常 ⇒ 退出码 1（不要上臂）。

用法：
    python -X utf8 tools/arm_smoke.py --arms speedtugc,speedc152,speedc159,speedc156 --n 20
    python -X utf8 tools/arm_smoke.py            # 默认读 var/.ab_mode 的臂
    python -X utf8 tools/arm_smoke.py --kind window-claim --class bot.speedc211.SpeedC211 --n 25
    python -X utf8 tools/arm_smoke.py --kind window-live --class bot.speedc211.SpeedC211 --n 25
        # ★最优：只取"手牌本来就能碰/能吃"的局面 ⇒ 副露门控真正被考到
        # ★ 只取"当时真的吃/碰/杠了"的局面⇒ 副露门控类候选的影响面才会被真正跑到
        #   （默认 window 下 96% 是 pass，风险分支实际未覆盖）
    python -X utf8 tools/arm_smoke.py --class bot.speedc211.SpeedC211,bot.speedc135d.SpeedC135D --n 25
        # 未注册候选可直接给点号路径（不再需要 var/_smoke_inject.py 这种临时注入包装）
"""
from __future__ import annotations
import argparse, collections, glob, importlib, io, json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from _lowprio import lower          # noqa: E402
print("lower ->", lower(idle=True), flush=True)


def melds_from_am(rec):
    """从 dec 记录的 `am` 字段重建**四家副露**（供可见张扣除）。

    为什么需要（R877）：本地 `to_view` 一直把 `all_melds` 写死成 []，
    而实盘视图（`bot/model.py`）是**带的** ⇒ 所有基于 `to_view` 的**离线**工具
    在算 live 进张时**漏扣四家副露**，把死张当活张。
    `am` 格式：长度 4 的列表，每家一个**扁平牌表**（如 [["2w","4w","3w"], ...]）。
    —— 计数只需牌面，不需要分组，故每家封一个 dict 即可。
    """
    am = rec.get("am") or []
    if not (isinstance(am, list) and len(am) == 4):
        return []
    out = []
    for tiles in am:
        tiles = list(tiles or [])
        out.append([{"type": "meld", "tile": tiles[0] if tiles else "", "tiles": tiles}] if tiles else [])
    return out


def to_view(rec):
    """dec 记录 → 真实策略视图（口径与 `tools/offline_replay.to_view` 一致：my_hand **含刚摸牌**）。"""
    phase = rec.get("p")
    melds = []
    for m in rec.get("m") or []:
        if isinstance(m, dict):
            melds.append(dict(m))
        elif isinstance(m, (list, tuple)) and len(m) >= 2:
            melds.append({"type": m[0], "tile": m[1], "tiles": [m[1]]})
    return {"seat": rec.get("s"), "phase": phase, "turn": rec.get("t"),
            "responding_seats": [rec.get("s")] if str(phase).startswith("response_") else [],
            "my_hand": list(rec.get("h") or []), "melds": melds,
            "drawn_tile": rec.get("d"), "offer_tile": rec.get("o"),
            "river": list(rec.get("r") or []), "river_len": len(rec.get("r") or []),
            "all_melds": melds_from_am(rec),
            "god": {"baotou": False, "chain_count": 0, "catch_play": False,
                    "piao_count": 0, "god_discarder_seat": -1}}


def can_act(rec):
    """看牌型：这个 response 局面里我们本来就**能动**吗？

    ★ 为什么需要它：统一采样的 window 局面里 **96.3%** 是 pass
    （实测 82,917 条：pass 79,843 / chi 1,634 / peng 1,398 / gang 42），
    按"当时真副露了"采样（window-claim）又有选择偏差：那些局面连**严格**门控都放行了。
    本函数只看手牌（能碰 / 能吃），不看当时选了什么
    ⇒ 既有**分支覆盖**又有**鉴别力**（约 1/3 的可碰局面当时是 pass。那正是门控真正在起作用的位置）。
    """
    o = rec.get("o")
    if not o:
        return False
    h = list(rec.get("h") or [])
    if h.count(o) >= 2:
        return True
    if len(o) == 2 and o[0].isdigit() and o[1] in "wbt":
        v, s = int(o[0]), o[1]
        for a, b in ((v - 2, v - 1), (v - 1, v + 1), (v + 1, v + 2)):
            if 1 <= a <= 9 and 1 <= b <= 9 and ("%d%s" % (a, s)) in h and ("%d%s" % (b, s)) in h:
                return True
    return False


def fixtures(n=20, want="draw"):
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*_t0.dec.jsonl")))[-40:]:
        with io.open(f, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                if want == "draw" and r.get("p") == "draw" and r.get("d") and len(r.get("h") or []) >= 13:
                    out.append(r)
                elif want == "window" and str(r.get("p") or "").startswith("response_") and r.get("o"):
                    out.append(r)
                elif (want == "window-claim"
                        and str(r.get("p") or "").startswith("response_")
                        and r.get("o")
                        and (r.get("a") or {}).get("action") not in (None, "", "pass")):
                    out.append(r)
                elif (want == "window-live"
                        and str(r.get("p") or "").startswith("response_")
                        and can_act(r)):
                    out.append(r)
                if len(out) >= n:
                    return out
    return out


def factory_for(name, F):
    """把臂名/点号路径解析成零参数工厂。

    已注册的名字走 run_bot 的注册表；未注册候选可直接给点号路径
    （如 bot.speedc211.SpeedC211）⇒ 不再需要每次写临时注入包装（journal L13504）。
    """
    if name in F:
        return F[name]
    if "." in name:
        mod, cls = name.rsplit(".", 1)
        return lambda: getattr(importlib.import_module(mod), cls)()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="")
    ap.add_argument("--class", dest="classes", default="",
                    help="点号路径候选（逗号分隔），如 bot.speedc211.SpeedC211")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--kind", choices=("draw", "window", "window-claim", "window-live"), default="draw")
    a = ap.parse_args()
    arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    arms += [x.strip() for x in a.classes.split(",") if x.strip()]
    if not arms:
        try:
            cfg = json.loads(io.open(os.path.join(ROOT, "var", ".ab_mode"), encoding="utf-8").read())
            arms = [str(x) for x in (cfg.get("arms") or [cfg.get("a"), cfg.get("b")]) if x]
        except Exception:
            print("拿不到臂列表（--arms 或 var/.ab_mode）")
            return 1
    from run_bot import STRATEGY_FACTORIES as F
    fx = fixtures(a.n, a.kind)
    print("冒烟测试：%d 个臂 × %d 个真机%s局面" % (len(arms), len(fx), a.kind))
    bad = 0
    for name in arms:
        f = factory_for(name, F)
        if f is None:
            print("  %-16s ❌ 未注册（也不是点号路径）" % name)
            bad += 1
            continue
        try:
            pol = f()
        except Exception as e:
            print("  %-16s ❌ 实例化失败：%s" % (name, str(e)[:80]))
            bad += 1
            continue
        ts, acts, errs = [], collections.Counter(), []
        for r in fx:
            v = to_view(r)
            t0 = time.perf_counter()
            try:
                act = pol.decide(v) or {}
                acts[str(act.get("action") or "-")] += 1
            except Exception as e:
                errs.append("%s: %s" % (type(e).__name__, str(e)[:60]))
            ts.append((time.perf_counter() - t0) * 1000.0)
        ts.sort()
        ok = not errs
        bad += 0 if ok else 1
        print("  %-16s %s  n=%d  动作=%s  p50=%.1fms  max=%.1fms%s" % (
            name, "✅" if ok else "❌", len(fx), dict(acts),
            (ts[len(ts) // 2] if ts else -1), (ts[-1] if ts else -1),
            ("  异常样例：" + errs[0]) if errs else ""))
    print("结论：%s" % ("全部通过，可以上臂" if not bad else "**有臂未通过，先修**"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
