# -*- coding: utf-8 -*-
"""`var/_format_fidelity.py` —— **赛制保真核对**：把将要打的锦标赛 config 与"我们训练用的三测 config"逐项对比。

## 为什么（这是能悄悄毁掉一个月优化的那类风险）

我们所有结论（和牌率/房、分/轮、听牌率、副露/杠频率、1s/3s 窗口判据、M=10 延迟预算）
都是在**三测赛制**下测出来的。若正式赛的 config 变了，**判决口径与优化目标都可能失效**：

| 字段 | 若变化 | 后果 / 必须做的动作 |
|---|---|---|
| `YouCaiBiKao` | false→true（或反向） | **含/不含闸门的臂互斥**：跑错会主动拒掉合法平胡 ⇒ 必须换 `ycbk` 双胞胎臂（§O） |
| `M` | 10→其他 | 延迟预算与并发压力变化 ⇒ **重跑 `_m10_latency_gate`（按新 M）**；M 影响每房局数与噪声 |
| `Rounds` | 8→其他 | 分/房与和牌率/房的**方差**变化（轮数少 ⇒ 噪声大）；`_gate2` 的 MDE 会变 |
| `BaseScore` | 1→其他 | 计分尺度变化（臂的相对排序应不变，但阈值/预测的绝对量级要重算） |
| `DiscardTimeoutSec` / `PengTimeoutSec` / `ChiTimeoutSec` | 3/1/1→更小 | **窗口捕获率与"超窗=0"护栏**的前提变化；副露门控的风险上升 |
| `Kind` / `OnlineConfirm` | 变化 | §V.28 的 `_ready_1024` 到位语义变化（分桌实到/在线确认） |

## 用法

    # ① 先把"训练基线"存下来（已由本次执行完成）
    python -X utf8 var/_format_fidelity.py --save-from <三测的某个 tid>
    # ② 正式赛 config 一公布就核对
    python -X utf8 var/_format_fidelity.py --tid <正式赛 tid> [--token-file var/.token_<赛事>_<日期>]

退出码：0 = 逐项一致（或仅无害差异）；2 = 有关键差异（**必须按上表动作**）。
"""
from __future__ import annotations
import argparse, io, json, os, ssl, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_FILE = os.path.join(ROOT, "var", ".format_baseline.json")
HIST = os.path.join(ROOT, "var", "format_history.jsonl")   # ★ R1377：每次核对留档
BASE = "https://10.240.169.190:18080"
KEYS = ("M", "Rounds", "BaseScore", "Kind", "YouCaiBiKao",
        "DiscardTimeoutSec", "PengTimeoutSec", "ChiTimeoutSec", "OnlineConfirm")
CRITICAL = {"YouCaiBiKao", "M", "Rounds", "BaseScore",
            "DiscardTimeoutSec", "PengTimeoutSec", "ChiTimeoutSec", "Kind"}
HINT = {
    "YouCaiBiKao": "换 ycbk 双胞胎臂（§O / bot/ycbk_*.py）",
    "M": "按新 M 重跑 var/_m10_latency_gate.py",
    "Rounds": "重算 _gate2 的 MDE 与分/房方差；缩短轮数会放大噪声",
    "BaseScore": "重算分数尺度（相对排序不变）",
    "DiscardTimeoutSec": "窗口/超窗护栏前提变化；加大 snapshot 预算",
    "PengTimeoutSec": "副露门控风险上升；重跑窗口捕获率审计",
    "ChiTimeoutSec": "副露门控风险上升；重跑窗口捕获率审计",
    "Kind": "按新 Kind 重读指南与 _ready_1024 语义",
    "OnlineConfirm": "分桌实到/在线确认流程变化（§V.28）",
}


