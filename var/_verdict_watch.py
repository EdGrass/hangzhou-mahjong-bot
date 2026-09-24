# -*- coding: utf-8 -*-
"""`var/_verdict_watch.py` —— **役次判决看护**：到点自动跑 `_gate2.py` 并把判词落盘（只读台账/复盘）。

## 为什么（R1197）

役 2 的目标是"**各臂 ≥80 房有复盘** + 覆盖 ≥70%"，而全流程的瓶颈是**等待**（~2.9 房/时 ⇒ 约 30 小时）。
此前到点后必须**有人想起**去跑判决；本看护把这一步自动化：每 10 分钟检查一次，**一到门槛就自动出判词**，
落 `var/_verdict_<label>.txt` 并写日志。

## ★ R1304（2026-09-24 09:3x）修正：**UNDECIDED 不是终点**

预登记写的是"房数够但 z<1.50 ⇒ UNDECIDED ⇒ **继续攒房**"，而旧实现**首判即写 sentinel**
⇒ 若 80/80 的首判恰好落在 z=1.4~1.5（本役**很可能**），看护从此不再重跑，判词**永久冻结在 UNDECIDED**，
役 3 的起役窗口会**静默丢掉**（要等有人想起来手跑）。

现行为：
  * **决定性**判词（ADOPT / REJECT / 护栏或机制不许）⇒ 写判词 + **写 sentinel**（与旧行为一致，只出一次）；
  * **非决定性**判词（`UNDECIDED` / `房数不足` / `复盘覆盖 < 70%`）⇒ 只记进度、**不写 sentinel**，
    此后**每多攒 `--step` 房（默认 10）自动重跑一次**，判词文件覆盖为最新（文件头注明第几次/房数）；
  * **役盒（R1306）**：非决定性判词若已到 `--box-rooms`（默认 120 房/臂），判词文件会**显式标"已达役盒"**，
    提示按 §V.86 用 `_pick_arm.py` + 两半 Pareto 的**破平序列**收口，**不再无限攒房**（采用门槛仍不变）；
  * **判据一字不改**：`--min-rooms 80`（每臂有复盘房数）、`z >= 1.50`、覆盖 `>= 70%` 全部冻结不变，
    本修正只改"**什么时候重跑同一个冻结判据**"，不改判据本身。

## 红线

只读台账与 `var/replays/recent`，只写自己的判词文件与日志；**不启动/不停止任何 A/B**，不碰 `bot/`。

用法：
    python -X utf8 var/_verdict_watch.py --label 役2 --since "2026-09-23 03:13:44" \
        --baseline speedc151 --candidate speedvalue --mechanism pairs
    python -X utf8 var/_verdict_watch.py --label 役2 --check-only     # 只看进度，不跑判词
"""
from __future__ import annotations
import argparse, glob, io, json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "var", "auto_ranking.jsonl")
RECENT = os.path.join(ROOT, "var", "replays", "recent")
MIN_ROOMS = 80
MIN_COVER = 0.70


def _log(path, msg):
    try:
        with io.open(path, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def progress(since, arms):
    """→ {arm: (房数, 有复盘房数)}；有复盘的判据 = 该房在 recent 里 ≥1 个 gid 文件（覆盖度另算）。"""
    have = {}
    for p in glob.glob(os.path.join(RECENT, "*.json")):
        b = os.path.basename(p)[:-5]
        if "_r" in b:
            have[b.split("_r")[0]] = have.get(b.split("_r")[0], 0) + 1
    out = {a: [0, 0] for a in arms}
    for ln in io.open(LEDGER, encoding="utf-8", errors="ignore"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("status") != "finished" or (d.get("ts") or "") < since:
            continue
        a = d.get("strategy")
        if a not in out:
            continue
        out[a][0] += 1
        if have.get(d.get("room"), 0) >= 10:      # 1 房 = 10 gid（R1171 实证）
            out[a][1] += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--since", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--mechanism", default="pairs")
    ap.add_argument("--min-rooms", type=int, default=MIN_ROOMS)
    ap.add_argument("--step", type=int, default=10,
                    help="非决定性判词后，每多攒 N 房自动重跑一次（默认 10）")
    ap.add_argument("--box-rooms", type=int, default=120,
                    help="役盒：非决定性判词到该房数/臂时在判词里标「已达役盒」（默认 120）")
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args()

    log = os.path.join(ROOT, "var", "_verdict_watch.log")
    sent = os.path.join(ROOT, "var", ".verdict_done_%s" % a.label)
    out = os.path.join(ROOT, "var", "_verdict_%s.txt" % a.label)
    arms = (a.baseline, a.candidate)
    pr = progress(a.since, arms)
    n0, r0 = pr[a.baseline]
    n1, r1 = pr[a.candidate]
    c0 = r0 / max(1, n0)
    c1 = r1 / max(1, n1)
    ready = (r0 >= a.min_rooms and r1 >= a.min_rooms and min(c0, c1) >= MIN_COVER)

    if a.check_only:
        print("%s：%s %d 房（有复盘 %d, 覆盖 %.0f%%） / %s %d 房（有复盘 %d, 覆盖 %.0f%%）⇒ %s"
              % (a.label, a.baseline, n0, r0, 100 * c0, a.candidate, n1, r1, 100 * c1,
                 "✅ 可判决" if ready else "… 攒房中"))
        return 0

    if not ready:
        return 0                                   # 未到门槛 ⇒ 静默（不写日志，避免刷屏）
    if os.path.exists(sent):
        return 0                                   # 已出**决定性**判词 ⇒ 幂等（只出一次）
    # ★ R1304：非决定性判词不写 sentinel，按 --step 房数重跑同一个冻结判据
    marker = os.path.join(ROOT, "var", ".verdict_last_%s" % a.label)
    try:
        _p = (io.open(marker, encoding="utf-8").read() or "").split()
        last, attempt = int(_p[0]), int(_p[1])
    except Exception:
        last, attempt = 0, 0
    low = min(r0, r1)
    if last and low < last + a.step:
        return 0                                   # 还没多攒够 --step 房 ⇒ 静默（不重跑、不刷屏）
    cmd = [sys.executable, "-X", "utf8", os.path.join(ROOT, "var", "_gate2.py"),
           "--since", a.since, "--baseline", a.baseline, "--candidate", a.candidate,
           "--mechanism", a.mechanism, "--min-rooms", str(a.min_rooms)]
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
        body = (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        _log(log, "%s 判词运行异常：%s" % (a.label, e))
        return 1
    nondet = (p.returncode == 2) or ("房数不足（" in body) or ("复盘覆盖 <" in body)
    boxed = bool(nondet and a.box_rooms and low >= a.box_rooms)
    with io.open(out, "w", encoding="utf-8") as f:
        f.write("【第 %d 次判词 · %s · %s=%d 房（有复盘 %d） / %s=%d 房（有复盘 %d）· %s】\n"
                % (attempt + 1, time.strftime("%Y-%m-%d %H:%M:%S"),
                   a.baseline, n0, r0, a.candidate, n1, r1,
                   "非决定性（会继续攒房重判）" if nondet else "决定性"))
        if boxed:
            f.write("\u26a0 已达役盒（>= %d 房/臂仍未决定性）\uff1a\u6309 \u00a7V.86 \u7528 `_pick_arm.py` + "
                    "\u4e24\u534a Pareto \u7684\u7834\u5e73\u5e8f\u5217\u6536\u53e3\uff0c**\u4e0d\u518d\u65e0\u9650\u6512\u623f**\uff1b"
                    "\u91c7\u7528\u95e8\u69db\uff08\u4e3b+\u526f z>=1.50\u3001\u5404 >=%d \u623f\u3001"
                    "\u8986\u76d6 >=70%%\uff09**\u4e0d\u53d8**\u3002\n" % (a.box_rooms, a.min_rooms))
        f.write(body)
    head = [x for x in body.splitlines() if x.startswith("★ 判定") or x.startswith("缺口")
            or x.startswith("护栏") or x.startswith("机制核对")]
    with io.open(marker, "w", encoding="utf-8") as f:
        f.write("%d %d\n" % (low, attempt + 1))
    if nondet:
        _log(log, "%s 判词非决定性%s（第 %d 次，%s=%d / %s=%d）⇒ 每 +%d 房自动重跑：%s"
             % (a.label, "\u3001**\u5df2\u8fbe\u5f79\u76d2**" if boxed else "", attempt + 1,
                a.baseline, n0, a.candidate, n1, a.step,
                " | ".join(head[-3:]) if head else "见 " + os.path.basename(out)))
        if boxed:
            # ★ R1460（真缺口）：到盒仍未决定性 ⇒ 按读卡"达役盒"分支用 §V.66 破平**收口**，
            #   是该役的终态 ⇒ **必须落 sentinel**，否则采用看护永远不动、链在役盒处静默停摆
            #   （原实现只给决定性判词写 sentinel；而 §V.66 预算说"到盒不可判定"才是预期落点）。
            with io.open(sent, "w", encoding="utf-8") as f:
                f.write("%s BOXED(达役盒未决定性，按§V.66破平收口)\r\n"
                        % time.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        _log(log, "%s 判词已出（决定性，第 %d 次）（%s → %s）：%s" % (a.label, attempt + 1, a.baseline,
             a.candidate, " | ".join(head[-4:]) if head else "见 " + os.path.basename(out)))
        with io.open(sent, "w", encoding="utf-8") as f:
            f.write("%s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