def fetch_config(tid, token):
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(BASE + "/api/tournaments/" + tid,
                                headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    return d.get("config") or {}, d


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tid", default="")
    ap.add_argument("--token-file", default=os.path.join(ROOT, "var", ".global_token"))
    ap.add_argument("--save-from", default="", help="把该 tid 的 config 存成训练基线")
    ap.add_argument("--no-history", action="store_true",
                    help="不写 `var/format_history.jsonl`（默认会留档：门户只保留当前 1 场，不留档等于证据丢失）")
    a = ap.parse_args(argv)
    tok = io.open(a.token_file, encoding="utf-8").read().strip()
    if a.save_from:
        cfg, _ = fetch_config(a.save_from, tok)
        keep = {k: cfg.get(k) for k in KEYS if k in cfg}
        io.open(BASE_FILE, "w", encoding="utf-8").write(
            json.dumps({"source_tid": a.save_from, "config": keep}, ensure_ascii=False, indent=1))
        print("已保存训练基线 %s ← tid=%s" % (BASE_FILE, a.save_from))
        print(json.dumps(keep, ensure_ascii=False))
        return 0
    if not a.tid:
        print("需要 --tid（或 --save-from）"); return 2
    if not os.path.exists(BASE_FILE):
        print("缺训练基线 %s（先跑 --save-from）" % BASE_FILE); return 2
    base = json.load(io.open(BASE_FILE, encoding="utf-8"))
    b = base.get("config") or {}
    cfg, raw = fetch_config(a.tid, tok)
    print("=" * 84)
    print("赛制保真核对：正式赛 tid=%s  vs  训练基线 tid=%s" % (a.tid, base.get("source_tid")))
    print("=" * 84)
    # ★ R1274：除了 config，也把**赛程结构**字段打出来（它们决定"该优化什么"）
    #   · status/stage/stage_status：是否分阶段、是否淘汰
    #   · qualified/qualify_role：我方是否已获资格（报名≠资格）
    #   ⇒ 若是"淘汰/晋级"制，目标是 P(晋级) 而非 E[分]，波动率偏好会变（当前方案是 E[分] 最大化）。
    struct = {k: raw.get(k) for k in ("status", "stage", "stage_status", "qualified",
                                      "qualify_role", "stage_crashed")}
    # ★ R1386：把“我方已完成局数”一并留档（信号 4：被淘汰者是否停打）
    struct["my_games"] = len(raw.get("my_games") or []) if isinstance(raw.get("my_games"), list) else raw.get("my_games")
    print("赛程结构（新赛事）:", json.dumps(struct, ensure_ascii=False)[:400])
    bad = []
    for k in KEYS:
        if k not in cfg and k not in b:
            continue
        x, y = b.get(k), cfg.get(k)
        if x == y:
            print("  ✅ %-18s %s" % (k, x))
        else:
            mark = "❌" if k in CRITICAL else "⚠"
            print("  %s %-18s 训练=%s  正式=%s   ⇒ %s" % (mark, k, x, y, HINT.get(k, "人工确认")))
            if k in CRITICAL:
                bad.append(k)
    diffs = {}
    for k in KEYS:
        if k not in cfg and k not in b:
            continue
        if b.get(k) != cfg.get(k):
            diffs[k] = [b.get(k), cfg.get(k)]
    # ★ R1377：每次核对都留档。为什么：门户**只保留当前 1 场**赛事（历届不可查），
    #   而 config 决定“我们所有结论能不能搬到这场” ⇒ 不留档就是**证据丢失**。
    if not a.no_history:
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "tid": a.tid,
               "baseline_tid": base.get("source_tid"),
               "config": {k: cfg.get(k) for k in KEYS}, "diffs": diffs,
               "critical": list(bad), "struct": struct}
        try:
            last = ""
            if os.path.exists(HIST):
                with io.open(HIST, encoding="utf-8") as fh:
                    lines = [x for x in fh if x.strip()]
                last = lines[-1] if lines else ""
            dup = False
            if last:
                try:
                    d0 = json.loads(last)
                    # ★ R1386：去重必须**连 struct 一起比** —— 否则四测期间 stage/qualified
                    #   发生变化时（config 未变）会被当“重复”丢掉，而那正是我们要观察的信号。
                    dup = (d0.get("tid") == a.tid and d0.get("diffs") == diffs
                           and d0.get("critical") == list(bad)
                           and d0.get("struct") == struct)
                except Exception:
                    dup = False
            if dup:
                print("  （与上一条相同 ⇒ 不重复留档）")
            else:
                with io.open(HIST, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                try:
                    _where = os.path.relpath(HIST, ROOT)      # ★ R1386：跨盘时 relpath 会抛，但**写入已成功** ⇒ 不能把“消息渲染失败”说成“留档失败”
                except Exception:
                    _where = HIST
                print("  （已留档 → %s）" % _where)
        except Exception as e:
            print("  ⚠ 留档失败（不影响判定）：%s" % str(e)[:80])
    print()
    if bad:
        print("❌ 有关键差异 %d 项：%s ⇒ **先按上表动作，再谈选臂**" % (len(bad), "、".join(bad)))
        return 2
    print("✅ 逐项一致（或仅无害差异）⇒ 训练口径可直接沿用")
    return 0


if __name__ == "__main__":
    sys.exit(main())
